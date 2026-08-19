"""Task-level reporting with no universal model leaderboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from opintel_qualification.tournament2_domain import (
    FailureBlastRadius,
    PostTournamentState,
    RecommendationDisposition,
    TournamentTask,
)


@dataclass(frozen=True, slots=True)
class TaskReportRow:
    task: TournamentTask
    candidate_id: UUID
    deployment_key: str
    disposition: RecommendationDisposition
    post_tournament_state: PostTournamentState
    safety_passed: bool
    deterministic_preferred: bool
    hard_gate_codes: tuple[str, ...]
    human_score_distributions: tuple[dict[str, object], ...]
    paired_preferences: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_micros: int


@dataclass(frozen=True, slots=True)
class IncidentRow:
    task: TournamentTask
    candidate_id: UUID
    case_id: UUID
    gate_code: str
    blast_radius: FailureBlastRadius
    detail_code: str


@dataclass(frozen=True, slots=True)
class TournamentReport:
    run_id: UUID
    created_at: datetime
    specification_version: str
    corpus_version: str
    evaluator_version: str
    safety_policy_version: str
    data_policy_version: str
    budget_policy_version: str
    candidate_intake_hashes: tuple[str, ...]
    task_rows: tuple[TaskReportRow, ...]
    incidents: tuple[IncidentRow, ...]
    preflight_cost_micros: int
    actual_cost_micros: int
    deterministic_validation_passed: bool
    route_activation_count: int = 0
    canonical_mutation_count: int = 0


def validate_report(report: TournamentReport) -> TournamentReport:
    if report.route_activation_count != 0:
        raise ValueError("Tournament II reports cannot activate routes")
    if report.canonical_mutation_count != 0:
        raise ValueError("Tournament II reports cannot record canonical mutations")
    for row in report.task_rows:
        if row.disposition in {
            RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN,
            RecommendationDisposition.DETERMINISTIC_SUPERIOR,
        } and not (
            row.deterministic_preferred
            and row.post_tournament_state is PostTournamentState.NO_ROUTE
        ):
            raise ValueError("deterministic preference requires no-route state")
        if row.disposition is RecommendationDisposition.DISQUALIFIED and row.safety_passed:
            raise ValueError("disqualified row cannot claim a safety pass")
    return report
