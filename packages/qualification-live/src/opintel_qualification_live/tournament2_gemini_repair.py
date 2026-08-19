"""Bounded Gemini-only successor certification for the closed M6.6B-3 failures."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_qualification.tournament2_prefreeze import SCHEMAS, PricingRevision, price_for

from opintel_qualification_live.contracts import HttpResponse, JsonTransport
from opintel_qualification_live.tournament2_certification import (
    CERTIFICATION_FIXTURES,
    TRANSIENT_HTTP_STATUSES,
    AuthorizationState,
    CallState,
    CertificationCallDefinition,
    CertificationOutcome,
    SafeCertificationReceipt,
    _cost_micros,
    _failed_receipt,
    _hash,
    _identity,
    _parse,
    _payload,
    _schema_validate,
    _semantic_contract_valid,
    call_definitions,
    deployment_outcomes,
)

CLOSURE_COMMIT = "c787e0961c31fefca87cd46f09fdef32497bcb73"
ORIGINAL_EVIDENCE_BLOB = "7b2d8c6ce1f162c42a5a6fb5b3643636cc332ea1"
REPAIR_BUDGET_MICROS = 250_000
REPAIR_WINDOW_MINUTES = 15
MAX_REPAIR_ATTEMPTS_PER_CALL = 2


class RepairRootCause(StrEnum):
    OTHER_REQUEST_CONTRACT_ERROR = "other_request_contract_error"


@dataclass(frozen=True, slots=True)
class GeminiSuccessorRevision:
    revision_id: str
    predecessor_configuration_hash: str
    predecessor_evidence_blob: str
    call: CertificationCallDefinition
    root_cause: RepairRootCause
    root_cause_confidence: str
    semantic_diff: tuple[str, ...]
    schema_transformation: str
    configuration_hash: str
    expected_max_cost_micros: int


@dataclass(frozen=True, slots=True)
class GeminiCertificationRepairAuthorization:
    authorization_id: UUID
    state: AuthorizationState
    closure_commit: str
    predecessor_evidence_blob: str
    approved_revision_ids: tuple[str, ...]
    approved_revision_hashes: tuple[str, ...]
    approved_call_ids: tuple[str, ...]
    approved_models: tuple[str, ...]
    approved_provider: str
    approved_endpoint: str
    synthetic_only: bool
    certification_schema_only: bool
    hidden_fixture_access: bool
    tournament_execution: bool
    openai_calls_authorized: bool
    anthropic_calls_authorized: bool
    maximum_primary_calls: int
    budget_ceiling_micros: int
    actor: str
    window_start: datetime
    window_end: datetime
    nonce_hash: str
    global_kill_switch_armed: bool
    budget_kill_switch_armed: bool


@dataclass(frozen=True, slots=True)
class SafeGoogleFailureDiagnostic:
    provider_error_code: str | None
    safe_error_category: str
    safe_message_codes: tuple[str, ...]
    rejected_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeminiRepairReceipt:
    revision_id: str
    predecessor_configuration_hash: str
    semantic_diff: tuple[str, ...]
    provider_receipt: SafeCertificationReceipt
    failure_diagnostic: SafeGoogleFailureDiagnostic | None


@dataclass(frozen=True, slots=True)
class GeminiRepairRunResult:
    schema_version: str
    authorization: GeminiCertificationRepairAuthorization
    authorization_hash: str
    started_at: datetime
    completed_at: datetime
    pricing_date: str
    reserved_maximum_cost_micros: int
    actual_cost_micros: int
    calls_authorized: int
    calls_attempted: int
    calls_completed: int
    transport_attempts: int
    receipts: tuple[GeminiRepairReceipt, ...]
    deployment_outcomes: Mapping[str, CertificationOutcome]
    security_attestation: tuple[str, ...]


_PREDECESSOR_CONFIG_HASHES = {
    "google-gemini-3.6-flash": ("abaa2ade613f4dbacab2d9491b0d2e442c55cfa14b5ab61ca41ea3bc0debcee6"),
    "google-gemini-3.5-flash-lite": (
        "7f22e18d917d297ed7470fc9b7acc550e7686e364819a00aa318e3cf4b8a293a"
    ),
}


def _successor_payload(call: CertificationCallDefinition) -> dict[str, object]:
    fixture = CERTIFICATION_FIXTURES[call.schema_family]
    payload = _payload(call, fixture)
    generation = payload.get("generation_config")
    if not isinstance(generation, dict):
        raise ValueError("successor requires generation_config")
    tool_choice = payload.pop("tool_choice", None)
    if tool_choice != "none":
        raise ValueError("predecessor tool_choice drifted")
    generation["tool_choice"] = tool_choice
    return payload


def _configuration_hash(payload: Mapping[str, object]) -> str:
    return _hash({key: value for key, value in payload.items() if key != "input"})


def successor_revisions(execution_date: str) -> tuple[GeminiSuccessorRevision, ...]:
    originals = tuple(
        item for item in call_definitions(execution_date) if item.provider == "google"
    )
    revisions = []
    for index, original in enumerate(originals, start=1):
        call = replace(original, call_id=f"gemini-repair-{index:02d}-{original.deployment_key}")
        payload = _successor_payload(call)
        revisions.append(
            GeminiSuccessorRevision(
                revision_id=f"m6.6b3r.{original.deployment_key}.{original.schema_family.value}@2",
                predecessor_configuration_hash=_PREDECESSOR_CONFIG_HASHES[original.deployment_key],
                predecessor_evidence_blob=ORIGINAL_EVIDENCE_BLOB,
                call=call,
                root_cause=RepairRootCause.OTHER_REQUEST_CONTRACT_ERROR,
                root_cause_confidence="documentation_demonstrated_provider_detail_not_retained",
                semantic_diff=(
                    "MOVE tool_choice='none' from top-level to generation_config.tool_choice",
                    "NO_CHANGE endpoint model input schema thinking storage output ceiling or task",
                ),
                schema_transformation="none_exact_m6.6a_schema_hash_preserved",
                configuration_hash=_configuration_hash(payload),
                expected_max_cost_micros=original.expected_max_cost_micros,
            )
        )
    return tuple(revisions)


def revision_hash(revision: GeminiSuccessorRevision) -> str:
    return _hash(asdict(revision))


_FORBIDDEN_KEYS = frozenset(
    {
        "tools",
        "tool",
        "thinking_budget",
        "temperature",
        "top_p",
        "top_k",
        "candidate_count",
        "response_mime_type",
        "response_schema",
        "files",
        "file_search",
        "google_search",
        "code_execution",
        "computer_use",
        "function",
        "functions",
    }
)


def validate_successor_payload(
    revision: GeminiSuccessorRevision, payload: Mapping[str, object]
) -> None:
    expected_top_level = {
        "model",
        "input",
        "store",
        "background",
        "generation_config",
        "response_format",
    }
    if set(payload) != expected_top_level:
        raise ValueError("google successor top-level contract mismatch")
    if payload.get("model") != revision.call.requested_model:
        raise ValueError("google successor model mismatch")
    if payload.get("store") is not False or payload.get("background") is not False:
        raise ValueError("google successor storage controls mismatch")
    response_format = payload.get("response_format")
    if not isinstance(response_format, Mapping) or set(response_format) != {
        "type",
        "mime_type",
        "schema",
    }:
        raise ValueError("google successor response_format shape mismatch")
    if response_format.get("type") != "text":
        raise ValueError("google successor response_format discriminator mismatch")
    if response_format.get("mime_type") != "application/json":
        raise ValueError("google successor mime_type mismatch")
    if response_format.get("schema") != SCHEMAS[revision.call.schema_family]:
        raise ValueError("google successor schema changed")
    generation = payload.get("generation_config")
    if not isinstance(generation, Mapping) or set(generation) != {
        "max_output_tokens",
        "thinking_level",
        "thinking_summaries",
        "tool_choice",
    }:
        raise ValueError("google successor generation_config shape mismatch")
    expected_thinking = "low" if revision.call.requested_model == "gemini-3.6-flash" else "minimal"
    if generation.get("thinking_level") != expected_thinking:
        raise ValueError("google successor thinking level mismatch")
    if generation.get("thinking_summaries") != "none":
        raise ValueError("google successor thinking summary mismatch")
    if generation.get("tool_choice") != "none":
        raise ValueError("google successor tool denial mismatch")

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            if _FORBIDDEN_KEYS.intersection(value):
                raise ValueError("google successor contains forbidden capability or legacy field")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)


def create_repair_authorization(
    *, actor: str, now: datetime, nonce: str, execution_date: str
) -> GeminiCertificationRepairAuthorization:
    revisions = successor_revisions(execution_date)
    authorization = GeminiCertificationRepairAuthorization(
        authorization_id=uuid5(NAMESPACE_URL, f"opintel:m6.6b3r:{now.isoformat()}:{nonce}"),
        state=AuthorizationState.ARMED,
        closure_commit=CLOSURE_COMMIT,
        predecessor_evidence_blob=ORIGINAL_EVIDENCE_BLOB,
        approved_revision_ids=tuple(item.revision_id for item in revisions),
        approved_revision_hashes=tuple(revision_hash(item) for item in revisions),
        approved_call_ids=tuple(item.call.call_id for item in revisions),
        approved_models=tuple(item.call.requested_model for item in revisions),
        approved_provider="google",
        approved_endpoint="https://generativelanguage.googleapis.com/v1/interactions",
        synthetic_only=True,
        certification_schema_only=True,
        hidden_fixture_access=False,
        tournament_execution=False,
        openai_calls_authorized=False,
        anthropic_calls_authorized=False,
        maximum_primary_calls=2,
        budget_ceiling_micros=REPAIR_BUDGET_MICROS,
        actor=actor,
        window_start=now,
        window_end=now + timedelta(minutes=REPAIR_WINDOW_MINUTES),
        nonce_hash=_hash(nonce),
        global_kill_switch_armed=True,
        budget_kill_switch_armed=True,
    )
    return validate_repair_authorization(authorization, now=now, execution_date=execution_date)


def validate_repair_authorization(
    authorization: GeminiCertificationRepairAuthorization,
    *,
    now: datetime,
    execution_date: str,
) -> GeminiCertificationRepairAuthorization:
    revisions = successor_revisions(execution_date)
    if authorization.state is not AuthorizationState.ARMED:
        raise ValueError("Gemini repair authorization is not armed")
    if authorization.closure_commit != CLOSURE_COMMIT:
        raise ValueError("Gemini repair closure commit mismatch")
    if authorization.predecessor_evidence_blob != ORIGINAL_EVIDENCE_BLOB:
        raise ValueError("Gemini repair predecessor evidence mismatch")
    if not (authorization.window_start <= now <= authorization.window_end):
        raise ValueError("Gemini repair authorization window invalid")
    if authorization.approved_provider != "google" or authorization.approved_endpoint != (
        "https://generativelanguage.googleapis.com/v1/interactions"
    ):
        raise ValueError("Gemini repair provider or endpoint mismatch")
    if authorization.approved_models != (
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ):
        raise ValueError("Gemini repair model allowlist mismatch")
    if authorization.maximum_primary_calls != 2:
        raise ValueError("Gemini repair call ceiling mismatch")
    if authorization.approved_revision_ids != tuple(item.revision_id for item in revisions):
        raise ValueError("Gemini repair revision allowlist mismatch")
    if authorization.approved_revision_hashes != tuple(revision_hash(item) for item in revisions):
        raise ValueError("Gemini repair revision hash mismatch")
    if authorization.approved_call_ids != tuple(item.call.call_id for item in revisions):
        raise ValueError("Gemini repair call allowlist mismatch")
    if not (
        authorization.synthetic_only
        and authorization.certification_schema_only
        and authorization.global_kill_switch_armed
        and authorization.budget_kill_switch_armed
    ):
        raise ValueError("Gemini repair safety controls are not armed")
    if (
        authorization.hidden_fixture_access
        or authorization.tournament_execution
        or authorization.openai_calls_authorized
        or authorization.anthropic_calls_authorized
    ):
        raise ValueError("Gemini repair cannot open other providers or Tournament II")
    reserved = sum(
        item.expected_max_cost_micros * MAX_REPAIR_ATTEMPTS_PER_CALL for item in revisions
    )
    if reserved > authorization.budget_ceiling_micros:
        raise ValueError("Gemini repair maximum cost exceeds hard budget")
    return authorization


_KNOWN_DIAGNOSTIC_FIELDS = (
    "tool_choice",
    "response_format",
    "mime_type",
    "schema",
    "generation_config",
    "thinking_level",
    "thinking_budget",
    "model",
    "store",
    "background",
)


def _safe_failure_diagnostic(response: HttpResponse) -> SafeGoogleFailureDiagnostic:
    error: Mapping[str, Any] = {}
    try:
        native = json.loads(response.body.decode("utf-8"))
        if isinstance(native, Mapping) and isinstance(native.get("error"), Mapping):
            error = native["error"]
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    code_value = error.get("status") or error.get("type") or error.get("code")
    code = None
    if isinstance(code_value, (str, int)):
        code = "".join(
            character for character in str(code_value) if character.isalnum() or character in "_.-"
        )[:64]
    message_value = error.get("message")
    message = message_value if isinstance(message_value, str) else ""
    lowered = message.lower()
    fields = tuple(field for field in _KNOWN_DIAGNOSTIC_FIELDS if field in lowered)
    safe_codes: list[str] = []
    if "unknown" in lowered or "cannot find field" in lowered:
        safe_codes.extend(f"unknown_or_misplaced_field:{field}" for field in fields)
    if "invalid" in lowered:
        safe_codes.extend(f"invalid_field:{field}" for field in fields)
    if not safe_codes:
        safe_codes.append("provider_message_redacted")
    return SafeGoogleFailureDiagnostic(
        provider_error_code=code,
        safe_error_category=(
            "transient_http" if response.status in TRANSIENT_HTTP_STATUSES else "request_rejected"
        ),
        safe_message_codes=tuple(dict.fromkeys(safe_codes)),
        rejected_fields=fields,
    )


def _successful_receipt(
    revision: GeminiSuccessorRevision,
    *,
    response: HttpResponse,
    payload: Mapping[str, object],
    attempts: int,
    latency_ms: int,
    pricing: PricingRevision,
) -> SafeCertificationReceipt:
    call = revision.call
    fixture = CERTIFICATION_FIXTURES[call.schema_family]
    parsed = _parse(call, response)
    schema_valid = _schema_validate(parsed.output, SCHEMAS[call.schema_family])
    semantic_valid = schema_valid and _semantic_contract_valid(fixture, parsed.output)
    identity = _identity(call, parsed.returned_model)
    cost = _cost_micros(
        pricing,
        provider="google",
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        reasoning_tokens=parsed.reasoning_tokens,
        cached_tokens=parsed.cached_tokens,
    )
    return SafeCertificationReceipt(
        call_id=call.call_id,
        provider="google",
        deployment_key=call.deployment_key,
        requested_model=call.requested_model,
        returned_model=parsed.returned_model,
        endpoint=call.endpoint,
        api_revision=call.api_revision,
        task=call.task,
        schema_family=call.schema_family,
        schema_version=call.schema_version,
        schema_hash=call.schema_hash,
        configuration_hash=revision.configuration_hash,
        request_hash=_hash(payload),
        output_hash=_hash(parsed.output) if parsed.output is not None else None,
        provider_request_id=parsed.provider_request_id,
        response_id=parsed.response_id,
        response_status=parsed.response_status,
        finish_reason=parsed.finish_reason,
        http_status=response.status,
        attempts=attempts,
        state=CallState.COMPLETED,
        schema_accepted=True,
        structured_output_valid=schema_valid,
        semantic_contract_valid=semantic_valid,
        tools_observed=parsed.tools_observed,
        identity_outcome=identity,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        reasoning_tokens=parsed.reasoning_tokens,
        cached_tokens=parsed.cached_tokens,
        total_tokens=parsed.total_tokens,
        latency_ms=latency_ms,
        pricing_version=pricing.version,
        actual_cost_micros=cost,
        storage_setting=call.storage_setting,
        safe_failure_code=(
            None
            if schema_valid and semantic_valid and not parsed.tools_observed
            else "certification_contract_invalid"
        ),
        lineage_metadata=parsed.lineage_metadata,
    )


class GeminiCertificationRepairRunner:
    def __init__(
        self,
        authorization: GeminiCertificationRepairAuthorization,
        *,
        execution_date: str,
        now: Callable[[], datetime],
        gemini_credential: str | None,
        transport: JsonTransport,
    ) -> None:
        self._authorization = validate_repair_authorization(
            authorization, now=now(), execution_date=execution_date
        )
        self._execution_date = execution_date
        self._now = now
        self._gemini_credential = gemini_credential
        self._transport = transport
        self._consumed = False

    def run(self) -> GeminiRepairRunResult:
        if self._consumed:
            raise RuntimeError("one-shot Gemini repair authorization already consumed")
        self._consumed = True
        started = self._now()
        revisions = successor_revisions(self._execution_date)
        reserved = sum(
            item.expected_max_cost_micros * MAX_REPAIR_ATTEMPTS_PER_CALL for item in revisions
        )
        repair_receipts = []
        actual_cost = 0
        for revision in revisions:
            if self._now() > self._authorization.window_end:
                receipt = _failed_receipt(
                    revision.call,
                    state=CallState.NOT_ATTEMPTED,
                    attempts=0,
                    latency_ms=0,
                    http_status=None,
                    failure="authorization_window_expired",
                    pricing=price_for(revision.call.deployment_key, self._execution_date),
                )
                repair_receipts.append(
                    GeminiRepairReceipt(
                        revision.revision_id,
                        revision.predecessor_configuration_hash,
                        revision.semantic_diff,
                        replace(receipt, configuration_hash=revision.configuration_hash),
                        None,
                    )
                )
                continue
            if not self._gemini_credential:
                receipt = _failed_receipt(
                    revision.call,
                    state=CallState.CREDENTIAL_UNAVAILABLE,
                    attempts=0,
                    latency_ms=0,
                    http_status=None,
                    failure="credential_unavailable",
                    pricing=price_for(revision.call.deployment_key, self._execution_date),
                )
                repair_receipts.append(
                    GeminiRepairReceipt(
                        revision.revision_id,
                        revision.predecessor_configuration_hash,
                        revision.semantic_diff,
                        replace(receipt, configuration_hash=revision.configuration_hash),
                        None,
                    )
                )
                continue
            result = self._run_revision(revision)
            actual_cost += result.provider_receipt.actual_cost_micros
            repair_receipts.append(result)
            if actual_cost > self._authorization.budget_ceiling_micros:
                raise RuntimeError("Gemini repair budget kill switch triggered")
        closed = replace(self._authorization, state=AuthorizationState.CONSUMED)
        receipts = tuple(repair_receipts)
        provider_receipts = tuple(item.provider_receipt for item in receipts)
        return GeminiRepairRunResult(
            schema_version="m6.6b3r.gemini-certification-repair@1",
            authorization=closed,
            authorization_hash=_hash(asdict(closed)),
            started_at=started,
            completed_at=self._now(),
            pricing_date=self._execution_date,
            reserved_maximum_cost_micros=reserved,
            actual_cost_micros=actual_cost,
            calls_authorized=2,
            calls_attempted=sum(item.attempts > 0 for item in provider_receipts),
            calls_completed=sum(item.state is CallState.COMPLETED for item in provider_receipts),
            transport_attempts=sum(item.attempts for item in provider_receipts),
            receipts=receipts,
            deployment_outcomes=deployment_outcomes(provider_receipts),
            security_attestation=(
                "Gemini successor revisions only",
                "original M6.6B-3 evidence retained unchanged",
                "synthetic certification fixtures only",
                "hidden real OpenAI and Anthropic access disabled",
                "stable v1 Google endpoint and exact host allowlist",
                "tools search files functions code and computer disabled",
                "raw request and response bodies not persisted",
                "Tournament II routes and M6.7 untouched",
            ),
        )

    def _run_revision(self, revision: GeminiSuccessorRevision) -> GeminiRepairReceipt:
        call = revision.call
        payload = _successor_payload(call)
        validate_successor_payload(revision, payload)
        pricing = price_for(call.deployment_key, self._execution_date)
        latency = 0
        for attempt in range(1, MAX_REPAIR_ATTEMPTS_PER_CALL + 1):
            try:
                response = self._transport.post(
                    call.endpoint,
                    {
                        "x-goog-api-key": self._gemini_credential or "",
                        "Content-Type": "application/json",
                    },
                    payload,
                    90.0,
                )
            except TimeoutError:
                if attempt < MAX_REPAIR_ATTEMPTS_PER_CALL:
                    continue
                receipt = _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=None,
                    failure="transient_transport_failure",
                    pricing=pricing,
                )
                return GeminiRepairReceipt(
                    revision.revision_id,
                    revision.predecessor_configuration_hash,
                    revision.semantic_diff,
                    replace(
                        receipt,
                        configuration_hash=revision.configuration_hash,
                        request_hash=_hash(payload),
                    ),
                    None,
                )
            except RuntimeError as error:
                if str(error) != "provider_transport_failure":
                    raise
                if attempt < MAX_REPAIR_ATTEMPTS_PER_CALL:
                    continue
                receipt = _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=None,
                    failure="transient_transport_failure",
                    pricing=pricing,
                )
                return GeminiRepairReceipt(
                    revision.revision_id,
                    revision.predecessor_configuration_hash,
                    revision.semantic_diff,
                    replace(
                        receipt,
                        configuration_hash=revision.configuration_hash,
                        request_hash=_hash(payload),
                    ),
                    None,
                )
            latency += response.latency_ms
            if response.status != 200:
                diagnostic = _safe_failure_diagnostic(response)
                if response.status in TRANSIENT_HTTP_STATUSES and attempt < (
                    MAX_REPAIR_ATTEMPTS_PER_CALL
                ):
                    continue
                receipt = _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=response.status,
                    failure=(
                        f"provider_rejected:{diagnostic.provider_error_code or response.status}"
                    ),
                    pricing=pricing,
                    provider_request_id=(
                        response.headers.get("x-request-id") or response.headers.get("request-id")
                    ),
                )
                return GeminiRepairReceipt(
                    revision.revision_id,
                    revision.predecessor_configuration_hash,
                    revision.semantic_diff,
                    replace(
                        receipt,
                        configuration_hash=revision.configuration_hash,
                        request_hash=_hash(payload),
                    ),
                    diagnostic,
                )
            try:
                receipt = _successful_receipt(
                    revision,
                    response=response,
                    payload=payload,
                    attempts=attempt,
                    latency_ms=latency,
                    pricing=pricing,
                )
            except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
                receipt = _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=response.status,
                    failure="malformed_or_unparseable_structured_output",
                    pricing=pricing,
                    provider_request_id=(
                        response.headers.get("x-request-id") or response.headers.get("request-id")
                    ),
                )
                receipt = replace(
                    receipt,
                    configuration_hash=revision.configuration_hash,
                    request_hash=_hash(payload),
                )
            return GeminiRepairReceipt(
                revision.revision_id,
                revision.predecessor_configuration_hash,
                revision.semantic_diff,
                receipt,
                None,
            )
        raise AssertionError("bounded Gemini repair attempt loop exhausted")


def safe_repair_result_dict(result: GeminiRepairRunResult) -> dict[str, object]:
    return asdict(result)
