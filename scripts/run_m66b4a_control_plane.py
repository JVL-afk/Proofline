"""Run the explicitly authorized read-only M6.6B-4A provider metadata checks."""

from __future__ import annotations

import argparse
import gc
import json
from datetime import UTC, datetime
from pathlib import Path

from opintel_qualification_live.secrets import load_available_secret_bundle
from opintel_qualification_live.tournament2_control_plane import (
    run_control_plane_probe,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

_HOSTS = {
    "openai": "api.openai.com",
    "anthropic": "api.anthropic.com",
    "google": "generativelanguage.googleapis.com",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--execute-read-only-control-plane", action="store_true")
    value.add_argument("--confirm-no-inference", action="store_true")
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument(
        "--output",
        type=Path,
        default=Path("local-data/m6.6b-4a/control-plane-probe.json"),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    if not args.execute_read_only_control_plane or not args.confirm_no_inference:
        print("Control-plane probe denied: both explicit safety flags are required.")
        return 2
    if args.output.exists():
        print("Control-plane probe denied: output already exists.")
        return 2
    credentials = load_available_secret_bundle(args.credentials)

    def transport_for_provider(provider: str) -> UrllibJsonTransport:
        return UrllibJsonTransport(allowed_hosts=frozenset({_HOSTS[provider]}))

    try:
        result = run_control_plane_probe(
            now=lambda: datetime.now(UTC),
            secret_for_provider=credentials.for_provider,
            transport_for_provider=transport_for_provider,
        )
    finally:
        del credentials
        gc.collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(safe_result_dict(result), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"Control-plane probe closed: {result.calls_completed}/{result.calls_attempted} "
        "metadata checks verified; zero inference calls."
    )
    print(f"Safe local review artifact: {args.output}")
    return 0 if result.calls_completed == result.calls_attempted else 3


if __name__ == "__main__":
    raise SystemExit(main())
