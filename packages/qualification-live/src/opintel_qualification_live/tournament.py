"""Fail-closed staged M2.6 tournament; outputs are review artifacts, never product truth."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_qualification.corpus import POLICY_VERSION, SCHEMA_VERSION, TASK_CONTRACTS
from opintel_qualification.domain import (
    CRITICAL_GATES,
    CaseEvaluationResult,
    DataClassification,
    EvaluationCase,
    GateFailure,
    IntelligenceRequest,
    QualificationStatus,
    RoutingStage,
    TaskClass,
)
from opintel_qualification.evaluator import evaluate_response

from opintel_qualification_live.config import MAX_OUTPUT_TOKENS, TOURNAMENT_BUDGET_MICROS
from opintel_qualification_live.contracts import DeploymentSpec, ProviderReceipt
from opintel_qualification_live.fixtures import cases_for_round


@dataclass(frozen=True, slots=True)
class TournamentRecord:
    deployment_id: UUID
    provider: str
    model_id: str
    config_hash: str
    task_class: TaskClass
    round_name: str
    family: str
    repetition: int
    result: CaseEvaluationResult
    receipt: ProviderReceipt


@dataclass(frozen=True, slots=True)
class PairSummary:
    deployment_id: UUID
    provider: str
    model_id: str
    config_hash: str
    task_class: TaskClass
    status: QualificationStatus
    cases_completed: int
    runs_completed: int
    hard_gate_failures: tuple[str, ...]
    unsupported_claims: int
    unsupported_claims_per_run: str
    evidence_fidelity_ratio: str
    citation_validity_ratio: str
    citation_entailment_ratio: str
    unknown_preservation_ratio: str
    contradiction_recognition_ratio: str
    prompt_injection_resistance_ratio: str
    schema_first_pass_ratio: str
    bounded_retry_rate: str
    schema_repair_rate: str
    semantic_invariant_ratio: str
    human_usefulness: str
    latency_p50_ms: int
    latency_p95_ms: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_cost_micros: int
    cost_per_success_micros: int | None
    projected_cost_per_business_micros: int | None


class TournamentBudget:
    def __init__(self, deployments: tuple[DeploymentSpec, ...]) -> None:
        self.total_limit = TOURNAMENT_BUDGET_MICROS
        self.deployment_limits = {item.id: item.sub_budget_micros for item in deployments}
        self.total_spent = 0
        self.deployment_spent = {item.id: 0 for item in deployments}

    def authorize(self, deployment: DeploymentSpec, estimated_cost_micros: int) -> bool:
        return (
            self.total_spent + estimated_cost_micros <= self.total_limit
            and self.deployment_spent[deployment.id] + estimated_cost_micros
            <= self.deployment_limits[deployment.id]
        )

    def record(self, deployment: DeploymentSpec, actual_cost_micros: int) -> None:
        if not self.authorize(deployment, actual_cost_micros):
            raise RuntimeError("tournament_budget_exceeded")
        self.total_spent += actual_cost_micros
        self.deployment_spent[deployment.id] += actual_cost_micros


def estimated_maximum_cost(deployments: tuple[DeploymentSpec, ...]) -> tuple[int, dict[UUID, int]]:
    # Certification, critical-only, and tournament passes plus all staged task rounds.
    calls_per_deployment = 3 + 4 * (
        4 * len(cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "critical"))
        + len(cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "quality"))
        + len(cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "economic"))
    )
    input_estimate = 1_500
    by_deployment = {
        item.id: calls_per_deployment
        * item.pricing.cost_micros(input_estimate, MAX_OUTPUT_TOKENS, 0)
        for item in deployments
    }
    return sum(by_deployment.values()), by_deployment


class TournamentRunner:
    def __init__(
        self,
        deployments: tuple[DeploymentSpec, ...],
        adapters: dict[UUID, object],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.deployments = deployments
        self.adapters = adapters
        self.budget = TournamentBudget(deployments)
        self.records: list[TournamentRecord] = []
        self._now = now

    def run(self) -> tuple[PairSummary, ...]:
        estimate, estimates = estimated_maximum_cost(self.deployments)
        if estimate > TOURNAMENT_BUDGET_MICROS or any(
            estimates[item.id] > item.sub_budget_micros for item in self.deployments
        ):
            raise RuntimeError("preflight_budget_exceeded")
        survivors = self.run_critical()
        for deployment in self.deployments:
            for task in TASK_CONTRACTS:
                if (deployment.id, task) not in survivors:
                    continue
                for case in cases_for_round(task, "quality"):
                    self._run_case(deployment, case, "quality", 1)
                for case in cases_for_round(task, "economic"):
                    record = self._run_case(deployment, case, "economic", 1)
                    if record.result.critically_failed:
                        survivors.discard((deployment.id, task))
                        break
        for deployment in self.deployments:
            for task in TASK_CONTRACTS:
                if (deployment.id, task) not in survivors:
                    continue
                for repetition in (2, 3):
                    for case in cases_for_round(task, "critical"):
                        record = self._run_case(deployment, case, "consistency", repetition)
                        if record.result.critically_failed:
                            survivors.discard((deployment.id, task))
                            break
                    if (deployment.id, task) not in survivors:
                        break
        return self.summaries()

    def run_critical(self) -> set[tuple[UUID, TaskClass]]:
        survivors: set[tuple[UUID, TaskClass]] = {
            (deployment.id, task) for deployment in self.deployments for task in TASK_CONTRACTS
        }
        for deployment in self.deployments:
            for task in TASK_CONTRACTS:
                key = (deployment.id, task)
                for case in cases_for_round(task, "critical"):
                    record = self._run_case(deployment, case, "critical", 1)
                    if record.result.critically_failed:
                        survivors.discard(key)
                        break
        return survivors

    def _run_case(
        self,
        deployment: DeploymentSpec,
        case: EvaluationCase,
        round_name: str,
        repetition: int,
    ) -> TournamentRecord:
        request = self._request(deployment, case, repetition)
        estimated = deployment.pricing.cost_micros(1_500, MAX_OUTPUT_TOKENS, 0)
        if not self.budget.authorize(deployment, estimated):
            raise RuntimeError("tournament_budget_reservation_denied")
        adapter = self.adapters[deployment.id]
        invocation = adapter.invoke_with_receipt(request, 1)  # type: ignore[attr-defined]
        if invocation.response.failure_code in {
            "transient_failure",
            "rate_limited",
            "malformed_response",
        }:
            invocation = adapter.invoke_with_receipt(request, 2)  # type: ignore[attr-defined]
            attempts = 2
        else:
            attempts = 1
        self.budget.record(deployment, invocation.receipt.actual_cost_micros)
        result = evaluate_response(
            uuid5(NAMESPACE_URL, f"result:{deployment.id}:{case.id}:{repetition}"),
            request.workspace_id,
            request.evaluation_run_id,
            deployment.id,
            self._qualification_key(deployment, case),
            case,
            invocation.response,
            attempts,
            self._now(),
        )
        if invocation.response.failure_code:
            failure = (
                GateFailure.BUDGET_EXCEEDED
                if invocation.response.failure_code == "budget_exceeded"
                else GateFailure.SCHEMA_INVALID
                if invocation.response.failure_code == "malformed_response"
                else GateFailure.PROVIDER_FAILURE
            )
            result = CaseEvaluationResult(
                result.id,
                result.workspace_id,
                result.evaluation_run_id,
                result.case_id,
                result.deployment_id,
                result.qualification_key,
                result.metrics,
                (*result.gate_failures, failure),
                result.attempt_count,
                result.output_hash,
                result.created_at,
            )
        record = TournamentRecord(
            deployment.id,
            deployment.provider,
            deployment.model_id,
            deployment.config_hash,
            case.task_class,
            round_name,
            case.family,
            repetition,
            result,
            invocation.receipt,
        )
        self.records.append(record)
        return record

    def summaries(self) -> tuple[PairSummary, ...]:
        values: list[PairSummary] = []
        for deployment in self.deployments:
            for task in TASK_CONTRACTS:
                records = [
                    item
                    for item in self.records
                    if item.deployment_id == deployment.id and item.task_class == task
                ]
                hard = tuple(
                    sorted(
                        {
                            failure.value
                            for item in records
                            for failure in item.result.gate_failures
                            if failure in CRITICAL_GATES
                        }
                    )
                )
                noncritical = any(item.result.gate_failures for item in records)
                status = (
                    QualificationStatus.DISQUALIFIED
                    if hard
                    else QualificationStatus.CONDITIONAL
                    if noncritical
                    else QualificationStatus.QUALIFIED
                )
                latencies = sorted(item.receipt.latency_ms for item in records)
                successful = sum(
                    1
                    for item in records
                    if item.receipt.safe_failure_code is None and not item.result.critically_failed
                )
                costs = sum(item.receipt.actual_cost_micros for item in records)
                required_evidence = sum(item.result.metrics.evidence_required for item in records)
                matched_evidence = sum(item.result.metrics.evidence_matched for item in records)
                citation_pairs = sum(item.result.metrics.citation_pairs for item in records)
                valid_citations = sum(item.result.metrics.citation_valid for item in records)
                entailed_citations = sum(item.result.metrics.citation_entailed for item in records)
                required_unknowns = sum(item.result.metrics.unknowns_required for item in records)
                preserved_unknowns = sum(item.result.metrics.unknowns_preserved for item in records)
                required_contradictions = sum(
                    item.result.metrics.contradictions_required for item in records
                )
                recognized_contradictions = sum(
                    item.result.metrics.contradictions_recognized for item in records
                )
                injection_records = [
                    item
                    for item in records
                    if item.family in {"prompt_injection", "indirect_prompt_injection"}
                ]
                values.append(
                    PairSummary(
                        deployment.id,
                        deployment.provider,
                        deployment.model_id,
                        deployment.config_hash,
                        task,
                        status,
                        len({item.family for item in records}),
                        len(records),
                        hard,
                        sum(item.result.metrics.unsupported_claims for item in records),
                        self._ratio(
                            sum(item.result.metrics.unsupported_claims for item in records),
                            len(records),
                        ),
                        self._ratio(matched_evidence, required_evidence),
                        self._ratio(valid_citations, citation_pairs),
                        self._ratio(entailed_citations, citation_pairs),
                        self._ratio(preserved_unknowns, required_unknowns),
                        self._ratio(recognized_contradictions, required_contradictions),
                        self._ratio(
                            sum(
                                GateFailure.PROMPT_INJECTION_COMPLIANCE
                                not in item.result.gate_failures
                                for item in injection_records
                            ),
                            len(injection_records),
                        ),
                        self._ratio(
                            sum(item.result.metrics.schema_valid for item in records), len(records)
                        ),
                        self._ratio(
                            sum(item.result.attempt_count > 1 for item in records), len(records)
                        ),
                        self._ratio(
                            sum(
                                item.result.attempt_count > 1 and item.result.metrics.schema_valid
                                for item in records
                            ),
                            len(records),
                        ),
                        self._semantic_ratio(records),
                        "pending_human_rubric",
                        round(statistics.median(latencies)) if latencies else 0,
                        self._percentile(latencies, 0.95),
                        sum(item.receipt.input_tokens for item in records),
                        sum(item.receipt.output_tokens for item in records),
                        sum(item.receipt.reasoning_tokens for item in records),
                        costs,
                        costs // successful if successful else None,
                        costs // successful if successful else None,
                    )
                )
        return tuple(values)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> str:
        return f"{numerator / denominator:.4f}" if denominator else "0.0000"

    @classmethod
    def _semantic_ratio(cls, records: list[TournamentRecord]) -> str:
        repeated = [item for item in records if item.round_name in {"critical", "consistency"}]
        groups: dict[str, list[TournamentRecord]] = {}
        for item in repeated:
            groups.setdefault(item.family, []).append(item)
        stable = sum(
            1
            for items in groups.values()
            if len(items) >= 3
            and len(
                {
                    (
                        item.result.metrics.evidence_matched,
                        item.result.metrics.unknowns_preserved,
                        item.result.metrics.contradictions_recognized,
                        tuple(
                            failure.value
                            for failure in item.result.gate_failures
                            if failure in CRITICAL_GATES
                        ),
                    )
                    for item in items
                }
            )
            == 1
        )
        eligible = sum(1 for items in groups.values() if len(items) >= 3)
        return cls._ratio(stable, eligible)

    @staticmethod
    def _percentile(values: list[int], fraction: float) -> int:
        if not values:
            return 0
        return values[min(len(values) - 1, max(0, round((len(values) - 1) * fraction)))]

    @staticmethod
    def _qualification_key(deployment: DeploymentSpec, case: EvaluationCase):  # type: ignore[no-untyped-def]
        from opintel_qualification.domain import QualificationKey

        return QualificationKey(
            deployment.id,
            deployment.deployment_version,
            deployment.config_hash,
            case.task_class,
            case.task_version,
            SCHEMA_VERSION,
            POLICY_VERSION,
            case.corpus_version,
            DataClassification.PUBLIC,
        )

    @staticmethod
    def _request(
        deployment: DeploymentSpec, case: EvaluationCase, repetition: int
    ) -> IntelligenceRequest:
        workspace = uuid5(NAMESPACE_URL, "opintel:m2.6:workspace")
        run = uuid5(NAMESPACE_URL, f"opintel:m2.6:run:{deployment.id}")
        prompt_hash = hashlib.sha256(
            json.dumps(
                {"case": case.manifest_hash, "task": case.task_class.value, "rep": repetition},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return IntelligenceRequest(
            uuid5(NAMESPACE_URL, f"request:{deployment.id}:{case.id}:{repetition}"),
            workspace,
            run,
            case.id,
            TASK_CONTRACTS[case.task_class],
            RoutingStage.EVALUATION_ONLY,
            case.evidence,
            tuple(item.id for item in case.evidence),
            POLICY_VERSION,
            case.corpus_version,
            DataClassification.PUBLIC,
            prompt_hash,
            deployment.config_hash,
            MAX_OUTPUT_TOKENS,
            deployment.pricing.cost_micros(1_500, MAX_OUTPUT_TOKENS, 0),
            uuid5(NAMESPACE_URL, f"trace:{deployment.id}:{case.id}:{repetition}"),
            tuple(item.label for item in case.required_claims),
            case.protected_unknowns,
            case.hard_contradictions,
            case.acceptable_alternatives,
        )


def safe_report(runner: TournamentRunner, summaries: tuple[PairSummary, ...]) -> dict[str, object]:
    return {
        "schema_version": "m2_6.tournament_report@1",
        "generated_at": datetime.now(UTC).isoformat(),
        "authority": "evaluation_only_non_authoritative",
        "synthetic_only": True,
        "budget_limit_micros": runner.budget.total_limit,
        "actual_cost_micros": runner.budget.total_spent,
        "deployment_costs_micros": {
            str(key): value for key, value in runner.budget.deployment_spent.items()
        },
        "summaries": [asdict(item) for item in summaries],
        "records": [asdict(item) for item in runner.records],
    }
