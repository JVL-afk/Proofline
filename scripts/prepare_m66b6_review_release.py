"""Verify sealed M6.6B-5R packages and produce identity-free workbook input JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from opintel_qualification.tournament2_review_release import (
    ASSIGNMENT_FILE_SHA256,
    FROZEN_REVIEWER_ASSIGNMENTS,
    PACKAGE_SET_SHA256,
    RECOVERY_COMMIT,
    RECOVERY_RESULT_SHA256,
    RENDERED_OUTPUT_SHA256,
    REVIEWER_RELEASE_MANIFEST,
    WORKBOOK_SCHEMA_VERSION,
    ReviewerRole,
    assignment_manifest_hash,
    release_manifest_hash,
    validate_release_manifest,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _package_set_hash(paths: tuple[Path, ...]) -> str:
    aggregate = "".join(_sha256(path).upper() for path in sorted(paths))
    return hashlib.sha256(aggregate.encode()).hexdigest()


def _packages_for_slot(root: Path, slot: str) -> tuple[dict[str, Any], ...]:
    paths = tuple(sorted((root / slot).glob("*.json")))
    if len(paths) != 5:
        raise ValueError(f"sealed slot package count mismatch:{slot}")
    values = tuple(json.loads(path.read_text(encoding="utf-8")) for path in paths)
    if any(
        item["reviewer_slot"] != slot or not item["sealed"] or item["released"] for item in values
    ):
        raise ValueError(f"sealed package state mismatch:{slot}")
    if sum(len(item["cases"]) for item in values) != 105:
        raise ValueError(f"sealed case count mismatch:{slot}")
    return values


def prepare(source_root: Path, output_dir: Path) -> tuple[Path, ...]:
    validate_release_manifest()
    if _head() != RECOVERY_COMMIT:
        raise ValueError("repository HEAD must match exact M6.6B-5R recovery commit")
    expected = {
        source_root.parent.parent / "recovery-safe-result.json": RECOVERY_RESULT_SHA256,
        source_root.parent / "internal" / "rendered-outputs.json": RENDERED_OUTPUT_SHA256,
        source_root.parent / "internal" / "assignments.json": ASSIGNMENT_FILE_SHA256,
    }
    for path, expected_hash in expected.items():
        if _sha256(path) != expected_hash:
            raise ValueError(f"sealed artifact hash mismatch:{path.name}")
    all_packages = tuple(sorted(source_root.glob("*/*.json")))
    if len(all_packages) != 20 or _package_set_hash(all_packages) != PACKAGE_SET_SHA256:
        raise ValueError("sealed package-set hash mismatch")

    output_dir.mkdir(parents=True, exist_ok=False)
    outputs = []
    for assignment in FROZEN_REVIEWER_ASSIGNMENTS:
        if assignment.role is not ReviewerRole.PRIMARY:
            continue
        packages = _packages_for_slot(source_root, assignment.sealed_slot)
        payload = {
            "workbook_schema_version": WORKBOOK_SCHEMA_VERSION,
            "reviewer_id": assignment.reviewer_id,
            "reviewer_role": assignment.role.value,
            "assignment_manifest_hash": assignment_manifest_hash(),
            "release_manifest_hash": release_manifest_hash(),
            "package_set_hash": PACKAGE_SET_SHA256,
            "source_package_hashes": tuple(item["package_hash"] for item in packages),
            "completion_state": "IN_PROGRESS",
            "packages": packages,
        }
        path = output_dir / f"{assignment.reviewer_id}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
    (output_dir / "release-manifest.json").write_text(
        json.dumps(
            {
                "manifest": asdict(REVIEWER_RELEASE_MANIFEST),
                "assignment_manifest_hash": assignment_manifest_hash(),
                "release_manifest_hash": release_manifest_hash(),
                "adjudicator_material_released": False,
                "provider_calls": 0,
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return tuple(outputs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("local-data/m6.6b-5r/sealed/reviewer"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = prepare(args.source_root, args.output_dir)
    print(f"Prepared {len(outputs)} blinded primary workbook inputs; adjudicator unreleased.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
