"""Execute only the two authorized M6.6B-3R Gemini successor certifications."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from opintel_qualification_live.secrets import (
    SecretConfigurationError,
    load_available_secret_bundle,
)
from opintel_qualification_live.tournament2_gemini_repair import (
    CLOSURE_COMMIT,
    MAX_REPAIR_ATTEMPTS_PER_CALL,
    ORIGINAL_EVIDENCE_BLOB,
    REPAIR_BUDGET_MICROS,
    GeminiCertificationRepairRunner,
    create_repair_authorization,
    revision_hash,
    safe_repair_result_dict,
    successor_revisions,
)
from opintel_qualification_live.transport import UrllibJsonTransport

_ORIGINAL_EVIDENCE_PATH = Path("docs/evidence/m6.6b-3/certification-run-2026-08-19.json")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run the bounded M6.6B-3R Gemini-only certification repair"
    )
    value.add_argument("--execute-gemini-repair", action="store_true")
    value.add_argument("--confirm-synthetic-only", action="store_true")
    value.add_argument("--confirm-successor-diff-only", action="store_true")
    value.add_argument("--arm-global-kill-switch", action="store_true")
    value.add_argument("--arm-budget-kill-switch", action="store_true")
    value.add_argument("--confirm-closure-commit", required=True)
    value.add_argument("--confirm-original-evidence-blob", required=True)
    value.add_argument("--confirm-successor-revision-hash", action="append", default=[])
    value.add_argument("--actor", required=True)
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument("--budget-usd", type=Decimal, default=Decimal("0.25"))
    value.add_argument(
        "--output",
        type=Path,
        default=Path("local-data/m6.6b-3r/gemini-repair-run.json"),
    )
    return value


def _git_output(*arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def main() -> int:
    args = parser().parse_args()
    confirmations = (
        args.execute_gemini_repair,
        args.confirm_synthetic_only,
        args.confirm_successor_diff_only,
        args.arm_global_kill_switch,
        args.arm_budget_kill_switch,
    )
    if not all(confirmations):
        print("Gemini repair denied: all explicit one-shot safety flags are required.")
        return 2
    if args.confirm_closure_commit != CLOSURE_COMMIT or _git_output("rev-parse", "HEAD") != (
        CLOSURE_COMMIT
    ):
        print("Gemini repair denied: repository HEAD does not match M6.6B-3 closure.")
        return 2
    if (
        args.confirm_original_evidence_blob != ORIGINAL_EVIDENCE_BLOB
        or _git_output("hash-object", str(_ORIGINAL_EVIDENCE_PATH)) != ORIGINAL_EVIDENCE_BLOB
    ):
        print("Gemini repair denied: immutable predecessor evidence mismatch.")
        return 2
    if args.budget_usd != Decimal("0.25"):
        print("Gemini repair denied: hard authorization ceiling is exactly USD 0.25.")
        return 2
    if args.output.exists():
        print("Gemini repair denied: one-shot output already exists.")
        return 2

    started = datetime.now(UTC)
    execution_date = started.date().isoformat()
    revisions = successor_revisions(execution_date)
    hashes = tuple(revision_hash(item) for item in revisions)
    if tuple(args.confirm_successor_revision_hash) != hashes:
        print("Gemini repair denied: successor revision confirmations do not match.")
        return 2
    reserved = sum(
        item.expected_max_cost_micros * MAX_REPAIR_ATTEMPTS_PER_CALL for item in revisions
    )
    print(f"Gemini repair preflight maximum: USD {reserved / 1_000_000:.6f}")
    if reserved > REPAIR_BUDGET_MICROS:
        print("Gemini repair denied: refreshed pricing exceeds hard budget.")
        return 2

    try:
        credentials = load_available_secret_bundle(args.credentials)
    except (OSError, SecretConfigurationError) as error:
        provider = (
            error.provider if isinstance(error, SecretConfigurationError) else "credential_file"
        )
        print(f"Gemini repair denied: credential boundary unavailable for {provider}.")
        return 2
    gemini_credential = credentials.gemini
    del credentials
    gc.collect()

    authorization = create_repair_authorization(
        actor=args.actor,
        now=started,
        nonce=str(uuid4()),
        execution_date=execution_date,
    )
    transport = UrllibJsonTransport(allowed_hosts=frozenset({"generativelanguage.googleapis.com"}))
    try:
        result = GeminiCertificationRepairRunner(
            authorization,
            execution_date=execution_date,
            now=lambda: datetime.now(UTC),
            gemini_credential=gemini_credential,
            transport=transport,
        ).run()
    except RuntimeError as error:
        print(f"Gemini repair stopped safely: {error}")
        return 3
    finally:
        del gemini_credential
        gc.collect()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(safe_repair_result_dict(result), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"Gemini repair closed: {result.calls_completed}/2 calls completed; "
        f"calculated cost USD {result.actual_cost_micros / 1_000_000:.6f}."
    )
    print(f"Safe local review artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
