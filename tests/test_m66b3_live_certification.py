from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from opintel_qualification.tournament2_prefreeze import DRAFT_MANIFEST_HASH, SchemaFamily
from opintel_qualification_live.contracts import HttpResponse
from opintel_qualification_live.secrets import load_available_secret_bundle
from opintel_qualification_live.tournament2_certification import (
    B2_DRAFT_MANIFEST_HASH,
    CERTIFICATION_BUDGET_MICROS,
    CERTIFICATION_FIXTURES,
    MAX_ATTEMPTS_PER_CALL,
    AuthorizationState,
    CallState,
    CertificationOutcome,
    IdentityOutcome,
    OneShotCertificationRunner,
    _payload,
    call_definitions,
    create_authorization,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

EXECUTION_DATE = "2026-08-19"
NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


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


def _native_response(provider: str, model: str, family: SchemaFamily) -> HttpResponse:
    target = CERTIFICATION_FIXTURES[family].target_output
    text = json.dumps(target, separators=(",", ":"))
    if provider == "openai":
        body = {
            "id": "resp_certification_safe",
            "model": model,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 20},
            },
        }
    elif provider == "anthropic":
        body = {
            "id": "msg_certification_safe",
            "model": model,
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": text}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "output_tokens_details": {"thinking_tokens": 20},
            },
        }
    else:
        body = {
            "id": "interaction_certification_safe",
            "model": model,
            "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}],
            "usage": {
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "total_thought_tokens": 20,
                "total_cached_tokens": 0,
                "total_tokens": 170,
                "total_tool_use_tokens": 0,
            },
        }
    return HttpResponse(200, {"x-request-id": "request-safe"}, json.dumps(body).encode(), 8)


def _runner(
    transports: dict[str, FakeTransport],
    *,
    secret_for_provider: object | None = None,
) -> OneShotCertificationRunner:
    authorization = create_authorization(
        actor="test-owner", now=NOW, nonce="synthetic-nonce", execution_date=EXECUTION_DATE
    )
    resolver = secret_for_provider or (lambda _provider: "test-secret")
    assert callable(resolver)
    return OneShotCertificationRunner(
        authorization,
        execution_date=EXECUTION_DATE,
        now=lambda: NOW,
        secret_for_provider=resolver,
        transport_for_provider=lambda provider: transports[provider],
    )


def _successful_transports() -> dict[str, FakeTransport]:
    calls = call_definitions(EXECUTION_DATE)
    grouped: dict[str, list[HttpResponse | Exception]] = {
        "openai": [],
        "anthropic": [],
        "google": [],
    }
    for call in calls:
        grouped[call.provider].append(
            _native_response(call.provider, call.requested_model, call.schema_family)
        )
    return {provider: FakeTransport(responses) for provider, responses in grouped.items()}


def test_exact_five_call_allowlist_and_budget_are_frozen() -> None:
    calls = call_definitions(EXECUTION_DATE)
    assert len(calls) == 5
    assert [item.requested_model for item in calls] == [
        "gpt-5.6-sol",
        "claude-sonnet-5",
        "claude-sonnet-5",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]
    assert {item.endpoint for item in calls} == {
        "https://api.openai.com/v1/responses",
        "https://api.anthropic.com/v1/messages",
        "https://generativelanguage.googleapis.com/v1/interactions",
    }
    reserved = sum(item.expected_max_cost_micros * MAX_ATTEMPTS_PER_CALL for item in calls)
    assert reserved == 290_934
    assert reserved < CERTIFICATION_BUDGET_MICROS
    assert B2_DRAFT_MANIFEST_HASH == DRAFT_MANIFEST_HASH


def test_authorization_is_synthetic_one_shot_and_cannot_open_tournament() -> None:
    authorization = create_authorization(
        actor="test-owner", now=NOW, nonce="synthetic-nonce", execution_date=EXECUTION_DATE
    )
    assert authorization.state is AuthorizationState.ARMED
    assert authorization.synthetic_only
    assert authorization.certification_schema_only
    assert not authorization.hidden_fixture_access
    assert not authorization.tournament_execution
    assert authorization.global_kill_switch_armed
    assert authorization.budget_kill_switch_armed


def test_payloads_bind_exact_controls_without_tools_or_secrets() -> None:
    payloads = [
        _payload(call, CERTIFICATION_FIXTURES[call.schema_family])
        for call in call_definitions(EXECUTION_DATE)
    ]
    serialized = json.dumps(payloads)
    assert "test-secret" not in serialized
    assert payloads[0]["reasoning"] == {"effort": "high", "context": "current_turn"}
    assert payloads[0]["store"] is False
    assert payloads[1]["thinking"] == {"type": "adaptive"}
    assert payloads[3]["tool_choice"] == "none"
    assert payloads[3]["store"] is False
    assert payloads[4]["background"] is False


