"""Execute the separately authorized Anthropic-only human-review recovery once."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from opintel_qualification.tournament2_machine_closure import ORIGINAL_MANIFEST_HASH
from opintel_qualification_live.secrets import load_single_provider_secret
from opintel_qualification_live.tournament2_review_recovery import (
    RECOVERY_HARD_CAP_MICROS,
    REVIEWER_SLOTS,
    OneShotReviewRecoveryRunner,
    create_recovery_authorization,
    recovery_plan,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

ORIGINAL_CLOSURE_COMMIT = "63bea8a9951cd14fc4f91845743d683bb447b081"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run exact M6.6B-5R Sonnet review recovery")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--confirm-new-samples", action="store_true")
    value.add_argument("--confirm-sealed-no-release", action="store_true")
    value.add_argument("--arm-budget-kill-switch", action="store_true")
    value.add_argument("--manifest-hash", required=True)
    value.add_argument("--actor", required=True)
    value.add_argument("--budget-usd", type=int, default=5)
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument("--output-dir", type=Path, default=Path("local-data/m6.6b-5r"))
    return value


def main() -> int:
    args = parser().parse_args()
    if not all(
        (
            args.execute,
            args.confirm_new_samples,
            args.confirm_sealed_no_release,
            args.arm_budget_kill_switch,
        )
    ):
        print("Recovery denied: all one-shot recovery flags are required.")
        return 2
    if args.manifest_hash != ORIGINAL_MANIFEST_HASH or args.budget_usd * 1_000_000 != (
        RECOVERY_HARD_CAP_MICROS
    ):
        print("Recovery denied: exact original manifest and USD 5 cap are mandatory.")
        return 2
    if _head() != ORIGINAL_CLOSURE_COMMIT:
        print("Recovery denied: repository HEAD must be the original machine closure commit.")
        return 2
    safe_path = args.output_dir / "recovery-safe-result.json"
    if safe_path.exists():
        print("Recovery denied: one-shot result already exists.")
        return 2
    credential = load_single_provider_secret(args.credentials, "anthropic")
    started = datetime.now(UTC)
    authorization = create_recovery_authorization(
        actor=args.actor,
        now=started,
        expires_at=started + timedelta(hours=2),
        nonce=str(uuid4()),
    )
    print(
        f"Recovery preflight: {len(recovery_plan())} logical calls; "
        f"maximum 210 attempts; exact hard cap USD {args.budget_usd}."
    )
    try:
        result = OneShotReviewRecoveryRunner(
            authorization,
            now=lambda: datetime.now(UTC),
            anthropic_credential=credential,
            transport=UrllibJsonTransport(allowed_hosts=frozenset({"api.anthropic.com"})),
        ).run()
    finally:
        del credential
        gc.collect()

    internal_dir = args.output_dir / "sealed" / "internal"
    reviewer_dir = args.output_dir / "sealed" / "reviewer"
    internal_dir.mkdir(parents=True, exist_ok=False)
    reviewer_dir.mkdir(parents=True, exist_ok=False)
    (internal_dir / "rendered-outputs.json").write_text(
        json.dumps([asdict(item) for item in result.rendered_outputs], indent=2, default=str)
        + "\n",
        encoding="utf-8",
    )
    (internal_dir / "assignments.json").write_text(
        json.dumps([asdict(item) for item in result.assignments], indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    for package in result.packages:
        slot_dir = reviewer_dir / package.reviewer_slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        (slot_dir / f"{package.task_id}.json").write_text(
            json.dumps(asdict(package), indent=2, default=str) + "\n", encoding="utf-8"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(
        json.dumps(safe_result_dict(result), indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        f"Recovery {result.state.value}: {result.calls_attempted}/{result.calls_planned} calls; "
        f"{len(result.rendered_outputs)} rendered outputs; {len(result.packages)} sealed packages; "
        f"calculated cost USD {result.actual_cost_micros / 1_000_000:.6f}."
    )
    print(f"Reviewer slots remain unnamed and sealed: {len(REVIEWER_SLOTS)}.")
    return 0 if result.stop_reason is None else 3


if __name__ == "__main__":
    raise SystemExit(main())
