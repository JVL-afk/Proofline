from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from opintel_research.domain import (
    Business,
    CrawlPolicy,
    FetchAttempt,
    ResearchRun,
    ResearchRunStatus,
)
from opintel_research_local.persistence import Base, SqlAlchemyResearchRepository
from opintel_research_worker.kill_switch import AwsSsmStopSignal


class _SsmClient:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_parameter(self, *, Name: str) -> object:
        assert Name == "/synthetic/kill-switch"
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def _exercise_lifecycle(database_url: str) -> tuple[object, ...]:
    repository = SqlAlchemyResearchRepository(database_url)
    repository.initialize()
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    workspace_id = uuid4()
    business_id = uuid4()
    run_id = uuid4()
    repository.create_business(
        Business(
            id=business_id,
            workspace_id=workspace_id,
            name="Synthetic HVAC",
            canonical_url="https://synthetic.invalid/",
            permitted_host="synthetic.invalid",
            created_by="synthetic-reviewer",
            created_at=now,
        )
    )
    run = ResearchRun(
        id=run_id,
        workspace_id=workspace_id,
        business_id=business_id,
        operation_id=uuid4(),
        trace_id=uuid4(),
        start_url="https://synthetic.invalid/",
        permitted_host="synthetic.invalid",
        policy=CrawlPolicy(),
        status=ResearchRunStatus.PENDING,
        created_by="synthetic-reviewer",
        created_at=now,
        updated_at=now,
    )
    created, was_created = repository.create_or_get_run(run, "synthetic-idempotency-key")
    duplicate, duplicate_created = repository.create_or_get_run(run, "synthetic-idempotency-key")
    claimed = repository.claim_run(now, timedelta(seconds=30))
    assert claimed is not None
    repository.record_attempt(
        FetchAttempt(
            id=uuid4(),
            research_run_id=run_id,
            normalized_url=run.start_url,
            attempt_number=1,
            started_at=now,
            completed_at=now,
            outcome="succeeded",
        )
    )
    repository.complete_run(
        run_id,
        ResearchRunStatus.SUCCEEDED,
        pages_attempted=1,
        pages_succeeded=1,
        bytes_stored=128,
        now=now + timedelta(seconds=1),
    )
    completed = repository.get_run(workspace_id, run_id)
    attempts = repository.list_attempts(workspace_id, run_id)
    result = (
        was_created,
        duplicate_created,
        created.id == duplicate.id,
        claimed.status,
        completed.status if completed else None,
        len(attempts),
        attempts[0].outcome,
    )
    Base.metadata.drop_all(repository.engine)
    repository.engine.dispose()
    return result


def test_sqlite_and_postgres_preserve_critical_lifecycle_semantics() -> None:
    postgres_url = os.environ.get("OPINTEL_TEST_POSTGRES_URL")
    if postgres_url is None:
        pytest.skip("set OPINTEL_TEST_POSTGRES_URL for local PostgreSQL parity execution")
    sqlite_result = _exercise_lifecycle("sqlite:///:memory:")
    postgres_result = _exercise_lifecycle(postgres_url)
    assert postgres_result == sqlite_result


@pytest.mark.parametrize(
    ("response", "active"),
    [
        ({"Parameter": {"Value": "RUN"}}, False),
        ({"Parameter": {"Value": "STOP"}}, True),
        (RuntimeError("synthetic SSM failure"), True),
    ],
)
def test_phase1_kill_switch_fails_closed(response: object, active: bool) -> None:
    signal = AwsSsmStopSignal("/synthetic/kill-switch", "us-east-2", client=_SsmClient(response))
    assert signal.is_active() is active
