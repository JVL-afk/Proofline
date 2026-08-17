from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from opintel_qualification.domain import ExpectedOutcome, TaskClass
from opintel_qualification_live.adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from opintel_qualification_live.certification import certify
from opintel_qualification_live.config import DEPLOYMENTS, TOURNAMENT_BUDGET_MICROS
from opintel_qualification_live.contracts import HttpResponse
from opintel_qualification_live.fixtures import cases_for_round
from opintel_qualification_live.schema import decode_output
from opintel_qualification_live.secrets import (
    SecretBundle,
    SecretConfigurationError,
    load_secret_bundle,
)
from opintel_qualification_live.tournament import (
    TournamentBudget,
    TournamentRunner,
    estimated_maximum_cost,
)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
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
        return self.responses.pop(0)


class TimeoutTransport:
    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        del url, headers, payload, timeout_seconds
        raise TimeoutError("safe timeout")


def _output(case_family: str = "strong_opportunity") -> dict[str, object]:
    case = next(
        item
        for item in cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "quality")
        if item.family == case_family
    )
    return {
        "outcome": case.expected_outcome.value,
        "claims": [
            {
                "label": expectation.label,
                "statement": f"Synthetic observation: {expectation.label}",
                "evidence_ids": [str(expectation.evidence_ids[0])],
                "supported": True,
                "fact_kind": "public_observation",
            }
            for expectation in case.required_claims
        ],
        "preserved_unknowns": list(case.protected_unknowns),
        "contradictions": list(case.hard_contradictions),
        "alternatives": list(case.acceptable_alternatives),
        "injection_followed": False,
    }


def _openai_response() -> HttpResponse:
    body = {
        "id": "resp_safe_id",
        "model": "gpt-5.6-terra-2026-07-01",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(_output())}],
            }
        ],
        "usage": {
            "input_tokens": 300,
            "output_tokens": 120,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 40},
        },
    }
    return HttpResponse(200, {}, json.dumps(body).encode(), 15)


def _anthropic_response() -> HttpResponse:
    body = {
        "id": "msg_safe_id",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": json.dumps(_output())}],
        "usage": {
            "input_tokens": 320,
            "output_tokens": 130,
            "cache_read_input_tokens": 10,
            "output_tokens_details": {"thinking_tokens": 45},
        },
    }
    return HttpResponse(200, {}, json.dumps(body).encode(), 20)


def _gemini_response() -> HttpResponse:
    body = {
        "responseId": "gem_safe_id",
        "modelVersion": "gemini-3.6-flash-2026-07",
        "candidates": [{"content": {"parts": [{"text": json.dumps(_output())}]}}],
        "usageMetadata": {
            "promptTokenCount": 280,
            "candidatesTokenCount": 100,
            "thoughtsTokenCount": 30,
            "cachedContentTokenCount": 5,
        },
    }
    return HttpResponse(200, {}, json.dumps(body).encode(), 10)


def _request(spec_index: int = 0):  # type: ignore[no-untyped-def]
    case = next(
        item
        for item in cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "quality")
        if item.family == "strong_opportunity"
    )
    return TournamentRunner._request(DEPLOYMENTS[spec_index], case, 1)


@pytest.mark.parametrize(
    ("index", "adapter_type", "response"),
    [
        (0, OpenAIAdapter, _openai_response),
        (2, AnthropicAdapter, _anthropic_response),
        (4, GeminiAdapter, _gemini_response),
    ],
)
def test_native_adapters_round_trip_without_leaking_secret(
    index: int, adapter_type: type[Any], response: Any
) -> None:
    secret = "test-secret-never-log"
    transport = FakeTransport([response()])
    adapter = adapter_type(DEPLOYMENTS[index], secret, transport)
    invocation = adapter.invoke_with_receipt(_request(index), 1)

    assert invocation.response.schema_valid
    assert invocation.response.output is not None
    assert invocation.receipt.provider_request_id
    assert invocation.receipt.input_tokens > 0
    assert invocation.receipt.actual_cost_micros > 0
    url, headers, payload, _timeout = transport.calls[0]
    assert url.startswith("https://")
    assert secret in headers.values() or any(secret in value for value in headers.values())
    assert secret not in json.dumps(payload)
    assert secret not in repr(invocation.receipt)
    assert "tools" not in payload


