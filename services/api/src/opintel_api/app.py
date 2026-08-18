"""FastAPI transport and local M0-M4 composition root."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opintel_audit.application import AuditApplicationService
from opintel_audit.contracts import (
    AuditBundleView,
    AuditCreate,
    AuditOperationView,
    AuditReviewRequest,
)
from opintel_audit.domain import AuditError, AuditNotFoundError
from opintel_audit.ports import AuditRepository
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
from opintel_demo.application import DemoApplicationService, DemoRuntimeService
from opintel_demo.contracts import (
    CapabilityExchangeRequest,
    DemoBundleView,
    DemoCreate,
    DemoOperationView,
    DemoReviewRequest,
    DemoRevokeRequest,
    RuntimeEventRequest,
    RuntimeSessionResponse,
    SessionCapabilityView,
    SessionIssueRequest,
)
from opintel_demo.domain import DemoError, DemoNotFoundError
from opintel_demo.ports import DemoRepository
from opintel_demo_local import (
    CanonicalDemoSourceCatalog,
    SecureLocalCapabilityFactory,
    SqlAlchemyDemoRepository,
)
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
    audit_repository: AuditRepository | None = None,
    demo_repository: DemoRepository | None = None,
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
    active_audit_repository = audit_repository or SqlAlchemyAuditRepository(
        active_settings.database_url
    )
    active_audit_repository.initialize()
    active_demo_repository = demo_repository or SqlAlchemyDemoRepository(
        active_settings.database_url
    )
    active_demo_repository.initialize()
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
    audit_source = CanonicalAuditSourceCatalog(
        active_opportunity_repository, active_research_repository
    )
    audit_service = AuditApplicationService(
        active_audit_repository,
        audit_source,
        clock or SystemClock(),
        identifiers or UuidFactory(),
    )
    demo_source = CanonicalDemoSourceCatalog(
        active_audit_repository, active_opportunity_repository, active_research_repository
    )
    capabilities = SecureLocalCapabilityFactory()
    demo_service = DemoApplicationService(
        active_demo_repository,
        demo_source,
        clock or SystemClock(),
        identifiers or UuidFactory(),
        capabilities,
    )
    demo_runtime_service = DemoRuntimeService(
        active_demo_repository,
        demo_service,
        clock or SystemClock(),
        identifiers or UuidFactory(),
        capabilities,
    )

    app = FastAPI(
        title="Opportunity Intelligence M4 API",
        version="0.5.0",
        description=(
            "Bounded research, deterministic opportunities, evidence-linked audits, and private "
            "mock-only simulations. Live AI, publication, and real integrations are disabled."
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
    app.state.audit_repository = active_audit_repository
    app.state.audit_source = audit_source
    app.state.audit_service = audit_service
    app.state.demo_repository = active_demo_repository
    app.state.demo_source = demo_source
    app.state.demo_service = demo_service
    app.state.demo_runtime_service = demo_runtime_service

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

    @app.exception_handler(AuditNotFoundError)
    def audit_not_found_handler(request: Request, error: AuditNotFoundError) -> JSONResponse:
        del request, error
        return JSONResponse(status_code=404, content={"detail": "audit resource not found"})

    @app.exception_handler(AuditError)
    def audit_error_handler(request: Request, error: AuditError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=403 if error.code == "forbidden" else 400,
            content={"detail": error.safe_message, "code": error.code},
        )

    @app.exception_handler(DemoNotFoundError)
    def demo_not_found_handler(request: Request, error: DemoNotFoundError) -> JSONResponse:
        del request, error
        return JSONResponse(status_code=404, content={"detail": "demo resource not found"})

    @app.exception_handler(DemoError)
    def demo_error_handler(request: Request, error: DemoError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=403 if error.code == "forbidden" else 400,
            content={"detail": error.safe_message, "code": error.code},
        )

    @app.get("/healthz", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "m4-local"}

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

    @app.post(
        "/api/v1/opportunities/{hypothesis_id}/audit-revisions",
        response_model=AuditOperationView,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["audits"],
    )
    def create_audit_revision(
        hypothesis_id: UUID,
        command: AuditCreate,
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
    ) -> AuditOperationView:
        operation, created = audit_service.start_generation(
            principal,
            hypothesis_id,
            command.expected_hypothesis_revision_id,
            idempotency_key,
            command.parent_revision_id,
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return AuditOperationView.from_domain(operation)

    @app.get(
        "/api/v1/audit-operations/{operation_id}",
        response_model=AuditOperationView,
        tags=["audits"],
    )
    def get_audit_operation(
        operation_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> AuditOperationView:
        return AuditOperationView.from_domain(audit_service.get_operation(principal, operation_id))

    @app.get(
        "/api/v1/audit-revisions/{revision_id}",
        response_model=AuditBundleView,
        tags=["audits"],
    )
    def get_audit_revision(
        revision_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> AuditBundleView:
        return AuditBundleView.from_domain(audit_service.get_revision(principal, revision_id))

    @app.get(
        "/api/v1/audit-revisions/{revision_id}/claims/{claim_id}/lineage",
        response_model=dict[str, object],
        tags=["audits"],
    )
    def get_audit_claim_lineage(
        revision_id: UUID,
        claim_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> dict[str, object]:
        bundle = audit_service.get_revision(principal, revision_id)
        claim = next((item for item in bundle.revision.claims if item.id == claim_id), None)
        if claim is None:
            raise AuditNotFoundError()
        return {
            "claim": asdict(claim),
            "manifest_hash": bundle.revision.manifest.checksum,
            "evidence_links": [f"/api/v1/research-evidence/{item}" for item in claim.evidence_ids],
            "economic_run_id": claim.economic_run_id,
            "assumption_revision_ids": list(claim.assumption_revision_ids),
            "inference_revision_ids": list(claim.inference_revision_ids),
            "dependency_claim_ids": list(claim.dependency_claim_ids),
        }

    @app.get(
        "/api/v1/audits/{audit_id}/revisions",
        response_model=list[AuditBundleView],
        tags=["audits"],
    )
    def list_audit_revisions(
        audit_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[AuditBundleView]:
        return [
            AuditBundleView.from_domain(item)
            for item in audit_service.list_revisions(principal, audit_id)
        ]

    @app.post(
        "/api/v1/audit-revisions/{revision_id}/review-decisions",
        response_model=AuditBundleView,
        tags=["audits"],
    )
    def review_audit_revision(
        revision_id: UUID,
        command: AuditReviewRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> AuditBundleView:
        return AuditBundleView.from_domain(
            audit_service.review(
                principal,
                revision_id,
                command.expected_revision_hash,
                command.expected_manifest_hash,
                command.decision,
                command.reason,
                tuple(command.acknowledged_qc_codes),
            )
        )

    @app.post(
        "/api/v1/audit-revisions/{audit_revision_id}/demo-revisions",
        response_model=DemoOperationView,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["demos"],
    )
    def create_demo_revision(
        audit_revision_id: UUID,
        command: DemoCreate,
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
    ) -> DemoOperationView:
        operation, created = demo_service.start_generation(
            principal,
            audit_revision_id,
            command.expected_audit_revision_hash,
            idempotency_key,
            command.parent_revision_id,
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return DemoOperationView.from_domain(operation)

    @app.get(
        "/api/v1/demo-operations/{operation_id}",
        response_model=DemoOperationView,
        tags=["demos"],
    )
    def get_demo_operation(
        operation_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> DemoOperationView:
        return DemoOperationView.from_domain(demo_service.get_operation(principal, operation_id))

    @app.get(
        "/api/v1/demo-revisions/{revision_id}",
        response_model=DemoBundleView,
        tags=["demos"],
    )
    def get_demo_revision(
        revision_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> DemoBundleView:
        return DemoBundleView.from_domain(demo_service.get_revision(principal, revision_id))

    @app.get(
        "/api/v1/demos/{demo_id}/revisions",
        response_model=list[DemoBundleView],
        tags=["demos"],
    )
    def list_demo_revisions(
        demo_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[DemoBundleView]:
        return [
            DemoBundleView.from_domain(item)
            for item in demo_service.list_revisions(principal, demo_id)
        ]

    @app.get(
        "/api/v1/demo-revisions/{revision_id}/statements/{statement_id}/lineage",
        response_model=dict[str, object],
        tags=["demos"],
    )
    def get_demo_statement_lineage(
        revision_id: UUID,
        statement_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> dict[str, object]:
        bundle = demo_service.get_revision(principal, revision_id)
        statement = next(
            (item for item in bundle.revision.specification.statements if item.id == statement_id),
            None,
        )
        if statement is None:
            raise DemoNotFoundError()
        return {
            "statement": asdict(statement),
            "manifest_hash": bundle.revision.manifest.checksum,
            "audit_revision": (
                f"/api/v1/audit-revisions/{bundle.revision.manifest.audit_revision_id}"
            ),
            "audit_claim_id": statement.audit_claim_id,
            "evidence_links": [
                f"/api/v1/research-evidence/{item}" for item in statement.evidence_ids
            ],
            "assumption_revision_ids": list(statement.assumption_revision_ids),
            "economic_run_id": statement.economic_run_id,
            "formula_version": statement.formula_version,
        }

    @app.post(
        "/api/v1/demo-revisions/{revision_id}/review-decisions",
        response_model=DemoBundleView,
        tags=["demos"],
    )
    def review_demo_revision(
        revision_id: UUID,
        command: DemoReviewRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> DemoBundleView:
        return DemoBundleView.from_domain(
            demo_service.review(
                principal,
                revision_id,
                command.expected_revision_hash,
                command.expected_manifest_hash,
                command.expected_specification_hash,
                command.decision,
                command.reason,
            )
        )

    @app.post(
        "/api/v1/demo-revisions/{revision_id}/revocations",
        response_model=DemoBundleView,
        tags=["demos"],
    )
    def revoke_demo_revision(
        revision_id: UUID,
        command: DemoRevokeRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> DemoBundleView:
        return DemoBundleView.from_domain(
            demo_service.revoke_revision(principal, revision_id, command.reason)
        )

    @app.post(
        "/api/v1/demo-revisions/{revision_id}/session-issuances",
        response_model=SessionCapabilityView,
        tags=["demos"],
    )
    def issue_demo_session(
        revision_id: UUID,
        command: SessionIssueRequest,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> SessionCapabilityView:
        issuance, capability = demo_service.issue_session(
            principal, revision_id, command.expected_revision_hash
        )
        return SessionCapabilityView(
            issuance_id=issuance.id,
            capability=capability,
            expires_at=issuance.expires_at.isoformat(),
            runtime_origin=demo_service.runtime_origin,
        )

    @app.post(
        "/api/v1/demo-runtime-sessions/{session_id}/revocations",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["demos"],
    )
    def revoke_demo_session(
        session_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Response:
        demo_service.revoke_session(principal, session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/demo-revisions/{revision_id}/telemetry",
        response_model=list[dict[str, object]],
        tags=["demos"],
    )
    def list_demo_telemetry(
        revision_id: UUID,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> list[dict[str, object]]:
        demo_service.get_revision(principal, revision_id)
        return [
            asdict(item)
            for item in active_demo_repository.list_telemetry(principal.workspace_id, revision_id)
        ]

    # Capability possession is the sole narrow authority at this internal boundary. These routes
    # deliberately do not accept the core bearer credential and are intended only for the separate
    # localhost runtime process in M4.
    @app.post(
        "/internal/demo-runtime/capabilities/exchange",
        response_model=RuntimeSessionResponse,
        include_in_schema=False,
    )
    def exchange_demo_capability(
        command: CapabilityExchangeRequest,
    ) -> RuntimeSessionResponse:
        runtime, token = demo_runtime_service.exchange(
            command.capability, command.persona_id, command.seed
        )
        return RuntimeSessionResponse.from_domain(runtime, token)

    @app.post(
        "/internal/demo-runtime/events",
        response_model=RuntimeSessionResponse,
        include_in_schema=False,
    )
    def apply_demo_runtime_event(command: RuntimeEventRequest) -> RuntimeSessionResponse:
        runtime = demo_runtime_service.apply_event(
            command.session_token, command.event, command.value, command.duration_ms
        )
        return RuntimeSessionResponse.from_domain(runtime, command.session_token)

    return app
