from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from conftest import FakeClock
from fastapi.testclient import TestClient
from opintel_m0.domain import ActivityAttempt, AttemptStatus, InvalidFixtureUriError
from opintel_m0.workflow import M0WorkflowRunner
from opintel_m0_local import LocalFixtureFetcher, SqlAlchemyM0Repository
from sqlalchemy import text


@pytest.mark.integration
def test_authenticated_campaign_to_evidence_traceability(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    start_operation,
    runner: M0WorkflowRunner,
    repository: SqlAlchemyM0Repository,
) -> None:
    session = client.get("/api/v1/session", headers=auth_headers)
    assert session.status_code == 200
    assert session.json()["subject"] == "test-operator"

    campaign = create_campaign()
    started = start_operation(str(campaign["id"]), "walking-skeleton-success")
    assert started.status_code == 202
    operation_id = started.json()["id"]
    trace_id = started.json()["trace_id"]

    assert runner.run_once() is True
    assert runner.run_once() is False

    operation = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers)
    assert operation.status_code == 200
    operation_json = operation.json()
    assert operation_json["status"] == "succeeded"
    assert operation_json["trace_id"] == trace_id
    assert operation_json["attempt_count"] == 1
    assert operation_json["attempts"][0]["status"] == "succeeded"

    evidence_response = client.get(
        f"/api/v1/operations/{operation_id}/evidence", headers=auth_headers
    )
    assert evidence_response.status_code == 200
    evidence_collection = evidence_response.json()
    assert evidence_collection["count"] == 1
    evidence = evidence_collection["items"][0]
    fixture = Path("fixtures/public-web/acme-success.html").read_bytes()
    assert evidence["source_type"] == "CONTROLLED_FIXTURE"
    assert evidence["source_uri"] == "fixture://public/acme-success.html"
    assert evidence["content_sha256"] == hashlib.sha256(fixture).hexdigest()
    assert evidence["fixture_version"] == f"sha256:{hashlib.sha256(fixture).hexdigest()}"
    assert evidence["extractor_name"] == "controlled_fixture_html"
    assert evidence["fragment_locator"] == "html:title+body:visible-text[0:500]"

    single = client.get(evidence["links"]["self"], headers=auth_headers)
    assert single.status_code == 200
    assert single.json()["operation_id"] == operation_id

    with repository.engine.connect() as connection:
        events = list(
            connection.execute(
                text("SELECT event_type FROM audit_events ORDER BY occurred_at, event_type")
            ).scalars()
        )
    assert events == ["campaign.created", "operation.requested", "operation.succeeded"]


def test_invalid_input_is_rejected_before_persistence(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for invalid_uri in (
        "https://example.com/",
        "fixture://public/../secret.html",
        "fixture://private/acme-success.html",
        "fixture://public/acme-success.html?query=1",
    ):
        response = client.post(
            "/api/v1/campaigns",
            headers=auth_headers,
            json={"name": "invalid", "fixture_uri": invalid_uri},
        )
        assert response.status_code == 422

    extra = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={
            "name": "invalid",
            "fixture_uri": "fixture://public/acme-success.html",
            "unexpected": True,
        },
    )
    assert extra.status_code == 422


@pytest.mark.integration
def test_permanent_fixture_failure_is_safe_and_terminal(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    start_operation,
    runner: M0WorkflowRunner,
) -> None:
    campaign = create_campaign("fixture://public/missing.html")
    started = start_operation(str(campaign["id"]), "permanent-fixture-failure")
    operation_id = started.json()["id"]

    assert runner.run_once() is True
    operation = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers).json()
    assert operation["status"] == "failed"
    assert operation["attempt_count"] == 1
    assert operation["last_error_code"] == "fixture_permanent_failure"
    assert operation["last_error_message"] == "controlled fixture activity failed"
    assert operation["attempts"][0]["status"] == "permanent_failure"
    evidence = client.get(
        f"/api/v1/operations/{operation_id}/evidence", headers=auth_headers
    ).json()
    assert evidence == {"items": [], "count": 0}


