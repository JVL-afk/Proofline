"""Credential-free deterministic M2-M5 intelligence worker."""

from __future__ import annotations

import json
import logging
import signal
import time

import boto3  # type: ignore[import-untyped]
from opintel_audit import AuditWorkflowRunner, DeterministicAuditComposer
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
from opintel_demo import DemoWorkflowRunner, DeterministicDemoComposer
from opintel_demo_local import CanonicalDemoSourceCatalog, SqlAlchemyDemoRepository
from opintel_m0_local import SystemClock, UuidFactory
from opintel_opportunity import OpportunityWorkflowRunner
from opintel_opportunity_local import (
    EchoMockReasoner,
    ResearchEvidenceCatalog,
    SqlAlchemyOpportunityRepository,
)
from opintel_outreach import DeterministicOutreachComposer, OutreachWorkflowRunner
from opintel_outreach_local import CanonicalOutreachSourceCatalog, SqlAlchemyOutreachRepository
from opintel_research_local import SqlAlchemyResearchRepository

from opintel_intelligence_worker.settings import IntelligenceWorkerSettings


def run() -> None:
    settings = IntelligenceWorkerSettings()  # type: ignore[call-arg]
    database_url = settings.database_url()
    research = SqlAlchemyResearchRepository(database_url)
    research.initialize()
    repository = SqlAlchemyOpportunityRepository(database_url)
    repository.initialize()
    opportunity_runner = OpportunityWorkflowRunner(
        repository,
        ResearchEvidenceCatalog(research),
        EchoMockReasoner(),
        SystemClock(),
        UuidFactory(),
    )
    audit_repository = SqlAlchemyAuditRepository(database_url)
    audit_repository.initialize()
    audit_runner = AuditWorkflowRunner(
        audit_repository,
        CanonicalAuditSourceCatalog(repository, research),
        DeterministicAuditComposer(UuidFactory()),
        SystemClock(),
    )
    demo_repository = SqlAlchemyDemoRepository(database_url)
    demo_repository.initialize()
    demo_runner = DemoWorkflowRunner(
        demo_repository,
        CanonicalDemoSourceCatalog(audit_repository, repository, research),
        DeterministicDemoComposer(UuidFactory()),
        SystemClock(),
    )
    outreach_repository = SqlAlchemyOutreachRepository(database_url)
    outreach_repository.initialize()
    outreach_runner = OutreachWorkflowRunner(
        outreach_repository,
        CanonicalOutreachSourceCatalog(demo_repository, audit_repository, repository, research),
        DeterministicOutreachComposer(UuidFactory()),
        SystemClock(),
    )
    stopped = False
    ssm = boto3.client("ssm", region_name=settings.aws_region)

    def kill_switch_tripped() -> bool:
        try:
            value = str(
                ssm.get_parameter(Name=settings.kill_switch_parameter)["Parameter"]["Value"]
            )
        except Exception:
            return True
        return value != "RUN"

    def stop(signum: int, frame: object) -> None:
        nonlocal stopped
        del signum, frame
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(json.dumps({"event": "m5_intelligence_worker.started", "live_ai": False}))
    while not stopped:
        if kill_switch_tripped():
            time.sleep(settings.worker_poll_seconds)
            continue
        if (
            not opportunity_runner.run_once()
            and not audit_runner.run_once()
            and not demo_runner.run_once()
            and not outreach_runner.run_once()
        ):
            time.sleep(settings.worker_poll_seconds)
    logging.info(json.dumps({"event": "m5_intelligence_worker.stopped"}))


if __name__ == "__main__":
    run()
