"""Validate and render the no-network M6.6B-9 Tournament II closure report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from opintel_qualification.tournament2_final_scoring import (
    ADJUDICATOR_LOCK_HASH,
    PRIMARY_LOCK_HASHES,
    build_final_closure,
    closure_as_dict,
)

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_DIR = ROOT / "local-data" / "m6.6b-7" / "locked"
ADJUDICATOR_LOCK = ROOT / "local-data" / "m6.6b-8" / "locked" / ("ADJUDICATOR_D-review.json")
ASSIGNMENTS = ROOT / "local-data" / "m6.6b-5r" / "sealed" / "internal" / "assignments.json"
RENDERED = ROOT / "local-data" / "m6.6b-5r" / "sealed" / "internal" / "rendered-outputs.json"
ORIGINAL_RUN = ROOT / "local-data" / "m6.6b" / "tournament-run-2.json"
RECOVERY_RUN = ROOT / "local-data" / "m6.6b-5r" / "recovery-safe-result.json"
DEFAULT_REPORT = ROOT / "docs" / "evidence" / "m6.6b-9" / "final-report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _sequence(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be a list of JSON objects")
    return value


def build_report() -> dict[str, object]:
    primary_locks: dict[str, dict[str, Any]] = {}
    for reviewer_id, expected_hash in PRIMARY_LOCK_HASHES.items():
        path = PRIMARY_DIR / f"{reviewer_id}-review.json"
        if _sha256(path) != expected_hash:
            raise ValueError(f"primary review lock changed:{reviewer_id}")
        primary_locks[reviewer_id] = _mapping(_read(path), reviewer_id)
    if _sha256(ADJUDICATOR_LOCK) != ADJUDICATOR_LOCK_HASH:
        raise ValueError("adjudicator review lock changed")

    original = _mapping(_read(ORIGINAL_RUN), "original run")
    recovery = _mapping(_read(RECOVERY_RUN), "recovery run")
    if (
        original.get("state") != "completed"
        or original.get("calls_attempted") != 194
        or original.get("actual_cost_micros") != 1_145_397
        or original.get("route_activation_count") != 0
        or original.get("canonical_mutation_count") != 0
    ):
        raise ValueError("original Tournament II machine evidence changed")
    if (
        recovery.get("state") != "completed"
        or recovery.get("calls_attempted") != 105
        or recovery.get("actual_cost_micros") != 597_460
        or recovery.get("route_activation_count") != 0
        or recovery.get("canonical_mutation_count") != 0
    ):
        raise ValueError("review-recovery machine evidence changed")

    closure = build_final_closure(
        primary_locks=primary_locks,
        adjudicator_lock=_mapping(_read(ADJUDICATOR_LOCK), "adjudicator lock"),
        assignment_rows=_sequence(_read(ASSIGNMENTS), "assignments"),
        rendered_rows=_sequence(_read(RENDERED), "rendered outputs"),
        original_receipts=_sequence(original["receipts"], "original receipts"),
        recovery_receipts=_sequence(recovery["receipts"], "recovery receipts"),
    )
    return closure_as_dict(closure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--print", action="store_true", dest="print_report")
    args = parser.parse_args()
    actual = build_report()
    if args.report.exists():
        expected = _mapping(_read(args.report), "tracked final report")
        if actual != expected:
            raise ValueError("tracked M6.6B-9 final report differs from locked-source result")
    elif not args.print_report:
        raise ValueError("tracked M6.6B-9 final report is missing")
    if args.print_report:
        print(json.dumps(actual, indent=2, sort_keys=True))
    else:
        print("M6.6B-9 final report matches all immutable scoring inputs; provider calls: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
