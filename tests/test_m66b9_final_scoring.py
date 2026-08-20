from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from opintel_qualification.tournament2_adjudication import CONFIRMED_CONFLICT_CASE_ID
from opintel_qualification.tournament2_domain import (
    PostTournamentState,
    RecommendationDisposition,
    TournamentTask,
)
from opintel_qualification.tournament2_final_scoring import (
    ADJUDICATOR_WORKBOOK_HASH,
    ShadowEligibility,
    build_final_closure,
    validate_final_closure,
)

ROOT = Path(__file__).resolve().parents[1]


def _response(
    case_id: str, task: TournamentTask, *, preference: str, defect: str = "NO"
) -> dict[str, Any]:
    baseline = {
        "clarity": 3,
        "naturalness": 3,
        "concision": 3,
        "usefulness": 3,
        "relevance": 3,
        "trustworthiness": 3,
    }
    candidate = dict(baseline)
    if preference != "TIE":
        candidate["usefulness"] = 5
        candidate["trustworthiness"] = 5
    return {
        "case_id": case_id,
        "task_id": task.value,
        "ratings": {"version_a": baseline, "version_b": candidate},
        "paired_preference": preference,
        "material_defect": defect,
    }


def _closure() -> Any:
    task_cases: dict[TournamentTask, list[str]] = {}
    for task in (
        TournamentTask.EVIDENCE_INTERPRETATION,
        TournamentTask.CONTRADICTION_ANALYSIS,
        TournamentTask.OPPORTUNITY_REASONING,
        TournamentTask.AUDIT_WORDING,
        TournamentTask.OUTREACH_WORDING,
    ):
        task_cases[task] = [f"{task.value}-{index:02d}" for index in range(21)]
    task_cases[TournamentTask.OUTREACH_WORDING][0] = CONFIRMED_CONFLICT_CASE_ID

    slots = (
        "PRIMARY_REVIEWER_SLOT_1",
        "PRIMARY_REVIEWER_SLOT_2",
        "PRIMARY_REVIEWER_SLOT_3",
        "CONDITIONAL_ADJUDICATOR_SLOT",
    )
    assignments = [
        {
            "reviewer_slot": slot,
            "anonymous_case_id": case_id,
            "candidate_side": "VERSION B",
        }
        for slot in slots
        for cases in task_cases.values()
        for case_id in cases
    ]
    rendered = []
    for task, cases in task_cases.items():
        for index, case_id in enumerate(cases):
            identical = task in {
                TournamentTask.EVIDENCE_INTERPRETATION,
                TournamentTask.CONTRADICTION_ANALYSIS,
                TournamentTask.OPPORTUNITY_REASONING,
            } or (task is TournamentTask.AUDIT_WORDING and index == 20)
            rendered.append(
                {
                    "task": task.value,
                    "anonymous_case_id": case_id,
                    "deterministic_rendered_text": "same",
                    "candidate_rendered_text": "same" if identical else "improved",
                }
            )

    primary_locks: dict[str, dict[str, Any]] = {}
    for reviewer_id in ("PRIMARY_A", "PRIMARY_B", "PRIMARY_C"):
        primary_locks[reviewer_id] = {
            "responses": [
                _response(
                    case_id,
                    task,
                    preference="TIE"
                    if task
                    in {
                        TournamentTask.EVIDENCE_INTERPRETATION,
                        TournamentTask.CONTRADICTION_ANALYSIS,
                        TournamentTask.OPPORTUNITY_REASONING,
                    }
                    else "B",
                )
                for task, cases in task_cases.items()
                for case_id in cases
            ]
        }
    audit_cases = task_cases[TournamentTask.AUDIT_WORDING][:-1]
    outreach_cases = task_cases[TournamentTask.OUTREACH_WORDING]
    adjudicator_responses = [
        _response(
            case_id,
            TournamentTask.AUDIT_WORDING,
            preference="B",
            defect="YES" if index == 0 else "NO",
        )
        for index, case_id in enumerate(audit_cases)
    ] + [
        _response(
            case_id,
            TournamentTask.OUTREACH_WORDING,
            preference="B",
            defect="YES" if index == 1 else "NO",
        )
        for index, case_id in enumerate(outreach_cases)
    ]
    receipts = [{"task": task.value, "actual_cost_micros": 1} for task in task_cases]
    return build_final_closure(
        primary_locks=primary_locks,
        adjudicator_lock={
            "state": "LOCKED_ADJUDICATION_REVIEW",
            "workbook_sha256": ADJUDICATOR_WORKBOOK_HASH,
            "responses": adjudicator_responses,
        },
        assignment_rows=assignments,
        rendered_rows=rendered,
        original_receipts=[
            {**receipt, "deployment_key": "anthropic-claude-sonnet-5"} for receipt in receipts
        ],
        recovery_receipts=receipts,
    )


def test_final_scoring_preserves_ties_and_blocks_wording_defects() -> None:
    closure = _closure()
    reasoning = closure.human_task_results[:3]
    assert all(
        result.disposition is RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
        and result.identical_cases == 21
        and result.final_preferences.tie == 21
        for result in reasoning
    )
    audit, outreach = closure.human_task_results[3:]
    assert audit.disposition is RecommendationDisposition.CONDITIONAL
    assert audit.resolved_material_defects == 1
    assert not audit.material_gain_checks.no_unresolved_material_defect
    assert not audit.material_gain_checks.all_passed
    assert outreach.disposition is RecommendationDisposition.CONDITIONAL
    assert outreach.resolved_material_defects == 2
    assert outreach.shadow_eligibility is ShadowEligibility.BLOCKED_PENDING_VALIDATOR_FIX
    assert all(
        result.post_tournament_state is PostTournamentState.NO_ROUTE
        for result in closure.binding_results
    )


def test_final_closure_rejects_route_activation_or_m67_start() -> None:
    closure = _closure()
    with pytest.raises(ValueError, match="cannot activate"):
        validate_final_closure(replace(closure, route_activation_count=1))
    with pytest.raises(ValueError, match="cannot activate"):
        validate_final_closure(replace(closure, m67_started=True))


def test_tracked_report_has_task_results_not_a_universal_leaderboard() -> None:
    report = json.loads(
        (ROOT / "docs" / "evidence" / "m6.6b-9" / "final-report.json").read_text(encoding="utf-8")
    )
    assert len(report["binding_results"]) == 12
    assert len(report["human_task_results"]) == 5
    assert "leaderboard" not in report
    assert "universal_score" not in report
    assert report["route_activation_count"] == 0
    assert report["canonical_mutation_count"] == 0
