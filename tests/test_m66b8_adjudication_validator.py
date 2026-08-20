from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from opintel_qualification.tournament2_adjudication import (
    ADJUDICATION_WORKBOOK_SCHEMA_VERSION,
    ADJUDICATOR_ID,
    stable_hash,
)


def _load_validator() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "validate_m66b8_adjudication.py"
    specification = importlib.util.spec_from_file_location("m66b8_adjudication_validator", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("unable to load M6.6B-8 validator")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


review = _load_validator()


def _release() -> dict[str, Any]:
    value: dict[str, Any] = {
        "workbook_schema_version": ADJUDICATION_WORKBOOK_SCHEMA_VERSION,
        "reviewer_id": ADJUDICATOR_ID,
        "reviewer_role": "conditional_adjudicator",
        "assignment_manifest_hash": "assignment",
        "primary_release_manifest_hash": "primary-release",
        "package_set_hash": "package-set",
        "primary_lock_hashes": {},
        "source_package_hashes": {"audit_wording": "source-package"},
        "completion_state": "IN_PROGRESS",
        "case_count": 1,
        "cases": [
            {
                "anonymous_case_id": "case-1",
                "task_id": "audit_wording",
                "review_context": "context",
                "adjudication_context": "neutral",
                "version_a": "A text",
                "version_b": "B text",
            }
        ],
    }
    value["adjudicator_package_hash"] = stable_hash(value)
    return value


def _values(release: dict[str, Any], *, complete: bool) -> dict[str, dict[int, list[str]]]:
    review_fields = ["3"] * 12 + ["A", "NO", ""] if complete else [""] * 15
    return {
        "Instructions": {
            3: ["Reviewer ID", ADJUDICATOR_ID],
            5: ["Assignment", "assignment"],
            6: ["Release", "primary-release"],
            7: ["Packages", "package-set"],
            8: ["Schema", ADJUDICATION_WORKBOOK_SCHEMA_VERSION],
            9: ["State", "IN_PROGRESS"],
            10: ["Timestamp", "2026-08-20T12:00:00Z" if complete else ""],
            11: ["Package", release["adjudicator_package_hash"]],
            12: ["Count", "1"],
        },
        "Audit Wording": {
            3: ["Task", "audit_wording"],
            4: ["Source", "source-package", "Release", release["adjudicator_package_hash"]],
            6: list(review._HEADERS),
            7: ["case-1", "context", "A text", "B text", *review_fields],
        },
    }


def _write_release(tmp_path: Path, value: dict[str, Any]) -> Path:
    path = tmp_path / "release.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_blank_release_and_complete_lock_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _release()
    release_path = _write_release(tmp_path, release)
    workbook = tmp_path / "Tournament-II-Adjudication-ADJUDICATOR_D.xlsx"
    workbook.write_bytes(b"adjudication")
    monkeypatch.setattr(review, "read_workbook", lambda _: _values(release, complete=False))
    assert review.validate_released_workbook(workbook, release_path)["case_count"] == 1
    monkeypatch.setattr(review, "read_workbook", lambda _: _values(release, complete=True))
    result = review.validate_submission(workbook, release_path)
    assert result["state"] == "LOCKED_ADJUDICATION_REVIEW"
    assert not result["qualification_calculated"]


def test_tampered_case_or_incomplete_review_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _release()
    release_path = _write_release(tmp_path, release)
    workbook = tmp_path / "Tournament-II-Adjudication-ADJUDICATOR_D.xlsx"
    workbook.write_bytes(b"adjudication")
    values = _values(release, complete=True)
    values["Audit Wording"][7][2] = "changed"
    monkeypatch.setattr(review, "read_workbook", lambda _: values)
    with pytest.raises(ValueError, match="presentation changed"):
        review.validate_submission(workbook, release_path)

    values = _values(release, complete=True)
    values["Audit Wording"][7][4] = ""
    monkeypatch.setattr(review, "read_workbook", lambda _: values)
    with pytest.raises(ValueError, match="ratings must be integers"):
        review.validate_submission(workbook, release_path)


def test_excel_text_escape_is_normalized_before_utc_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _release()
    release_path = _write_release(tmp_path, release)
    workbook = tmp_path / "Tournament-II-Adjudication-ADJUDICATOR_D.xlsx"
    workbook.write_bytes(b"adjudication")
    values = _values(release, complete=True)
    values["Instructions"][10][1] = "'2026-08-20T12:00:00Z"
    monkeypatch.setattr(review, "read_workbook", lambda _: values)

    result = review.validate_submission(workbook, release_path)

    assert result["completion_timestamp"] == "2026-08-20T12:00:00Z"
