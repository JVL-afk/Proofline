from __future__ import annotations

import json
from pathlib import Path

from opintel_qualification.tournament2_machine_closure import (
    ORIGINAL_ARTIFACT_SHA256,
    ORIGINAL_MACHINE_CLOSURE,
    HumanUsefulnessState,
    MachineClosureState,
    closure_hash,
    validate_original_machine_closure,
)


def test_original_machine_run_closes_without_human_usefulness_or_route_authority() -> None:
    value = validate_original_machine_closure()
    assert value.calls_planned == 384
    assert (value.calls_attempted, value.calls_released, value.retries) == (194, 190, 0)
    assert value.actual_cost_micros == 1_145_397
    assert value.hard_cap_micros == 25_000_000
    assert value.qualified_bindings == value.route_activations == value.canonical_mutations == 0
    assert value.usable_human_review_packages == 0
    assert len(closure_hash()) == 64


def test_exact_five_survivors_are_explicitly_not_evaluable() -> None:
    survived = tuple(
        item
        for item in ORIGINAL_MACHINE_CLOSURE.outcomes
        if item.machine_state is MachineClosureState.AUTOMATED_SAFETY_PASS_HUMAN_REVIEW_UNAVAILABLE
    )
    assert len(survived) == 5
    assert all(
        item.human_usefulness_state is HumanUsefulnessState.NOT_EVALUABLE_FROM_RETAINED_ARTIFACTS
        for item in survived
    )


def test_tracked_summary_binds_ignored_artifact_without_raw_content() -> None:
    path = Path("docs/evidence/m6.6b-5/tournament-ii-machine-run-safe-summary.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["safe_artifact_sha256"] == ORIGINAL_ARTIFACT_SHA256
    assert value["review_retention"] == {
        "hash_only_package_markers": 5,
        "usable_human_review_packages": 0,
        "human_usefulness_state": "NOT_EVALUABLE_FROM_RETAINED_ARTIFACTS",
    }
    assert "receipts" not in value and "provider_bodies" not in value
