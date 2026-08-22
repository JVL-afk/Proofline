"""Entrypoint for the isolated exact-host controlled research-egress gateway."""

from __future__ import annotations

import os

from opintel_research_local.egress import run_gateway


def run() -> None:
    revision = os.environ.get("OPINTEL_EGRESS_POLICY_REVISION", "")
    hosts = frozenset(
        host.strip().lower()
        for host in os.environ.get("OPINTEL_EGRESS_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    )
    run_gateway(hosts, revision)


if __name__ == "__main__":
    run()
