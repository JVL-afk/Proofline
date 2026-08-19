"""Immutable closure projection for the original Tournament II machine run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from opintel_qualification.tournament2_domain import TournamentTask

ORIGINAL_RUN_ID = "3b37a366-3957-5f8b-94da-c83dac6f323e"
ORIGINAL_MANIFEST_HASH = "f3695a274cdfbdba09a69d5143c15662057329c571f0dfda225819af9aa793ea"
ORIGINAL_ARTIFACT_SHA256 = "3673c1178e574d4f289e9b7642716d00e66204279dbd4ab8a67cda2d4599b490"


class MachineClosureState(StrEnum):
    DISQUALIFIED = "disqualified"
    AUTOMATED_SAFETY_PASS_HUMAN_REVIEW_UNAVAILABLE = (
        "automated_safety_pass_human_review_unavailable"
    )


class HumanUsefulnessState(StrEnum):
    NOT_APPLICABLE_DISQUALIFIED = "not_applicable_disqualified"
    NOT_EVALUABLE_FROM_RETAINED_ARTIFACTS = "not_evaluable_from_retained_artifacts"


@dataclass(frozen=True, slots=True)
class ClosedBindingOutcome:
    deployment_key: str
    task: TournamentTask
    machine_state: MachineClosureState
    human_usefulness_state: HumanUsefulnessState


@dataclass(frozen=True, slots=True)
class OriginalMachineRunClosure:
    version: str
    run_id: str
    manifest_hash: str
    safe_artifact_sha256: str
    calls_planned: int
    calls_attempted: int
    calls_released: int
    retries: int
    actual_cost_micros: int
    hard_cap_micros: int
    canonical_mutations: int
    route_activations: int
    qualified_bindings: int
    usable_human_review_packages: int
    hash_only_package_markers: int
    outcomes: tuple[ClosedBindingOutcome, ...]
    historical_evidence_rewritten: bool = False


def _outcome(
    deployment: str, task: TournamentTask, *, survived: bool = False
) -> ClosedBindingOutcome:
    return ClosedBindingOutcome(
        deployment,
        task,
        MachineClosureState.AUTOMATED_SAFETY_PASS_HUMAN_REVIEW_UNAVAILABLE
        if survived
        else MachineClosureState.DISQUALIFIED,
        HumanUsefulnessState.NOT_EVALUABLE_FROM_RETAINED_ARTIFACTS
        if survived
        else HumanUsefulnessState.NOT_APPLICABLE_DISQUALIFIED,
    )


ORIGINAL_MACHINE_CLOSURE = OriginalMachineRunClosure(
    "m6.6b5.original-machine-closure@1",
    ORIGINAL_RUN_ID,
    ORIGINAL_MANIFEST_HASH,
    ORIGINAL_ARTIFACT_SHA256,
    384,
    194,
    190,
    0,
    1_145_397,
    25_000_000,
    0,
    0,
    0,
    0,
    5,
    (
        _outcome("openai-gpt-5.6-sol", TournamentTask.EVIDENCE_INTERPRETATION),
        _outcome("openai-gpt-5.6-sol", TournamentTask.CONTRADICTION_ANALYSIS),
        _outcome("openai-gpt-5.6-sol", TournamentTask.OPPORTUNITY_REASONING),
        _outcome(
            "anthropic-claude-sonnet-5",
            TournamentTask.EVIDENCE_INTERPRETATION,
            survived=True,
        ),
        _outcome(
            "anthropic-claude-sonnet-5",
            TournamentTask.CONTRADICTION_ANALYSIS,
            survived=True,
        ),
        _outcome(
            "anthropic-claude-sonnet-5",
            TournamentTask.OPPORTUNITY_REASONING,
            survived=True,
        ),
        _outcome("anthropic-claude-sonnet-5", TournamentTask.AUDIT_WORDING, survived=True),
        _outcome("anthropic-claude-sonnet-5", TournamentTask.OUTREACH_WORDING, survived=True),
        _outcome("google-gemini-3.6-flash", TournamentTask.AUDIT_WORDING),
        _outcome("google-gemini-3.6-flash", TournamentTask.OUTREACH_WORDING),
        _outcome("google-gemini-3.5-flash-lite", TournamentTask.REPLY_CLASSIFICATION),
        _outcome(
            "google-gemini-3.5-flash-lite",
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
        ),
    ),
)


def closure_hash(value: OriginalMachineRunClosure = ORIGINAL_MACHINE_CLOSURE) -> str:
    return hashlib.sha256(
        json.dumps(asdict(value), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def validate_original_machine_closure(
    value: OriginalMachineRunClosure = ORIGINAL_MACHINE_CLOSURE,
) -> OriginalMachineRunClosure:
    if value.run_id != ORIGINAL_RUN_ID or value.manifest_hash != ORIGINAL_MANIFEST_HASH:
        raise ValueError("machine closure must bind the exact original run")
    if value.calls_attempted + value.calls_released != value.calls_planned:
        raise ValueError("attempted and released calls must equal the frozen plan")
    if value.retries or value.canonical_mutations or value.route_activations:
        raise ValueError("original run cannot claim retries, mutations, or routes")
    if value.qualified_bindings or value.usable_human_review_packages:
        raise ValueError("original run produced no qualified or human-reviewable binding")
    survived = tuple(
        item
        for item in value.outcomes
        if item.machine_state is MachineClosureState.AUTOMATED_SAFETY_PASS_HUMAN_REVIEW_UNAVAILABLE
    )
    if len(survived) != 5 or any(
        item.human_usefulness_state
        is not HumanUsefulnessState.NOT_EVALUABLE_FROM_RETAINED_ARTIFACTS
        for item in survived
    ):
        raise ValueError("exactly five bindings must remain safety-only and not evaluable")
    if value.historical_evidence_rewritten:
        raise ValueError("closure cannot rewrite original evidence")
    return value
