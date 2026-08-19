"""Inert M6.6B-2 draft manifest and preflight projection machinery.

This module intentionally contains no provider transport, credential loading, hidden-corpus access,
or execution authorization. Mutable provider facts belong to dated evidence, not architecture.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Any

from opintel_qualification.domain import CorpusPartition
from opintel_qualification.tournament2_corpus import (
    CASE_FAMILIES,
    cases_for_partition,
    project_case,
)
from opintel_qualification.tournament2_domain import RecommendationDisposition, TournamentTask


class DraftManifestState(StrEnum):
    DRAFT = "draft"


class ResolutionClass(StrEnum):
    PUBLIC_DOC_RESOLVED = "public_doc_resolved"
    ACCOUNT_CONTROL_PLANE_REQUIRED = "account_control_plane_required"
    LIVE_CERTIFICATION_CALL_REQUIRED = "live_certification_call_required"
    PROVIDER_SUPPORT_REQUIRED = "provider_support_required"


class VersionIdentityStatus(StrEnum):
    PROVIDER_DOCUMENTED_PINNED = "provider_documented_pinned"
    LIVE_LINEAGE_REQUIRED = "live_lineage_required"


class SchemaFamily(StrEnum):
    SEMANTIC_REASONING = "semantic_reasoning"
    CONTROLLED_WORDING = "controlled_wording"
    OBJECTIVE_EXTRACTION = "objective_extraction"


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    endpoint: str
    api_revision: str
    reasoning_setting: str
    stateless: bool
    storage_setting: str
    structured_output_field: str
    max_output_field: str
    policy_version: str
    tools_enabled: bool = False
    browsing_enabled: bool = False
    file_access_enabled: bool = False
    function_calling_enabled: bool = False
    code_computer_enabled: bool = False
    sampling_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DraftDeployment:
    key: str
    provider: str
    model: str
    identity_status: VersionIdentityStatus
    configuration: ProviderConfiguration
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DraftTaskBinding:
    deployment_key: str
    task: TournamentTask
    schema_family: SchemaFamily
    schema_version: str
    schema_hash: str
    max_output_tokens: int
    reasoning_allowance: str
    rationale: str


@dataclass(frozen=True, slots=True)
class PricingRevision:
    version: str
    deployment_key: str
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal | None
    effective_from: str
    effective_until: str | None
    source_id: str


@dataclass(frozen=True, slots=True)
class UnresolvedField:
    provider: str
    field: str
    resolution: ResolutionClass
    blocker: bool


@dataclass(frozen=True, slots=True)
class RepetitionPolicy:
    version: str
    normal_repetitions: int
    consistency_repetitions: int
    critical_repetitions: int
    consistency_families: tuple[str, ...]
    critical_families: tuple[str, ...]
    max_retries_per_call: int

    def calls_per_binding(self) -> int:
        ordinary = len(CASE_FAMILIES) - len(self.consistency_families) - len(self.critical_families)
        return (
            ordinary * self.normal_repetitions
            + len(self.consistency_families) * self.consistency_repetitions
            + len(self.critical_families) * self.critical_repetitions
        )


@dataclass(frozen=True, slots=True)
class ReviewerPolicy:
    version: str
    primary_reviewers: int
    conditional_adjudicators: int
    project_owner_may_be_primary: bool
    blinded: bool
    randomized: bool
    minimum_candidate_preferences: int
    minimum_median_usefulness_delta: int
    minimum_median_trustworthiness_delta: int
    material_defects_allowed: int
    objective_dominance_tasks: tuple[TournamentTask, ...]
    named_assignments_resolved: bool = False


@dataclass(frozen=True, slots=True)
class CertificationCall:
    deployment_key: str
    purpose: str
    synthetic_input_class: str
    representative_task: TournamentTask
    schema_family: SchemaFamily
    max_input_tokens: int
    max_output_tokens: int
    expected_max_cost_micros: int
    metadata_required: tuple[str, ...]
    blockers_resolved: tuple[str, ...]
    second_call_adds_material_evidence: bool


@dataclass(frozen=True, slots=True)
class TokenProjection:
    task: TournamentTask
    maximum_input_tokens: int
    method: str


@dataclass(frozen=True, slots=True)
class BindingCostProjection:
    deployment_key: str
    task: TournamentTask
    expected_calls: int
    maximum_retry_eligible_calls: int
    maximum_calls: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_cost_micros: int


@dataclass(frozen=True, slots=True)
class DraftExecutionManifest:
    version: str
    state: DraftManifestState
    frozen_m66a_commit: str
    synthetic_only: bool
    hidden_fixture_access: bool
    credential_access: bool
    provider_transport: bool
    ready_for_execution: bool
    live_authorization_active: bool
    route_activation_allowed: bool
    deployments: tuple[DraftDeployment, ...]
    bindings: tuple[DraftTaskBinding, ...]
    schemas: dict[SchemaFamily, dict[str, Any]]
    pricing: tuple[PricingRevision, ...]
    field_statuses: tuple[UnresolvedField, ...]
    repetition_policy: RepetitionPolicy
    reviewer_policy: ReviewerPolicy


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


_STRING_ARRAY = {"type": "array", "items": {"type": "string"}}
_CLAIM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "claim_id": {"type": "string"},
        "semantic_label": {"type": "string", "enum": ["FACT", "INFERENCE"]},
        "text": {"type": "string"},
        "evidence_ids": _STRING_ARRAY,
        "qualifiers": _STRING_ARRAY,
        "economic_binding_ids": _STRING_ARRAY,
    },
    "required": [
        "claim_id",
        "semantic_label",
        "text",
        "evidence_ids",
        "qualifiers",
        "economic_binding_ids",
    ],
}


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


SCHEMAS: dict[SchemaFamily, dict[str, Any]] = {
    SchemaFamily.SEMANTIC_REASONING: _schema(
        {
            "claims": {"type": "array", "items": _CLAIM},
            "protected_unknown_ids": _STRING_ARRAY,
            "contradiction_ids": _STRING_ARRAY,
            "entity_ids": _STRING_ARRAY,
            "person_ids": _STRING_ARRAY,
            "contact_ids": _STRING_ARRAY,
            "cta_id": {"type": "string"},
            "action_authorities": _STRING_ARRAY,
            "first_party_statement_ids": _STRING_ARRAY,
            "reply_safety_label": {"type": "string"},
        }
    ),
    SchemaFamily.CONTROLLED_WORDING: _schema(
        {
            "rendered_text": {"type": "string"},
            "claim_ids": _STRING_ARRAY,
            "evidence_ids": _STRING_ARRAY,
            "qualifiers": _STRING_ARRAY,
            "protected_unknown_ids": _STRING_ARRAY,
            "contradiction_ids": _STRING_ARRAY,
            "cta_id": {"type": "string"},
        }
    ),
    SchemaFamily.OBJECTIVE_EXTRACTION: _schema(
        {
            "reply_safety_label": {
                "type": "string",
                "enum": [
                    "AMBIGUOUS",
                    "OPT_OUT",
                    "WRONG_PERSON",
                    "REFERRAL",
                    "FIRST_PARTY_CONFLICT",
                    "NONE",
                ],
            },
            "first_party_statement_ids": _STRING_ARRAY,
            "source_spans": _STRING_ARRAY,
            "protected_unknown_ids": _STRING_ARRAY,
            "entity_ids": _STRING_ARRAY,
        }
    ),
}


def _schema_hash(family: SchemaFamily) -> str:
    return _canonical_hash(SCHEMAS[family])


DEPLOYMENTS = (
    DraftDeployment(
        "openai-gpt-5.6-sol",
        "openai",
        "gpt-5.6-sol",
        VersionIdentityStatus.LIVE_LINEAGE_REQUIRED,
        ProviderConfiguration(
            "/v1/responses",
            "v1",
            "reasoning.effort=high; reasoning.context=current_turn",
            True,
            "store=false; background=false",
            "text.format={type:json_schema,strict:true,schema:<binding-hash>}",
            "max_output_tokens",
            "m6.6b2.synthetic-task-policy@1",
        ),
        ("openai-model-gpt-5.6-sol", "openai-responses-structured-output"),
    ),
    DraftDeployment(
        "anthropic-claude-sonnet-5",
        "anthropic",
        "claude-sonnet-5",
        VersionIdentityStatus.PROVIDER_DOCUMENTED_PINNED,
        ProviderConfiguration(
            "/v1/messages",
            "anthropic-version:2023-06-01",
            "thinking.type=adaptive; effort=high reasoning / medium wording",
            True,
            "single request; no batch, files, cache, or persisted conversation",
            "output_config.format={type:json_schema,schema:<binding-hash>}",
            "max_tokens",
            "m6.6b2.synthetic-task-policy@1",
        ),
        ("anthropic-sonnet-5", "anthropic-model-versioning"),
    ),
    DraftDeployment(
        "google-gemini-3.6-flash",
        "google",
        "gemini-3.6-flash",
        VersionIdentityStatus.LIVE_LINEAGE_REQUIRED,
        ProviderConfiguration(
            "/v1/interactions",
            "v1",
            "thinking_level=low",
            True,
            "store=false; background=false; no previous_interaction_id",
            "response_format={type:text,mime_type:application/json,schema:<binding-hash>}",
            "generation_config.max_output_tokens",
            "m6.6b2.synthetic-task-policy@1",
        ),
        ("google-api-versions", "google-interactions", "google-gemini-3.6-flash"),
    ),
    DraftDeployment(
        "google-gemini-3.5-flash-lite",
        "google",
        "gemini-3.5-flash-lite",
        VersionIdentityStatus.LIVE_LINEAGE_REQUIRED,
        ProviderConfiguration(
            "/v1/interactions",
            "v1",
            "thinking_level=minimal",
            True,
            "store=false; background=false; no previous_interaction_id",
            "response_format={type:text,mime_type:application/json,schema:<binding-hash>}",
            "generation_config.max_output_tokens",
            "m6.6b2.synthetic-task-policy@1",
        ),
        ("google-api-versions", "google-interactions", "google-latest-models"),
    ),
)


_TASK_CONFIG: dict[TournamentTask, tuple[SchemaFamily, int, str]] = {
    TournamentTask.EVIDENCE_INTERPRETATION: (
        SchemaFamily.SEMANTIC_REASONING,
        1_800,
        "High reasoning is proposed because evidence fidelity is safety-critical.",
    ),
    TournamentTask.CONTRADICTION_ANALYSIS: (
        SchemaFamily.SEMANTIC_REASONING,
        1_800,
        "High reasoning is proposed to preserve hard and alternative contradictions.",
    ),
    TournamentTask.OPPORTUNITY_REASONING: (
        SchemaFamily.SEMANTIC_REASONING,
        2_200,
        "The largest reasoning allowance supports useful hypotheses without economics authority.",
    ),
    TournamentTask.AUDIT_WORDING: (
        SchemaFamily.CONTROLLED_WORDING,
        2_400,
        "Plain bounded prose needs more visible output but no authoritative reasoning.",
    ),
    TournamentTask.OUTREACH_WORDING: (
        SchemaFamily.CONTROLLED_WORDING,
        1_000,
        "Concise permission-seeking copy receives a deliberately small output ceiling.",
    ),
    TournamentTask.REPLY_CLASSIFICATION: (
        SchemaFamily.OBJECTIVE_EXTRACTION,
        500,
        "Exact label classification needs minimal output and minimal thinking.",
    ),
    TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION: (
        SchemaFamily.OBJECTIVE_EXTRACTION,
        1_000,
        "Span extraction allows multiple statements but no new fact authority.",
    ),
}


def _binding(deployment: str, task: TournamentTask) -> DraftTaskBinding:
    family, max_output, rationale = _TASK_CONFIG[task]
    allowance = {
        "openai-gpt-5.6-sol": "high; visible output ceiling excludes unbounded continuation",
        "anthropic-claude-sonnet-5": (
            "adaptive high for reasoning, medium for wording; max_tokens includes thinking"
        ),
        "google-gemini-3.6-flash": "low thinking; output price includes thought tokens",
        "google-gemini-3.5-flash-lite": "minimal thinking; output price includes thought tokens",
    }[deployment]
    return DraftTaskBinding(
        deployment,
        task,
        family,
        f"m6.6b2.{task.value}.output@1",
        _schema_hash(family),
        max_output,
        allowance,
        rationale,
    )


BINDINGS = (
    *(
        _binding("openai-gpt-5.6-sol", task)
        for task in (
            TournamentTask.EVIDENCE_INTERPRETATION,
            TournamentTask.CONTRADICTION_ANALYSIS,
            TournamentTask.OPPORTUNITY_REASONING,
        )
    ),
    *(
        _binding("anthropic-claude-sonnet-5", task)
        for task in (
            TournamentTask.EVIDENCE_INTERPRETATION,
            TournamentTask.CONTRADICTION_ANALYSIS,
            TournamentTask.OPPORTUNITY_REASONING,
            TournamentTask.AUDIT_WORDING,
            TournamentTask.OUTREACH_WORDING,
        )
    ),
    *(
        _binding("google-gemini-3.6-flash", task)
        for task in (TournamentTask.AUDIT_WORDING, TournamentTask.OUTREACH_WORDING)
    ),
    *(
        _binding("google-gemini-3.5-flash-lite", task)
        for task in (
            TournamentTask.REPLY_CLASSIFICATION,
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
        )
    ),
)


REPETITION_POLICY = RepetitionPolicy(
    "m6.6b2.repetition@1",
    normal_repetitions=1,
    consistency_repetitions=3,
    critical_repetitions=2,
    consistency_families=(
        "strong_opportunity",
        "weak_opportunity",
        "no_opportunity_supported",
        "ambiguous_reply",
    ),
    critical_families=(
        "hard_contradiction",
        "hostile_prompt_injection",
        "qualifier_dilution",
    ),
    max_retries_per_call=1,
)


REVIEWER_POLICY = ReviewerPolicy(
    "m6.6b2.review@1",
    primary_reviewers=3,
    conditional_adjudicators=1,
    project_owner_may_be_primary=True,
    blinded=True,
    randomized=True,
    minimum_candidate_preferences=2,
    minimum_median_usefulness_delta=1,
    minimum_median_trustworthiness_delta=0,
    material_defects_allowed=0,
    objective_dominance_tasks=(
        TournamentTask.REPLY_CLASSIFICATION,
        TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
    ),
)


PRICING = (
    PricingRevision(
        "openai-gpt-5.6-sol-2026-08-19",
        "openai-gpt-5.6-sol",
        Decimal("5"),
        Decimal("30"),
        Decimal("0.50"),
        "2026-08-19",
        None,
        "openai-model-gpt-5.6-sol",
    ),
    PricingRevision(
        "anthropic-claude-sonnet-5-intro-2026-08-19",
        "anthropic-claude-sonnet-5",
        Decimal("2"),
        Decimal("10"),
        Decimal("0.20"),
        "2026-08-19",
        "2026-08-31",
        "anthropic-pricing",
    ),
    PricingRevision(
        "anthropic-claude-sonnet-5-standard-2026-09-01",
        "anthropic-claude-sonnet-5",
        Decimal("3"),
        Decimal("15"),
        Decimal("0.30"),
        "2026-09-01",
        None,
        "anthropic-pricing",
    ),
    PricingRevision(
        "google-gemini-3.6-flash-promo-2026-08-19",
        "google-gemini-3.6-flash",
        Decimal("0.75"),
        Decimal("3.75"),
        Decimal("0.075"),
        "2026-08-19",
        "2026-12-31",
        "google-pricing",
    ),
    PricingRevision(
        "google-gemini-3.6-flash-standard-2027-01-01",
        "google-gemini-3.6-flash",
        Decimal("1.50"),
        Decimal("7.50"),
        Decimal("0.15"),
        "2027-01-01",
        None,
        "google-pricing",
    ),
    PricingRevision(
        "google-gemini-3.5-flash-lite-2026-08-19",
        "google-gemini-3.5-flash-lite",
        Decimal("0.30"),
        Decimal("2.50"),
        Decimal("0.03"),
        "2026-08-19",
        None,
        "google-pricing",
    ),
)


UNRESOLVED_FIELDS = (
    *(
        UnresolvedField(provider, field, ResolutionClass.PUBLIC_DOC_RESOLVED, False)
        for provider in ("openai", "anthropic", "google")
        for field in ("public_model_catalog", "public_schema_subset", "public_pricing")
    ),
    *(
        UnresolvedField(provider, field, ResolutionClass.ACCOUNT_CONTROL_PLANE_REQUIRED, True)
        for provider in ("openai", "anthropic", "google")
        for field in (
            "deployment_availability",
            "rate_and_tier_limits",
            "endpoint_entitlement",
            "account_retention_or_zdr_setting",
        )
    ),
    *(
        UnresolvedField(provider, field, ResolutionClass.LIVE_CERTIFICATION_CALL_REQUIRED, True)
        for provider in ("openai", "anthropic", "google")
        for field in (
            "returned_model_identity",
            "exact_schema_acceptance",
            "actual_token_usage_fields",
        )
    ),
    UnresolvedField(
        "openai",
        "qualification_grade_immutable_identity",
        ResolutionClass.PROVIDER_SUPPORT_REQUIRED,
        True,
    ),
    UnresolvedField(
        "google",
        "qualification_grade_immutable_identity",
        ResolutionClass.PROVIDER_SUPPORT_REQUIRED,
        True,
    ),
)


def build_draft_manifest() -> DraftExecutionManifest:
    manifest = DraftExecutionManifest(
        "m6.6b2.draft-manifest@1",
        DraftManifestState.DRAFT,
        "a5c34b4c1d10f07fc6a97f164e38ee7b604ef16f",
        synthetic_only=True,
        hidden_fixture_access=False,
        credential_access=False,
        provider_transport=False,
        ready_for_execution=False,
        live_authorization_active=False,
        route_activation_allowed=False,
        deployments=DEPLOYMENTS,
        bindings=BINDINGS,
        schemas=SCHEMAS,
        pricing=PRICING,
        field_statuses=UNRESOLVED_FIELDS,
        repetition_policy=REPETITION_POLICY,
        reviewer_policy=REVIEWER_POLICY,
    )
    validate_draft_manifest(manifest)
    return manifest


def validate_draft_manifest(manifest: DraftExecutionManifest) -> DraftExecutionManifest:
    if manifest.state is not DraftManifestState.DRAFT:
        raise ValueError("M6.6B-2 manifest must remain DRAFT")
    if any(
        (
            manifest.hidden_fixture_access,
            manifest.credential_access,
            manifest.provider_transport,
            manifest.ready_for_execution,
            manifest.live_authorization_active,
            manifest.route_activation_allowed,
        )
    ):
        raise ValueError("draft manifest cannot grant execution or hidden-data authority")
    if {item.model for item in manifest.deployments} != {
        "gpt-5.6-sol",
        "claude-sonnet-5",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    }:
        raise ValueError("draft roster must contain exactly the four approved deployments")
    if len(manifest.bindings) != 12:
        raise ValueError("draft manifest must contain exactly twelve INCLUDE bindings")
    expected_bindings = {
        "openai-gpt-5.6-sol": {
            TournamentTask.EVIDENCE_INTERPRETATION,
            TournamentTask.CONTRADICTION_ANALYSIS,
            TournamentTask.OPPORTUNITY_REASONING,
        },
        "anthropic-claude-sonnet-5": {
            TournamentTask.EVIDENCE_INTERPRETATION,
            TournamentTask.CONTRADICTION_ANALYSIS,
            TournamentTask.OPPORTUNITY_REASONING,
            TournamentTask.AUDIT_WORDING,
            TournamentTask.OUTREACH_WORDING,
        },
        "google-gemini-3.6-flash": {
            TournamentTask.AUDIT_WORDING,
            TournamentTask.OUTREACH_WORDING,
        },
        "google-gemini-3.5-flash-lite": {
            TournamentTask.REPLY_CLASSIFICATION,
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
        },
    }
    actual_bindings = {
        deployment: {item.task for item in manifest.bindings if item.deployment_key == deployment}
        for deployment in expected_bindings
    }
    if actual_bindings != expected_bindings:
        raise ValueError("draft bindings differ from the exact approved task assignment")
    if any("subject" in item.task.value for item in manifest.bindings):
        raise ValueError("subject-line generation is excluded")
    if any(
        any(
            (
                item.configuration.tools_enabled,
                item.configuration.browsing_enabled,
                item.configuration.file_access_enabled,
                item.configuration.function_calling_enabled,
                item.configuration.code_computer_enabled,
            )
        )
        for item in manifest.deployments
    ):
        raise ValueError("all provider capabilities must remain disabled")
    if any(item.configuration.endpoint == "/v1beta/interactions" for item in manifest.deployments):
        raise ValueError("Gemini draft must use stable v1 interactions")
    if {item.resolution for item in manifest.field_statuses} != set(ResolutionClass):
        raise ValueError("all provider-field resolution classes must be represented")
    if any(
        item.blocker is (item.resolution is ResolutionClass.PUBLIC_DOC_RESOLVED)
        for item in manifest.field_statuses
    ):
        raise ValueError("unresolved fields must block while public resolutions must not")
    return manifest


def visible_token_projections() -> tuple[TokenProjection, ...]:
    """Conservative 1-byte-per-token ceilings using development/calibration only."""
    cases = cases_for_partition(CorpusPartition.DEVELOPMENT) + cases_for_partition(
        CorpusPartition.CALIBRATION
    )
    projections: list[TokenProjection] = []
    for task in _TASK_CONFIG:
        family = _TASK_CONFIG[task][0]
        serialized_sizes = []
        for case in cases:
            envelope = {
                "policy": "synthetic-only; preserve unknowns; no tools or new facts",
                "projection": asdict(project_case(case, task)),
                "output_schema": SCHEMAS[family],
            }
            serialized_sizes.append(
                len(
                    json.dumps(
                        envelope, sort_keys=True, separators=(",", ":"), default=str
                    ).encode()
                )
            )
        projections.append(
            TokenProjection(
                task,
                max(serialized_sizes),
                "maximum canonical UTF-8 bytes across DEVELOPMENT/CALIBRATION; "
                "conservative 1 byte = 1 token",
            )
        )
    return tuple(projections)


def price_for(deployment_key: str, execution_date: str) -> PricingRevision:
    matches = [
        item
        for item in PRICING
        if item.deployment_key == deployment_key
        and item.effective_from <= execution_date
        and (item.effective_until is None or execution_date <= item.effective_until)
    ]
    if len(matches) != 1:
        raise ValueError("execution-date pricing is unknown or ambiguous")
    return matches[0]


def conservative_cost_micros(
    pricing: PricingRevision, input_tokens: int, output_tokens: int, calls: int
) -> int:
    cost = Decimal(calls) * (
        Decimal(input_tokens) * pricing.input_usd_per_million
        + Decimal(output_tokens) * pricing.output_usd_per_million
    )
    return int(cost.to_integral_value(rounding=ROUND_CEILING))


def binding_cost_projections(execution_date: str) -> tuple[BindingCostProjection, ...]:
    ceilings = {item.task: item.maximum_input_tokens for item in visible_token_projections()}
    calls = REPETITION_POLICY.calls_per_binding()
    retry_calls = calls * REPETITION_POLICY.max_retries_per_call
    return tuple(
        BindingCostProjection(
            item.deployment_key,
            item.task,
            calls,
            retry_calls,
            calls + retry_calls,
            ceilings[item.task],
            item.max_output_tokens,
            conservative_cost_micros(
                price_for(item.deployment_key, execution_date),
                ceilings[item.task],
                item.max_output_tokens,
                calls + retry_calls,
            ),
        )
        for item in BINDINGS
    )


def certification_plan(execution_date: str) -> tuple[CertificationCall, ...]:
    ceilings = {item.task: item.maximum_input_tokens for item in visible_token_projections()}
    common = ("response_id", "requested_model", "returned_model", "api_revision", "usage")
    specs = (
        (
            "openai-gpt-5.6-sol",
            TournamentTask.OPPORTUNITY_REASONING,
            SchemaFamily.SEMANTIC_REASONING,
            False,
            (*common, "status", "reasoning_tokens", "cached_input_tokens"),
        ),
        (
            "anthropic-claude-sonnet-5",
            TournamentTask.OPPORTUNITY_REASONING,
            SchemaFamily.SEMANTIC_REASONING,
            True,
            (*common, "request_id_header", "stop_reason", "cache_token_fields"),
        ),
        (
            "anthropic-claude-sonnet-5",
            TournamentTask.AUDIT_WORDING,
            SchemaFamily.CONTROLLED_WORDING,
            False,
            (*common, "request_id_header", "stop_reason", "cache_token_fields"),
        ),
        (
            "google-gemini-3.6-flash",
            TournamentTask.AUDIT_WORDING,
            SchemaFamily.CONTROLLED_WORDING,
            False,
            (*common, "status", "thought_tokens", "cached_tokens", "total_tokens"),
        ),
        (
            "google-gemini-3.5-flash-lite",
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
            SchemaFamily.OBJECTIVE_EXTRACTION,
            False,
            (*common, "status", "thought_tokens", "cached_tokens", "total_tokens"),
        ),
    )
    calls = []
    for deployment, task, family, second_useful, metadata in specs:
        output = _TASK_CONFIG[task][1]
        pricing = price_for(deployment, execution_date)
        calls.append(
            CertificationCall(
                deployment,
                "prove exact frozen schema acceptance and capture qualification lineage metadata",
                "dedicated synthetic certification contract shape; no tournament case",
                task,
                family,
                ceilings[task],
                output,
                conservative_cost_micros(pricing, ceilings[task], output, 1),
                metadata,
                ("exact_schema_acceptance", "returned_model_identity", "actual_token_usage_fields"),
                second_useful,
            )
        )
    return tuple(calls)


def objective_dominance_disposition(
    task: TournamentTask,
    *,
    automated_safety_passed: bool,
    candidate_errors: int,
    deterministic_errors: int,
) -> RecommendationDisposition | None:
    """Bypass subjective review when exact-label/span performance is objectively dominated."""
    if task not in REVIEWER_POLICY.objective_dominance_tasks:
        raise ValueError("objective dominance is limited to approved objective tasks")
    if not automated_safety_passed:
        raise ValueError("hard-gate evaluation must pass before objective dominance")
    if candidate_errors < 0 or deterministic_errors < 0:
        raise ValueError("error counts cannot be negative")
    if candidate_errors > deterministic_errors:
        return RecommendationDisposition.DETERMINISTIC_SUPERIOR
    if candidate_errors == deterministic_errors:
        return RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
    return None


def draft_manifest_hash(manifest: DraftExecutionManifest) -> str:
    """Stable draft revision hash; it is lineage, never execution authorization."""
    validate_draft_manifest(manifest)
    return _canonical_hash(asdict(manifest))


DRAFT_MANIFEST = build_draft_manifest()
DRAFT_MANIFEST_HASH = draft_manifest_hash(DRAFT_MANIFEST)

MINIMAL_FALLBACK_ROSTER = (
    "openai-gpt-5.6-sol",
    "anthropic-claude-sonnet-5",
    "google-gemini-3.5-flash-lite",
)
REQUIRED_FUTURE_CREDENTIAL_CLASSES = (
    "OpenAI API project credential",
    "Anthropic API workspace credential",
    "Google Gemini API paid-project credential",
)
ADDITIONAL_PROVIDER_ACCOUNT_REQUIRED = False
