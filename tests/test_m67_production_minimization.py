from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_research import ObservationalHtmlExtractor, ResearchWorkflowRunner
from opintel_research.domain import (
    Business,
    CrawlPolicy,
    FetchedDocument,
    PageSnapshot,
    ResearchRun,
    ResearchRunStatus,
    RobotsPolicyEvidence,
    UrlPolicyError,
)
from opintel_research.url_policy import normalize_public_url
from opintel_research_local import DisabledBrowserFallback
from opintel_research_local.persistence import SqlAlchemyResearchRepository
from opintel_research_worker.minimization import ProductionPhaseOneCaptureMinimizer
from sqlalchemy import text

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)
HOSTILE = b"""<html><head><title>SafeCo Commercial HVAC</title></head><body>
<h1>Texas commercial HVAC service for business facilities</h1>
<p>Businesses may request a service estimate online.</p>
<p>For commercial service, email dispatch@example.com or call +1 (512) 555-0199.</p>
<section class="staff contact-card"><h2>Jane Technician</h2>
<p>jane.technician@example.com</p><p>512-555-0101</p></section>
<script type="application/ld+json">{"@type":"ContactPoint","telephone":"5125550102"}</script>
</body></html>"""
PROHIBITED = (
    "dispatch@example.com",
    "jane.technician@example.com",
    "512-555-0101",
    "5125550102",
    "Jane Technician",
)


class Clock:
    def now(self) -> datetime:
        return NOW


class NoSleep:
    def sleep(self, seconds: float) -> None:
        del seconds


class AllowSyntheticRobots:
    def evaluate(self, research_run_id, url, permitted_host, policy):
        del url, policy
        return RobotsPolicyEvidence(
            id=uuid4(), research_run_id=research_run_id, host=permitted_host,
            requested_path="/", captured_at=NOW, http_status=200,
            body_sha256="0" * 64, body_length=0, decision="ALLOW",
            reason_code="synthetic_robots_allowed", allowed=True,
        )


class AllowSyntheticResearch:
    def authorize(self, run, business) -> None:
        assert run.business_id == business.id


class OneDocumentFetcher:
    def __init__(self, content: bytes, charset: str = "utf-8") -> None:
        self.content = content
        self.charset = charset

    def fetch(
        self, url: str, permitted_host: str, policy: CrawlPolicy, attempt_number: int
    ) -> FetchedDocument:
        del permitted_host, policy, attempt_number
        return FetchedDocument(
            source_url=url,
            canonical_url=url,
            final_url=url,
            status_code=200,
            headers=(
                ("content-type", "text/html; charset=utf-8"),
                ("set-cookie", "contact=dispatch@example.com"),
            ),
            content=self.content,
            content_type="text/html",
            charset=self.charset,
            captured_at=NOW,
        )


class FailingMinimizer:
    def minimize(self, snapshot: PageSnapshot, business_name: str, observed_visible_text: str):
        del business_name, observed_visible_text
        raise RuntimeError(f"must not be logged: {snapshot.content!r}")


