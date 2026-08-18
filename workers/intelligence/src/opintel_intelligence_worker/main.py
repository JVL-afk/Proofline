"""Credential-free deterministic M2 opportunity, M3 audit, and M4 demo worker."""

from __future__ import annotations

import json
import logging
import signal
import time

from opintel_audit import AuditWorkflowRunner, DeterministicAuditComposer
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
from opintel_demo import DemoWorkflowRunner, DeterministicDemoComposer
from opintel_demo_local import CanonicalDemoSourceCatalog, SqlAlchemyDemoRepository
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
    demo_repository = SqlAlchemyDemoRepository(settings.database_url)
    demo_repository.initialize()
    demo_runner = DemoWorkflowRunner(
        demo_repository,
        CanonicalDemoSourceCatalog(audit_repository, repository, research),
        DeterministicDemoComposer(UuidFactory()),
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
    logging.info(json.dumps({"event": "m4_intelligence_worker.started", "live_ai": False}))
    while not stopped:
        if (
            not opportunity_runner.run_once()
            and not audit_runner.run_once()
            and not demo_runner.run_once()
        ):
            time.sleep(settings.worker_poll_seconds)
    logging.info(json.dumps({"event": "m4_intelligence_worker.stopped"}))


if __name__ == "__main__":
    run()
