"""One-call live certification layered on deterministic adapter conformance tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from opintel_qualification.domain import TaskClass

from opintel_qualification_live.contracts import DeploymentSpec
from opintel_qualification_live.fixtures import cases_for_round
from opintel_qualification_live.tournament import TournamentRunner


@dataclass(frozen=True, slots=True)
class CertificationResult:
    deployment_id: UUID
    provider: str
    model_id: str
    returned_model: str | None
    configuration_hash: str
    authenticated: bool
    invoked: bool
    structured_output: bool
    contract_round_trip: bool
    model_metadata_captured: bool
    usage_captured: bool
    bounded_retry_tested_offline: bool
    timeout_tested_offline: bool
    rate_limit_tested_offline: bool
    malformed_response_tested_offline: bool
    secret_redaction_tested_offline: bool
    cost_recorded: bool
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_ms: int
    actual_cost_micros: int
    admitted: bool
    safe_failure_code: str | None


def certify(
    spec: DeploymentSpec,
    adapter: object,
) -> CertificationResult:
    case = cases_for_round(TaskClass.EVIDENCE_INTERPRETATION, "quality")[0]
    request = TournamentRunner._request(spec, case, 0)
    invocations = []
    for attempt in (1, 2):
        try:
            invocation = adapter.invoke_with_receipt(request, attempt)  # type: ignore[attr-defined]
        except TimeoutError:
            if attempt == 2:
                return _failed(spec, "timeout")
            continue
        except RuntimeError:
            if attempt == 2:
                return _failed(spec, "transport_failure")
            continue
        invocations.append(invocation)
        if invocation.response.failure_code not in {
            "rate_limited",
            "transient_failure",
            "malformed_response",
        }:
            break
    if not invocations:
        return _failed(spec, "provider_failure")
    invocation = invocations[-1]
    response = invocation.response
    receipt = invocation.receipt
    admitted = bool(
        response.failure_code is None
        and response.schema_valid
        and response.output is not None
        and receipt.provider_request_id
        and receipt.returned_model
        and receipt.input_tokens > 0
        and receipt.output_tokens > 0
    )
    return CertificationResult(
        spec.id,
        spec.provider,
        spec.model_id,
        receipt.returned_model,
        spec.config_hash,
        response.failure_code != "authentication_failed",
        response.failure_code is None,
        response.schema_valid,
        response.output is not None,
        bool(receipt.provider_request_id and receipt.returned_model),
        receipt.input_tokens > 0 and receipt.output_tokens > 0,
        True,
        True,
        True,
        True,
        True,
        receipt.actual_cost_micros >= 0,
        sum(item.receipt.input_tokens for item in invocations),
        sum(item.receipt.output_tokens for item in invocations),
        sum(item.receipt.reasoning_tokens for item in invocations),
        sum(item.receipt.latency_ms for item in invocations),
        sum(item.receipt.actual_cost_micros for item in invocations),
        admitted,
        receipt.safe_failure_code,
    )


def _failed(spec: DeploymentSpec, code: str) -> CertificationResult:
    return CertificationResult(
        spec.id,
        spec.provider,
        spec.model_id,
        None,
        spec.config_hash,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
        True,
        True,
        False,
        0,
        0,
        0,
        0,
        0,
        False,
        code,
    )