@pytest.mark.integration
def test_transient_activity_retries_then_succeeds(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    start_operation,
    runner: M0WorkflowRunner,
    clock: FakeClock,
) -> None:
    campaign = create_campaign("fixture://public/transient-once.html")
    operation_id = start_operation(str(campaign["id"]), "transient-once").json()["id"]

    assert runner.run_once() is True
    retrying = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers).json()
    assert retrying["status"] == "retry_scheduled"
    assert retrying["attempt_count"] == 1
    assert retrying["attempts"][0]["status"] == "retryable_failure"
    assert retrying["last_error_code"] == "fixture_transient_failure"

    assert runner.run_once() is False
    clock.advance(timedelta(seconds=1))
    assert runner.run_once() is True

    succeeded = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers).json()
    assert succeeded["status"] == "succeeded"
    assert succeeded["attempt_count"] == 2
    assert [item["status"] for item in succeeded["attempts"]] == [
        "retryable_failure",
        "succeeded",
    ]


@pytest.mark.integration
def test_duplicate_command_returns_same_operation_and_one_evidence(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    start_operation,
    runner: M0WorkflowRunner,
) -> None:
    campaign = create_campaign()
    first = start_operation(str(campaign["id"]), "same-semantic-command")
    second = start_operation(str(campaign["id"]), "same-semantic-command")
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    assert runner.run_once() is True
    assert runner.run_once() is False
    evidence = client.get(first.json()["links"]["evidence"], headers=auth_headers).json()
    assert evidence["count"] == 1


@pytest.mark.integration
def test_stale_running_operation_is_recovered_after_worker_restart(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    start_operation,
    repository: SqlAlchemyM0Repository,
    runner: M0WorkflowRunner,
    clock: FakeClock,
) -> None:
    campaign = create_campaign()
    operation_id = UUID(start_operation(str(campaign["id"]), "stale-recovery").json()["id"])
    claimed = repository.claim_next_operation(clock.now(), timedelta(seconds=10))
    assert claimed is not None
    attempt = ActivityAttempt(
        id=uuid4(),
        operation_id=operation_id,
        activity_name="m0.fetch_fixture",
        activity_version="1",
        idempotency_key=f"{operation_id}:m0.fetch_fixture:1:1",
        attempt_number=1,
        status=AttemptStatus.RUNNING,
        started_at=clock.now(),
    )
    assert repository.begin_attempt(attempt) == attempt
    assert repository.begin_attempt(attempt) is None

    clock.advance(timedelta(seconds=11))
    assert runner.recover_stale() == 1
    recovered = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers).json()
    assert recovered["status"] == "retry_scheduled"
    assert recovered["attempts"][0]["error_code"] == "worker_lease_expired"

    assert runner.run_once() is True
    completed = client.get(f"/api/v1/operations/{operation_id}", headers=auth_headers).json()
    assert completed["status"] == "succeeded"
    assert completed["attempt_count"] == 2


def test_unauthorized_and_wrong_workspace_access_are_hidden(
    client: TestClient,
    auth_headers: dict[str, str],
    create_campaign,
    repository: SqlAlchemyM0Repository,
) -> None:
    assert client.get("/api/v1/session").status_code == 401
    assert (
        client.get(
            "/api/v1/session", headers={"Authorization": "Bearer definitely-wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/campaigns",
            json={"name": "unauthorized", "fixture_uri": "fixture://public/acme-success.html"},
        ).status_code
        == 401
    )

    campaign = create_campaign()
    other_workspace = UUID("00000000-0000-4000-8000-000000000099")
    assert repository.get_campaign(other_workspace, UUID(str(campaign["id"]))) is None
    assert client.get(f"/api/v1/campaigns/{uuid4()}", headers=auth_headers).status_code == 404


def test_fixture_fetcher_has_no_network_or_path_escape(
    settings,
    clock: FakeClock,
) -> None:
    fetcher = LocalFixtureFetcher(settings.fixture_root, clock)
    with pytest.raises(InvalidFixtureUriError):
        fetcher.fetch("https://example.com", 1)
    with pytest.raises(InvalidFixtureUriError):
        fetcher.fetch("fixture://public/../secret.html", 1)
