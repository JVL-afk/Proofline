"""Provider-neutral live-adapter support records; never contain credentials or raw payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from opintel_qualification.domain import ProviderResponse, TaskClass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    latency_ms: int


class JsonTransport(Protocol):
    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class Pricing:
    version: str
    input_micros_per_million: int
    output_micros_per_million: int
    cached_input_micros_per_million: int = 0

    def cost_micros(self, input_tokens: int, output_tokens: int, cached_tokens: int) -> int:
        uncached = max(0, input_tokens - cached_tokens)
        numerator = (
            uncached * self.input_micros_per_million
            + cached_tokens * self.cached_input_micros_per_million
            + output_tokens * self.output_micros_per_million
        )
        return (numerator + 999_999) // 1_000_000


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    id: UUID
    provider: str
    model_id: str
    deployment_version: str
    configuration: Mapping[str, object]
    config_hash: str
    pricing: Pricing
    sub_budget_micros: int


@dataclass(frozen=True, slots=True)
class ProviderReceipt:
    provider: str
    deployment_id: UUID
    task_class: TaskClass
    provider_request_id: str | None
    requested_model: str
    returned_model: str | None
    config_hash: str
    pricing_version: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    latency_ms: int
    retry_after_ms: int | None
    actual_cost_micros: int
    validation_outcome: str
    safe_failure_code: str | None
    provider_reported_cost_micros: int | None = None


@dataclass(frozen=True, slots=True)
class AdapterInvocation:
    response: ProviderResponse
    receipt: ProviderReceipt


class LiveProviderAdapter(Protocol):
    deployment_id: UUID

    def invoke_with_receipt(self, request: object, attempt: int) -> AdapterInvocation: ...
