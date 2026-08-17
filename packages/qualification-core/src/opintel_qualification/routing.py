"""Qualified-only advisory routing with deterministic M2 fallback."""

from __future__ import annotations

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory

from opintel_qualification.domain import (
    DeploymentRecord,
    IntelligenceRequest,
    InvocationLedgerEntry,
    LiveEvaluationPolicy,
    ProviderKind,
    ProviderResponse,
    QualificationStatus,
    RouteResult,
    RoutingStage,
)
from opintel_qualification.ports import (
    BudgetGuard,
    LiveEvaluationGate,
    ProviderCatalog,
    QualificationRepository,
)


class QualificationRouter:
    def __init__(
        self,
        repository: QualificationRepository,
        providers: ProviderCatalog,
        budget: BudgetGuard,
        live_gate: LiveEvaluationGate,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._providers = providers
        self._budget = budget
        self._live_gate = live_gate
        self._clock = clock
        self._identifiers = identifiers

    def route(
        self,
        principal: Principal,
        request: IntelligenceRequest,
        live_policy: LiveEvaluationPolicy,
    ) -> RouteResult:
        if request.workspace_id != principal.workspace_id:
            return self._fallback(request.stage, 0, "workspace mismatch")
        if request.stage not in request.task_contract.allowed_stages:
            return self._fallback(request.stage, 0, "routing stage is not allowed")
        decisions = self._repository.list_decisions(
            principal.workspace_id, QualificationStatus.QUALIFIED
        )
        candidates = tuple(
            item
            for item in decisions
            if item.key.task_class == request.task_contract.task_class
            and item.key.task_version == request.task_contract.task_version
            and item.key.schema_version == request.task_contract.output_schema_version
            and item.key.policy_version == request.policy_version
            and item.key.corpus_version == request.corpus_version
            and item.key.data_classification == request.data_classification
        )
        attempts = 0
        for fallback_index, decision in enumerate(candidates):
            deployment = self._repository.get_deployment(
                principal.workspace_id, decision.key.deployment_id
            )
            provider = self._providers.get(decision.key.deployment_id)
            if deployment is None or provider is None:
                continue
            if (
                deployment.deployment_version != decision.key.deployment_version
                or deployment.config_hash != decision.key.deployment_config_hash
                or provider.deployment_id != deployment.id
            ):
                continue
            if deployment.provider_kind == ProviderKind.LIVE and not self._live_gate.authorize(
                live_policy, request, deployment
            ):
                continue
            for local_attempt in (1, 2):
                attempts += 1
                if not self._budget.reserve(
                    principal.workspace_id,
                    request.evaluation_run_id,
                    request.max_output_tokens,
                    request.estimated_cost_micros,
                ):
                    self._ledger(
                        deployment,
                        request,
                        ProviderResponse(None, True, "budget_exceeded", 0, 0, 0, 0, 0, "none"),
                        local_attempt,
                        fallback_index,
                    )
                    return self._fallback(request.stage, attempts, "budget denied")
                try:
                    response = provider.invoke(request, local_attempt)
                except (RuntimeError, TimeoutError):
                    response = ProviderResponse(
                        None, True, "provider_failure", 0, 0, 0, 0, 0, "none"
                    )
                within_budget = self._budget.record_actual(
                    principal.workspace_id,
                    request.evaluation_run_id,
                    response.input_tokens + response.output_tokens,
                    response.estimated_cost_micros,
                )
                if not within_budget:
                    response = ProviderResponse(
                        None,
                        True,
                        "budget_exceeded",
                        response.input_tokens,
                        response.output_tokens,
                        response.cached_tokens,
                        response.latency_ms,
                        response.estimated_cost_micros,
                        response.pricing_version,
                    )
                self._ledger(deployment, request, response, local_attempt, fallback_index)
                if response.failure_code is not None:
                    break
                if not response.schema_valid or response.output is None:
                    continue
                if not self._safe_output(request, response):
                    break
                deterministic = request.stage != RoutingStage.ADVISORY
                return RouteResult(
                    request.stage,
                    deployment.id,
                    response.output,
                    deterministic,
                    attempts,
                    "qualified advisory output"
                    if not deterministic
                    else "qualified output recorded without application authority",
                )
        return self._fallback(request.stage, attempts, "no qualified deployment succeeded")

    @staticmethod
    def _safe_output(request: IntelligenceRequest, response: ProviderResponse) -> bool:
        assert response.output is not None
        allowlist = set(request.evidence_allowlist)
        return not response.output.injection_followed and all(
            claim.supported
            and claim.fact_kind != "internal_business_fact"
            and set(claim.evidence_ids).issubset(allowlist)
            for claim in response.output.claims
        )

    def _ledger(
        self,
        deployment: DeploymentRecord,
        request: IntelligenceRequest,
        response: ProviderResponse,
        attempt: int,
        fallback_index: int,
    ) -> None:
        self._repository.save_invocation(
            InvocationLedgerEntry(
                self._identifiers.new(),
                request.workspace_id,
                request.evaluation_run_id,
                request.case_id,
                deployment.id,
                request.task_contract.task_class,
                request.task_contract.task_version,
                deployment.model_version,
                deployment.deployment_version,
                request.prompt_hash,
                request.config_hash,
                request.policy_version,
                request.corpus_version,
                response.pricing_version,
                attempt,
                fallback_index,
                response.input_tokens,
                response.output_tokens,
                response.cached_tokens,
                response.latency_ms,
                response.estimated_cost_micros,
                "valid" if response.schema_valid and response.failure_code is None else "failed",
                response.failure_code,
                self._clock.now(),
            )
        )

    @staticmethod
    def _fallback(stage: RoutingStage, attempts: int, reason: str) -> RouteResult:
        return RouteResult(stage, None, None, True, attempts, reason)