def test_successful_run_records_only_safe_metadata_and_expected_identity() -> None:
    transports = _successful_transports()
    result = _runner(transports).run()

    assert result.authorization.state is AuthorizationState.CONSUMED
    assert result.calls_completed == 5
    assert result.transport_attempts == 5
    assert len(result.receipts) == 5
    assert result.actual_cost_micros > 0
    assert result.actual_cost_micros < CERTIFICATION_BUDGET_MICROS
    assert result.deployment_outcomes == {
        "openai-gpt-5.6-sol": CertificationOutcome.CERTIFICATION_CONDITIONAL,
        "anthropic-claude-sonnet-5": CertificationOutcome.CERTIFICATION_PASS,
        "google-gemini-3.6-flash": CertificationOutcome.CERTIFICATION_CONDITIONAL,
        "google-gemini-3.5-flash-lite": CertificationOutcome.CERTIFICATION_CONDITIONAL,
    }
    assert result.receipts[0].identity_outcome is IdentityOutcome.IDENTITY_CONDITIONAL
    assert result.receipts[1].identity_outcome is IdentityOutcome.IDENTITY_SUFFICIENT
    rendered = json.dumps(safe_result_dict(result), default=str)
    assert "test-secret" not in rendered
    assert "TARGET_OUTPUT" not in rendered
    assert all(item.structured_output_valid for item in result.receipts)
    assert all(item.semantic_contract_valid for item in result.receipts)


def test_transient_retry_is_bounded_to_one() -> None:
    transports = _successful_transports()
    transports["openai"].responses.insert(0, TimeoutError("safe timeout"))
    result = _runner(transports).run()
    assert result.receipts[0].attempts == 2
    assert result.transport_attempts == 6
    assert result.receipts[0].state is CallState.COMPLETED


def test_non_transient_transport_control_failure_stops_immediately() -> None:
    transports = _successful_transports()
    transports["openai"].responses[0] = RuntimeError("provider_host_outside_egress_allowlist")
    with pytest.raises(RuntimeError, match="outside_egress_allowlist"):
        _runner(transports).run()
    assert len(transports["openai"].calls) == 1


def test_missing_provider_credential_does_not_block_other_providers() -> None:
    transports = _successful_transports()
    result = _runner(
        transports,
        secret_for_provider=lambda provider: None if provider == "anthropic" else "secret",
    ).run()
    assert [item.state for item in result.receipts].count(CallState.CREDENTIAL_UNAVAILABLE) == 2
    assert not transports["anthropic"].calls
    assert len(transports["openai"].calls) == 1
    assert len(transports["google"].calls) == 2


def test_runner_authorization_cannot_be_reused() -> None:
    runner = _runner(_successful_transports())
    runner.run()
    with pytest.raises(RuntimeError, match="already consumed"):
        runner.run()


def test_partial_credential_loader_is_redacted(tmp_path: Path) -> None:
    path = tmp_path / "keys.txt"
    path.write_text("OPENAI:open-secret\n", encoding="utf-8")
    bundle = load_available_secret_bundle(path)
    assert bundle.for_provider("openai") == "open-secret"
    assert bundle.for_provider("anthropic") is None
    assert "open-secret" not in repr(bundle)


def test_https_transport_rejects_non_allowlisted_host_before_network() -> None:
    transport = UrllibJsonTransport(allowed_hosts=frozenset({"api.openai.com"}))
    with pytest.raises(RuntimeError, match="outside_egress_allowlist"):
        transport.post(
            "https://example.invalid/v1/responses",
            {"Authorization": "Bearer test-secret"},
            {"synthetic": True},
            1,
        )


def test_certification_fixtures_are_dedicated_synthetic_contract_shapes() -> None:
    assert set(CERTIFICATION_FIXTURES) == {
        SchemaFamily.SEMANTIC_REASONING,
        SchemaFamily.CONTROLLED_WORDING,
        SchemaFamily.OBJECTIVE_EXTRACTION,
    }
    assert all(item.synthetic for item in CERTIFICATION_FIXTURES.values())
    assert all(item.fixture_id.startswith("m6.6b3.") for item in CERTIFICATION_FIXTURES.values())
    assert all("hidden" not in item.fixture_id for item in CERTIFICATION_FIXTURES.values())
