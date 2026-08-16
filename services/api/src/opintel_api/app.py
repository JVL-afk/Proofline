"""FastAPI transport and M0 composition root."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opintel_m0.application import M0ApplicationService
from opintel_m0.contracts import (
    CampaignCreate,
    CampaignView,
    EvidenceCollection,
    EvidenceView,
    OperationView,
    PrincipalView,
)
from opintel_m0.domain import AuthorizationError, NotFoundError, Principal
from opintel_m0.ports import Clock, IdentifierFactory, M0Repository
from opintel_m0_local import (
    LocalSettings,
    LocalTokenAuthenticator,
    SqlAlchemyM0Repository,
    SystemClock,
    UuidFactory,
)
from opintel_m0_local.settings import get_local_settings
from opintel_opportunity.application import OpportunityApplicationService
from opintel_opportunity.contracts import (
    AnalysisRunView,
    InferenceRejectRequest,
    OpportunityBundleView,
    OpportunityRunCreate,
    RecalculateRequest,
    ReviewRequest,
)
from opintel_opportunity.domain import OpportunityError, OpportunityNotFoundError
from opintel_opportunity.ports import OpportunityRepository
from opintel_opportunity_local import SqlAlchemyOpportunityRepository
from opintel_research.application import ResearchApplicationService
from opintel_research.contracts import (
    BusinessCreate,
    BusinessView,
    FetchAttemptView,
    MaterialView,
    PageView,
    ResearchEvidenceView,
    ResearchRunCreate,
    ResearchRunView,
    SnapshotView,
)
from opintel_research.domain import ResearchError, ResearchNotFoundError, UrlPolicyError
from opintel_research.ports import ResearchRepository
from opintel_research_local import SqlAlchemyResearchRepository

bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: LocalSettings | None = None,
    repository: M0Repository | None = None,
    clock: Clock | None = None,
    identifiers: IdentifierFactory | None = None,
    research_repository: ResearchRepository | None = None,
    opportunity_repository: OpportunityRepository | None = None,
) -> FastAPI:
    active_settings = settings or get_local_settings()
    active_repository = repository or SqlAlchemyM0Repository(active_settings.database_url)
    active_repository.initialize()
    active_research_repository = research_repository or SqlAlchemyResearchRepository(
        active_settings.database_url
    )
    active_research_repository.initialize()
    active_opportunity_repository = opportunity_repository or SqlAlchemyOpportunityRepository(
        active_settings.database_url
    )
    active_opportunity_repository.initialize()
    authenticator = LocalTokenAuthenticator(
        active_settings.auth_token.get_secret_value(),
        active_settings.auth_subject,
        active_settings.workspace_id,
        active_settings.local_roles,
    )
    service = M0ApplicationService(
        active_repository,
        clock or SystemClock(),
        identifiers or UuidFactory(),
    )
    research_service = ResearchApplicationService(
        active_research_repository,
        clock or SystemClock(),
        identifiers or UuidFactory(),
    )
    opportunity_service = OpportunityApplicationService(
        active_opportunity_repository,
        clock or SystemClock(),
        identifiers or UuidFactory(),
    )

    app = FastAPI(
        title="Opportunity Intelligence M2 API",
        version="0.3.0",
        description=(
            "Bounded local research and deterministic opportunity API. Live AI and M3 behavior "
            "are disabled."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.state.repository = active_repository
    app.state.service = service
    app.state.authenticator = authenticator
    app.state.research_repository = active_research_repository
    app.state.research_service = research_service
    app.state.opportunity_repository = active_opportunity_repository
    app.state.opportunity_service = opportunity_service

    def current_principal(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        principal = authenticator.authenticate(credentials.credentials)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid authentication",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return principal

    @app.exception_handler(NotFoundError)
    def not_found_handler(request: Request, error: NotFoundError) -> JSONResponse:
        del request
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(AuthorizationError)
    def authorization_handler(request: Request, error: AuthorizationError) -> JSONResponse:
        del request
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(ResearchNotFoundError)
    def research_not_found_handler(request: Request, error: ResearchNotFoundError) -> JSONResponse:
        del request, error
        return JSONResponse(status_code=404, content={"detail": "research resource not found"})

    @app.exception_handler(ResearchError)
    def research_error_handler(request: Request, error: ResearchError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422 if isinstance(error, UrlPolicyError) else 400,
            content={"detail": error.safe_message, "code": error.code},
        )

    @app.exception_handler(OpportunityNotFoundError)
    def opportunity_not_found_handler(
        request: Request, error: OpportunityNotFoundError
    ) -> JSONResponse:
        del request, error
        return JSONResponse(status_code=404, content={"detail": "opportunity resource not found"})

    @app.exception_handler(OpportunityError)
    def opportunity_error_handler(request: Request, error: OpportunityError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=403 if error.code == "forbidden" else 400,
            content={"detail": error.safe_message, "code": error.code},
        )

    @app.get("/healthz", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "m2-local"}

    @app.get("/api/v1/session", response_model=PrincipalView, tags=["identity"])
    def session(principal: Annotated[Principal, Depends(current_principal)]) -> PrincipalView:
        return PrincipalView(
            subject=principal.subject,
            workspace_id=principal.workspace_id,
            roles=sorted(role.value for role in principal.roles),
        )

    @app.post(
        "/api/v1/campaigns",
        response_model=CampaignView,
        status_code=status.HTTP_201_CREATED,
        tags=["campaigns"],
    )
    def create_campaign(
        command: CampaignCreate,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> CampaignView:
        return CampaignView.from_domain(service.create_campaign(principal, command))

    @app.get(
        "/api/v1/campaigns/{campaign_id}",
        response_model=CampaignView,
        tags=["campaigns"],
    )
    def get_campaign(
        campaign_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> CampaignView:
        return CampaignView.from_domain(service.get_campaign(principal, campaign_id))

    @app.post(
        "/api/v1/campaigns/{campaign_id}/operations",
        response_model=OperationView,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["operations"],
    )
    def start_operation(
        campaign_id: UUID,
        response: Response,
        principal: Annotated[Principal, Depends(current_principal)],
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=8,
                max_length=128,
                pattern=r"^[A-Za-z0-9._:-]+$",
            ),
        ],
    ) -> OperationView:
        operation, created = service.start_operation(principal, campaign_id, idempotency_key)
        if not created:
            response.status_code = status.HTTP_200_OK
        attempts = active_repository.list_attempts(operation.id)
        return OperationView.from_domain(operation, attempts)

    @app.get(
        "/api/v1/operations/{operation_id}",
        response_model=OperationView,
        tags=["operations"],
    )
    def get_operation(
        operation_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OperationView:
        operation = service.get_operation(principal, operation_id)
        return OperationView.from_domain(operation, active_repository.list_attempts(operation.id))

    @app.get(
        "/api/v1/operations/{operation_id}/evidence",
        response_model=EvidenceCollection,
        tags=["evidence"],
    )
    def list_evidence(
        operation_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> EvidenceCollection:
        service.get_operation(principal, operation_id)
        items = active_repository.list_evidence(principal.workspace_id, operation_id)
        views = [EvidenceView.from_domain(item) for item in items]
        return EvidenceCollection(items=views, count=len(views))

    @app.get(
        "/api/v1/evidence/{evidence_id}",
        response_model=EvidenceView,
        tags=["evidence"],
    )
    def get_evidence(
        evidence_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> EvidenceView:
        return EvidenceView.from_domain(service.get_evidence(principal, evidence_id))

    @app.post(
        "/api/v1/businesses",
        response_model=BusinessView,
        status_code=status.HTTP_201_CREATED,
        tags=["research"],
    )
    def create_business(
        command: BusinessCreate,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> BusinessView:
        return BusinessView.from_domain(
            research_service.create_business(principal, command.name, command.public_url)
        )

    @app.get("/api/v1/businesses/{business_id}", response_model=BusinessView, tags=["research"])
    def get_business(
        business_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> BusinessView:
        return BusinessView.from_domain(research_service.get_business(principal, business_id))

    @app.post(
        "/api/v1/businesses/{business_id}/research-runs",
        response_model=ResearchRunView,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["research"],
    )
    def start_research_run(
        business_id: UUID,
        command: ResearchRunCreate,
        response: Response,
        principal: Annotated[Principal, Depends(current_principal)],
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=8,
                max_length=128,
                pattern=r"^[A-Za-z0-9._:-]+$",
            ),
        ],
    ) -> ResearchRunView:
        run, created = research_service.start_run(
            principal,
            business_id,
            command.policy.to_domain(),
            idempotency_key,
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return ResearchRunView.from_domain(run)

    @app.get(
        "/api/v1/research-runs/{run_id}",
        response_model=ResearchRunView,
        tags=["research"],
    )
    def get_research_run(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> ResearchRunView:
        return ResearchRunView.from_domain(research_service.get_run(principal, run_id))

    @app.get(
        "/api/v1/research-runs/{run_id}/pages",
        response_model=list[PageView],
        tags=["research"],
    )
    def list_research_pages(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[PageView]:
        return [
            PageView.from_domain(item) for item in research_service.list_pages(principal, run_id)
        ]

    @app.get(
        "/api/v1/research-runs/{run_id}/attempts",
        response_model=list[FetchAttemptView],
        tags=["research"],
    )
    def list_research_attempts(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[FetchAttemptView]:
        return [
            FetchAttemptView.from_domain(item)
            for item in research_service.list_attempts(principal, run_id)
        ]

    @app.get(
        "/api/v1/page-snapshots/{snapshot_id}",
        response_model=SnapshotView,
        tags=["research"],
    )
    def get_page_snapshot(
        snapshot_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> SnapshotView:
        return SnapshotView.from_domain(research_service.get_snapshot(principal, snapshot_id))

    @app.get(
        "/api/v1/extracted-material/{material_id}",
        response_model=MaterialView,
        tags=["research"],
    )
    def get_extracted_material(
        material_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> MaterialView:
        return MaterialView.from_domain(research_service.get_material(principal, material_id))

    @app.get(
        "/api/v1/research-runs/{run_id}/evidence",
        response_model=list[ResearchEvidenceView],
        tags=["research"],
    )
    def list_research_evidence(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[ResearchEvidenceView]:
        return [
            ResearchEvidenceView.from_domain(item)
            for item in research_service.list_evidence(principal, run_id)
        ]

    @app.get(
        "/api/v1/research-evidence/{evidence_id}",
        response_model=ResearchEvidenceView,
        tags=["research"],
    )
    def get_research_evidence(
        evidence_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> ResearchEvidenceView:
        return ResearchEvidenceView.from_domain(
            research_service.get_evidence(principal, evidence_id)
        )

    @app.post(
        "/api/v1/businesses/{business_id}/opportunity-analysis-runs",
        response_model=AnalysisRunView,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["opportunities"],
    )
    def start_opportunity_analysis(
        business_id: UUID,
        command: OpportunityRunCreate,
        response: Response,
        principal: Annotated[Principal, Depends(current_principal)],
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=8,
                max_length=128,
                pattern=r"^[A-Za-z0-9._:-]+$",
            ),
        ],
    ) -> AnalysisRunView:
        research_run = research_service.get_run(principal, command.research_run_id)
        if research_run.business_id != business_id:
            raise OpportunityNotFoundError()
        run, created = opportunity_service.start_run(
            principal, business_id, command.research_run_id, idempotency_key
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return AnalysisRunView.from_domain(run)

    @app.get(
        "/api/v1/opportunity-analysis-runs/{run_id}",
        response_model=AnalysisRunView,
        tags=["opportunities"],
    )
    def get_opportunity_analysis(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> AnalysisRunView:
        return AnalysisRunView.from_domain(opportunity_service.get_run(principal, run_id))

    @app.get(
        "/api/v1/opportunity-analysis-runs/{run_id}/result",
        response_model=OpportunityBundleView,
        tags=["opportunities"],
    )
    def get_opportunity_result(
        run_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OpportunityBundleView:
        return OpportunityBundleView.from_domain(
            opportunity_service.get_bundle_by_run(principal, run_id)
        )

    @app.get(
        "/api/v1/opportunities/{hypothesis_id}",
        response_model=OpportunityBundleView,
        tags=["opportunities"],
    )
    def get_opportunity(
        hypothesis_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OpportunityBundleView:
        return OpportunityBundleView.from_domain(
            opportunity_service.get_bundle_by_hypothesis(principal, hypothesis_id)
        )

    @app.post(
        "/api/v1/opportunities/{hypothesis_id}/recalculate",
        response_model=OpportunityBundleView,
        tags=["opportunities"],
    )
    def recalculate_opportunity(
        hypothesis_id: UUID,
        command: RecalculateRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OpportunityBundleView:
        inputs = tuple(item.model_dump() for item in command.assumptions)
        return OpportunityBundleView.from_domain(
            opportunity_service.recalculate(
                principal, hypothesis_id, command.expected_hypothesis_revision_id, inputs
            )
        )

    @app.post(
        "/api/v1/opportunities/{hypothesis_id}/review-decisions",
        response_model=OpportunityBundleView,
        tags=["opportunities"],
    )
    def review_opportunity(
        hypothesis_id: UUID,
        command: ReviewRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OpportunityBundleView:
        return OpportunityBundleView.from_domain(
            opportunity_service.review(
                principal,
                hypothesis_id,
                command.expected_hypothesis_revision_id,
                command.decision,
                command.reason,
            )
        )

    @app.post(
        "/api/v1/inferences/{inference_id}/rejections",
        response_model=OpportunityBundleView,
        tags=["opportunities"],
    )
    def reject_inference(
        inference_id: UUID,
        command: InferenceRejectRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> OpportunityBundleView:
        return OpportunityBundleView.from_domain(
            opportunity_service.reject_hypothesis_inference(
                principal,
                command.hypothesis_id,
                inference_id,
                command.expected_hypothesis_revision_id,
                command.reason,
            )
        )

    return app
