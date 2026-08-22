"""Separate local M1 research worker entry point."""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta

from opintel_research import (
    ObservationalHtmlExtractor,
    PublicUrlPolicy,
    ResearchWorkflowRunner,
    SocketResolver,
)
from opintel_research.ports import HttpTransport
from opintel_research_local import (
    ControlledEgressTransport,
    DisabledBrowserFallback,
    IsolatedBrowserFallback,
    SafeHttpFetcher,
    SqlAlchemyResearchRepository,
    StdlibPinnedTransport,
    SystemClock,
    SystemSleeper,
    UuidFactory,
    get_research_worker_settings,
)

from opintel_research_worker.kill_switch import AwsSsmStopSignal
from opintel_research_worker.minimization import ProductionPhaseOneCaptureMinimizer


def build_runner() -> ResearchWorkflowRunner:
    settings = get_research_worker_settings()
    transport: HttpTransport
    if settings.app_env == "phase1":
        if settings.controlled_egress_url is None or settings.egress_policy_revision is None:
            raise RuntimeError("phase1 controlled egress configuration is incomplete")
        transport = ControlledEgressTransport(
            settings.controlled_egress_url, settings.egress_policy_revision
        )
    else:
        transport = StdlibPinnedTransport()
    clock = SystemClock()
    repository = SqlAlchemyResearchRepository(settings.resolved_database_url())
    repository.initialize()
    browser = (
        IsolatedBrowserFallback(
            ("opintel-browser-worker",),
            clock,
        )
        if settings.research_browser_enabled
        else DisabledBrowserFallback()
    )
    return ResearchWorkflowRunner(
        repository=repository,
        fetcher=SafeHttpFetcher(
            PublicUrlPolicy(SocketResolver()),
            transport,
            clock,
            live_enabled=settings.research_live_enabled,
        ),
        browser=browser,
        extractor=ObservationalHtmlExtractor(),
        clock=clock,
        identifiers=UuidFactory(),
        sleeper=SystemSleeper(),
        capture_minimizer=ProductionPhaseOneCaptureMinimizer(),
        lease_duration=timedelta(seconds=settings.worker_lease_seconds),
        stop_signal=(
            AwsSsmStopSignal(settings.kill_switch_parameter or "", settings.aws_region)
            if settings.app_env == "phase1"
            else None
        ),
    )


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_research_worker_settings()
    runner = build_runner()
    recovered = runner.recover_stale()
    logging.info(json.dumps({"event": "research_worker.started", "recovered_runs": recovered}))
    try:
        while True:
            if not runner.run_once():
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logging.info(json.dumps({"event": "research_worker.stopped"}))


if __name__ == "__main__":
    run()
