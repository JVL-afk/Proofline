"""Credential-free deterministic M2 opportunity and M3 audit worker entry point."""

from __future__ import annotations

import json
import logging
import signal
import time

from opintel_audit import AuditWorkflowRunner, DeterministicAuditComposer
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
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
    opportunity_runner = OpportunityWorkflowRunner(
        repository,
        ResearchEvidenceCatalog(research),
        EchoMockReasoner(),
        SystemClock(),
        UuidFactory(),
    )
    audit_repository = SqlAlchemyAuditRepository(settings.database_url)
    audit_repository.initialize()
    audit_runner = AuditWorkflowRunner(
        audit_repository,
        CanonicalAuditSourceCatalog(repository, research),
        DeterministicAuditComposer(UuidFactory()),
        SystemClock(),
    )
    stopped = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopped
        del signum, frame
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(json.dumps({"event": "m3_intelligence_worker.started", "live_ai": False}))
    while not stopped:
        if not opportunity_runner.run_once() and not audit_runner.run_once():
            time.sleep(settings.worker_poll_seconds)
    logging.info(json.dumps({"event": "m3_intelligence_worker.stopped"}))


if __name__ == "__main__":
    run()
