"""Validate and lock a returned M6.6B-6 primary-review workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from opintel_qualification.tournament2_review_release import (
    IMPORT_SCHEMA_VERSION,
    PACKAGE_SET_SHA256,
    TASK_REVIEW_CONTEXTS,
    WORKBOOK_SCHEMA_VERSION,
    assignment_manifest_hash,
    release_manifest_hash,
    workbook_filename,
)

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_TASK_SHEETS = (
    "Evidence Interpretation",
    "Contradiction Analysis",
    "Opportunity Reasoning",
    "Audit Wording",
    "Outreach Wording",
)
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


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if letters is None:
        raise ValueError("invalid cell reference")
    value = 0
    for character in letters.group(0):
        value = value * 26 + ord(character) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> tuple[str, ...]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return ()
    return tuple("".join(node.itertext()) for node in root.findall("m:si", _NS))


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relations.findall("r:Relationship", _REL_NS)
    }
    result = {}
    for sheet in workbook.findall("m:sheets/m:sheet", _NS):
        relationship = sheet.attrib[f"{{{_DOC_REL}}}id"]
        target = targets[relationship].lstrip("/")
        result[sheet.attrib["name"]] = target if target.startswith("xl/") else f"xl/{target}"
    return result


def _sheet_values(
    archive: zipfile.ZipFile, path: str, shared: tuple[str, ...]
) -> dict[int, list[str]]:
    root = ET.fromstring(archive.read(path))
    rows: dict[int, list[str]] = {}
    for row in root.findall("m:sheetData/m:row", _NS):
        row_number = int(row.attrib["r"])
        values: dict[int, str] = {}
        for cell in row.findall("m:c", _NS):
            index = _column_index(cell.attrib["r"])
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                node = cell.find("m:is", _NS)
                value = "" if node is None else "".join(node.itertext())
            else:
                node = cell.find("m:v", _NS)
                raw = "" if node is None or node.text is None else node.text
                value = shared[int(raw)] if cell_type == "s" and raw else raw
            values[index] = value
        width = max(values, default=-1) + 1
        rows[row_number] = [values.get(index, "") for index in range(width)]
    return rows


def read_workbook(path: Path) -> dict[str, dict[int, list[str]]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        return {
            name: _sheet_values(archive, sheet_path, shared)
            for name, sheet_path in _sheet_paths(archive).items()
        }


def _cell(rows: dict[int, list[str]], row: int, column: int) -> str:
    values = rows.get(row, [])
    return values[column] if column < len(values) else ""


def _expected_packages(reviewer_id: str, source_root: Path) -> dict[str, dict[str, Any]]:
    reviewer_slot = {
        "PRIMARY_A": "PRIMARY_REVIEWER_SLOT_1",
        "PRIMARY_B": "PRIMARY_REVIEWER_SLOT_2",
        "PRIMARY_C": "PRIMARY_REVIEWER_SLOT_3",
    }[reviewer_id]
    result: dict[str, dict[str, Any]] = {}
    for path in (source_root / reviewer_slot).glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        result[value["task_id"]] = value
    return result


def _validate_frozen_workbook(
    workbook: Path,
    reviewer_id: str,
    source_root: Path,
) -> tuple[dict[str, dict[int, list[str]]], dict[str, dict[str, Any]]]:
    if workbook.name != workbook_filename(reviewer_id):
        raise ValueError("returned workbook filename does not match reviewer ID")
    values = read_workbook(workbook)
    if set(values) != {"Instructions", *_TASK_SHEETS}:
        raise ValueError("workbook sheets changed")
    instructions = values["Instructions"]
    if _cell(instructions, 3, 1) != reviewer_id:
        raise ValueError("reviewer ID mismatch")
    if _cell(instructions, 5, 1) != assignment_manifest_hash():
        raise ValueError("assignment manifest hash mismatch")
    if _cell(instructions, 6, 1) != release_manifest_hash():
        raise ValueError("release manifest hash mismatch")
    if _cell(instructions, 7, 1) != PACKAGE_SET_SHA256:
        raise ValueError("package set hash mismatch")
    if _cell(instructions, 8, 1) != WORKBOOK_SCHEMA_VERSION:
        raise ValueError("workbook schema version mismatch")
    if _cell(instructions, 9, 1) != "IN_PROGRESS":
        raise ValueError("workbook release state changed")
    expected_packages = _expected_packages(reviewer_id, source_root)
    if len(expected_packages) != 5:
        raise ValueError("exactly five sealed task packages are required")
    for sheet_name in _TASK_SHEETS:
        rows = values.get(sheet_name)
        if rows is None or tuple(_cell(rows, 6, index) for index in range(19)) != _HEADERS:
            raise ValueError(f"sheet/header mismatch:{sheet_name}")
        task_id = _cell(rows, 3, 1)
        package_hash = _cell(rows, 4, 1)
        package = expected_packages.get(task_id)
        if package is None or package["package_hash"] != package_hash:
            raise ValueError(f"package hash mismatch:{sheet_name}")
        if _cell(rows, 3, 3) != TASK_REVIEW_CONTEXTS[task_id]:
            raise ValueError(f"review context changed:{sheet_name}")
        expected_cases = package["cases"]
        seen = set()
        for offset, expected in enumerate(expected_cases, start=7):
            row = [_cell(rows, offset, index) for index in range(19)]
            if row[0] != expected["anonymous_case_id"]:
                raise ValueError(f"case ID or ordering changed:{sheet_name}:{offset}")
            if row[1] != TASK_REVIEW_CONTEXTS[task_id]:
                raise ValueError(f"case review context changed:{sheet_name}:{offset}")
            if row[2] != expected["version_a"] or row[3] != expected["version_b"]:
                raise ValueError(f"frozen A/B presentation changed:{sheet_name}:{offset}")
            if row[0] in seen:
                raise ValueError(f"duplicate case:{row[0]}")
            seen.add(row[0])
        if len(seen) != 21:
            raise ValueError(f"missing cases:{sheet_name}")
        if any(_cell(rows, row_number, 0) for row_number in rows if row_number > 27):
            raise ValueError(f"unexpected extra case rows:{sheet_name}")
    return values, expected_packages


def validate_released_workbook(
    workbook: Path,
    reviewer_id: str,
    source_root: Path,
) -> dict[str, Any]:
    values, _ = _validate_frozen_workbook(workbook, reviewer_id, source_root)
    if _cell(values["Instructions"], 10, 1).strip():
        raise ValueError("released workbook must not contain a completion timestamp")
    for sheet_name in _TASK_SHEETS:
        rows = values[sheet_name]
        for row_number in range(7, 28):
            if any(_cell(rows, row_number, column).strip() for column in range(4, 19)):
                raise ValueError(
                    f"released workbook contains review data:{sheet_name}:{row_number}"
                )
    return {
        "state": "IN_PROGRESS",
        "reviewer_id": reviewer_id,
        "case_count": 105,
        "assignment_manifest_hash": assignment_manifest_hash(),
        "release_manifest_hash": release_manifest_hash(),
        "package_set_hash": PACKAGE_SET_SHA256,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
    }


def validate_submission(
    workbook: Path,
    reviewer_id: str,
    source_root: Path,
) -> dict[str, Any]:
    values, expected_packages = _validate_frozen_workbook(workbook, reviewer_id, source_root)
    completion_timestamp = _cell(values["Instructions"], 10, 1).strip()
    try:
        parsed_timestamp = datetime.fromisoformat(completion_timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("valid UTC ISO completion timestamp is required") from error
    if parsed_timestamp.utcoffset() != timedelta(0):
        raise ValueError("completion timestamp must include the UTC offset")

    responses = []
    for sheet_name in _TASK_SHEETS:
        rows = values[sheet_name]
        task_id = _cell(rows, 3, 1)
        package_hash = expected_packages[task_id]["package_hash"]
        for row_number in range(7, 28):
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
                    "package_hash": package_hash,
                }
            )
    if len(responses) != 105:
        raise ValueError("review must contain exactly 105 complete cases")
    return {
        "schema_version": IMPORT_SCHEMA_VERSION,
        "state": "LOCKED_PRIMARY_REVIEW",
        "reviewer_id": reviewer_id,
        "assignment_manifest_hash": assignment_manifest_hash(),
        "release_manifest_hash": release_manifest_hash(),
        "package_set_hash": PACKAGE_SET_SHA256,
        "completion_timestamp": completion_timestamp,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "responses": responses,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reviewer",
        choices=("PRIMARY_A", "PRIMARY_B", "PRIMARY_C"),
        required=True,
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("local-data/m6.6b-5r/sealed/reviewer"),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-release", action="store_true")
    mode.add_argument("--lock-output", type=Path)
    parser.add_argument("--correction-of", type=Path)
    parser.add_argument("--correction-reason")
    args = parser.parse_args()
    if args.check_release:
        if args.correction_of or args.correction_reason:
            raise SystemExit("Correction options apply only when locking a completed review.")
        result = validate_released_workbook(args.workbook, args.reviewer, args.source_root)
        print(
            f"IN_PROGRESS release validated: {args.reviewer}; "
            f"{result['case_count']} cases; sha256={result['workbook_sha256']}"
        )
        return 0
    if args.lock_output is None:
        raise SystemExit("Lock output is required.")
    if args.lock_output.exists():
        raise SystemExit("Lock denied: output already exists and locked reviews are immutable.")
    if bool(args.correction_of) != bool(args.correction_reason):
        raise SystemExit("Correction requires both --correction-of and --correction-reason.")
    result = validate_submission(args.workbook, args.reviewer, args.source_root)
    if args.correction_of is not None:
        prior = json.loads(args.correction_of.read_text(encoding="utf-8"))
        if (
            prior.get("state") != "LOCKED_PRIMARY_REVIEW"
            or prior.get("reviewer_id") != args.reviewer
        ):
            raise SystemExit("Correction must reference this reviewer's locked primary review.")
        if not args.correction_reason or not args.correction_reason.strip():
            raise SystemExit("Correction reason must be non-empty.")
        result["correction_of_sha256"] = hashlib.sha256(args.correction_of.read_bytes()).hexdigest()
        result["correction_reason"] = args.correction_reason.strip()
        result["supersedes_state"] = prior["state"]
    args.lock_output.parent.mkdir(parents=True, exist_ok=True)
    args.lock_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"LOCKED_PRIMARY_REVIEW: {args.reviewer}; 105 cases validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
