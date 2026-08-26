"""Production-only bounded sampled-slot activation command."""

from __future__ import annotations

import argparse
import json
import os
from uuid import UUID

from opintel_research_local import (
    SqlAlchemyResearchRepository,
    SystemClock,
    get_research_worker_settings,
)

from opintel_research_worker.activation import FrozenA09DecisionRegistry, SampledSlotActivator
from opintel_research_worker.authorization import AwsSsmResearchAuthorization
from opintel_research_worker.kill_switch import AwsSsmStopSignal
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot-number", type=int, required=True)
    parser.add_argument("--release-id", type=UUID, required=True)
    args = parser.parse_args()

    settings = get_research_worker_settings()
    if settings.app_env != "phase1":
        raise RuntimeError("sampled-slot activation is production Phase 1 only")
    a09_path = os.environ.get("OPINTEL_PHASE1_A09_DECISION_REGISTRY_PATH", "")
    if not a09_path:
        raise RuntimeError("exact A-09 decision registry is required")
    runtime = settings.research_runtime_revision or ""
    repository = SqlAlchemyResearchRepository(settings.resolved_database_url())
    repository.initialize()
    authority = AwsSsmResearchAuthorization(
        settings.research_release_parameter or "",
        settings.aws_region,
        runtime,
        settings.phase1_slot_registry_path or "",
    )
    activator = SampledSlotActivator(
        sample_registry=FrozenPhaseOneSampleRegistry(settings.phase1_slot_registry_path or ""),
        a09_registry=FrozenA09DecisionRegistry(a09_path),
        repository=repository,
        authority=authority,
        stop_signal=AwsSsmStopSignal(settings.kill_switch_parameter or "", settings.aws_region),
        clock=SystemClock(),
        runtime_revision=runtime,
    )
    try:
        work_item, created = activator.activate(args.slot_number, args.release_id)
        activation = work_item.sampled_slot_activation
        identity = work_item.sampled_slot_identity
        assert activation is not None and identity is not None
        print(
            json.dumps(
                {
                    "activation_sha256": activation.activation_sha256,
                    "created": created,
                    "event": "m67.sampled_slot_activation.complete",
                    "release_id": str(activation.authorization_release_id),
                    "slot_number": identity.slot_number,
                    "work_item_id": str(work_item.id),
                    "work_item_identity_sha256": identity.identity_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    finally:
        repository.engine.dispose()


if __name__ == "__main__":
    run()
