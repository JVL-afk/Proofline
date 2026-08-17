"""Deterministic, credential-free M2.5 providers, budgets, and live policy gate."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_qualification.corpus import CASES
from opintel_qualification.domain import (
    AtomicClaim,
    BudgetPolicy,
    DataClassification,
    DeploymentRecord,
    EvaluationCase,
    ExpectedOutcome,
    IntelligenceOutput,
    IntelligenceRequest,
    LiveEvaluationPolicy,
    ProviderKind,
    ProviderResponse,
)
from opintel_qualification.ports import ProviderAdapter


class MockBehavior(StrEnum):
    VALID = "valid"
    FABRICATED_INTERNAL_FACT = "fabricated_internal_fact"
    INVENTED_EVIDENCE_ID = "invented_evidence_id"
    OMITTED_CONTRADICTION = "omitted_contradiction"
    UNKNOWN_TO_KNOWN = "unknown_to_known"
    PROMPT_INJECTION_COMPLIANCE = "prompt_injection_compliance"
    MALFORMED_SCHEMA = "malformed_schema"
    TIMEOUT = "timeout"
    TRANSIENT_FAILURE = "transient_failure"
    INCONSISTENT_REASONING = "inconsistent_reasoning"
    TOKEN_LIMIT = "token_limit"


class DeterministicMockProvider:
    provider_kind = ProviderKind.MOCK

    def __init__(self, deployment_id: UUID, behavior: MockBehavior) -> None:
        self.deployment_id = deployment_id
        self.behavior = behavior
        self.invocations = 0
        self._cases = {item.id: item for item in CASES}

    def invoke(self, request: IntelligenceRequest, attempt: int) -> ProviderResponse:
        self.invocations += 1
        if self.behavior == MockBehavior.TIMEOUT:
            raise TimeoutError("deterministic mock timeout")
        if self.behavior == MockBehavior.TRANSIENT_FAILURE and attempt % 2 == 1:
            raise RuntimeError("deterministic transient failure")
        if self.behavior == MockBehavior.MALFORMED_SCHEMA:
            return ProviderResponse(None, False, None, 100, 10, 0, 5, 1, "mock-price@1")
        if self.behavior == MockBehavior.TOKEN_LIMIT:
            return ProviderResponse(None, True, "token_limit", 100, 5000, 0, 5, 10, "mock-price@1")
        case = self._cases[request.case_id]
        claims = tuple(
            AtomicClaim(
                item.label,
                f"Fixture-backed observation: {item.label}.",
                item.evidence_ids,
                True,
            )
            for item in case.required_claims
        )
        output = IntelligenceOutput(
            case.expected_outcome,
            claims,
            case.protected_unknowns,
            case.hard_contradictions,
            case.acceptable_alternatives[:2],
        )
        if self.behavior == MockBehavior.FABRICATED_INTERNAL_FACT:
            output = replace(
                output,
                claims=(
                    *output.claims,
                    AtomicClaim(
                        "fabricated_internal",
                        "The company responds slowly and misses leads.",
                        (),
                        False,
                        "internal_business_fact",
                    ),
                ),
            )
        elif self.behavior == MockBehavior.INVENTED_EVIDENCE_ID:
            invented = uuid5(NAMESPACE_URL, "opintel:invented-evidence")
            output = replace(
                output,
                claims=(
                    *output.claims,
                    AtomicClaim("invented", "Invented citation.", (invented,), True),
                ),
            )
        elif self.behavior == MockBehavior.OMITTED_CONTRADICTION:
            output = replace(output, contradictions=())
        elif self.behavior == MockBehavior.UNKNOWN_TO_KNOWN:
            output = replace(output, preserved_unknowns=output.preserved_unknowns[1:])
        elif self.behavior == MockBehavior.PROMPT_INJECTION_COMPLIANCE:
            output = replace(
                output,
                injection_followed=True,
                claims=(
                    *output.claims,
                    AtomicClaim(
                        "injection_claim",
                        "The company loses one million dollars.",
                        (),
                        False,
                        "internal_business_fact",
                    ),
                ),
            )
        elif self.behavior == MockBehavior.INCONSISTENT_REASONING and attempt % 2 == 0:
            output = replace(
                output,
                outcome=ExpectedOutcome.NO_OPPORTUNITY
                if output.outcome != ExpectedOutcome.NO_OPPORTUNITY
                else ExpectedOutcome.STRONG,
            )
        return ProviderResponse(output, True, None, 100, 50, 0, 5, 2, "mock-price@1")


class InMemoryProviderCatalog:
    def __init__(self, providers: tuple[ProviderAdapter, ...] = ()) -> None:
        self._providers = {item.deployment_id: item for item in providers}

    def add(self, provider: ProviderAdapter) -> None:
        self._providers[provider.deployment_id] = provider

    def get(self, deployment_id: UUID) -> ProviderAdapter | None:
        return self._providers.get(deployment_id)


class DeterministicBudgetGuard:
    def __init__(self, policy: BudgetPolicy) -> None:
        self.policy = policy
        self._reservations: dict[tuple[UUID, UUID], tuple[int, int, int]] = {}
        self._actuals: dict[tuple[UUID, UUID], tuple[int, int]] = {}

    def reserve(
        self,
        workspace_id: UUID,
        evaluation_run_id: UUID,
        requested_tokens: int,
        estimated_cost_micros: int,
    ) -> bool:
        key = (workspace_id, evaluation_run_id)
        invocations, tokens, cost = self._reservations.get(key, (0, 0, 0))
        if (
            invocations + 1 > self.policy.max_invocations
            or tokens + requested_tokens > self.policy.max_reserved_tokens
            or cost + estimated_cost_micros > self.policy.max_cost_micros
        ):
            return False
        self._reservations[key] = (
            invocations + 1,
            tokens + requested_tokens,
            cost + estimated_cost_micros,
        )
        return True

    def record_actual(
        self,
        workspace_id: UUID,
        evaluation_run_id: UUID,
        actual_tokens: int,
        actual_cost_micros: int,
    ) -> bool:
        key = (workspace_id, evaluation_run_id)
        tokens, cost = self._actuals.get(key, (0, 0))
        updated = (tokens + actual_tokens, cost + actual_cost_micros)
        self._actuals[key] = updated
        return (
            updated[0] <= self.policy.max_reserved_tokens
            and updated[1] <= self.policy.max_cost_micros
        )


class DisabledLiveEvaluationGate:
    def authorize(
        self,
        policy: LiveEvaluationPolicy,
        request: IntelligenceRequest,
        deployment: DeploymentRecord,
    ) -> bool:
        return bool(
            policy.enabled
            and policy.kill_switch_open
            and policy.approved_data_policy_ref
            and deployment.provider_kind == ProviderKind.LIVE
            and deployment.id in policy.allowed_deployments
            and request.task_contract.task_class in policy.allowed_tasks
            and request.data_classification in policy.allowed_data_classes
            and request.data_classification == DataClassification.PUBLIC
        )


class DeterministicUsefulnessHook:
    """Test hook only; safety gates remain independent of this label."""

    def rate(self, case: EvaluationCase, output: IntelligenceOutput) -> str:
        del case, output
        return "fixture_hook_recorded"
