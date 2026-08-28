"""Separate local M1 research worker entry point."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import timedelta

from opintel_research import (
    ObservationalHtmlExtractor,
    PublicUrlPolicy,
    ResearchWorkflowRunner,
    SocketResolver,
)
from opintel_research.ports import HttpTransport, ResearchAuthorization
from opintel_research_local import (
    ControlledEgressTransport,
    DisabledBrowserFallback,
    IsolatedBrowserFallback,
    RuntimeRobotsPolicy,
    SafeHttpFetcher,
    SqlAlchemyResearchRepository,
    StdlibPinnedTransport,
    SystemClock,
    SystemSleeper,
    UuidFactory,
    get_research_worker_settings,
)

from opintel_research_worker.authorization import (
    AwsSsmResearchAuthorization,
    SyntheticResearchAuthorization,
)
from opintel_research_worker.kill_switch import AwsSsmStopSignal
from opintel_research_worker.minimization import ProductionPhaseOneCaptureMinimizer
from opintel_research_worker.synthetic_validation import run_deployed_synthetic_validation


def build_runner() -> ResearchWorkflowRunner:
    settings = get_research_worker_settings()
    transport: HttpTransport
    research_authorization: ResearchAuthorization
    if settings.app_env == "phase1":
        if settings.controlled_egress_url is None or settings.egress_policy_revision is None:
            raise RuntimeError("phase1 controlled egress configuration is incomplete")
        research_authorization = AwsSsmResearchAuthorization(
            settings.research_release_parameter or "",
            settings.aws_region,
            settings.research_runtime_revision or "",
            settings.phase1_slot_registry_path or "",
            settings.controlled_egress_lease_parameter,
            require_egress_lease=True,
        )
        transport = ControlledEgressTransport(
            settings.controlled_egress_url,
            research_authorization.current_revision,
            research_authorization.current_gateway_capability,
        )
    else:
        transport = StdlibPinnedTransport()
        research_authorization = SyntheticResearchAuthorization()
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
        ),
        browser=browser,
        extractor=ObservationalHtmlExtractor(),
        clock=clock,
        identifiers=UuidFactory(),
        sleeper=SystemSleeper(),
        capture_minimizer=ProductionPhaseOneCaptureMinimizer(),
        robots_policy=RuntimeRobotsPolicy(
            PublicUrlPolicy(SocketResolver()), transport, clock, UuidFactory()
        ),
        research_authorization=research_authorization,
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
    validation_mode = os.environ.get("OPINTEL_SYNTHETIC_VALIDATION_MODE")
    if validation_mode is not None:
        run_deployed_synthetic_validation(
            settings,
            validation_mode,
            os.environ.get("OPINTEL_SYNTHETIC_VALIDATION_ID", ""),
        )
        return
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
