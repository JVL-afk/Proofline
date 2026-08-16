"""Credential-free deterministic M2 worker entry point."""

from __future__ import annotations

import json
import logging
import signal
import time

from opintel_m0_local import SystemClock, UuidFactory
from opintel_m0_local.settings import get_local_settings
from opintel_opportunity import OpportunityWorkflowRunner
from opintel_opportunity_local import (
    EchoMockReasoner,
    ResearchEvidenceCatalog,
    SqlAlchemyOpportunityRepository,
)
from opintel_research_local import SqlAlchemyResearchRepository


def run() -> None:
    settings = get_local_settings()
    research = SqlAlchemyResearchRepository(settings.database_url)
    research.initialize()
    repository = SqlAlchemyOpportunityRepository(settings.database_url)
    repository.initialize()
    runner = OpportunityWorkflowRunner(
        repository,
        ResearchEvidenceCatalog(research),
        EchoMockReasoner(),
        SystemClock(),
        UuidFactory(),
    )
    stopped = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopped
        del signum, frame
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(json.dumps({"event": "m2_intelligence_worker.started", "live_ai": False}))
    while not stopped:
        if not runner.run_once():
            time.sleep(settings.worker_poll_seconds)
    logging.info(json.dumps({"event": "m2_intelligence_worker.stopped"}))


if __name__ == "__main__":
    run()
