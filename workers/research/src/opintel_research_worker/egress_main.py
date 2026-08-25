"""Entrypoint for the isolated exact-host controlled research-egress gateway."""

from __future__ import annotations

import os

from opintel_research_local.egress import run_gateway

from opintel_research_worker.authorization import AwsSsmResearchAuthorization


def run() -> None:
    authorization = AwsSsmResearchAuthorization(
        os.environ.get("OPINTEL_RESEARCH_RELEASE_PARAMETER", ""),
        os.environ.get("OPINTEL_AWS_REGION", "us-east-2"),
        os.environ.get("OPINTEL_RESEARCH_RUNTIME_REVISION", ""),
    )
    run_gateway(frozenset(), "", policy_provider=authorization.current_gateway_policy)


if __name__ == "__main__":
    run()
