"""Entrypoint for the isolated exact-host controlled research-egress gateway."""

from __future__ import annotations

import os

from opintel_research_local.egress import run_gateway

from opintel_research_worker.authorization import AwsSsmResearchAuthorization
from opintel_research_worker.kill_switch import AwsSsmStopSignal


def run() -> None:
    authorization = AwsSsmResearchAuthorization(
        os.environ.get("OPINTEL_RESEARCH_RELEASE_PARAMETER", ""),
        os.environ.get("OPINTEL_AWS_REGION", "us-east-2"),
        os.environ.get("OPINTEL_RESEARCH_RUNTIME_REVISION", ""),
        os.environ.get("OPINTEL_PHASE1_SLOT_REGISTRY_PATH", ""),
        os.environ.get("OPINTEL_CONTROLLED_EGRESS_LEASE_PARAMETER", ""),
    )
    stop_signal = AwsSsmStopSignal(
        os.environ.get("OPINTEL_KILL_SWITCH_PARAMETER", ""),
        os.environ.get("OPINTEL_AWS_REGION", "us-east-2"),
    )

    def current_capability() -> dict[str, object]:
        if stop_signal.is_active():
            raise ValueError("kill switch denies controlled-egress capability")
        return authorization.current_gateway_capability()

    run_gateway(
        frozenset(),
        "",
        policy_provider=authorization.current_gateway_policy,
        capability_provider=current_capability,
    )


if __name__ == "__main__":
    run()
