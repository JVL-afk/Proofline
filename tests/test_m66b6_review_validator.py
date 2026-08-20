from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from opintel_qualification.tournament2_review_release import (
    PACKAGE_SET_SHA256,
    TASK_REVIEW_CONTEXTS,
    WORKBOOK_SCHEMA_VERSION,
    assignment_manifest_hash,
    release_manifest_hash,
)


def _load_validator() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "validate_m66b6_review.py"
    specification = importlib.util.spec_from_file_location("m66b6_review_validator", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("unable to load M6.6B-6 validator")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


review = _load_validator()

_TASKS = (
    ("Evidence Interpretation", "evidence_interpretation"),
    ("Contradiction Analysis", "contradiction_analysis"),
    ("Opportunity Reasoning", "opportunity_reasoning"),
    ("Audit Wording", "audit_wording"),
    ("Outreach Wording", "outreach_wording"),
)


def _workbook_values(*, complete: bool = False) -> dict[str, dict[int, list[str]]]:
    instructions = {
        3: ["Reviewer ID", "PRIMARY_A"],
        5: ["Assignment manifest hash", assignment_manifest_hash()],
        6: ["Release manifest hash", release_manifest_hash()],
        7: ["Package-set hash", PACKAGE_SET_SHA256],
        8: ["Workbook schema", WORKBOOK_SCHEMA_VERSION],
        9: ["Release state", "IN_PROGRESS"],
        10: ["Completion timestamp", "2026-08-20T08:00:00Z" if complete else ""],
    }
    values = {"Instructions": instructions}
    for sheet_name, task_id in _TASKS:
        rows = {
            3: ["Task ID", task_id, "Review context", TASK_REVIEW_CONTEXTS[task_id]],
            4: ["Package hash", f"hash-{task_id}"],
            6: list(review._HEADERS),
        }
        for index in range(21):
            review_values = ["1"] * 12 + ["A", "NO", ""] if complete else [""] * 15
            rows[index + 7] = [
                f"{task_id}-case-{index:02d}",
                TASK_REVIEW_CONTEXTS[task_id],
                f"A-{task_id}-{index}",
                f"B-{task_id}-{index}",
                *review_values,
            ]
        values[sheet_name] = rows
    return values


def _packages() -> dict[str, dict[str, Any]]:
    return {
        task_id: {
            "task_id": task_id,
            "package_hash": f"hash-{task_id}",
            "cases": [
                {
                    "anonymous_case_id": f"{task_id}-case-{index:02d}",
                    "version_a": f"A-{task_id}-{index}",
                    "version_b": f"B-{task_id}-{index}",
                }
                for index in range(21)
            ],
        }
        for _, task_id in _TASKS
    }


def _patch_inputs(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, dict[int, list[str]]],
) -> None:
    monkeypatch.setattr(review, "read_workbook", lambda _: values)
    monkeypatch.setattr(review, "_expected_packages", lambda _reviewer, _root: _packages())


def test_release_validator_preserves_in_progress_and_exact_blinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook = tmp_path / "Tournament-II-Review-PRIMARY_A.xlsx"
    workbook.write_bytes(b"frozen-review-workbook")
    _patch_inputs(monkeypatch, _workbook_values())

    result = review.validate_released_workbook(workbook, "PRIMARY_A", tmp_path)

    assert result["state"] == "IN_PROGRESS"
    assert result["case_count"] == 105


def test_complete_review_locks_exact_ratings_and_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook = tmp_path / "Tournament-II-Review-PRIMARY_A.xlsx"
    workbook.write_bytes(b"completed-review-workbook")
    _patch_inputs(monkeypatch, _workbook_values(complete=True))

    result = review.validate_submission(workbook, "PRIMARY_A", tmp_path)

    assert result["state"] == "LOCKED_PRIMARY_REVIEW"
    assert len(result["responses"]) == 105
    assert result["responses"][0]["ratings"]["version_a"]["clarity"] == 1
    assert result["responses"][0]["package_hash"] == "hash-evidence_interpretation"


def test_tampered_presentation_or_incomplete_rating_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook = tmp_path / "Tournament-II-Review-PRIMARY_A.xlsx"
    workbook.write_bytes(b"tampered-review-workbook")
    values = _workbook_values(complete=True)
    values["Evidence Interpretation"][7][2] = "changed"
    _patch_inputs(monkeypatch, values)
    with pytest.raises(ValueError, match="presentation changed"):
        review.validate_submission(workbook, "PRIMARY_A", tmp_path)

    values = _workbook_values(complete=True)
    values["Evidence Interpretation"][7][4] = ""
    _patch_inputs(monkeypatch, values)
    with pytest.raises(ValueError, match="ratings must be integers"):
        review.validate_submission(workbook, "PRIMARY_A", tmp_path)
