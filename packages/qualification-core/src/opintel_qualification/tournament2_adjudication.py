"""Fail-closed M6.6B-8 primary-review adjudication selection contracts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from opintel_qualification.tournament2_review_release import (
    IMPORT_SCHEMA_VERSION,
    PACKAGE_SET_SHA256,
    assignment_manifest_hash,
    release_manifest_hash,
)

ADJUDICATOR_ID = "ADJUDICATOR_D"
ADJUDICATOR_SLOT = "CONDITIONAL_ADJUDICATOR_SLOT"
CONFIRMED_CONFLICT_CASE_ID = "51ee87af09907a072639e7b6"
ADJUDICATION_WORKBOOK_SCHEMA_VERSION = "m6.6b8.adjudication-review-workbook@1"
ADJUDICATION_IMPORT_SCHEMA_VERSION = "m6.6b8.locked-adjudication-review@1"

PRIMARY_LOCK_SHA256 = {
    "PRIMARY_A": "f462cfb9510f2c1c25be2f5f5bd445483d155469c0d80da6231ba4122ee21337",
    "PRIMARY_B": "e37102a10e08ec109b2cc6be0e09bbbe0f335b5b4ac2e78ced30755edeea01b8",
    "PRIMARY_C": "8890b612ccdf77a28208a99ad04e3d13c18184d01d7f9d5337e68ba9f8ecc449",
}


class AdjudicationTrigger(StrEnum):
    PREFERENCE_SPLIT = "PREFERENCE_SPLIT"
    USEFULNESS_HIGH_VARIANCE = "USEFULNESS_HIGH_VARIANCE"
    TRUSTWORTHINESS_HIGH_VARIANCE = "TRUSTWORTHINESS_HIGH_VARIANCE"
    MATERIAL_DEFECT_REPORTED = "MATERIAL_DEFECT_REPORTED"
    MECHANICALLY_CONFIRMED_SEMANTIC_CONFLICT = "MECHANICALLY_CONFIRMED_SEMANTIC_CONFLICT"
    POLICY_ADJUDICATION_REQUIRED = "POLICY_ADJUDICATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class SelectedAdjudicationCase:
    case_id: str
    task_id: str
    triggers: tuple[AdjudicationTrigger, ...]


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def validate_lock(
    lock: Mapping[str, Any],
    *,
    reviewer_id: str,
    lock_sha256: str,
    expected_packages: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if lock_sha256 != PRIMARY_LOCK_SHA256[reviewer_id]:
        raise ValueError(f"locked review hash mismatch:{reviewer_id}")
    if lock.get("schema_version") != IMPORT_SCHEMA_VERSION:
        raise ValueError(f"locked review schema mismatch:{reviewer_id}")
    if lock.get("state") != "LOCKED_PRIMARY_REVIEW" or lock.get("reviewer_id") != reviewer_id:
        raise ValueError(f"locked review identity/state mismatch:{reviewer_id}")
    if (
        lock.get("assignment_manifest_hash") != assignment_manifest_hash()
        or lock.get("release_manifest_hash") != release_manifest_hash()
        or lock.get("package_set_hash") != PACKAGE_SET_SHA256
    ):
        raise ValueError(f"locked review lineage mismatch:{reviewer_id}")
    try:
        timestamp = datetime.fromisoformat(str(lock["completion_timestamp"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as error:
        raise ValueError(f"locked review completion timestamp invalid:{reviewer_id}") from error
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError(f"locked review timestamp must be UTC:{reviewer_id}")
    responses = lock.get("responses")
    if not isinstance(responses, list) or len(responses) != 105:
        raise ValueError(f"locked review must contain 105 cases:{reviewer_id}")
    expected_by_id = {
        case["anonymous_case_id"]: (task_id, package["package_hash"])
        for task_id, package in expected_packages.items()
        for case in package["cases"]
    }
    if len(expected_by_id) != 105:
        raise ValueError(f"sealed source must contain 105 unique cases:{reviewer_id}")
    seen: set[str] = set()
    for response in responses:
        case_id = response.get("case_id")
        if case_id in seen or case_id not in expected_by_id:
            raise ValueError(f"duplicate or unknown locked case:{reviewer_id}:{case_id}")
        seen.add(case_id)
        task_id, package_hash = expected_by_id[case_id]
        if response.get("task_id") != task_id or response.get("package_hash") != package_hash:
            raise ValueError(f"locked case package lineage mismatch:{reviewer_id}:{case_id}")
    if seen != set(expected_by_id):
        raise ValueError(f"locked review case set incomplete:{reviewer_id}")
    return lock


def _preference_split(preferences: Sequence[str]) -> bool:
    counts = Counter(preferences)
    return set(preferences) == {"A", "B", "TIE"} or (
        counts["TIE"] == 2 and (counts["A"] == 1 or counts["B"] == 1)
    )


def _high_variance(responses: Sequence[Mapping[str, Any]], dimension: str) -> bool:
    for side in ("version_a", "version_b"):
        values = [int(response["ratings"][side][dimension]) for response in responses]
        if max(values) - min(values) >= 3:
            return True
    return False


def select_adjudication_cases(
    locks: Mapping[str, Mapping[str, Any]],
    case_order: Sequence[tuple[str, str]],
) -> tuple[SelectedAdjudicationCase, ...]:
    expected_reviewers = tuple(PRIMARY_LOCK_SHA256)
    if tuple(locks) != expected_reviewers:
        raise ValueError("exactly the three frozen primary locks are required")
    response_maps = {
        reviewer_id: {item["case_id"]: item for item in lock["responses"]}
        for reviewer_id, lock in locks.items()
    }
    result: list[SelectedAdjudicationCase] = []
    for task_id, case_id in case_order:
        responses = [response_maps[reviewer_id][case_id] for reviewer_id in expected_reviewers]
        triggers: list[AdjudicationTrigger] = []
        if _preference_split([str(item["paired_preference"]) for item in responses]):
            triggers.append(AdjudicationTrigger.PREFERENCE_SPLIT)
        if _high_variance(responses, "usefulness"):
            triggers.append(AdjudicationTrigger.USEFULNESS_HIGH_VARIANCE)
        if _high_variance(responses, "trustworthiness"):
            triggers.append(AdjudicationTrigger.TRUSTWORTHINESS_HIGH_VARIANCE)
        if any(item["material_defect"] == "YES" for item in responses):
            triggers.append(AdjudicationTrigger.MATERIAL_DEFECT_REPORTED)
        if case_id == CONFIRMED_CONFLICT_CASE_ID:
            triggers.extend(
                (
                    AdjudicationTrigger.MECHANICALLY_CONFIRMED_SEMANTIC_CONFLICT,
                    AdjudicationTrigger.POLICY_ADJUDICATION_REQUIRED,
                )
            )
        if triggers:
            result.append(SelectedAdjudicationCase(case_id, task_id, tuple(triggers)))
    if len({item.case_id for item in result}) != len(result):
        raise ValueError("adjudication cases must be unique")
    return tuple(result)


def trigger_counts(cases: Sequence[SelectedAdjudicationCase]) -> dict[str, int]:
    return {
        trigger.value: sum(trigger in item.triggers for item in cases)
        for trigger in AdjudicationTrigger
    }