def _runner(
    repository: SqlAlchemyResearchRepository,
    content: bytes,
    *,
    minimizer: object | None = None,
    charset: str = "utf-8",
) -> tuple[ResearchRun, ResearchWorkflowRunner]:
    workspace_id = uuid4()
    business_id = uuid4()
    run_id = uuid4()
    repository.initialize()
    repository.create_business(
        Business(
            id=business_id,
            workspace_id=workspace_id,
            name="SafeCo Commercial HVAC",
            canonical_url="https://synthetic.invalid/",
            permitted_host="synthetic.invalid",
            created_by="synthetic-reviewer",
            created_at=NOW,
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
        policy=CrawlPolicy(max_pages=1, per_domain_delay_seconds=0),
        status=ResearchRunStatus.PENDING,
        created_by="synthetic-reviewer",
        created_at=NOW,
        updated_at=NOW,
    )
    repository.create_or_get_run(run, "synthetic-minimization")
    runner = ResearchWorkflowRunner(
        repository=repository,
        fetcher=OneDocumentFetcher(content, charset),
        browser=DisabledBrowserFallback(),
        extractor=ObservationalHtmlExtractor(),
        clock=Clock(),
        identifiers=UuidFactory(),
        sleeper=NoSleep(),
        capture_minimizer=minimizer or ProductionPhaseOneCaptureMinimizer(),  # type: ignore[arg-type]
        robots_policy=AllowSyntheticRobots(),
        research_authorization=AllowSyntheticResearch(),
    )
    return run, runner


def _all_durable_text(repository: SqlAlchemyResearchRepository) -> str:
    values: list[str] = []
    with repository.engine.connect() as connection:
        for table in (
            "page_snapshots",
            "extracted_material",
            "research_evidence",
            "research_capture_quarantines",
            "research_pages",
            "research_fetch_attempts",
            "research_runs",
        ):
            rows = connection.execute(text(f'SELECT * FROM "{table}"')).mappings()
            values.extend(repr(dict(row)) for row in rows)
    return "\n".join(values)


def _exercise_minimized_persistence(database_url: str) -> dict[str, object]:
    repository = SqlAlchemyResearchRepository(database_url)
    run, runner = _runner(repository, HOSTILE)
    assert runner.run_once()
    snapshot_row: dict[str, object]
    with repository.engine.connect() as connection:
        snapshot_row = dict(
            connection.execute(text("SELECT * FROM page_snapshots")).mappings().one()
        )
        material_row = dict(
            connection.execute(text("SELECT * FROM extracted_material")).mappings().one()
        )
        evidence_rows = [
            dict(item)
            for item in connection.execute(text("SELECT * FROM research_evidence")).mappings()
        ]
    durable = _all_durable_text(repository)
    assert all(item not in durable for item in PROHIBITED)
    assert "SafeCo Commercial HVAC" in str(snapshot_row["minimized_text"])
    assert "Texas commercial HVAC service" in str(snapshot_row["minimized_text"])
    assert "[EMAIL_REDACTED]" in str(snapshot_row["minimized_text"])
    assert "[PHONE_REDACTED]" in str(snapshot_row["minimized_text"])
    assert snapshot_row["removed_email_count"] == 2
    assert snapshot_row["removed_phone_count"] == 3
    assert int(snapshot_row["removed_structured_contact_blocks"]) >= 2
    assert "response_headers_json" not in snapshot_row
    assert "content" not in snapshot_row
    assert json.loads(str(material_row["material_json"]))["contacts"] == []
    assert evidence_rows
    assert all(
        str(item["extracted_fragment"]) in str(snapshot_row["minimized_text"])
        for item in evidence_rows
    )
    result = {
        "run_status": repository.get_run(run.workspace_id, run.id).status.value,  # type: ignore[union-attr]
        "source_content_sha256": snapshot_row["source_content_sha256"],
        "minimized_content_sha256": snapshot_row["content_sha256"],
        "minimization_event_sha256": snapshot_row["minimization_event_sha256"],
        "evidence_count": len(evidence_rows),
    }
    repository.engine.dispose()
    return result


def test_production_path_persists_only_minimized_capture_in_sqlite() -> None:
    result = _exercise_minimized_persistence("sqlite:///:memory:")
    assert result["run_status"] == "succeeded"
    assert result["source_content_sha256"] != result["minimized_content_sha256"]


def test_postgresql_adapter_preserves_the_same_minimized_invariant() -> None:
    postgres_url = os.environ.get("OPINTEL_TEST_POSTGRES_URL")
    if postgres_url is None:
        pytest.skip("set OPINTEL_TEST_POSTGRES_URL for PostgreSQL minimization execution")
    result = _exercise_minimized_persistence(postgres_url)
    assert result["run_status"] == "succeeded"


@pytest.mark.parametrize(
    ("content", "minimizer"),
    [
        (b"\xff\xfe\x00malformed", None),
        (HOSTILE, FailingMinimizer()),
    ],
)
def test_minimization_failure_or_unsafe_content_quarantines_without_raw_persistence(
    content: bytes, minimizer: object | None, caplog: pytest.LogCaptureFixture
) -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    caplog.set_level(logging.DEBUG)
    run, runner = _runner(repository, content, minimizer=minimizer)
    assert runner.run_once()
    durable = _all_durable_text(repository)
    assert repr(content) not in durable
    assert repr(content) not in caplog.text
    with repository.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM page_snapshots")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM extracted_material")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM research_evidence")).scalar_one() == 0
        quarantine = dict(
            connection.execute(text("SELECT * FROM research_capture_quarantines")).mappings().one()
        )
    assert set(quarantine).isdisjoint({"content", "minimized_text", "response_headers_json"})
    assert repository.get_run(run.workspace_id, run.id).status is ResearchRunStatus.FAILED  # type: ignore[union-attr]


def test_repository_rejects_raw_snapshot_and_legacy_raw_schema(tmp_path: Path) -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    run, _ = _runner(repository, HOSTILE)
    raw = PageSnapshot(
        id=uuid4(),
        workspace_id=run.workspace_id,
        business_id=run.business_id,
        research_run_id=run.id,
        operation_id=run.operation_id,
        trace_id=run.trace_id,
        source_url=run.start_url,
        canonical_url=run.start_url,
        final_url=run.start_url,
        snapshot_version="sha256:synthetic",
        captured_at=NOW,
        content_sha256="0" * 64,
        content_type="text/html",
        charset="utf-8",
        status_code=200,
        content_length=len(HOSTILE),
        response_headers=(),
        content=HOSTILE,
    )
    with pytest.raises(TypeError, match="durable minimized page bundle"):
        repository.save_page_bundle(Any, raw)  # type: ignore[arg-type]

    legacy = tmp_path / "legacy.sqlite3"
    legacy_repository = SqlAlchemyResearchRepository(f"sqlite:///{legacy}")
    with legacy_repository.engine.begin() as connection:
        connection.execute(text("CREATE TABLE page_snapshots (id TEXT, content BLOB)"))
    with pytest.raises(RuntimeError, match="legacy raw snapshot schema"):
        legacy_repository.initialize()


def test_raw_objects_hide_bodies_and_contact_urls_fail_closed() -> None:
    document = OneDocumentFetcher(HOSTILE).fetch(
        "https://synthetic.invalid/", "synthetic.invalid", CrawlPolicy(), 1
    )
    assert "dispatch@example.com" not in repr(document)
    assert repr(HOSTILE) not in repr(document)
    for value in (
        "https://synthetic.invalid/?email=dispatch@example.com",
        "https://synthetic.invalid/call/512-555-0199",
    ):
        with pytest.raises(UrlPolicyError, match="prohibited contact"):
            normalize_public_url(value)


def test_production_observability_and_storage_code_has_no_raw_body_sink() -> None:
    root = Path(__file__).resolve().parents[1]
    worker = (root / "workers/research/src/opintel_research_worker/main.py").read_text()
    egress = (root / "packages/research-local/src/opintel_research_local/egress.py").read_text()
    persistence = (
        root / "packages/research-local/src/opintel_research_local/persistence.py"
    ).read_text()
    assert "logging.info(document" not in worker
    assert "logging.info(snapshot" not in worker
    assert '"body_b64"' in egress  # ephemeral private transport payload only
    assert '"body_b64"' not in egress[egress.index("logging.info") :]
    assert "LargeBinary" not in persistence
    assert "mapped_column(LargeBinary" not in persistence
    assert "put_object" not in worker
