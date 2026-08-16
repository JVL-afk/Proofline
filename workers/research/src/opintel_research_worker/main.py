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
from opintel_research_local import (
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


def build_runner() -> ResearchWorkflowRunner:
    settings = get_research_worker_settings()
    clock = SystemClock()
    repository = SqlAlchemyResearchRepository(settings.database_url)
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
            StdlibPinnedTransport(),
            clock,
            live_enabled=settings.research_live_enabled,
        ),
        browser=browser,
        extractor=ObservationalHtmlExtractor(),
        clock=clock,
        identifiers=UuidFactory(),
        sleeper=SystemSleeper(),
        lease_duration=timedelta(seconds=settings.worker_lease_seconds),
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
