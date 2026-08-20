"""Frozen M6.6B-9 scoring, unblinding, and no-route closure contracts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import median
from typing import Any, cast

from opintel_qualification.tournament2_adjudication import CONFIRMED_CONFLICT_CASE_ID
from opintel_qualification.tournament2_domain import (
    PostTournamentState,
    RecommendationDisposition,
    TournamentTask,
)
from opintel_qualification.tournament2_prefreeze import REVIEWER_POLICY
from opintel_qualification.tournament2_review_release import ASSIGNMENT_FILE_SHA256

FINAL_REPORT_SCHEMA_VERSION = "m6.6b9.final-tournament-report@1"
UNBLINDING_POLICY_VERSION = "m6.6b9.locked-inputs-before-identity@1"
RENDERED_CTA_GAP_CODE = "RENDERED_CTA_SEMANTIC_CONSISTENCY_GAP"
UNBLINDED_AT = "2026-08-20T13:53:12Z"

PRIMARY_LOCK_HASHES = {
    "PRIMARY_A": "f462cfb9510f2c1c25be2f5f5bd445483d155469c0d80da6231ba4122ee21337",
    "PRIMARY_B": "e37102a10e08ec109b2cc6be0e09bbbe0f335b5b4ac2e78ced30755edeea01b8",
    "PRIMARY_C": "8890b612ccdf77a28208a99ad04e3d13c18184d01d7f9d5337e68ba9f8ecc449",
}
ADJUDICATOR_LOCK_HASH = "ea31c0efa7a4d6d87845ba9e4ec58e5045c01c36a1dbdad95adc2effd9aa6120"
ADJUDICATOR_WORKBOOK_HASH = "f2081368dbe23ee5bc1035475da8a103a1bbd2d462e418cce561f317da45e2d4"
ORIGINAL_RUN_COST_MICROS = 1_145_397
RECOVERY_RUN_COST_MICROS = 597_460
ORIGINAL_RUN_CALLS = 194
RECOVERY_RUN_CALLS = 105

SURVIVING_TASKS = (
    TournamentTask.EVIDENCE_INTERPRETATION,
    TournamentTask.CONTRADICTION_ANALYSIS,
    TournamentTask.OPPORTUNITY_REASONING,
    TournamentTask.AUDIT_WORDING,
    TournamentTask.OUTREACH_WORDING,
)
REASONING_TASKS = SURVIVING_TASKS[:3]
SUBSTANTIVE_IMPROVEMENT_TASKS = frozenset(
    {TournamentTask.AUDIT_WORDING, TournamentTask.OUTREACH_WORDING}
)

REVIEWER_SLOTS = {
    "PRIMARY_A": "PRIMARY_REVIEWER_SLOT_1",
    "PRIMARY_B": "PRIMARY_REVIEWER_SLOT_2",
    "PRIMARY_C": "PRIMARY_REVIEWER_SLOT_3",
    "ADJUDICATOR_D": "CONDITIONAL_ADJUDICATOR_SLOT",
}

MACHINE_DISQUALIFICATIONS = (
    ("openai-gpt-5.6-sol", TournamentTask.EVIDENCE_INTERPRETATION),
    ("openai-gpt-5.6-sol", TournamentTask.CONTRADICTION_ANALYSIS),
    ("openai-gpt-5.6-sol", TournamentTask.OPPORTUNITY_REASONING),
    ("google-gemini-3.6-flash", TournamentTask.AUDIT_WORDING),
    ("google-gemini-3.6-flash", TournamentTask.OUTREACH_WORDING),
    ("google-gemini-3.5-flash-lite", TournamentTask.REPLY_CLASSIFICATION),
    ("google-gemini-3.5-flash-lite", TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION),
)


class UnblindedPreference(StrEnum):
    CANDIDATE = "candidate"
    DETERMINISTIC = "deterministic"
    TIE = "tie"


class ShadowEligibility(StrEnum):
    NO_AI_SHADOW_CANDIDATE = "no_ai_shadow_candidate"
    AI_SHADOW_CANDIDATE = "ai_shadow_candidate"
    BLOCKED_PENDING_VALIDATOR_FIX = "blocked_pending_validator_fix"


@dataclass(frozen=True, slots=True)
class CountDistribution:
    candidate: int
    deterministic: int
    tie: int

    @property
    def total(self) -> int:
        return self.candidate + self.deterministic + self.tie


@dataclass(frozen=True, slots=True)
class DifferenceDistribution:
    counts: tuple[tuple[int, int], ...]

    @property
    def total(self) -> int:
        return sum(count for _, count in self.counts)

    @property
    def median(self) -> float:
        values = [value for value, count in self.counts for _ in range(count)]
        return float(median(values))


@dataclass(frozen=True, slots=True)
class MaterialGainChecks:
    automated_safety_survived: bool
    reviewer_preference_threshold: bool
    usefulness_improvement: bool
    no_trustworthiness_regression: bool
    improvement_across_multiple_cases: bool
    more_than_superficial_style: bool
    no_unresolved_material_defect: bool
    cost_latency_within_frozen_envelope: bool

    @property
    def all_passed(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True, slots=True)
class HumanTaskResult:
    task: TournamentTask
    comparison_cases: int
    identical_cases: int
    primary_preferences: CountDistribution
    adjudication_count: int
    final_preferences: CountDistribution
    usefulness_differences: DifferenceDistribution
    trustworthiness_differences: DifferenceDistribution
    resolved_material_defects: int
    mechanically_confirmed_semantic_defects: int
    original_cost_micros: int
    recovery_cost_micros: int
    material_gain_checks: MaterialGainChecks
    disposition: RecommendationDisposition
    post_tournament_state: PostTournamentState
    shadow_eligibility: ShadowEligibility
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BindingResult:
    deployment_key: str
    task: TournamentTask
    disposition: RecommendationDisposition
    post_tournament_state: PostTournamentState
    shadow_eligibility: ShadowEligibility


@dataclass(frozen=True, slots=True)
class UnblindingEvent:
    policy_version: str
    unblinded_at: str
    assignment_mapping_sha256: str
    locked_scoring_inputs_sha256: str
    event_sha256: str
    mapping: str


@dataclass(frozen=True, slots=True)
class FinalTournamentClosure:
    schema_version: str
    unblinding: UnblindingEvent
    human_task_results: tuple[HumanTaskResult, ...]
    binding_results: tuple[BindingResult, ...]
    original_calls: int
    recovery_calls: int
    original_cost_micros: int
    recovery_cost_micros: int
    route_activation_count: int
    canonical_mutation_count: int
    m66_complete: bool
    m67_started: bool


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _distribution(values: Sequence[UnblindedPreference]) -> CountDistribution:
    counts = Counter(values)
    return CountDistribution(
        counts[UnblindedPreference.CANDIDATE],
        counts[UnblindedPreference.DETERMINISTIC],
        counts[UnblindedPreference.TIE],
    )


def _difference_distribution(values: Sequence[int]) -> DifferenceDistribution:
    counts = Counter(values)
    return DifferenceDistribution(tuple(sorted(counts.items())))


def _candidate_side(
    assignments: Mapping[tuple[str, str], str], reviewer_id: str, case_id: str
) -> str:
    try:
        side = assignments[(REVIEWER_SLOTS[reviewer_id], case_id)]
    except KeyError as error:
        raise ValueError(f"missing frozen assignment:{reviewer_id}:{case_id}") from error
    if side not in {"VERSION A", "VERSION B"}:
        raise ValueError(f"invalid frozen assignment:{reviewer_id}:{case_id}")
    return side


def _unblind_response(
    response: Mapping[str, Any], candidate_side: str
) -> tuple[UnblindedPreference, int, int]:
    paired = str(response["paired_preference"])
    if paired == "TIE":
        preference = UnblindedPreference.TIE
    elif f"VERSION {paired}" == candidate_side:
        preference = UnblindedPreference.CANDIDATE
    else:
        preference = UnblindedPreference.DETERMINISTIC
    candidate_key = "version_a" if candidate_side == "VERSION A" else "version_b"
    deterministic_key = "version_b" if candidate_key == "version_a" else "version_a"
    ratings = response["ratings"]
    if not isinstance(ratings, Mapping):
        raise ValueError("review ratings must be a mapping")
    candidate = ratings[candidate_key]
    deterministic = ratings[deterministic_key]
    if not isinstance(candidate, Mapping) or not isinstance(deterministic, Mapping):
        raise ValueError("version ratings must be mappings")
    return (
        preference,
        int(candidate["usefulness"]) - int(deterministic["usefulness"]),
        int(candidate["trustworthiness"]) - int(deterministic["trustworthiness"]),
    )


def _majority(values: Sequence[UnblindedPreference]) -> UnblindedPreference:
    counts = Counter(values)
    highest = max(counts.values())
    winners = tuple(value for value, count in counts.items() if count == highest)
    return winners[0] if len(winners) == 1 else UnblindedPreference.TIE


def _human_result(
    task: TournamentTask,
    *,
    cases: Sequence[str],
    primary_responses: Mapping[str, Mapping[str, Mapping[str, Any]]],
    adjudicator_responses: Mapping[str, Mapping[str, Any]],
    assignments: Mapping[tuple[str, str], str],
    identical_cases: frozenset[str],
    original_cost_micros: int,
    recovery_cost_micros: int,
) -> HumanTaskResult:
    primary_values: list[UnblindedPreference] = []
    final_values: list[UnblindedPreference] = []
    usefulness: list[int] = []
    trustworthiness: list[int] = []
    resolved_defects: set[str] = set()

    for case_id in cases:
        case_primary: list[tuple[UnblindedPreference, int, int]] = []
        for reviewer_id in PRIMARY_LOCK_HASHES:
            response = primary_responses[reviewer_id][case_id]
            value = _unblind_response(response, _candidate_side(assignments, reviewer_id, case_id))
            case_primary.append(value)
            primary_values.append(value[0])

        if case_id in identical_cases:
            final_values.append(UnblindedPreference.TIE)
            usefulness.append(0)
            trustworthiness.append(0)
            continue

        adjudicator = adjudicator_responses.get(case_id)
        if adjudicator is not None:
            preference, usefulness_delta, trustworthiness_delta = _unblind_response(
                adjudicator, _candidate_side(assignments, "ADJUDICATOR_D", case_id)
            )
            if adjudicator["material_defect"] == "YES":
                resolved_defects.add(case_id)
        else:
            preference = _majority([item[0] for item in case_primary])
            usefulness_delta = int(median(item[1] for item in case_primary))
            trustworthiness_delta = int(median(item[2] for item in case_primary))
        final_values.append(preference)
        usefulness.append(usefulness_delta)
        trustworthiness.append(trustworthiness_delta)

    mechanical_defects = int(CONFIRMED_CONFLICT_CASE_ID in cases)
    if mechanical_defects:
        resolved_defects.add(CONFIRMED_CONFLICT_CASE_ID)

    primary_distribution = _distribution(primary_values)
    final_distribution = _distribution(final_values)
    usefulness_distribution = _difference_distribution(usefulness)
    trustworthiness_distribution = _difference_distribution(trustworthiness)
    checks = MaterialGainChecks(
        automated_safety_survived=True,
        reviewer_preference_threshold=(
            final_distribution.candidate >= REVIEWER_POLICY.minimum_candidate_preferences
        ),
        usefulness_improvement=(
            usefulness_distribution.median >= REVIEWER_POLICY.minimum_median_usefulness_delta
        ),
        no_trustworthiness_regression=(
            trustworthiness_distribution.median
            >= REVIEWER_POLICY.minimum_median_trustworthiness_delta
        ),
        improvement_across_multiple_cases=final_distribution.candidate > 1,
        more_than_superficial_style=task in SUBSTANTIVE_IMPROVEMENT_TASKS,
        no_unresolved_material_defect=(
            len(resolved_defects) <= REVIEWER_POLICY.material_defects_allowed
        ),
        cost_latency_within_frozen_envelope=True,
    )

    if resolved_defects:
        disposition = RecommendationDisposition.CONDITIONAL
        post_state = PostTournamentState.NO_ROUTE
        shadow = ShadowEligibility.BLOCKED_PENDING_VALIDATOR_FIX
        reason_code_set = {"RESOLVED_MATERIAL_DEFECT"}
        if mechanical_defects:
            reason_code_set.add(RENDERED_CTA_GAP_CODE)
        reason_codes = tuple(sorted(reason_code_set))
    elif len(identical_cases.intersection(cases)) == len(cases):
        disposition = RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
        post_state = PostTournamentState.NO_ROUTE
        shadow = ShadowEligibility.NO_AI_SHADOW_CANDIDATE
        reason_codes = ("NO_EVIDENCE_OF_MATERIAL_GAIN",)
    else:
        if checks.all_passed:
            disposition = RecommendationDisposition.QUALIFIED_WITH_MATERIAL_GAIN
            post_state = PostTournamentState.SHADOW_CANDIDATE
            shadow = ShadowEligibility.AI_SHADOW_CANDIDATE
            reason_codes = ("FROZEN_MATERIAL_GAIN_RULE_SATISFIED",)
        else:
            disposition = RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
            post_state = PostTournamentState.NO_ROUTE
            shadow = ShadowEligibility.NO_AI_SHADOW_CANDIDATE
            reason_codes = ("FROZEN_MATERIAL_GAIN_RULE_NOT_SATISFIED",)

    return HumanTaskResult(
        task,
        len(cases),
        len(identical_cases.intersection(cases)),
        primary_distribution,
        sum(case_id in adjudicator_responses for case_id in cases),
        final_distribution,
        usefulness_distribution,
        trustworthiness_distribution,
        len(resolved_defects),
        mechanical_defects,
        original_cost_micros,
        recovery_cost_micros,
        checks,
        disposition,
        post_state,
        shadow,
        reason_codes,
    )


def build_final_closure(
    *,
    primary_locks: Mapping[str, Mapping[str, Any]],
    adjudicator_lock: Mapping[str, Any],
    assignment_rows: Sequence[Mapping[str, Any]],
    rendered_rows: Sequence[Mapping[str, Any]],
    original_receipts: Sequence[Mapping[str, Any]],
    recovery_receipts: Sequence[Mapping[str, Any]],
) -> FinalTournamentClosure:
    """Score exact locked records and reveal identity only through the frozen mapping."""
    if set(primary_locks) != set(PRIMARY_LOCK_HASHES):
        raise ValueError("exactly three frozen primary locks are required")
    if adjudicator_lock.get("state") != "LOCKED_ADJUDICATION_REVIEW":
        raise ValueError("locked adjudication review is required")
    if adjudicator_lock.get("workbook_sha256") != ADJUDICATOR_WORKBOOK_HASH:
        raise ValueError("adjudicator workbook lineage changed")
    if len(assignment_rows) != 420 or len(rendered_rows) != 105:
        raise ValueError("frozen assignment/rendered-output corpus changed")

    locked_scoring_inputs = {
        "primary_lock_sha256": PRIMARY_LOCK_HASHES,
        "adjudicator_lock_sha256": ADJUDICATOR_LOCK_HASH,
        "adjudicator_workbook_sha256": ADJUDICATOR_WORKBOOK_HASH,
    }
    locked_scoring_inputs_sha256 = stable_hash(locked_scoring_inputs)
    event_payload = {
        "policy_version": UNBLINDING_POLICY_VERSION,
        "unblinded_at": UNBLINDED_AT,
        "assignment_mapping_sha256": ASSIGNMENT_FILE_SHA256,
        "locked_scoring_inputs_sha256": locked_scoring_inputs_sha256,
        "mapping": "VERSION A/B -> deterministic baseline / Claude Sonnet 5 per sealed assignment",
    }
    unblinding = UnblindingEvent(
        **event_payload,
        event_sha256=stable_hash(event_payload),
    )

    assignments = {
        (str(row["reviewer_slot"]), str(row["anonymous_case_id"])): str(row["candidate_side"])
        for row in assignment_rows
    }
    rendered_by_task: dict[TournamentTask, list[str]] = {task: [] for task in SURVIVING_TASKS}
    identical: set[str] = set()
    for row in rendered_rows:
        task = TournamentTask(str(row["task"]))
        case_id = str(row["anonymous_case_id"])
        rendered_by_task[task].append(case_id)
        if row["candidate_rendered_text"] == row["deterministic_rendered_text"]:
            identical.add(case_id)

    primary_responses = {
        reviewer_id: {str(item["case_id"]): item for item in lock["responses"]}
        for reviewer_id, lock in primary_locks.items()
    }
    adjudicator_responses = {str(item["case_id"]): item for item in adjudicator_lock["responses"]}

    def receipt_cost(receipts: Sequence[Mapping[str, Any]], task: TournamentTask) -> int:
        return sum(
            int(receipt["actual_cost_micros"])
            for receipt in receipts
            if receipt["task"] == task.value
            and (
                "deployment_key" not in receipt
                or receipt["deployment_key"] == "anthropic-claude-sonnet-5"
            )
        )

    human_results = tuple(
        _human_result(
            task,
            cases=rendered_by_task[task],
            primary_responses=primary_responses,
            adjudicator_responses=adjudicator_responses,
            assignments=assignments,
            identical_cases=frozenset(identical),
            original_cost_micros=receipt_cost(original_receipts, task),
            recovery_cost_micros=receipt_cost(recovery_receipts, task),
        )
        for task in SURVIVING_TASKS
    )
    binding_results = tuple(
        BindingResult(
            deployment,
            task,
            RecommendationDisposition.DISQUALIFIED,
            PostTournamentState.NO_ROUTE,
            ShadowEligibility.NO_AI_SHADOW_CANDIDATE,
        )
        for deployment, task in MACHINE_DISQUALIFICATIONS
    ) + tuple(
        BindingResult(
            "anthropic-claude-sonnet-5",
            result.task,
            result.disposition,
            result.post_tournament_state,
            result.shadow_eligibility,
        )
        for result in human_results
    )
    closure = FinalTournamentClosure(
        FINAL_REPORT_SCHEMA_VERSION,
        unblinding,
        human_results,
        binding_results,
        ORIGINAL_RUN_CALLS,
        RECOVERY_RUN_CALLS,
        ORIGINAL_RUN_COST_MICROS,
        RECOVERY_RUN_COST_MICROS,
        0,
        0,
        True,
        False,
    )
    return validate_final_closure(closure)


def validate_final_closure(value: FinalTournamentClosure) -> FinalTournamentClosure:
    if len(value.binding_results) != 12 or len(value.human_task_results) != 5:
        raise ValueError(
            "Tournament II closure requires exactly twelve bindings and five survivors"
        )
    if value.route_activation_count or value.canonical_mutation_count or value.m67_started:
        raise ValueError(
            "Tournament II closure cannot activate routes, mutate truth, or begin M6.7"
        )
    if not value.m66_complete:
        raise ValueError("final closure must mark M6.6 complete")
    if value.original_calls != 194 or value.recovery_calls != 105:
        raise ValueError("immutable provider call counts changed")
    if value.original_cost_micros != 1_145_397 or value.recovery_cost_micros != 597_460:
        raise ValueError("immutable provider spend changed")
    if any(result.comparison_cases != 21 for result in value.human_task_results):
        raise ValueError("each human-review task requires exactly 21 comparisons")
    reasoning = tuple(
        result for result in value.human_task_results if result.task in REASONING_TASKS
    )
    if any(
        result.identical_cases != 21
        or result.disposition is not RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
        or result.post_tournament_state is not PostTournamentState.NO_ROUTE
        for result in reasoning
    ):
        raise ValueError("byte-identical reasoning tasks must remain safe/no-gain/no-route")
    audit = next(
        result for result in value.human_task_results if result.task is TournamentTask.AUDIT_WORDING
    )
    outreach = next(
        result
        for result in value.human_task_results
        if result.task is TournamentTask.OUTREACH_WORDING
    )
    if audit.resolved_material_defects != 1 or audit.disposition is not (
        RecommendationDisposition.CONDITIONAL
    ):
        raise ValueError("audit wording must preserve its adjudicated material defect")
    if (
        outreach.resolved_material_defects != 2
        or outreach.mechanically_confirmed_semantic_defects != 1
        or outreach.disposition is not RecommendationDisposition.CONDITIONAL
        or RENDERED_CTA_GAP_CODE not in outreach.reason_codes
    ):
        raise ValueError("outreach wording must preserve both defects and the validator gap")
    if any(
        result.post_tournament_state not in {PostTournamentState.NO_ROUTE}
        for result in value.human_task_results
    ):
        raise ValueError("no surviving Tournament II binding may activate or enter a route")
    return value


def closure_as_dict(value: FinalTournamentClosure) -> dict[str, object]:
    """Create the canonical JSON-compatible report representation."""
    return cast(
        dict[str, object],
        json.loads(json.dumps(asdict(validate_final_closure(value)), default=str)),
    )
