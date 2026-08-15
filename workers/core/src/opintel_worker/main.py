"""CLI entry point for the separate M0 durable worker process."""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta

from opintel_m0.workflow import M0WorkflowRunner
from opintel_m0_local import (
    FixtureHtmlExtractor,
    LocalFixtureFetcher,
    SqlAlchemyM0Repository,
    SystemClock,
    UuidFactory,
)
from opintel_m0_local.settings import get_local_settings


def build_runner() -> M0WorkflowRunner:
    settings = get_local_settings()
    clock = SystemClock()
    repository = SqlAlchemyM0Repository(settings.database_url)
    repository.initialize()
    return M0WorkflowRunner(
        repository=repository,
        fetcher=LocalFixtureFetcher(settings.fixture_root, clock),
        extractor=FixtureHtmlExtractor(),
        clock=clock,
        identifiers=UuidFactory(),
        lease_duration=timedelta(seconds=settings.worker_lease_seconds),
    )


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_local_settings()
    runner = build_runner()
    recovered = runner.recover_stale()
    logging.info(json.dumps({"event": "worker.started", "recovered_operations": recovered}))
    try:
        while True:
            if not runner.run_once():
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logging.info(json.dumps({"event": "worker.stopped"}))


if __name__ == "__main__":
    run()
