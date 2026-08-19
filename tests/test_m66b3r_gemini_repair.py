from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from opintel_qualification.tournament2_prefreeze import SCHEMAS, SchemaFamily
from opintel_qualification_live.contracts import HttpResponse
from opintel_qualification_live.tournament2_certification import (
    CERTIFICATION_FIXTURES,
    AuthorizationState,
    CertificationOutcome,
    IdentityOutcome,
)
from opintel_qualification_live.tournament2_gemini_repair import (
    CLOSURE_COMMIT,
    MAX_REPAIR_ATTEMPTS_PER_CALL,
    ORIGINAL_EVIDENCE_BLOB,
    REPAIR_BUDGET_MICROS,
    GeminiCertificationRepairRunner,
    RepairRootCause,
    _successor_payload,
    create_repair_authorization,
    safe_repair_result_dict,
    successor_revisions,
    validate_successor_payload,
)

EXECUTION_DATE = "2026-08-19"
NOW = datetime(2026, 8, 19, 13, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, str], Mapping[str, object], float]] = []

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((url, headers, payload, timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _success_response(model: str, family: SchemaFamily) -> HttpResponse:
    fixture = CERTIFICATION_FIXTURES[family]
    body = {
        "id": f"interaction-safe-{model}",
        "model": model,
        "status": "completed",
        "created": "2026-08-19T13:00:01Z",
        "updated": "2026-08-19T13:00:02Z",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(fixture.target_output, separators=(",", ":")),
                    }
                ],
            }
        ],
        "usage": {
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_thought_tokens": 20,
            "total_cached_tokens": 0,
            "total_tokens": 170,
            "total_tool_use_tokens": 0,
        },
    }
    return HttpResponse(200, {"x-request-id": "request-safe"}, json.dumps(body).encode(), 9)


def _authorization():  # type: ignore[no-untyped-def]
    return create_repair_authorization(
        actor="test-owner",
        now=NOW,
        nonce="repair-nonce",
        execution_date=EXECUTION_DATE,
    )


def test_successors_preserve_lineage_and_change_only_tool_choice_location() -> None:
    revisions = successor_revisions(EXECUTION_DATE)
    assert len(revisions) == 2
    assert [item.call.requested_model for item in revisions] == [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]
    assert all(item.predecessor_evidence_blob == ORIGINAL_EVIDENCE_BLOB for item in revisions)
    assert all(
        item.root_cause is RepairRootCause.OTHER_REQUEST_CONTRACT_ERROR for item in revisions
    )
    assert all(item.schema_transformation.startswith("none_exact") for item in revisions)
    assert all("MOVE tool_choice" in item.semantic_diff[0] for item in revisions)


def test_successor_payload_matches_current_stable_v1_contract() -> None:
    for revision in successor_revisions(EXECUTION_DATE):
        payload = _successor_payload(revision.call)
        validate_successor_payload(revision, payload)
        assert set(payload) == {
            "model",
            "input",
            "store",
            "background",
            "generation_config",
            "response_format",
        }
        assert "tool_choice" not in payload
        generation = payload["generation_config"]
        assert isinstance(generation, Mapping)
        assert generation["tool_choice"] == "none"
        assert "thinking_budget" not in generation
        response_format = payload["response_format"]
        assert isinstance(response_format, Mapping)
        assert response_format["type"] == "text"
        assert response_format["mime_type"] == "application/json"
        assert response_format["schema"] == SCHEMAS[revision.call.schema_family]


def test_thinking_profiles_remain_low_and_minimal() -> None:
    revisions = successor_revisions(EXECUTION_DATE)
    levels = []
    for revision in revisions:
        generation = _successor_payload(revision.call)["generation_config"]
        assert isinstance(generation, Mapping)
        levels.append(generation["thinking_level"])
    assert levels == ["low", "minimal"]


def test_legacy_or_mutually_incompatible_thinking_field_is_rejected() -> None:
    revision = successor_revisions(EXECUTION_DATE)[0]
    payload = json.loads(json.dumps(_successor_payload(revision.call)))
    payload["generation_config"]["thinking_budget"] = 128
    with pytest.raises(ValueError, match="generation_config shape"):
        validate_successor_payload(revision, payload)


