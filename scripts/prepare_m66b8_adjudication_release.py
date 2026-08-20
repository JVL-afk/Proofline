"""Compute the frozen M6.6B-8 adjudication set and prepare a blinded release payload."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from opintel_qualification.tournament2_adjudication import (
    ADJUDICATION_WORKBOOK_SCHEMA_VERSION,
    ADJUDICATOR_ID,
    ADJUDICATOR_SLOT,
    PRIMARY_LOCK_SHA256,
    select_adjudication_cases,
    stable_hash,
    trigger_counts,
    validate_lock,
)
from opintel_qualification.tournament2_review_release import (
    ASSIGNMENT_FILE_SHA256,
    PACKAGE_SET_SHA256,
    RENDERED_OUTPUT_SHA256,
    TASK_REVIEW_CONTEXTS,
    assignment_manifest_hash,
    release_manifest_hash,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_set_hash(paths: tuple[Path, ...]) -> str:
    aggregate = "".join(_sha256(path).upper() for path in sorted(paths))
    return hashlib.sha256(aggregate.encode()).hexdigest()


def _load_packages(source_root: Path, slot: str) -> dict[str, dict[str, Any]]:
    paths = tuple(sorted((source_root / slot).glob("*.json")))
    if len(paths) != 5:
        raise ValueError(f"sealed slot package count mismatch:{slot}")
    packages = {
        value["task_id"]: value for path in paths for value in [json.loads(path.read_text())]
    }
    if any(
        value["reviewer_slot"] != slot or not value["sealed"] or value["released"]
        for value in packages.values()
    ):
        raise ValueError(f"sealed package state mismatch:{slot}")
    return packages


def _validate_assignment_mapping(source_root: Path) -> None:
    internal = source_root.parent / "internal"
    assignment_path = internal / "assignments.json"
    rendered_path = internal / "rendered-outputs.json"
    if _sha256(assignment_path) != ASSIGNMENT_FILE_SHA256:
        raise ValueError("frozen assignment mapping hash mismatch")
    if _sha256(rendered_path) != RENDERED_OUTPUT_SHA256:
        raise ValueError("frozen rendered-output hash mismatch")
    assignments = json.loads(assignment_path.read_text(encoding="utf-8"))
    renderings = {
        (item["task"], item["anonymous_case_id"]): item
        for item in json.loads(rendered_path.read_text(encoding="utf-8"))
    }
    adjudicator_packages = _load_packages(source_root, ADJUDICATOR_SLOT)
    adjudicator_assignments = {
        (item["task"], item["anonymous_case_id"]): item
        for item in assignments
        if item["reviewer_slot"] == ADJUDICATOR_SLOT
    }
    if len(adjudicator_assignments) != 105:
        raise ValueError("frozen adjudicator mapping must contain 105 cases")
    for task_id, package in adjudicator_packages.items():
        for case in package["cases"]:
            key = (task_id, case["anonymous_case_id"])
            assignment = adjudicator_assignments.get(key)
            rendering = renderings.get(key)
            if assignment is None or rendering is None:
                raise ValueError(f"missing frozen adjudicator mapping:{key[1]}")
            candidate_side = assignment["candidate_side"]
            expected_a = (
                rendering["candidate_rendered_text"]
                if candidate_side == "VERSION A"
                else rendering["deterministic_rendered_text"]
            )
            expected_b = (
                rendering["candidate_rendered_text"]
                if candidate_side == "VERSION B"
                else rendering["deterministic_rendered_text"]
            )
            if case["version_a"] != expected_a or case["version_b"] != expected_b:
                raise ValueError(f"frozen adjudicator A/B mapping changed:{key[1]}")


def prepare(source_root: Path, locks_root: Path, output_dir: Path) -> dict[str, Any]:
    all_package_paths = tuple(sorted(source_root.glob("*/*.json")))
    if len(all_package_paths) != 20 or _package_set_hash(all_package_paths) != PACKAGE_SET_SHA256:
        raise ValueError("sealed package-set hash mismatch")
    _validate_assignment_mapping(source_root)

    primary_slots = {
        "PRIMARY_A": "PRIMARY_REVIEWER_SLOT_1",
        "PRIMARY_B": "PRIMARY_REVIEWER_SLOT_2",
        "PRIMARY_C": "PRIMARY_REVIEWER_SLOT_3",
    }
    locks: dict[str, dict[str, Any]] = {}
    for reviewer_id, slot in primary_slots.items():
        path = locks_root / f"{reviewer_id}-review.json"
        lock = json.loads(path.read_text(encoding="utf-8"))
        packages = _load_packages(source_root, slot)
        validate_lock(
            lock,
            reviewer_id=reviewer_id,
            lock_sha256=_sha256(path),
            expected_packages=packages,
        )
        locks[reviewer_id] = lock

    adjudicator_packages = _load_packages(source_root, ADJUDICATOR_SLOT)
    case_order = tuple(
        (task_id, case["anonymous_case_id"])
        for task_id, package in adjudicator_packages.items()
        for case in package["cases"]
    )
    selected = select_adjudication_cases(locks, case_order)
    selected_ids = {item.case_id for item in selected}
    cases = [
        {
            "anonymous_case_id": case["anonymous_case_id"],
            "task_id": task_id,
            "review_context": TASK_REVIEW_CONTEXTS[task_id],
            "adjudication_context": "Primary panel requires adjudication under the frozen policy.",
            "version_a": case["version_a"],
            "version_b": case["version_b"],
        }
        for task_id, package in adjudicator_packages.items()
        for case in package["cases"]
        if case["anonymous_case_id"] in selected_ids
    ]
    release_payload: dict[str, Any] = {
        "workbook_schema_version": ADJUDICATION_WORKBOOK_SCHEMA_VERSION,
        "reviewer_id": ADJUDICATOR_ID,
        "reviewer_role": "conditional_adjudicator",
        "assignment_manifest_hash": assignment_manifest_hash(),
        "primary_release_manifest_hash": release_manifest_hash(),
        "package_set_hash": PACKAGE_SET_SHA256,
        "primary_lock_hashes": PRIMARY_LOCK_SHA256,
        "source_package_hashes": {
            task_id: package["package_hash"] for task_id, package in adjudicator_packages.items()
        },
        "completion_state": "IN_PROGRESS",
        "case_count": len(cases),
        "cases": cases,
    }
    release_payload["adjudicator_package_hash"] = stable_hash(release_payload)
    selection_payload = {
        "schema_version": "m6.6b8.adjudication-selection@1",
        "state": "ADJUDICATION_SET_FROZEN",
        "primary_lock_hashes": PRIMARY_LOCK_SHA256,
        "selected_cases": [asdict(item) for item in selected],
        "trigger_counts": trigger_counts(selected),
        "policy_blockers": [
            {
                "case_id": "51ee87af09907a072639e7b6",
                "state": "POLICY_ADJUDICATION_REQUIRED",
                "blocks_final_disposition": True,
                "reason": "Frozen evaluator lacks the confirmed wording/CTA cross-field rule.",
            }
        ],
        "provider_calls": 0,
        "qualification_calculated": False,
        "candidate_mapping_revealed": False,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "adjudication-selection.json").write_text(
        json.dumps(selection_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    release_path = output_dir / f"{ADJUDICATOR_ID}.json"
    release_path.write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
    return release_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path, default=Path("local-data/m6.6b-5r/sealed/reviewer")
    )
    parser.add_argument("--locks-root", type=Path, default=Path("local-data/m6.6b-7/locked"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = prepare(args.source_root, args.locks_root, args.output_dir)
    print(
        f"Adjudication set frozen: {payload['case_count']} blinded cases; "
        f"package={payload['adjudicator_package_hash']}; provider calls=0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
