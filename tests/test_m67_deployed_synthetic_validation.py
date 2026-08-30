from __future__ import annotations

import json

import pytest
from opintel_research_local import SqlAlchemyResearchRepository
from opintel_research_worker.synthetic_validation import execute_synthetic_validation
from sqlalchemy import inspect, text

PROHIBITED = (
    "validation@example.invalid",
    "technician@example.invalid",
    "512-555-0199",
    "512-555-0101",
    "5125550102",
    "Synthetic Technician",
)


class StopSignal:
    def __init__(self, active: bool) -> None:
        self.active = active

    def is_active(self) -> bool:
        return self.active


def test_deployed_validation_proves_kill_switch_before_fetch() -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    result = execute_synthetic_validation(
        repository,
        "KILL_SWITCH_BLOCK_V1",
        "synthetic-kill-switch-block-v1",
        StopSignal(True),
    )

    assert result.run_status == "failed"
    assert not result.fetch_called
    assert result.snapshot_count == 0
    durable = result.safe_log_record()
    assert all(value not in durable for value in PROHIBITED)


def test_deployed_validation_persists_minimized_record_and_restore_can_inspect() -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    validation_id = "synthetic-minimized-persistence-v1"
    result = execute_synthetic_validation(
        repository,
        "MINIMIZATION_PERSISTENCE_V1",
        validation_id,
        StopSignal(False),
    )
    restored = execute_synthetic_validation(
        repository,
        "RESTORE_INSPECTION_V1",
        validation_id,
        StopSignal(True),
    )

    assert result.run_status == restored.run_status == "succeeded"
    assert result.snapshot_count == restored.snapshot_count == 1
    assert result.evidence_count == restored.evidence_count
    assert result.removed_email_count == 2
    assert result.removed_phone_count == 3
    assert result.removed_structured_contact_blocks >= 2
    assert result.source_content_sha256 != result.minimized_content_sha256
    safe_log = json.loads(result.safe_log_record())
    assert safe_log["event"] == "phase1.synthetic_validation.completed"
    assert all(value not in result.safe_log_record() for value in PROHIBITED)

    columns = {item["name"] for item in inspect(repository.engine).get_columns("page_snapshots")}
    assert columns.isdisjoint({"content", "response_headers_json", "raw_body"})
    with repository.engine.connect() as connection:
        durable = "\n".join(
            repr(dict(row))
            for table in (
                "page_snapshots",
                "extracted_material",
                "research_evidence",
                "research_capture_quarantines",
            )
            for row in connection.execute(text(f'SELECT * FROM "{table}"')).mappings()
        )
    assert all(value not in durable for value in PROHIBITED)


@pytest.mark.parametrize(
    ("mode", "validation_id"),
    [("UNKNOWN", "valid-id"), ("MINIMIZATION_PERSISTENCE_V1", "")],
)
def test_deployed_validation_rejects_unbounded_or_unknown_request(
    mode: str, validation_id: str
) -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    with pytest.raises(ValueError):
        execute_synthetic_validation(repository, mode, validation_id, StopSignal(True))


def test_bounded_site_crawl_synthetic_validation_proves_multi_page_v2() -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    result = execute_synthetic_validation(
        repository, "BOUNDED_SITE_CRAWL_V1", "synthetic-bounded-site-crawl-v1", StopSignal(False)
    )
    assert result.run_status == "succeeded"
    assert result.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"
    assert result.page_count >= 3
    assert "commercial_hvac" in result.captured_categories
    assert "request_service_scheduling" in result.captured_categories
    assert result.coverage_record_sha256 and len(result.coverage_record_sha256) == 64
    assert result.catalog_converged is True
    assert result.discovery_edges_persisted >= result.page_count
    assert result.stop_reasons  # deterministic stop reason recorded
    assert result.historical_rows_preserved is True
    assert all(value not in result.safe_log_record() for value in PROHIBITED)


def test_bounded_site_crawl_synthetic_validation_is_deterministic() -> None:
    def one() -> str:
        repo = SqlAlchemyResearchRepository("sqlite:///:memory:")
        res = execute_synthetic_validation(
            repo, "BOUNDED_SITE_CRAWL_V1", "synthetic-bounded-site-crawl-v1", StopSignal(False)
        )
        assert res.coverage_record_sha256 is not None
        return f"{res.captured_categories}|{res.page_count}|{res.evidence_count}"

    assert one() == one()


def test_bounded_site_crawl_synthetic_validation_blocks_on_kill_switch() -> None:
    repository = SqlAlchemyResearchRepository("sqlite:///:memory:")
    with pytest.raises(RuntimeError):
        execute_synthetic_validation(
            repository, "BOUNDED_SITE_CRAWL_V1", "synthetic-bounded-kill", StopSignal(True)
        )
