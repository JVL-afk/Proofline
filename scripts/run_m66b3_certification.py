"""Execute only the five approved M6.6B-3 synthetic certification calls."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from opintel_qualification_live.secrets import (
    SecretConfigurationError,
    load_available_secret_bundle,
)
from opintel_qualification_live.tournament2_certification import (
    B2_COMMIT,
    B2_DRAFT_MANIFEST_HASH,
    CERTIFICATION_BUDGET_MICROS,
    OneShotCertificationRunner,
    call_definitions,
    create_authorization,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

_HOSTS = {
    "openai": "api.openai.com",
    "anthropic": "api.anthropic.com",
    "google": "generativelanguage.googleapis.com",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run the bounded M6.6B-3 synthetic candidate certification"
    )
    value.add_argument("--execute-certification", action="store_true")
    value.add_argument("--confirm-synthetic-only", action="store_true")
    value.add_argument("--arm-global-kill-switch", action="store_true")
    value.add_argument("--arm-budget-kill-switch", action="store_true")
    value.add_argument("--confirm-b2-commit", required=True)
    value.add_argument("--confirm-manifest-hash", required=True)
    value.add_argument("--actor", required=True)
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument("--budget-usd", type=int, default=1)
    value.add_argument(
        "--output",
        type=Path,
        default=Path("local-data/m6.6b-3/certification-run.json"),
    )
    return value


def _head_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> int:
    args = parser().parse_args()
    confirmations = (
        args.execute_certification,
        args.confirm_synthetic_only,
        args.arm_global_kill_switch,
        args.arm_budget_kill_switch,
    )
    if not all(confirmations):
        print("Certification denied: all explicit one-shot safety flags are required.")
        return 2
    if args.confirm_b2_commit != B2_COMMIT or _head_commit() != B2_COMMIT:
        print("Certification denied: repository HEAD does not match closed M6.6B-2.")
        return 2
    if args.confirm_manifest_hash != B2_DRAFT_MANIFEST_HASH:
        print("Certification denied: draft manifest confirmation does not match M6.6B-2.")
        return 2
    if args.budget_usd != 1:
        print("Certification denied: the hard authorization ceiling is exactly USD 1.")
        return 2
    if args.output.exists():
        print("Certification denied: the one-shot output already exists.")
        return 2

    started = datetime.now(UTC)
    execution_date = started.date().isoformat()
    calls = call_definitions(execution_date)
    reserved = sum(item.expected_max_cost_micros * 2 for item in calls)
    print(f"Preflight maximum estimate: USD {reserved / 1_000_000:.6f}")
    if reserved > CERTIFICATION_BUDGET_MICROS:
        print("Certification denied: refreshed pricing exceeds the hard budget.")
        return 2

    try:
        credentials = load_available_secret_bundle(args.credentials)
    except (OSError, SecretConfigurationError) as error:
        provider = (
            error.provider if isinstance(error, SecretConfigurationError) else "credential_file"
        )
        print(f"Certification denied: credential boundary unavailable for {provider}.")
        return 2

    authorization = create_authorization(
        actor=args.actor,
        now=started,
        nonce=str(uuid4()),
        execution_date=execution_date,
    )

    def transport_for_provider(provider: str) -> UrllibJsonTransport:
        host = _HOSTS.get(provider)
        if host is None:
            raise RuntimeError("provider_outside_certification_allowlist")
        return UrllibJsonTransport(allowed_hosts=frozenset({host}))

    try:
        runner = OneShotCertificationRunner(
            authorization,
            execution_date=execution_date,
            now=lambda: datetime.now(UTC),
            secret_for_provider=credentials.for_provider,
            transport_for_provider=transport_for_provider,
        )
        result = runner.run()
    except RuntimeError as error:
        print(f"Certification stopped safely: {error}")
        return 3
    finally:
        del credentials
        gc.collect()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(safe_result_dict(result), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"Certification closed: {result.calls_completed}/5 calls completed; "
        f"calculated cost USD {result.actual_cost_micros / 1_000_000:.6f}."
    )
    print(f"Safe local review artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
