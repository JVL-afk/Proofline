"""Read-only, no-inference provider checks for the M6.6B-4A execution gate."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from opintel_qualification_live.contracts import HttpResponse


class ReadOnlyTransport(Protocol):
    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse: ...


class ProbeOutcome(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ControlPlaneProbe:
    provider: str
    model: str
    endpoint: str
    api_revision: str
    credential_label: str


@dataclass(frozen=True, slots=True)
class SafeControlPlaneReceipt:
    provider: str
    requested_model: str
    endpoint: str
    api_revision: str
    http_status: int
    outcome: ProbeOutcome
    returned_model: str | None
    latency_ms: int
    rate_limit_evidence: tuple[tuple[str, str], ...]
    body_retained: bool
    credential_retained: bool
    inference_requested: bool
    safe_failure_code: str | None


@dataclass(frozen=True, slots=True)
class ControlPlaneProbeResult:
    schema_version: str
    started_at: datetime
    completed_at: datetime
    receipts: tuple[SafeControlPlaneReceipt, ...]
    calls_attempted: int
    calls_completed: int
    inference_calls: int
    hidden_fixture_access: bool
    raw_bodies_retained: bool
    credentials_retained: bool


PROBES = (
    ControlPlaneProbe(
        "openai",
        "gpt-5.6-sol",
        "https://api.openai.com/v1/models/gpt-5.6-sol",
        "v1",
        "openai",
    ),
    ControlPlaneProbe(
        "anthropic",
        "claude-sonnet-5",
        "https://api.anthropic.com/v1/models/claude-sonnet-5",
        "anthropic-version:2023-06-01",
        "anthropic",
    ),
    ControlPlaneProbe(
        "google",
        "gemini-3.6-flash",
        "https://generativelanguage.googleapis.com/v1/models/gemini-3.6-flash",
        "v1",
        "gemini",
    ),
    ControlPlaneProbe(
        "google",
        "gemini-3.5-flash-lite",
        "https://generativelanguage.googleapis.com/v1/models/gemini-3.5-flash-lite",
        "v1",
        "gemini",
    ),
)

_RATE_LIMIT_HEADERS = frozenset(
    {
        "x-ratelimit-limit-requests",
        "x-ratelimit-limit-tokens",
        "anthropic-ratelimit-requests-limit",
        "anthropic-ratelimit-input-tokens-limit",
        "anthropic-ratelimit-output-tokens-limit",
        "retry-after",
    }
)


def _headers(probe: ControlPlaneProbe, credential: str) -> dict[str, str]:
    if probe.provider == "openai":
        return {"Authorization": f"Bearer {credential}"}
    if probe.provider == "anthropic":
        return {"x-api-key": credential, "anthropic-version": "2023-06-01"}
    return {"x-goog-api-key": credential}


def _returned_model(probe: ControlPlaneProbe, response: HttpResponse) -> str | None:
    if response.status != 200:
        return None
    try:
        body = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    value = body.get("id") if probe.provider != "google" else body.get("name")
    if not isinstance(value, str):
        return None
    return value.removeprefix("models/")


def run_control_plane_probe(
    *,
    now: Callable[[], datetime],
    secret_for_provider: Callable[[str], str | None],
    transport_for_provider: Callable[[str], ReadOnlyTransport],
) -> ControlPlaneProbeResult:
    started = now()
    receipts = []
    for probe in PROBES:
        secret = secret_for_provider(probe.credential_label)
        if not secret:
            receipts.append(
                SafeControlPlaneReceipt(
                    probe.provider,
                    probe.model,
                    probe.endpoint,
                    probe.api_revision,
                    0,
                    ProbeOutcome.FAILED,
                    None,
                    0,
                    (),
                    False,
                    False,
                    False,
                    "credential_unavailable",
                )
            )
            continue
        transport = transport_for_provider(probe.provider)
        response = transport.get(probe.endpoint, _headers(probe, secret), 15)
        returned_model = _returned_model(probe, response)
        verified = response.status == 200 and returned_model == probe.model
        receipts.append(
            SafeControlPlaneReceipt(
                probe.provider,
                probe.model,
                probe.endpoint,
                probe.api_revision,
                response.status,
                ProbeOutcome.VERIFIED if verified else ProbeOutcome.FAILED,
                returned_model,
                response.latency_ms,
                tuple(
                    sorted(
                        (name, value)
                        for name, value in response.headers.items()
                        if name in _RATE_LIMIT_HEADERS
                    )
                ),
                False,
                False,
                False,
                None if verified else f"metadata_http_{response.status}",
            )
        )
    return ControlPlaneProbeResult(
        "m6.6b4a.control-plane-probe@1",
        started,
        now(),
        tuple(receipts),
        len(receipts),
        sum(item.outcome is ProbeOutcome.VERIFIED for item in receipts),
        0,
        False,
        False,
        False,
    )


def safe_result_dict(result: ControlPlaneProbeResult) -> dict[str, object]:
    return asdict(result)