def test_repair_authorization_is_gemini_only_and_bounded() -> None:
    authorization = _authorization()
    revisions = successor_revisions(EXECUTION_DATE)
    assert authorization.state is AuthorizationState.ARMED
    assert authorization.closure_commit == CLOSURE_COMMIT
    assert authorization.predecessor_evidence_blob == ORIGINAL_EVIDENCE_BLOB
    assert authorization.approved_provider == "google"
    assert not authorization.openai_calls_authorized
    assert not authorization.anthropic_calls_authorized
    assert not authorization.hidden_fixture_access
    assert not authorization.tournament_execution
    assert authorization.maximum_primary_calls == 2
    reserved = sum(
        item.expected_max_cost_micros * MAX_REPAIR_ATTEMPTS_PER_CALL for item in revisions
    )
    assert reserved == 26_578
    assert reserved < REPAIR_BUDGET_MICROS


def test_successful_repair_is_schema_valid_but_identity_conditional() -> None:
    revisions = successor_revisions(EXECUTION_DATE)
    transport = FakeTransport(
        [
            _success_response(item.call.requested_model, item.call.schema_family)
            for item in revisions
        ]
    )
    runner = GeminiCertificationRepairRunner(
        _authorization(),
        execution_date=EXECUTION_DATE,
        now=lambda: NOW,
        gemini_credential="test-secret",
        transport=transport,
    )
    result = runner.run()
    assert result.authorization.state is AuthorizationState.CONSUMED
    assert result.calls_attempted == 2
    assert result.calls_completed == 2
    assert result.transport_attempts == 2
    assert all(item.provider_receipt.structured_output_valid for item in result.receipts)
    assert all(item.provider_receipt.semantic_contract_valid for item in result.receipts)
    assert all(
        item.provider_receipt.identity_outcome is IdentityOutcome.IDENTITY_CONDITIONAL
        for item in result.receipts
    )
    assert set(result.deployment_outcomes.values()) == {
        CertificationOutcome.CERTIFICATION_CONDITIONAL
    }
    rendered = json.dumps(safe_repair_result_dict(result), default=str)
    assert "test-secret" not in rendered
    assert all(
        call[0] == "https://generativelanguage.googleapis.com/v1/interactions"
        for call in transport.calls
    )


def test_http_400_is_not_retried_and_retains_only_redacted_diagnostics() -> None:
    body = {
        "error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": (
                'Invalid JSON payload. Unknown name "tool_choice" at generation_config. '
                "Sensitive input text must not survive."
            ),
        }
    }
    transport = FakeTransport(
        [
            HttpResponse(
                400, {"x-request-id": "google-request-safe"}, json.dumps(body).encode(), 4
            ),
            HttpResponse(400, {}, json.dumps(body).encode(), 4),
        ]
    )
    result = GeminiCertificationRepairRunner(
        _authorization(),
        execution_date=EXECUTION_DATE,
        now=lambda: NOW,
        gemini_credential="test-secret",
        transport=transport,
    ).run()
    assert result.transport_attempts == 2
    assert all(item.provider_receipt.attempts == 1 for item in result.receipts)
    first = result.receipts[0]
    assert first.provider_receipt.provider_request_id == "google-request-safe"
    assert first.failure_diagnostic is not None
    assert first.failure_diagnostic.provider_error_code == "INVALID_ARGUMENT"
    assert "tool_choice" in first.failure_diagnostic.rejected_fields
    assert "generation_config" in first.failure_diagnostic.rejected_fields
    rendered = json.dumps(safe_repair_result_dict(result), default=str)
    assert "Sensitive input text" not in rendered
    assert "test-secret" not in rendered


def test_transient_failure_receives_only_one_retry() -> None:
    revisions = successor_revisions(EXECUTION_DATE)
    transport = FakeTransport(
        [
            TimeoutError("safe timeout"),
            _success_response(revisions[0].call.requested_model, revisions[0].call.schema_family),
            _success_response(revisions[1].call.requested_model, revisions[1].call.schema_family),
        ]
    )
    result = GeminiCertificationRepairRunner(
        _authorization(),
        execution_date=EXECUTION_DATE,
        now=lambda: NOW,
        gemini_credential="test-secret",
        transport=transport,
    ).run()
    assert result.transport_attempts == 3
    assert result.receipts[0].provider_receipt.attempts == 2


def test_original_certification_evidence_blob_remains_exact() -> None:
    path = Path("docs/evidence/m6.6b-3/certification-run-2026-08-19.json")
    assert path.is_file()
    assert ORIGINAL_EVIDENCE_BLOB == "7b2d8c6ce1f162c42a5a6fb5b3643636cc332ea1"
