"""One-shot M6.6B-3 live certification; incapable of opening Tournament II cases."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_qualification.tournament2_domain import TournamentTask
from opintel_qualification.tournament2_prefreeze import (
    DRAFT_MANIFEST,
    DRAFT_MANIFEST_HASH,
    SCHEMAS,
    PricingRevision,
    SchemaFamily,
    certification_plan,
    price_for,
)

from opintel_qualification_live.contracts import HttpResponse, JsonTransport

B2_COMMIT = "ec8b853a39906440b47db5b0c0c098befb17204d"
B2_DRAFT_MANIFEST_HASH = "f0a896720cb519625d5aa42a435a247388a5dbd51818938800f040e9907c3cf7"
CERTIFICATION_BUDGET_MICROS = 1_000_000
CERTIFICATION_WINDOW_MINUTES = 15
MAX_ATTEMPTS_PER_CALL = 2
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class AuthorizationState(StrEnum):
    ARMED = "armed"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"


class IdentityOutcome(StrEnum):
    IDENTITY_SUFFICIENT = "identity_sufficient"
    IDENTITY_CONDITIONAL = "identity_conditional"
    IDENTITY_INSUFFICIENT = "identity_insufficient"


class CertificationOutcome(StrEnum):
    CERTIFICATION_PASS = "certification_pass"
    CERTIFICATION_CONDITIONAL = "certification_conditional"
    CERTIFICATION_FAIL = "certification_fail"


class CallState(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class CertificationFixture:
    fixture_id: str
    family: SchemaFamily
    synthetic: bool
    input_text: str
    target_output: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CertificationCallDefinition:
    call_id: str
    deployment_key: str
    provider: str
    credential_provider: str
    requested_model: str
    endpoint: str
    api_revision: str
    task: TournamentTask
    schema_family: SchemaFamily
    schema_version: str
    schema_hash: str
    max_input_tokens: int
    max_output_tokens: int
    reasoning_setting: str
    storage_setting: str
    expected_max_cost_micros: int


@dataclass(frozen=True, slots=True)
class OneShotAuthorization:
    authorization_id: UUID
    state: AuthorizationState
    b2_commit: str
    draft_manifest_hash: str
    approved_deployments: tuple[str, ...]
    approved_call_ids: tuple[str, ...]
    synthetic_only: bool
    certification_schema_only: bool
    hidden_fixture_access: bool
    tournament_execution: bool
    budget_ceiling_micros: int
    approved_endpoints: tuple[str, ...]
    actor: str
    window_start: datetime
    window_end: datetime
    nonce_hash: str
    global_kill_switch_armed: bool
    budget_kill_switch_armed: bool


@dataclass(frozen=True, slots=True)
class SafeCertificationReceipt:
    call_id: str
    provider: str
    deployment_key: str
    requested_model: str
    returned_model: str | None
    endpoint: str
    api_revision: str
    task: TournamentTask
    schema_family: SchemaFamily
    schema_version: str
    schema_hash: str
    configuration_hash: str
    request_hash: str
    output_hash: str | None
    provider_request_id: str | None
    response_id: str | None
    response_status: str | None
    finish_reason: str | None
    http_status: int | None
    attempts: int
    state: CallState
    schema_accepted: bool
    structured_output_valid: bool
    semantic_contract_valid: bool
    tools_observed: bool
    identity_outcome: IdentityOutcome
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    total_tokens: int
    latency_ms: int
    pricing_version: str
    actual_cost_micros: int
    storage_setting: str
    safe_failure_code: str | None
    lineage_metadata: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CertificationRunResult:
    schema_version: str
    authorization: OneShotAuthorization
    authorization_hash: str
    started_at: datetime
    completed_at: datetime
    pricing_date: str
    reserved_maximum_cost_micros: int
    actual_cost_micros: int
    logical_calls_authorized: int
    calls_attempted: int
    calls_completed: int
    transport_attempts: int
    receipts: tuple[SafeCertificationReceipt, ...]
    deployment_outcomes: Mapping[str, CertificationOutcome]
    security_attestation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ParsedProviderResponse:
    output: object | None
    returned_model: str | None
    provider_request_id: str | None
    response_id: str | None
    response_status: str | None
    finish_reason: str | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    total_tokens: int
    tools_observed: bool
    lineage_metadata: tuple[str, ...]


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _configuration_hash(call: CertificationCallDefinition) -> str:
    return _hash(
        {
            "model": call.requested_model,
            "endpoint": call.endpoint,
            "api_revision": call.api_revision,
            "task": call.task,
            "schema_version": call.schema_version,
            "schema_hash": call.schema_hash,
            "max_output_tokens": call.max_output_tokens,
            "reasoning_setting": call.reasoning_setting,
            "storage_setting": call.storage_setting,
            "tools": False,
        }
    )


def _fixtures() -> dict[SchemaFamily, CertificationFixture]:
    reasoning_target: dict[str, object] = {
        "claims": [
            {
                "claim_id": "cert-claim-01",
                "semantic_label": "INFERENCE",
                "text": "Synthetic certification observation.",
                "evidence_ids": ["cert-evidence-01"],
                "qualifiers": ["source:synthetic_certification"],
                "economic_binding_ids": [],
            }
        ],
        "protected_unknown_ids": ["cert-unknown-internal-process"],
        "contradiction_ids": ["cert-contradiction-01"],
        "entity_ids": ["synthetic-certification-business"],
        "person_ids": [],
        "contact_ids": [],
        "cta_id": "cta-request-permission-for-conversation",
        "action_authorities": [],
        "first_party_statement_ids": [],
        "reply_safety_label": "NONE",
    }
    wording_target: dict[str, object] = {
        "rendered_text": "Synthetic wording fixture; no real business is represented.",
        "claim_ids": ["cert-claim-01"],
        "evidence_ids": ["cert-evidence-01"],
        "qualifiers": ["source:synthetic_certification"],
        "protected_unknown_ids": ["cert-unknown-internal-process"],
        "contradiction_ids": ["cert-contradiction-01"],
        "cta_id": "cta-request-permission-for-conversation",
    }
    objective_target: dict[str, object] = {
        "reply_safety_label": "WRONG_PERSON",
        "first_party_statement_ids": ["cert-statement-01"],
        "source_spans": ["synthetic span: wrong person"],
        "protected_unknown_ids": ["cert-unknown-internal-process"],
        "entity_ids": ["synthetic-certification-business"],
    }
    targets = {
        SchemaFamily.SEMANTIC_REASONING: reasoning_target,
        SchemaFamily.CONTROLLED_WORDING: wording_target,
        SchemaFamily.OBJECTIVE_EXTRACTION: objective_target,
    }
    return {
        family: CertificationFixture(
            f"m6.6b3.{family.value}.synthetic@1",
            family,
            True,
            (
                "Transport and schema certification only. Return one JSON object matching the "
                "provided schema. Copy all identifiers and protected unknowns from TARGET_OUTPUT. "
                "Do not add facts, tools, actions, people, contacts, or external information. "
                "TARGET_OUTPUT=" + json.dumps(target, sort_keys=True, separators=(",", ":"))
            ),
            target,
        )
        for family, target in targets.items()
    }


CERTIFICATION_FIXTURES = _fixtures()


def call_definitions(execution_date: str) -> tuple[CertificationCallDefinition, ...]:
    plan = certification_plan(execution_date)
    deployment_by_key = {item.key: item for item in DRAFT_MANIFEST.deployments}
    definitions = []
    for index, planned in enumerate(plan, start=1):
        deployment = deployment_by_key[planned.deployment_key]
        definitions.append(
            CertificationCallDefinition(
                f"cert-{index:02d}-{planned.deployment_key}-{planned.schema_family.value}",
                planned.deployment_key,
                deployment.provider,
                "gemini" if deployment.provider == "google" else deployment.provider,
                deployment.model,
                {
                    "openai": "https://api.openai.com/v1/responses",
                    "anthropic": "https://api.anthropic.com/v1/messages",
                    "google": "https://generativelanguage.googleapis.com/v1/interactions",
                }[deployment.provider],
                deployment.configuration.api_revision,
                planned.representative_task,
                planned.schema_family,
                f"m6.6b2.{planned.representative_task.value}.output@1",
                next(
                    item.schema_hash
                    for item in DRAFT_MANIFEST.bindings
                    if item.deployment_key == planned.deployment_key
                    and item.task == planned.representative_task
                ),
                planned.max_input_tokens,
                planned.max_output_tokens,
                deployment.configuration.reasoning_setting,
                deployment.configuration.storage_setting,
                planned.expected_max_cost_micros,
            )
        )
    return tuple(definitions)


def create_authorization(
    *,
    actor: str,
    now: datetime,
    nonce: str,
    execution_date: str,
) -> OneShotAuthorization:
    calls = call_definitions(execution_date)
    authorization = OneShotAuthorization(
        uuid5(NAMESPACE_URL, f"opintel:m6.6b3:{now.isoformat()}:{nonce}"),
        AuthorizationState.ARMED,
        B2_COMMIT,
        B2_DRAFT_MANIFEST_HASH,
        tuple(item.model for item in DRAFT_MANIFEST.deployments),
        tuple(item.call_id for item in calls),
        synthetic_only=True,
        certification_schema_only=True,
        hidden_fixture_access=False,
        tournament_execution=False,
        budget_ceiling_micros=CERTIFICATION_BUDGET_MICROS,
        approved_endpoints=tuple(dict.fromkeys(item.endpoint for item in calls)),
        actor=actor,
        window_start=now,
        window_end=now + timedelta(minutes=CERTIFICATION_WINDOW_MINUTES),
        nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
        global_kill_switch_armed=True,
        budget_kill_switch_armed=True,
    )
    validate_authorization(authorization, now=now, execution_date=execution_date)
    return authorization


def validate_authorization(
    authorization: OneShotAuthorization, *, now: datetime, execution_date: str
) -> OneShotAuthorization:
    calls = call_definitions(execution_date)
    if authorization.state is not AuthorizationState.ARMED:
        raise ValueError("certification authorization is not armed")
    if authorization.b2_commit != B2_COMMIT or authorization.draft_manifest_hash != (
        DRAFT_MANIFEST_HASH
    ):
        raise ValueError("authorization does not match the closed M6.6B-2 package")
    if B2_DRAFT_MANIFEST_HASH != DRAFT_MANIFEST_HASH:
        raise ValueError("compiled M6.6B-2 manifest hash drifted")
    if now < authorization.window_start or now > authorization.window_end:
        raise ValueError("certification authorization is outside its execution window")
    if not (
        authorization.synthetic_only
        and authorization.certification_schema_only
        and authorization.global_kill_switch_armed
        and authorization.budget_kill_switch_armed
    ):
        raise ValueError("certification safety controls are not armed")
    if authorization.hidden_fixture_access or authorization.tournament_execution:
        raise ValueError("certification authorization cannot open Tournament II")
    if authorization.approved_call_ids != tuple(item.call_id for item in calls):
        raise ValueError("certification call allowlist mismatch")
    if authorization.approved_deployments != tuple(
        item.model for item in DRAFT_MANIFEST.deployments
    ):
        raise ValueError("certification deployment allowlist mismatch")
    if authorization.approved_endpoints != tuple(dict.fromkeys(item.endpoint for item in calls)):
        raise ValueError("certification endpoint allowlist mismatch")
    reserved = sum(item.expected_max_cost_micros * MAX_ATTEMPTS_PER_CALL for item in calls)
    if reserved > authorization.budget_ceiling_micros:
        raise ValueError("certification preflight exceeds the hard budget")
    return authorization


def _schema_validate(value: object, schema: Mapping[str, object]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, Mapping):
            return False
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            return False
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        if not set(required).issubset(value):
            return False
        return all(
            isinstance(child_schema, Mapping) and _schema_validate(value[key], child_schema)
            for key, child_schema in properties.items()
            if key in value
        )
    if schema_type == "array":
        if not isinstance(value, list):
            return False
        items = schema.get("items")
        return isinstance(items, Mapping) and all(_schema_validate(item, items) for item in value)
    if schema_type == "string":
        if not isinstance(value, str):
            return False
        allowed = schema.get("enum")
        return not isinstance(allowed, list) or value in allowed
    if schema_type == "boolean":
        return isinstance(value, bool)
    return False


def _semantic_contract_valid(fixture: CertificationFixture, output: object) -> bool:
    if not isinstance(output, Mapping):
        return False
    target = fixture.target_output
    if fixture.family is SchemaFamily.SEMANTIC_REASONING:
        claims = output.get("claims")
        target_claims = target.get("claims")
        if not isinstance(claims, list) or not isinstance(target_claims, list):
            return False
        claim_ids = {item.get("claim_id") for item in claims if isinstance(item, Mapping)}
        target_ids = {item.get("claim_id") for item in target_claims if isinstance(item, Mapping)}
        fields = (
            "protected_unknown_ids",
            "contradiction_ids",
            "entity_ids",
            "person_ids",
            "contact_ids",
            "cta_id",
            "action_authorities",
            "first_party_statement_ids",
        )
        return claim_ids == target_ids and all(
            output.get(field) == target.get(field) for field in fields
        )
    reference_fields = tuple(key for key in target if key != "rendered_text")
    return all(output.get(field) == target.get(field) for field in reference_fields)


def _safe_json(body: bytes) -> Mapping[str, Any]:
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("provider_response_not_object")
    return value


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parse_output_text(value: str) -> object:
    return json.loads(value)


def _parse_openai(response: HttpResponse) -> _ParsedProviderResponse:
    native = _safe_json(response.body)
    texts = []
    tools_observed = False
    for item in native.get("output", []):
        if not isinstance(item, Mapping):
            continue
        if item.get("type") != "message":
            tools_observed = True
            continue
        for content in item.get("content", []):
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                text = _string(content.get("text"))
                if text is not None:
                    texts.append(text)
    if not texts:
        raise ValueError("missing_structured_output")
    usage = _mapping(native.get("usage"))
    input_details = _mapping(usage.get("input_tokens_details"))
    output_details = _mapping(usage.get("output_tokens_details"))
    reasoning = _mapping(native.get("reasoning"))
    response_id = _string(native.get("id"))
    return _ParsedProviderResponse(
        _parse_output_text("".join(texts)),
        _string(native.get("model")),
        response.headers.get("x-request-id") or response_id,
        response_id,
        _string(native.get("status")),
        _string(native.get("status")),
        _integer(usage.get("input_tokens")),
        _integer(usage.get("output_tokens")),
        _integer(output_details.get("reasoning_tokens")),
        _integer(input_details.get("cached_tokens")),
        _integer(usage.get("total_tokens")),
        tools_observed,
        tuple(
            item
            for item in (
                f"created_at={native.get('created_at')}" if native.get("created_at") else None,
                f"reasoning_context={reasoning.get('context')}"
                if reasoning.get("context")
                else None,
            )
            if item is not None
        ),
    )


def _parse_anthropic(response: HttpResponse) -> _ParsedProviderResponse:
    native = _safe_json(response.body)
    texts = []
    tools_observed = False
    for item in native.get("content", []):
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            texts.append(str(item["text"]))
        elif item.get("type") not in {"thinking", "redacted_thinking"}:
            tools_observed = True
    if not texts:
        raise ValueError("missing_structured_output")
    usage = _mapping(native.get("usage"))
    response_id = _string(native.get("id"))
    return _ParsedProviderResponse(
        _parse_output_text("".join(texts)),
        _string(native.get("model")),
        response.headers.get("request-id") or response.headers.get("x-request-id"),
        response_id,
        "completed"
        if native.get("stop_reason") not in {None, "refusal"}
        else _string(native.get("stop_reason")),
        _string(native.get("stop_reason")),
        _integer(usage.get("input_tokens")),
        _integer(usage.get("output_tokens")),
        _integer(_mapping(usage.get("output_tokens_details")).get("thinking_tokens")),
        _integer(usage.get("cache_read_input_tokens")),
        _integer(usage.get("input_tokens")) + _integer(usage.get("output_tokens")),
        tools_observed,
        (),
    )


def _parse_google(response: HttpResponse) -> _ParsedProviderResponse:
    native = _safe_json(response.body)
    texts = []
    tools_observed = False
    for step in native.get("steps", []):
        if not isinstance(step, Mapping):
            continue
        if step.get("type") != "model_output":
            if step.get("type") != "thought":
                tools_observed = True
            continue
        for content in step.get("content", []):
            if isinstance(content, Mapping) and content.get("type") == "text":
                text = _string(content.get("text"))
                if text is not None:
                    texts.append(text)
    output_text = _string(native.get("output_text"))
    if not texts and output_text is not None:
        texts.append(output_text)
    if not texts:
        raise ValueError("missing_structured_output")
    usage = _mapping(native.get("usage"))
    response_id = _string(native.get("id"))
    return _ParsedProviderResponse(
        _parse_output_text("".join(texts)),
        _string(native.get("model")),
        response.headers.get("x-request-id") or response_id,
        response_id,
        _string(native.get("status")),
        _string(native.get("status")),
        _integer(usage.get("total_input_tokens")),
        _integer(usage.get("total_output_tokens")),
        _integer(usage.get("total_thought_tokens")),
        _integer(usage.get("total_cached_tokens")),
        _integer(usage.get("total_tokens")),
        tools_observed or _integer(usage.get("total_tool_use_tokens")) > 0,
        tuple(
            item
            for item in (
                f"created={native.get('created')}" if native.get("created") else None,
                f"updated={native.get('updated')}" if native.get("updated") else None,
            )
            if item is not None
        ),
    )


def _payload(call: CertificationCallDefinition, fixture: CertificationFixture) -> dict[str, object]:
    schema = SCHEMAS[call.schema_family]
    if call.provider == "openai":
        return {
            "model": call.requested_model,
            "input": fixture.input_text,
            "reasoning": {"effort": "high", "context": "current_turn"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"m66b3_{call.schema_family.value}",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": call.max_output_tokens,
            "store": False,
            "background": False,
        }
    if call.provider == "anthropic":
        effort = "high" if call.schema_family is SchemaFamily.SEMANTIC_REASONING else "medium"
        return {
            "model": call.requested_model,
            "max_tokens": call.max_output_tokens,
            "system": (
                "Synthetic transport/schema certification only. No tools, external data, or new "
                "facts. Return only the structured output."
            ),
            "messages": [{"role": "user", "content": fixture.input_text}],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }
    return {
        "model": call.requested_model,
        "input": fixture.input_text,
        "store": False,
        "background": False,
        "generation_config": {
            "max_output_tokens": call.max_output_tokens,
            "thinking_level": ("low" if call.requested_model == "gemini-3.6-flash" else "minimal"),
            "thinking_summaries": "none",
        },
        "tool_choice": "none",
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
    }


def _headers(call: CertificationCallDefinition, credential: str) -> dict[str, str]:
    if call.provider == "openai":
        return {"Authorization": f"Bearer {credential}", "Content-Type": "application/json"}
    if call.provider == "anthropic":
        return {
            "x-api-key": credential,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {"x-goog-api-key": credential, "Content-Type": "application/json"}


def _parse(call: CertificationCallDefinition, response: HttpResponse) -> _ParsedProviderResponse:
    return {
        "openai": _parse_openai,
        "anthropic": _parse_anthropic,
        "google": _parse_google,
    }[call.provider](response)


def _identity(call: CertificationCallDefinition, returned: str | None) -> IdentityOutcome:
    if returned != call.requested_model:
        return IdentityOutcome.IDENTITY_INSUFFICIENT
    if call.provider == "anthropic":
        return IdentityOutcome.IDENTITY_SUFFICIENT
    return IdentityOutcome.IDENTITY_CONDITIONAL


def _safe_failure_code(response: HttpResponse) -> str:
    if response.status in TRANSIENT_HTTP_STATUSES:
        return f"transient_http_{response.status}"
    try:
        error = _mapping(_safe_json(response.body).get("error"))
        candidate = error.get("status") or error.get("type") or error.get("code")
        if isinstance(candidate, (str, int)):
            safe = "".join(
                character
                for character in str(candidate)
                if character.isalnum() or character in "_.-"
            )[:64]
            return f"provider_rejected:{safe or response.status}"
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return f"provider_rejected:http_{response.status}"


def _cost_micros(
    pricing: PricingRevision,
    *,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    cached_tokens: int,
) -> int:
    uncached = max(0, input_tokens - cached_tokens)
    billed_output = output_tokens + reasoning_tokens if provider == "google" else output_tokens
    cached_rate = pricing.cached_input_usd_per_million or pricing.input_usd_per_million
    value = (
        Decimal(uncached) * pricing.input_usd_per_million
        + Decimal(cached_tokens) * cached_rate
        + Decimal(billed_output) * pricing.output_usd_per_million
    )
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _failed_receipt(
    call: CertificationCallDefinition,
    *,
    state: CallState,
    attempts: int,
    latency_ms: int,
    http_status: int | None,
    failure: str,
    pricing: PricingRevision,
    provider_request_id: str | None = None,
) -> SafeCertificationReceipt:
    return SafeCertificationReceipt(
        call_id=call.call_id,
        provider=call.provider,
        deployment_key=call.deployment_key,
        requested_model=call.requested_model,
        returned_model=None,
        endpoint=call.endpoint,
        api_revision=call.api_revision,
        task=call.task,
        schema_family=call.schema_family,
        schema_version=call.schema_version,
        schema_hash=call.schema_hash,
        configuration_hash=_configuration_hash(call),
        request_hash=_hash(
            {
                "call_id": call.call_id,
                "fixture": CERTIFICATION_FIXTURES[call.schema_family].fixture_id,
            }
        ),
        output_hash=None,
        provider_request_id=provider_request_id,
        response_id=None,
        response_status=None,
        finish_reason=None,
        http_status=http_status,
        attempts=attempts,
        state=state,
        schema_accepted=False,
        structured_output_valid=False,
        semantic_contract_valid=False,
        tools_observed=False,
        identity_outcome=IdentityOutcome.IDENTITY_INSUFFICIENT,
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        cached_tokens=0,
        total_tokens=0,
        latency_ms=latency_ms,
        pricing_version=pricing.version,
        actual_cost_micros=0,
        storage_setting=call.storage_setting,
        safe_failure_code=failure,
        lineage_metadata=(),
    )


class OneShotCertificationRunner:
    def __init__(
        self,
        authorization: OneShotAuthorization,
        *,
        execution_date: str,
        now: Callable[[], datetime],
        secret_for_provider: Callable[[str], str | None],
        transport_for_provider: Callable[[str], JsonTransport],
    ) -> None:
        self._authorization = validate_authorization(
            authorization, now=now(), execution_date=execution_date
        )
        self._execution_date = execution_date
        self._now = now
        self._secret_for_provider = secret_for_provider
        self._transport_for_provider = transport_for_provider
        self._consumed = False

    def run(self) -> CertificationRunResult:
        if self._consumed:
            raise RuntimeError("one-shot certification authorization already consumed")
        self._consumed = True
        started = self._now()
        calls = call_definitions(self._execution_date)
        reserved = sum(item.expected_max_cost_micros * MAX_ATTEMPTS_PER_CALL for item in calls)
        if reserved > self._authorization.budget_ceiling_micros:
            raise RuntimeError("budget kill switch stopped certification before execution")
        receipts = []
        actual_cost = 0
        for call in calls:
            if self._now() > self._authorization.window_end:
                receipts.append(
                    _failed_receipt(
                        call,
                        state=CallState.NOT_ATTEMPTED,
                        attempts=0,
                        latency_ms=0,
                        http_status=None,
                        failure="authorization_window_expired",
                        pricing=price_for(call.deployment_key, self._execution_date),
                    )
                )
                continue
            credential = self._secret_for_provider(call.credential_provider)
            if not credential:
                receipts.append(
                    _failed_receipt(
                        call,
                        state=CallState.CREDENTIAL_UNAVAILABLE,
                        attempts=0,
                        latency_ms=0,
                        http_status=None,
                        failure="credential_unavailable",
                        pricing=price_for(call.deployment_key, self._execution_date),
                    )
                )
                continue
            remaining_reserved = call.expected_max_cost_micros * MAX_ATTEMPTS_PER_CALL
            if actual_cost + remaining_reserved > self._authorization.budget_ceiling_micros:
                receipts.append(
                    _failed_receipt(
                        call,
                        state=CallState.NOT_ATTEMPTED,
                        attempts=0,
                        latency_ms=0,
                        http_status=None,
                        failure="budget_kill_switch",
                        pricing=price_for(call.deployment_key, self._execution_date),
                    )
                )
                continue
            receipt = self._run_call(call, credential)
            actual_cost += receipt.actual_cost_micros
            receipts.append(receipt)
            if actual_cost > self._authorization.budget_ceiling_micros:
                break
        closed = replace(self._authorization, state=AuthorizationState.CONSUMED)
        receipt_tuple = tuple(receipts)
        return CertificationRunResult(
            "m6.6b3.live-certification@1",
            closed,
            _hash(asdict(closed)),
            started,
            self._now(),
            self._execution_date,
            reserved,
            actual_cost,
            len(calls),
            sum(item.attempts > 0 for item in receipt_tuple),
            sum(item.state is CallState.COMPLETED for item in receipt_tuple),
            sum(item.attempts for item in receipt_tuple),
            receipt_tuple,
            deployment_outcomes(receipt_tuple),
            (
                "synthetic certification fixtures only",
                "hidden and real data access disabled",
                "provider-specific HTTPS egress allowlists",
                "tools search files functions code and computer disabled",
                "raw request and response bodies not persisted",
                "credentials loaded only into the one-shot runner process",
                "M6 M6.5 M6.7 and application routes untouched",
            ),
        )

    def _run_call(
        self, call: CertificationCallDefinition, credential: str
    ) -> SafeCertificationReceipt:
        fixture = CERTIFICATION_FIXTURES[call.schema_family]
        if not fixture.synthetic:
            raise RuntimeError("non-synthetic certification fixture denied")
        payload = _payload(call, fixture)
        request_hash = _hash(payload)
        transport = self._transport_for_provider(call.provider)
        pricing = price_for(call.deployment_key, self._execution_date)
        latency = 0
        for attempt in range(1, MAX_ATTEMPTS_PER_CALL + 1):
            try:
                response = transport.post(call.endpoint, _headers(call, credential), payload, 90.0)
            except TimeoutError:
                if attempt < MAX_ATTEMPTS_PER_CALL:
                    continue
                return _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=None,
                    failure="transient_transport_failure",
                    pricing=pricing,
                )
            except RuntimeError as error:
                if str(error) != "provider_transport_failure":
                    raise
                if attempt < MAX_ATTEMPTS_PER_CALL:
                    continue
                return _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=None,
                    failure="transient_transport_failure",
                    pricing=pricing,
                )
            latency += response.latency_ms
            if response.status != 200:
                failure = _safe_failure_code(response)
                if response.status in TRANSIENT_HTTP_STATUSES and attempt < MAX_ATTEMPTS_PER_CALL:
                    continue
                return _failed_receipt(
                    call,
                    state=CallState.FAILED,
                    attempts=attempt,
                    latency_ms=latency,
                    http_status=response.status,
                    failure=failure,
                    pricing=pricing,
                    provider_request_id=(
                        response.headers.get("x-request-id") or response.headers.get("request-id")
                    ),
                )
            try:
                parsed = _parse(call, response)
            except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
                return _failed_receipt(
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
            schema_valid = _schema_validate(parsed.output, SCHEMAS[call.schema_family])
            semantic_valid = schema_valid and _semantic_contract_valid(fixture, parsed.output)
            cost = _cost_micros(
                pricing,
                provider=call.provider,
                input_tokens=parsed.input_tokens,
                output_tokens=parsed.output_tokens,
                reasoning_tokens=parsed.reasoning_tokens,
                cached_tokens=parsed.cached_tokens,
            )
            identity = _identity(call, parsed.returned_model)
            return SafeCertificationReceipt(
                call.call_id,
                call.provider,
                call.deployment_key,
                call.requested_model,
                parsed.returned_model,
                call.endpoint,
                call.api_revision,
                call.task,
                call.schema_family,
                call.schema_version,
                call.schema_hash,
                _configuration_hash(call),
                request_hash,
                _hash(parsed.output) if parsed.output is not None else None,
                parsed.provider_request_id,
                parsed.response_id,
                parsed.response_status,
                parsed.finish_reason,
                response.status,
                attempt,
                CallState.COMPLETED,
                True,
                schema_valid,
                semantic_valid,
                parsed.tools_observed,
                identity,
                parsed.input_tokens,
                parsed.output_tokens,
                parsed.reasoning_tokens,
                parsed.cached_tokens,
                parsed.total_tokens,
                latency,
                pricing.version,
                cost,
                call.storage_setting,
                None
                if schema_valid and semantic_valid and not parsed.tools_observed
                else "certification_contract_invalid",
                parsed.lineage_metadata,
            )
        raise AssertionError("bounded attempt loop exhausted unexpectedly")


def deployment_outcomes(
    receipts: tuple[SafeCertificationReceipt, ...],
) -> dict[str, CertificationOutcome]:
    grouped: dict[str, list[SafeCertificationReceipt]] = {}
    for receipt in receipts:
        grouped.setdefault(receipt.deployment_key, []).append(receipt)
    outcomes = {}
    for deployment, items in grouped.items():
        if any(
            item.state is not CallState.COMPLETED
            or not item.structured_output_valid
            or not item.semantic_contract_valid
            or item.tools_observed
            or item.identity_outcome is IdentityOutcome.IDENTITY_INSUFFICIENT
            for item in items
        ):
            outcomes[deployment] = CertificationOutcome.CERTIFICATION_FAIL
        elif any(item.identity_outcome is IdentityOutcome.IDENTITY_CONDITIONAL for item in items):
            outcomes[deployment] = CertificationOutcome.CERTIFICATION_CONDITIONAL
        else:
            outcomes[deployment] = CertificationOutcome.CERTIFICATION_PASS
    return outcomes


def safe_result_dict(result: CertificationRunResult) -> dict[str, object]:
    return asdict(result)
