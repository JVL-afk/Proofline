from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from opintel_api import create_app
from opintel_audit_local import SqlAlchemyAuditRepository
from opintel_demo_local import SqlAlchemyDemoRepository
from opintel_m0.workflow import M0WorkflowRunner
from opintel_m0_local import (
    FixtureHtmlExtractor,
    LocalFixtureFetcher,
    LocalSettings,
    SqlAlchemyM0Repository,
    UuidFactory,
)
from opintel_opportunity_local import SqlAlchemyOpportunityRepository
from opintel_research_local import SqlAlchemyResearchRepository
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "m0-test-token-that-is-deliberately-more-than-thirty-two-characters"
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")


@dataclass
class FakeClock:
    value: datetime

    def now(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 15, 12, 0, tzinfo=UTC))


@pytest.fixture
def settings(tmp_path: Path) -> LocalSettings:
    return LocalSettings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'm0.db').as_posix()}",
        fixture_root=ROOT / "fixtures" / "public-web",
        auth_token=SecretStr(TOKEN),
        auth_subject="test-operator",
        workspace_id=WORKSPACE_ID,
    )


@pytest.fixture
def repository(settings: LocalSettings) -> SqlAlchemyM0Repository:
    value = SqlAlchemyM0Repository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def research_repository(settings: LocalSettings) -> SqlAlchemyResearchRepository:
    value = SqlAlchemyResearchRepository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def opportunity_repository(settings: LocalSettings) -> SqlAlchemyOpportunityRepository:
    value = SqlAlchemyOpportunityRepository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def audit_repository(settings: LocalSettings) -> SqlAlchemyAuditRepository:
    value = SqlAlchemyAuditRepository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def demo_repository(settings: LocalSettings) -> SqlAlchemyDemoRepository:
    value = SqlAlchemyDemoRepository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def client(
    settings: LocalSettings,
    repository: SqlAlchemyM0Repository,
    research_repository: SqlAlchemyResearchRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    audit_repository: SqlAlchemyAuditRepository,
    demo_repository: SqlAlchemyDemoRepository,
    clock: FakeClock,
) -> Iterator[TestClient]:
    with TestClient(
        create_app(
            settings,
            repository,
            clock,
            UuidFactory(),
            research_repository,
            opportunity_repository,
            audit_repository,
            demo_repository,
        )
    ) as value:
        yield value


@pytest.fixture
def runner(
    settings: LocalSettings,
    repository: SqlAlchemyM0Repository,
    clock: FakeClock,
) -> M0WorkflowRunner:
    return M0WorkflowRunner(
        repository=repository,
        fetcher=LocalFixtureFetcher(settings.fixture_root, clock),
        extractor=FixtureHtmlExtractor(),
        clock=clock,
        identifiers=UuidFactory(),
        lease_duration=timedelta(seconds=10),
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def create_campaign(client: TestClient, auth_headers: dict[str, str]):
    def create(fixture_uri: str = "fixture://public/acme-success.html") -> dict[str, object]:
        response = client.post(
            "/api/v1/campaigns",
            headers=auth_headers,
            json={"name": f"M0 {uuid4()}", "fixture_uri": fixture_uri},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def start_operation(client: TestClient, auth_headers: dict[str, str]):
    def start(campaign_id: str, key: str | None = None):
        return client.post(
            f"/api/v1/campaigns/{campaign_id}/operations",
            headers={**auth_headers, "Idempotency-Key": key or f"test-{uuid4()}"},
        )

    return start
