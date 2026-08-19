"""Execute exact-manifest Tournament II once and persist safe local metadata only."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from opintel_qualification_live.secrets import load_secret_bundle
from opintel_qualification_live.tournament2_execution import (
    FINAL_MANIFEST_HASH,
    HARD_BUDGET_MICROS,
    OneShotTournamentRunner,
    create_authorization,
    execution_plan,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

_HOSTS = {
    "openai": "api.openai.com",
    "anthropic": "api.anthropic.com",
    "google": "generativelanguage.googleapis.com",
}


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run exact frozen Tournament II")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--confirm-synthetic-only", action="store_true")
    value.add_argument("--confirm-hidden-access", action="store_true")
    value.add_argument("--arm-global-kill-switch", action="store_true")
    value.add_argument("--arm-budget-kill-switch", action="store_true")
    value.add_argument("--manifest-hash", required=True)
    value.add_argument("--actor", required=True)
    value.add_argument("--budget-usd", type=int, default=25)
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument(
        "--output", type=Path, default=Path("local-data/m6.6b/tournament-run-2.json")
    )
    return value


def main() -> int:
    args = parser().parse_args()
    if not all(
        (
            args.execute,
            args.confirm_synthetic_only,
            args.confirm_hidden_access,
            args.arm_global_kill_switch,
            args.arm_budget_kill_switch,
        )
    ):
        print("Tournament II denied: all one-shot safety flags are required.")
        return 2
    if (
        args.manifest_hash != FINAL_MANIFEST_HASH
        or args.budget_usd * 1_000_000 != HARD_BUDGET_MICROS
    ):
        print("Tournament II denied: exact manifest and USD 25 ceiling are mandatory.")
        return 2
    if args.output.exists():
        print("Tournament II denied: the one-shot output already exists.")
        return 2
    if _head() != "c00440799762788b7946812c92cbca8cee35d1b5":
        print("Tournament II denied: readiness commit is not repository HEAD.")
        return 2
    now = datetime.now(UTC)
    authorization = create_authorization(
        actor=args.actor, now=now, nonce=str(uuid4()), manifest_hash=args.manifest_hash
    )
    plan = execution_plan()
    print(f"Preflight: {len(plan)} logical calls; exact hard cap USD {args.budget_usd}.")
    credentials = load_secret_bundle(args.credentials)

    def transport(provider: str) -> UrllibJsonTransport:
        return UrllibJsonTransport(allowed_hosts=frozenset({_HOSTS[provider]}))

    try:
        result = OneShotTournamentRunner(
            authorization,
            now=lambda: datetime.now(UTC),
            secret_for_provider=credentials.for_provider,
            transport_for_provider=transport,
        ).run()
    finally:
        del credentials
        gc.collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(safe_result_dict(result), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"Tournament II {result.state.value}: {result.calls_attempted}/{result.calls_planned} "
        f"logical calls; calculated cost USD {result.actual_cost_micros / 1_000_000:.6f}."
    )
    print(f"Safe local result: {args.output}")
    return 0 if result.stop_reason is None else 3


if __name__ == "__main__":
    raise SystemExit(main())
