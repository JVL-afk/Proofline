"""Fixture-only M6.6A runner with bounded retries and no live execution type."""

from __future__ import annotations

from dataclasses import dataclass

from opintel_qualification.tournament2_budget import (
    FixturePricing,
    Reservation,
    TournamentBudgetLedger,
    conservative_preflight_cost,
)
from opintel_qualification.tournament2_candidate import freeze_candidate
from opintel_qualification.tournament2_domain import (
    CandidateIntake,
    CandidateKind,
    EvaluationResult,
    IntakeState,
    TaskProjection,
    UsageLedgerEntry,
)
from opintel_qualification.tournament2_evaluator import evaluate_artifact
from opintel_qualification.tournament2_provider import DeterministicTournamentProvider


@dataclass(frozen=True, slots=True)
class FixtureExecutionResult:
    evaluations: tuple[EvaluationResult, ...]
    attempts: int


class Tournament2FixtureRunner:
    """A deliberately fake-only runner. M6.6B must introduce a different boundary."""

    def __init__(self, budget: TournamentBudgetLedger, max_attempts: int = 2) -> None:
        if max_attempts < 1 or max_attempts > 2:
            raise ValueError("M6.6A retries are bounded to at most two attempts")
        self._budget = budget
        self._max_attempts = max_attempts

    def execute(
        self,
        candidate: CandidateIntake,
        provider: DeterministicTournamentProvider,
        projection: TaskProjection,
        pricing: FixturePricing | None,
        *,
        stage: str = "safety",
    ) -> FixtureExecutionResult:
        if candidate.state is not IntakeState.FROZEN:
            raise ValueError("candidate intake must be frozen")
        if candidate.kind is not CandidateKind.DETERMINISTIC_FAKE:
            raise ValueError("M6.6A cannot execute a live candidate")
        if not provider.is_fixture_provider:
            raise ValueError("M6.6A requires a fixture provider")
        if projection.task not in candidate.supported_tasks:
            raise ValueError("candidate does not support the task")
        if pricing is not None and (
            candidate.pricing_version != pricing.version
            or provider.pricing_version != pricing.version
        ):
            raise ValueError("fixture pricing version does not match frozen candidate")
        reserved = conservative_preflight_cost(pricing, 256, 128)
        results: list[EvaluationResult] = []
        for attempt in range(1, self._max_attempts + 1):
            reservation_id = f"{candidate.id}:{projection.id}:{attempt}"
            self._budget.reserve(
                Reservation(
                    id=reservation_id,
                    provider_key=candidate.provider_key,
                    deployment_key=candidate.deployment_key,
                    task=projection.task,
                    stage=stage,
                    amount_micros=reserved,
                )
            )
            receipt = provider.invoke(projection)
            result = evaluate_artifact(projection, receipt.artifact)
            results.append(result)
            self._budget.reconcile(
                reservation_id,
                UsageLedgerEntry(
                    candidate_id=candidate.id,
                    task=projection.task,
                    stage=stage,
                    case_id=projection.case_id,
                    attempt=attempt,
                    input_tokens=receipt.input_tokens,
                    output_tokens=receipt.output_tokens,
                    latency_ms=receipt.latency_ms,
                    reserved_cost_micros=reserved,
                    actual_cost_micros=receipt.actual_cost_micros,
                    pricing_version=receipt.pricing_version,
                    validation_outcome="passed" if result.safety_passed else "failed",
                ),
            )
            retryable = receipt.artifact.provider_failure in {"timeout", "transient_failure"} or (
                not receipt.artifact.schema_valid
            )
            if not retryable:
                break
        return FixtureExecutionResult(tuple(results), len(results))


def assert_candidate_can_freeze(candidate: CandidateIntake) -> CandidateIntake:
    """Small public workflow hook used by deterministic contract tests."""
    return freeze_candidate(candidate)
