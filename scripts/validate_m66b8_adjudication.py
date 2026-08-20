"""Validate and lock the returned M6.6B-8 adjudicator workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from opintel_qualification.review_workbook_reader import cell as _cell
from opintel_qualification.review_workbook_reader import read_workbook
from opintel_qualification.tournament2_adjudication import (
    ADJUDICATION_IMPORT_SCHEMA_VERSION,
    ADJUDICATION_WORKBOOK_SCHEMA_VERSION,
    ADJUDICATOR_ID,
    stable_hash,
)

_TASK_SHEETS = {
    "evidence_interpretation": "Evidence Interpretation",
    "contradiction_analysis": "Contradiction Analysis",
    "opportunity_reasoning": "Opportunity Reasoning",
    "audit_wording": "Audit Wording",
    "outreach_wording": "Outreach Wording",
}
_HEADERS = (
    "Case ID",
    "Review Context",
    "VERSION A",
    "VERSION B",
    "A Clarity",
    "A Naturalness",
    "A Concision",
    "A Usefulness",
    "A Relevance",
    "A Trustworthiness",
    "B Clarity",
    "B Naturalness",
    "B Concision",
    "B Usefulness",
    "B Relevance",
    "B Trustworthiness",
    "Paired Preference",
    "Material Defect",
    "Material Defect Note",
)
_DIMENSIONS = (
    "clarity",
    "naturalness",
    "concision",
    "usefulness",
    "relevance",
    "trustworthiness",
)


def _validate_release_payload(payload: dict[str, Any]) -> dict[str, Any]:
    claimed_hash = payload.get("adjudicator_package_hash")
    unsigned = dict(payload)
    unsigned.pop("adjudicator_package_hash", None)
    if claimed_hash != stable_hash(unsigned):
        raise ValueError("adjudicator package hash mismatch")
    if (
        payload.get("workbook_schema_version") != ADJUDICATION_WORKBOOK_SCHEMA_VERSION
        or payload.get("reviewer_id") != ADJUDICATOR_ID
        or payload.get("completion_state") != "IN_PROGRESS"
    ):
        raise ValueError("adjudicator release identity/state mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != payload.get("case_count"):
        raise ValueError("adjudicator release case count mismatch")
    if len({item["anonymous_case_id"] for item in cases}) != len(cases):
        raise ValueError("adjudicator release contains duplicate cases")
    return payload


def _validate_frozen_workbook(
    workbook: Path, release_path: Path
) -> tuple[dict[str, Any], dict[str, dict[int, list[str]]], tuple[str, ...]]:
    if workbook.name != "Tournament-II-Adjudication-ADJUDICATOR_D.xlsx":
        raise ValueError("returned adjudicator workbook filename changed")
    release = _validate_release_payload(json.loads(release_path.read_text(encoding="utf-8")))
    values = read_workbook(workbook)
    expected_tasks = tuple(dict.fromkeys(item["task_id"] for item in release["cases"]))
    expected_sheets = {"Instructions", *(_TASK_SHEETS[item] for item in expected_tasks)}
    if set(values) != expected_sheets:
        raise ValueError("adjudicator workbook sheets changed")
    instructions = values["Instructions"]
    expected_metadata = (
        (3, ADJUDICATOR_ID),
        (5, release["assignment_manifest_hash"]),
        (6, release["primary_release_manifest_hash"]),
        (7, release["package_set_hash"]),
        (8, ADJUDICATION_WORKBOOK_SCHEMA_VERSION),
        (9, "IN_PROGRESS"),
        (11, release["adjudicator_package_hash"]),
        (12, str(release["case_count"])),
    )
    for row, expected in expected_metadata:
        if _cell(instructions, row, 1) != expected:
            raise ValueError(f"adjudicator workbook metadata changed:row {row}")
    for task_id in expected_tasks:
        rows = values[_TASK_SHEETS[task_id]]
        if tuple(_cell(rows, 6, index) for index in range(19)) != _HEADERS:
            raise ValueError(f"adjudicator header mismatch:{task_id}")
        if (
            _cell(rows, 3, 1) != task_id
            or _cell(rows, 4, 1) != release["source_package_hashes"][task_id]
            or _cell(rows, 4, 3) != release["adjudicator_package_hash"]
        ):
            raise ValueError(f"adjudicator task lineage mismatch:{task_id}")
        expected_cases = [item for item in release["cases"] if item["task_id"] == task_id]
        for row_number, expected in enumerate(expected_cases, start=7):
            row = [_cell(rows, row_number, index) for index in range(4)]
            if row != [
                expected["anonymous_case_id"],
                expected["review_context"],
                expected["version_a"],
                expected["version_b"],
            ]:
                raise ValueError(f"adjudicator case/order/presentation changed:{row[0]}")
        first_extra = 7 + len(expected_cases)
        if any(_cell(rows, row_number, 0) for row_number in rows if row_number >= first_extra):
            raise ValueError(f"unexpected adjudicator case rows:{task_id}")
    return release, values, expected_tasks


def validate_released_workbook(workbook: Path, release_path: Path) -> dict[str, Any]:
    release, values, expected_tasks = _validate_frozen_workbook(workbook, release_path)
    if _cell(values["Instructions"], 10, 1).strip():
        raise ValueError("released adjudicator workbook must not contain a completion timestamp")
    for task_id in expected_tasks:
        rows = values[_TASK_SHEETS[task_id]]
        cases = [item for item in release["cases"] if item["task_id"] == task_id]
        for row_number in range(7, 7 + len(cases)):
            if any(_cell(rows, row_number, column).strip() for column in range(4, 19)):
                raise ValueError(f"released workbook contains adjudication data:{task_id}")
    return {
        "state": "IN_PROGRESS",
        "reviewer_id": ADJUDICATOR_ID,
        "case_count": release["case_count"],
        "adjudicator_package_hash": release["adjudicator_package_hash"],
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
    }


def validate_submission(workbook: Path, release_path: Path) -> dict[str, Any]:
    release, values, expected_tasks = _validate_frozen_workbook(workbook, release_path)
    completion_timestamp = _cell(values["Instructions"], 10, 1).strip()
    if completion_timestamp.startswith("'"):
        completion_timestamp = completion_timestamp[1:]
    try:
        timestamp = datetime.fromisoformat(completion_timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("valid UTC ISO completion timestamp is required") from error
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("completion timestamp must include UTC offset")

    responses = []
    cases_by_task = {
        task_id: [item for item in release["cases"] if item["task_id"] == task_id]
        for task_id in expected_tasks
    }
    for task_id in expected_tasks:
        rows = values[_TASK_SHEETS[task_id]]
        expected_cases = cases_by_task[task_id]
        for row_number in range(7, 7 + len(expected_cases)):
            row = [_cell(rows, row_number, index) for index in range(19)]
            scores = row[4:16]
            if any(value not in {"1", "2", "3", "4", "5"} for value in scores):
                raise ValueError(f"all A/B ratings must be integers 1-5:{row[0]}")
            preference = row[16].upper()
            defect = row[17].upper()
            if preference not in {"A", "B", "TIE"}:
                raise ValueError(f"paired preference must be A, B, or TIE:{row[0]}")
            if defect not in {"YES", "NO"}:
                raise ValueError(f"material defect must be YES or NO:{row[0]}")
            if defect == "YES" and not row[18].strip():
                raise ValueError(f"material defect note required when YES:{row[0]}")
            responses.append(
                {
                    "case_id": row[0],
                    "task_id": task_id,
                    "ratings": {
                        "version_a": dict(zip(_DIMENSIONS, map(int, scores[:6]), strict=True)),
                        "version_b": dict(zip(_DIMENSIONS, map(int, scores[6:]), strict=True)),
                    },
                    "paired_preference": preference,
                    "material_defect": defect,
                    "material_defect_note": row[18].strip() or None,
                }
            )
    if len(responses) != release["case_count"]:
        raise ValueError("locked adjudication case count mismatch")
    return {
        "schema_version": ADJUDICATION_IMPORT_SCHEMA_VERSION,
        "state": "LOCKED_ADJUDICATION_REVIEW",
        "reviewer_id": ADJUDICATOR_ID,
        "adjudicator_package_hash": release["adjudicator_package_hash"],
        "completion_timestamp": completion_timestamp,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "responses": responses,
        "qualification_calculated": False,
        "candidate_mapping_revealed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-release", action="store_true")
    mode.add_argument("--lock-output", type=Path)
    args = parser.parse_args()
    if args.check_release:
        result = validate_released_workbook(args.workbook, args.release)
        print(
            f"IN_PROGRESS adjudicator release validated: {result['case_count']} cases; "
            f"sha256={result['workbook_sha256']}"
        )
        return 0
    if args.lock_output is None:
        raise SystemExit("Lock output is required.")
    if args.lock_output.exists():
        raise SystemExit(
            "Lock denied: output already exists and adjudication reviews are immutable."
        )
    result = validate_submission(args.workbook, args.release)
    args.lock_output.parent.mkdir(parents=True, exist_ok=True)
    args.lock_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"LOCKED_ADJUDICATION_REVIEW: {ADJUDICATOR_ID}; {len(result['responses'])} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
