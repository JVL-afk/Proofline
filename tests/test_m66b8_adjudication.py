from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from opintel_qualification.tournament2_adjudication import (
    AdjudicationTrigger,
    select_adjudication_cases,
    trigger_counts,
)


def _response(
    case_id: str,
    *,
    preference: str = "A",
    usefulness: int = 3,
    trustworthiness: int = 3,
    defect: str = "NO",
) -> dict[str, Any]:
    dimensions = {
        "clarity": 3,
        "naturalness": 3,
        "concision": 3,
        "usefulness": usefulness,
        "relevance": 3,
        "trustworthiness": trustworthiness,
    }
    return {
        "case_id": case_id,
        "task_id": "audit_wording",
        "ratings": {"version_a": dimensions, "version_b": dict(dimensions)},
        "paired_preference": preference,
        "material_defect": defect,
    }


def _locks(responses: tuple[dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    return {
        reviewer_id: {"responses": [response]}
        for reviewer_id, response in zip(
            ("PRIMARY_A", "PRIMARY_B", "PRIMARY_C"), responses, strict=True
        )
    }


def test_frozen_preference_and_variance_triggers_are_task_local() -> None:
    case_id = "case-1"
    responses = (
        _response(case_id, preference="A", usefulness=1),
        _response(case_id, preference="B", usefulness=4),
        _response(case_id, preference="TIE", usefulness=2),
    )
    selected = select_adjudication_cases(_locks(responses), (("audit_wording", case_id),))
    assert selected[0].triggers == (
        AdjudicationTrigger.PREFERENCE_SPLIT,
        AdjudicationTrigger.USEFULNESS_HIGH_VARIANCE,
    )


def test_one_preference_and_two_ties_requires_adjudication() -> None:
    case_id = "case-2"
    responses = tuple(_response(case_id, preference=value) for value in ("A", "TIE", "TIE"))
    selected = select_adjudication_cases(_locks(responses), (("audit_wording", case_id),))
    assert selected[0].triggers == (AdjudicationTrigger.PREFERENCE_SPLIT,)


def test_majority_preference_without_other_trigger_is_not_adjudicated() -> None:
    case_id = "case-3"
    responses = tuple(_response(case_id, preference=value) for value in ("A", "A", "B"))
    assert not select_adjudication_cases(_locks(responses), (("audit_wording", case_id),))


def test_any_potential_material_defect_is_preserved_and_deduplicated() -> None:
    case_id = "case-4"
    responses = (
        _response(case_id, defect="YES"),
        _response(case_id),
        _response(case_id, defect="YES"),
    )
    selected = select_adjudication_cases(_locks(responses), (("audit_wording", case_id),))
    assert len(selected) == 1
    assert trigger_counts(selected)["MATERIAL_DEFECT_REPORTED"] == 1


def test_confirmed_semantic_conflict_is_adjudicated_and_policy_blocked() -> None:
    case_id = "51ee87af09907a072639e7b6"
    response = _response(case_id)
    selected = select_adjudication_cases(
        _locks((response, deepcopy(response), deepcopy(response))),
        (("outreach_wording", case_id),),
    )
    assert AdjudicationTrigger.MECHANICALLY_CONFIRMED_SEMANTIC_CONFLICT in selected[0].triggers
    assert AdjudicationTrigger.POLICY_ADJUDICATION_REQUIRED in selected[0].triggers


def test_missing_primary_lock_fails_closed() -> None:
    with pytest.raises(ValueError, match="three frozen"):
        select_adjudication_cases({}, ())
