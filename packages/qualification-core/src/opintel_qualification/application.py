"""Authorized registry lifecycle and deterministic qualification execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from uuid import UUID

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory

from opintel_qualification.domain import (
    CRITICAL_GATES,
    CaseEvaluationResult,
    DeploymentRecord,
    EvaluationCase,
    GateFailure,
    IntelligenceRequest,
    InvocationLedgerEntry,
    LiveEvaluationPolicy,
    ProviderKind,
    ProviderResponse,
    QualificationAuthorizationError,
    QualificationDecision,
    QualificationKey,
    QualificationStatus,
    QualificationValidationError,
    RoutingStage,
)
from opintel_qualification.evaluator import evaluate_response, semantic_signature
from opintel_qualification.ports import (
    BudgetGuard,
    LiveEvaluationGate,
    ProviderAdapter,
    QualificationRepository,
    ReasoningUsefulnessHook,
)

TRANSITIONS = {
    QualificationStatus.UNASSESSED: {QualificationStatus.EVALUATING, QualificationStatus.RETIRED},
    QualificationStatus.EVALUATING: {
        QualificationStatus.QUALIFIED,
        QualificationStatus.CONDITIONAL,
        QualificationStatus.DISQUALIFIED,
        QualificationStatus.SUSPENDED,
    },
    QualificationStatus.QUALIFIED: {
        QualificationStatus.SUSPENDED,
        QualificationStatus.RETIRED,
    },
    QualificationStatus.CONDITIONAL: {
        QualificationStatus.EVALUATING,
        QualificationStatus.SUSPENDED,
        QualificationStatus.RETIRED,
    },
    QualificationStatus.DISQUALIFIED: {
        QualificationStatus.EVALUATING,
        QualificationStatus.RETIRED,
    },
    QualificationStatus.SUSPENDED: {
        QualificationStatus.EVALUATING,
        QualificationStatus.RETIRED,
    },
    QualificationStatus.RETIRED: set(),
}


class QualificationApplicationService:
    def __init__(
        self,
        repository: QualificationRepository,
        clock: Clock,
        identifiers: IdentifierFactory,
        live_gate: LiveEvaluationGate,
        usefulness_hook: ReasoningUsefulnessHook | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers
        self._live_gate = live_gate
        self._usefulness_hook = usefulness_hook

    def register_deployment(
        self, principal: Principal, deployment: DeploymentRecord, key: QualificationKey
    ) -> QualificationDecision:
        self._require_operator(principal)
        if deployment.workspace_id != principal.workspace_id or key.deployment_id != deployment.id:
            raise QualificationValidationError("workspace or deployment key mismatch")
        self._validate_key(deployment, key)
        for existing in self._repository.list_deployments(principal.workspace_id):
            if (
                existing.provider_key == deployment.provider_key
                and existing.model_key == deployment.model_key
                and existing.id != deployment.id
                and (
                    existing.model_version != deployment.model_version
                    or existing.deployment_version != deployment.deployment_version
                    or existing.config_hash != deployment.config_hash
                )
            ):
                self._suspend_active_for_deployment(
                    principal, existing.id, "model, deployment, or configuration drift"
                )
        self._repository.add_deployment(deployment)
        return self.register_key(principal, key)

    def register_key(self, principal: Principal, key: QualificationKey) -> QualificationDecision:
        self._require_operator(principal)
        deployment = self._repository.get_deployment(principal.workspace_id, key.deployment_id)
        if deployment is None:
            raise QualificationValidationError("deployment is not registered")
        self._validate_key(deployment, key)
        if self._repository.latest_decision(principal.workspace_id, key) is not None:
            raise QualificationValidationError("qualification key is already registered")
        decision = QualificationDecision(
            self._identifiers.new(),
            principal.workspace_id,
            key,
            QualificationStatus.UNASSESSED,
            None,
            "deployment registered; no qualification implied",
            None,
            self._clock.now(),
        )
        self._repository.append_decision(decision)
        return decision

    def evaluate(
        self,
        principal: Principal,
        key: QualificationKey,
        cases: tuple[EvaluationCase, ...],
        provider: ProviderAdapter,
        budget: BudgetGuard,
        live_policy: LiveEvaluationPolicy,
        *,
        repetitions: int = 2,
        provisional_consistency_minimum: str = "0.99",
    ) -> QualificationDecision:
        self._require_operator(principal)
        deployment = self._repository.get_deployment(principal.workspace_id, key.deployment_id)
        if deployment is None:
            raise QualificationValidationError("deployment is not registered")
        self._validate_key(deployment, key)
        if provider.deployment_id != deployment.id:
            raise QualificationValidationError("provider adapter does not match deployment")
        if not cases or any(
            case.task_class != key.task_class
            or case.task_version != key.task_version
            or case.corpus_version != key.corpus_version
            for case in cases
        ):
            raise QualificationValidationError("corpus cases do not match qualification key")
        if repetitions < 1 or repetitions > 5:
            raise QualificationValidationError("repetitions must be between one and five")
        if deployment.provider_kind == ProviderKind.LIVE:
            probe = self._request(principal, self._identifiers.new(), cases[0], key)
            if not self._live_gate.authorize(live_policy, probe, deployment):
                raise QualificationValidationError("live evaluation policy denied the request")

        prior = self._repository.latest_decision(principal.workspace_id, key)
        if prior is None:
            raise QualificationValidationError("qualification key is unregistered")
        evaluating = self._transition(
            principal, prior, QualificationStatus.EVALUATING, "evaluation started", None
        )
        evaluation_run_id = self._identifiers.new()
        all_results: list[CaseEvaluationResult] = []
        consistency_values: list[float] = []
        for case in cases:
            responses: list[ProviderResponse] = []
            attempts = 0
            for _repetition in range(repetitions):
                request = self._request(principal, evaluation_run_id, case, key)
                response, used_attempts = self._invoke_bounded(
                    deployment,
                    provider,
                    request,
                    budget,
                    fallback_index=0,
                    attempt_offset=attempts,
                )
                attempts += used_attempts
                responses.append(response)
                if response.failure_code in {"budget_exceeded", "timeout"}:
                    break
            valid_outputs = [item.output for item in responses if item.output is not None]
            signatures = {semantic_signature(item) for item in valid_outputs}
            consistency = 1.0 if len(signatures) <= 1 else 1.0 / len(signatures)
            consistency_values.append(consistency)
            final = responses[-1]
            usefulness = (
                self._usefulness_hook.rate(case, final.output)
                if self._usefulness_hook is not None and final.output is not None
                else None
            )
            result = evaluate_response(
                self._identifiers.new(),
                principal.workspace_id,
                evaluation_run_id,
                deployment.id,
                key,
                case,
                final,
                attempts,
                self._clock.now(),
                str(consistency),
                usefulness,
            )
            if final.failure_code:
                failure = (
                    GateFailure.BUDGET_EXCEEDED
                    if final.failure_code in {"budget_exceeded", "token_limit"}
                    else GateFailure.PROVIDER_FAILURE
                )
                result = replace(
                    result,
                    gate_failures=tuple(dict.fromkeys((*result.gate_failures, failure))),
                )
            self._repository.save_case_result(result)
            all_results.append(result)

        hard_failed = any(CRITICAL_GATES.intersection(item.gate_failures) for item in all_results)
        consistency_floor = float(provisional_consistency_minimum)
        noncritical_failed = any(item.gate_failures for item in all_results) or any(
            value < consistency_floor for value in consistency_values
        )
        status = (
            QualificationStatus.DISQUALIFIED
            if hard_failed
            else QualificationStatus.CONDITIONAL
            if noncritical_failed
            else QualificationStatus.QUALIFIED
        )
        return self._transition(
            principal,
            evaluating,
            status,
            "hard safety gate failed"
            if hard_failed
            else "provisional non-critical threshold or provider condition failed"
            if noncritical_failed
            else "all configured task qualification gates passed",
            evaluation_run_id,
        )

    def suspend_drifted(
        self, principal: Principal, desired_key: QualificationKey
    ) -> tuple[QualificationDecision, ...]:
        self._require_operator(principal)
        suspended: list[QualificationDecision] = []
        for decision in self._repository.list_decisions(principal.workspace_id):
            if (
                decision.key.deployment_id == desired_key.deployment_id
                and decision.status
                in {QualificationStatus.QUALIFIED, QualificationStatus.CONDITIONAL}
                and decision.key != desired_key
            ):
                suspended.append(
                    self._transition(
                        principal,
                        decision,
                        QualificationStatus.SUSPENDED,
                        "deployment, config, task, schema, policy, corpus, or data-class drift",
                        None,
                    )
                )
        return tuple(suspended)

    def retire(self, principal: Principal, key: QualificationKey) -> QualificationDecision:
        self._require_operator(principal)
        prior = self._repository.latest_decision(principal.workspace_id, key)
        if prior is None:
            raise QualificationValidationError("qualification key is not registered")
        return self._transition(principal, prior, QualificationStatus.RETIRED, "retired", None)

    def _suspend_active_for_deployment(
        self, principal: Principal, deployment_id: UUID, reason: str
    ) -> tuple[QualificationDecision, ...]:
        results: list[QualificationDecision] = []
        for decision in self._repository.list_decisions(principal.workspace_id):
            if decision.key.deployment_id == deployment_id and decision.status in {
                QualificationStatus.QUALIFIED,
                QualificationStatus.CONDITIONAL,
            }:
                results.append(
                    self._transition(
                        principal,
                        decision,
                        QualificationStatus.SUSPENDED,
                        reason,
                        None,
                    )
                )
        return tuple(results)

    def _invoke_bounded(
        self,
        deployment: DeploymentRecord,
        provider: ProviderAdapter,
        request: IntelligenceRequest,
        budget: BudgetGuard,
        fallback_index: int,
        attempt_offset: int,
    ) -> tuple[ProviderResponse, int]:
        last = ProviderResponse(None, False, "provider_failure", 0, 0, 0, 0, 0, "none")
        for local_attempt in (1, 2):
            attempt = attempt_offset + local_attempt
            if not budget.reserve(
                request.workspace_id,
                request.evaluation_run_id,
                request.max_output_tokens,
                request.estimated_cost_micros,
            ):
                last = ProviderResponse(None, True, "budget_exceeded", 0, 0, 0, 0, 0, "none")
                self._ledger(deployment, request, last, attempt, fallback_index)
                return last, local_attempt
            try:
                last = provider.invoke(request, attempt)
            except TimeoutError:
                last = ProviderResponse(None, True, "timeout", 0, 0, 0, 0, 0, "none")
            except RuntimeError:
                last = ProviderResponse(None, True, "transient_failure", 0, 0, 0, 0, 0, "none")
            within_budget = budget.record_actual(
                request.workspace_id,
                request.evaluation_run_id,
                last.input_tokens + last.output_tokens,
                last.estimated_cost_micros,
            )
            if not within_budget:
                last = replace(last, output=None, failure_code="budget_exceeded")
            self._ledger(deployment, request, last, attempt, fallback_index)
            if last.failure_code == "token_limit":
                return last, local_attempt
            if last.schema_valid and last.failure_code is None:
                return last, local_attempt
        return last, 2

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

    def _request(
        self,
        principal: Principal,
        evaluation_run_id: UUID,
        case: EvaluationCase,
        key: QualificationKey,
    ) -> IntelligenceRequest:
        from opintel_qualification.corpus import TASK_CONTRACTS

        contract = TASK_CONTRACTS[case.task_class]
        prompt_hash = hashlib.sha256(
            json.dumps(
                {
                    "case_manifest": case.manifest_hash,
                    "task": contract.task_version,
                    "policy": key.policy_version,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return IntelligenceRequest(
            self._identifiers.new(),
            principal.workspace_id,
            evaluation_run_id,
            case.id,
            contract,
            RoutingStage.EVALUATION_ONLY,
            case.evidence,
            tuple(item.id for item in case.evidence),
            key.policy_version,
            key.corpus_version,
            key.data_classification,
            prompt_hash,
            key.deployment_config_hash,
            1000,
            10,
            self._identifiers.new(),
            tuple(item.label for item in case.required_claims),
            case.protected_unknowns,
            case.hard_contradictions,
            case.acceptable_alternatives,
        )

    def _transition(
        self,
        principal: Principal,
        prior: QualificationDecision,
        status: QualificationStatus,
        reason: str,
        evaluation_run_id: UUID | None,
    ) -> QualificationDecision:
        if status not in TRANSITIONS[prior.status]:
            raise QualificationValidationError(
                f"invalid qualification transition {prior.status} -> {status}"
            )
        decision = QualificationDecision(
            self._identifiers.new(),
            principal.workspace_id,
            prior.key,
            status,
            prior.id,
            reason,
            evaluation_run_id,
            self._clock.now(),
        )
        self._repository.append_decision(decision)
        return decision

    @staticmethod
    def _validate_key(deployment: DeploymentRecord, key: QualificationKey) -> None:
        if (
            key.deployment_id != deployment.id
            or key.deployment_version != deployment.deployment_version
            or key.deployment_config_hash != deployment.config_hash
            or key.task_class not in deployment.capabilities
        ):
            raise QualificationValidationError("qualification key does not match deployment")

    @staticmethod
    def _require_operator(principal: Principal) -> None:
        if not principal.can_operate():
            raise QualificationAuthorizationError()