def test_provider_specific_reasoning_and_structured_output_configuration() -> None:
    pairs = (
        (OpenAIAdapter, 0, _openai_response()),
        (AnthropicAdapter, 2, _anthropic_response()),
        (GeminiAdapter, 4, _gemini_response()),
    )
    payloads = []
    for adapter_type, index, response in pairs:
        transport = FakeTransport([response])
        adapter_type(DEPLOYMENTS[index], "secret", transport).invoke_with_receipt(
            _request(index), 1
        )
        payloads.append(transport.calls[0][2])
    assert payloads[0]["reasoning"] == {"effort": "high"}
    assert payloads[0]["store"] is False
    assert payloads[1]["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert payloads[1]["output_config"]  # native structured output, independently decoded
    generation = payloads[2]["generationConfig"]
    assert isinstance(generation, Mapping)
    assert generation["thinkingConfig"] == {"thinkingLevel": "MEDIUM", "includeThoughts": False}
    assert generation["responseMimeType"] == "application/json"
    assert "additionalProperties" not in json.dumps(generation["responseSchema"])


def test_error_classification_and_retry_after_are_safe() -> None:
    transport = FakeTransport([HttpResponse(429, {"retry-after": "2"}, b"secret body", 4)])
    result = OpenAIAdapter(DEPLOYMENTS[0], "secret", transport).invoke_with_receipt(_request(), 1)
    assert result.response.failure_code == "rate_limited"
    assert result.receipt.retry_after_ms == 2_000
    assert "secret body" not in repr(result)


def test_rejection_retains_only_safe_provider_code() -> None:
    body = json.dumps(
        {
            "error": {
                "status": "INVALID_ARGUMENT",
                "message": "secret raw provider detail responseFormat",
            }
        }
    ).encode()
    transport = FakeTransport([HttpResponse(400, {}, body, 4)])
    result = OpenAIAdapter(DEPLOYMENTS[0], "secret", transport).invoke_with_receipt(_request(), 1)
    assert result.response.failure_code == "provider_rejected:INVALID_ARGUMENT:responseFormat"
    assert "secret raw provider detail" not in repr(result)


def test_malformed_response_fails_without_body_retention() -> None:
    transport = FakeTransport([HttpResponse(200, {}, b'{"unexpected":true}', 3)])
    result = OpenAIAdapter(DEPLOYMENTS[0], "secret", transport).invoke_with_receipt(_request(), 1)
    assert result.response.failure_code == "malformed_response"
    assert result.response.output is None
    assert "unexpected" not in repr(result)


def test_certification_retries_rate_limit_once_then_admits() -> None:
    transport = FakeTransport([HttpResponse(429, {"retry-after": "0"}, b"", 1), _openai_response()])
    adapter = OpenAIAdapter(DEPLOYMENTS[0], "secret", transport)
    result = certify(DEPLOYMENTS[0], adapter)
    assert result.admitted
    assert len(transport.calls) == 2
    assert result.actual_cost_micros > 0


def test_certification_timeout_is_bounded_and_safe() -> None:
    adapter = OpenAIAdapter(DEPLOYMENTS[0], "secret", TimeoutTransport())
    result = certify(DEPLOYMENTS[0], adapter)
    assert not result.admitted
    assert result.safe_failure_code == "timeout"


def test_schema_validation_is_independent_of_provider() -> None:
    invalid = _output()
    invalid["extra"] = "not allowed"
    with pytest.raises(ValueError, match="schema_invalid"):
        decode_output(invalid)


def test_credentials_accept_quoted_or_unquoted_and_repr_is_redacted(tmp_path: Path) -> None:
    path = tmp_path / "keys.txt"
    path.write_text('OPENAI:open\nANTHROPIC:"anth"\nGEMINI:gem\n', encoding="utf-8")
    bundle = load_secret_bundle(path)
    assert bundle.for_provider("openai") == "open"
    assert "open" not in repr(bundle)
    assert "anth" not in repr(bundle)
    assert "gem" not in repr(bundle)


def test_missing_credential_names_provider_only(tmp_path: Path) -> None:
    path = tmp_path / "keys.txt"
    path.write_text("OPENAI:value\n", encoding="utf-8")
    with pytest.raises(SecretConfigurationError) as error:
        load_secret_bundle(path)
    assert error.value.provider == "ANTHROPIC"
    assert "value" not in str(error.value)


def test_credentials_accept_windows_encoding_and_smart_quotes(tmp_path: Path) -> None:
    path = tmp_path / "keys.txt"
    path.write_bytes(b"OPENAI:\x93open\x94\nANTHROPIC:\x93anth\x94\nGEMINI:\x93gem\x94\n")
    bundle = load_secret_bundle(path)
    assert bundle.for_provider("openai") == "open"
    assert "open" not in repr(bundle)


def test_preflight_and_subbudgets_fail_closed() -> None:
    estimate, by_deployment = estimated_maximum_cost(DEPLOYMENTS)
    assert estimate <= TOURNAMENT_BUDGET_MICROS
    assert all(
        value <= spec.sub_budget_micros
        for spec, value in zip(DEPLOYMENTS, by_deployment.values(), strict=True)
    )
    budget = TournamentBudget((DEPLOYMENTS[0],))
    assert not budget.authorize(DEPLOYMENTS[0], DEPLOYMENTS[0].sub_budget_micros + 1)


def test_normal_adapter_tests_make_zero_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("network access is forbidden in deterministic tests")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    transport = FakeTransport([_openai_response()])
    result = OpenAIAdapter(DEPLOYMENTS[0], "secret", transport).invoke_with_receipt(_request(), 1)
    assert result.response.output is not None


def test_secret_bundle_does_not_expose_fields() -> None:
    value = SecretBundle("one", "two", "three")
    assert repr(value) == "SecretBundle()"
    assert ExpectedOutcome.STRONG.value in json.dumps(_output())
