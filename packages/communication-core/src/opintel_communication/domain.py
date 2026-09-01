"""M6.8 evidence-bound communication domain.

The deterministic engine (M2-M5) is authoritative for *what may be said*. A future
provider controls only *how* permitted information is expressed. This module holds
the immutable structured semantic envelope, the structured claim manifest a
candidate must return alongside its rendered communication, and the deterministic
validation result types.

Pure dataclasses. No provider, no network, no delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

SEMANTIC_ENVELOPE_SCHEMA_VERSION = "comm.semantic_envelope@1"
CLAIM_MANIFEST_SCHEMA_VERSION = "comm.claim_manifest@1"
GENERATION_CONTRACT_VERSION = "comm.generation_contract@1"
OUTPUT_VALIDATOR_VERSION = "comm.output_validator@1"
CTA_PARSER_VERSION = "comm.cta_parser@1"


class FactStrength(StrEnum):
    """How certain a rendered clause is allowed to sound about its source.

    A rendered clause may never assert *more* certainty than the fact that
    licenses it. ``VERIFIED_FACT`` is the ceiling that nothing available in the
    envelope ever reaches: internal behaviour is always an explicit UNKNOWN.
    """

    OBSERVED_PUBLIC_TEXT = "OBSERVED_PUBLIC_TEXT"
    OBSERVED_AVAILABILITY_SIGNAL = "OBSERVED_AVAILABILITY_SIGNAL"
    PUBLISHED_SELF_CLAIM = "PUBLISHED_SELF_CLAIM"
    LICENSED_INFERENCE = "LICENSED_INFERENCE"
    LICENSED_RECOMMENDATION = "LICENSED_RECOMMENDATION"
    VERIFIED_FACT = "VERIFIED_FACT"


_STRENGTH_RANK: dict[FactStrength, int] = {
    FactStrength.OBSERVED_PUBLIC_TEXT: 1,
    FactStrength.OBSERVED_AVAILABILITY_SIGNAL: 1,
    FactStrength.PUBLISHED_SELF_CLAIM: 2,
    FactStrength.LICENSED_INFERENCE: 2,
    FactStrength.LICENSED_RECOMMENDATION: 2,
    FactStrength.VERIFIED_FACT: 3,
}


def strength_rank(value: FactStrength) -> int:
    return _STRENGTH_RANK[value]


def strength_at_most(rendered: FactStrength, source: FactStrength) -> bool:
    """Whether a clause asserted at ``rendered`` stays within ``source``."""

    return strength_rank(rendered) <= strength_rank(source)


class ClaimType(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    RECOMMENDATION = "RECOMMENDATION"
    QUESTION = "QUESTION"
    DISCLOSURE = "DISCLOSURE"
    TRANSITION = "TRANSITION"
    SALUTATION = "SALUTATION"
    CTA = "CTA"
    SIGNATURE_SLOT = "SIGNATURE_SLOT"
    NON_SUBSTANTIVE = "NON_SUBSTANTIVE"


# Clause classes whose meaning the validator must license against the envelope.
SUBSTANTIVE_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION}
)


class GenerationStatus(StrEnum):
    CANDIDATES = "CANDIDATES"
    COMMUNICATION_NOT_DISTINCTIVE_ENOUGH = "COMMUNICATION_NOT_DISTINCTIVE_ENOUGH"
    REFUSED = "REFUSED"


class CommunicationOutcome(StrEnum):
    """Terminal state of one generation attempt for a business."""

    AI_COMMUNICATION_CANDIDATE_READY = "AI_COMMUNICATION_CANDIDATE_READY"
    AI_COMMUNICATION_REJECTED = "AI_COMMUNICATION_REJECTED"
    COMMUNICATION_NOT_DISTINCTIVE_ENOUGH = "COMMUNICATION_NOT_DISTINCTIVE_ENOUGH"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    GENERATION_REFUSED = "GENERATION_REFUSED"
    ENVELOPE_STALE = "ENVELOPE_STALE"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INJECTION_CONTAINMENT = "INJECTION_CONTAINMENT"


# COMMUNICATION_NOT_DISTINCTIVE_ENOUGH is a valid, non-error terminal (owner
# decision, 2026-09-01). It never auto-triggers regeneration and never forces a
# human to override it.
VALID_NON_ERROR_TERMINALS: frozenset[CommunicationOutcome] = frozenset(
    {
        CommunicationOutcome.AI_COMMUNICATION_CANDIDATE_READY,
        CommunicationOutcome.AI_COMMUNICATION_REJECTED,
        CommunicationOutcome.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH,
    }
)


class ValidatorSeverity(StrEnum):
    HARD_FAILURE = "hard_failure"


# --------------------------------------------------------------------------
# Semantic envelope (comm.semantic_envelope@1)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceLineage:
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    opportunity_hypothesis_revision_id: UUID
    audit_revision_id: UUID
    audit_revision_hash: str
    demo_revision_id: UUID
    demo_specification_hash: str
    outreach_revision_id: UUID
    outreach_content_hash: str
    m2_m5_bundle_sha256: str
    policy_versions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class BusinessIdentity:
    display_name: str
    name_tokens: tuple[str, ...]
    exact_public_hostname: str
    identity_note: str


@dataclass(frozen=True, slots=True)
class EnvelopeFact:
    fact_id: str
    category: str
    sanitized_phrase: str
    verbatim_source_phrase: str
    fact_class: str
    page_purpose: str
    evidence_ids: tuple[UUID, ...]
    content_sha256: str
    selector_version: str
    rendered_by_deterministic_m5: bool
    reader_specific: bool
    quotable: bool
    strength: FactStrength
    usage_rule: str
    deterministic_omission_reason: str | None = None
    injection_suspected: bool = False


@dataclass(frozen=True, slots=True)
class M3FindingRef:
    finding_id: str
    kind: str
    claim_type: str
    predicate: str | None
    rendered_text: str
    supporting_excerpt: str | None
    evidence_ids: tuple[UUID, ...]
    usage_rule: str


@dataclass(frozen=True, slots=True)
class ConditionalInference:
    inference_id: str
    text: str
    required_qualifiers: tuple[str, ...]
    usage_rule: str


@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: str
    text: str
    required_qualifiers: tuple[str, ...]
    dependency_finding_ids: tuple[str, ...]
    usage_rule: str


@dataclass(frozen=True, slots=True)
class ExplicitUnknown:
    component: str
    text: str
    hard_prohibition: str | None = None


@dataclass(frozen=True, slots=True)
class CtaSemanticFrame:
    asks_for: str
    does_not_ask_for: tuple[str, ...]
    must_remain_a_question: bool
    must_not_presume_a_problem: bool


@dataclass(frozen=True, slots=True)
class StructuredCTA:
    cta_policy_version: str
    cta_intent: str
    semantic_frame: CtaSemanticFrame
    canonical_discovery_questions: tuple[str, ...]
    usage_rule: str


@dataclass(frozen=True, slots=True)
class RequiredDisclosure:
    slot_kind: str
    rule: str
    canonical_text: str | None = None
    placeholder: str | None = None


@dataclass(frozen=True, slots=True)
class MentionableDemoFacts:
    scenario_id: str
    deployment_status: str
    is_deterministic: bool
    personas_are_synthetic: bool
    integrations: str
    may_say: tuple[str, ...]
    must_not_say: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EconomicsState:
    status: str
    result_label: str
    external_use_permitted: bool
    usage_rule: str
    monthly_value: str | None = None
    annualized_value: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceArtifacts:
    subject: str
    first_contact_email: str
    follow_up_draft: str
    call_opening_script: str
    note: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    artifacts_requested: tuple[str, ...]
    candidate_count: int
    max_body_words: int
    max_subject_chars: int
    tone_bounds: tuple[str, ...]
    distinctiveness_floor: str


DEFAULT_CANDIDATE_COUNT = 3
HARD_MAX_CANDIDATE_COUNT = 5  # >3 requires an explicitly authorized evaluation run


@dataclass(frozen=True, slots=True)
class SemanticEnvelope:
    envelope_sha256: str
    generated_at: datetime
    source_lineage: SourceLineage
    business_identity: BusinessIdentity
    eligible_company_facts: tuple[EnvelopeFact, ...]
    m3_findings: tuple[M3FindingRef, ...]
    allowed_conditional_inferences: tuple[ConditionalInference, ...]
    allowed_recommendations: tuple[Recommendation, ...]
    explicit_unknowns: tuple[ExplicitUnknown, ...]
    prohibited_claims: tuple[str, ...]
    economics_state: EconomicsState
    structured_cta: StructuredCTA
    available_validation_questions: tuple[str, ...]
    mentionable_demo_facts: MentionableDemoFacts
    required_disclosures: tuple[RequiredDisclosure, ...]
    deterministic_reference_artifacts: ReferenceArtifacts
    generation_request: GenerationRequest
    schema_version: str = SEMANTIC_ENVELOPE_SCHEMA_VERSION

    # -- convenience lookups -------------------------------------------------
    def source_by_id(self, source_id: str) -> object | None:
        for fact in self.eligible_company_facts:
            if fact.fact_id == source_id:
                return fact
        for finding in self.m3_findings:
            if finding.finding_id == source_id:
                return finding
        for inference in self.allowed_conditional_inferences:
            if inference.inference_id == source_id:
                return inference
        for rec in self.allowed_recommendations:
            if rec.recommendation_id == source_id:
                return rec
        return None

    def has_distinctive_fact(self) -> bool:
        """A materially company-specific fact strong enough to anchor a
        non-generic opening exists in the envelope."""

        for fact in self.eligible_company_facts:
            if fact.injection_suspected:
                continue
            if fact.strength in (
                FactStrength.PUBLISHED_SELF_CLAIM,
                FactStrength.LICENSED_INFERENCE,
            ):
                return True
            if (
                fact.reader_specific
                and fact.quotable
                and not _is_generic_label(fact.sanitized_phrase)
            ):
                return True
        return False


# Short public labels that carry no distinguishing signal on their own.
_GENERIC_LABELS: frozenset[str] = frozenset(
    {
        "contact us",
        "contact us today!",
        "request service",
        "request a quote",
        "get a quote",
        "commercial ac",
        "commercial hvac",
        "service area",
        "service areas",
        "our service area",
        "schedule service",
        "learn more",
    }
)


def _is_generic_label(phrase: str) -> bool:
    norm = " ".join(phrase.split()).strip().lower()
    if norm in _GENERIC_LABELS:
        return True
    return len(norm.split()) <= 2 and not any(ch.isdigit() for ch in norm)


# --------------------------------------------------------------------------
# Claim manifest (comm.claim_manifest@1)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClaimManifestEntry:
    claim_id: str
    claim_type: ClaimType
    rendered_artifact: str
    rendered_span: str
    licensed_source_ids: tuple[str, ...]
    qualifiers: tuple[str, ...] = ()
    asserted_strength: FactStrength | None = None
    cta_intent: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimManifest:
    entries: tuple[ClaimManifestEntry, ...]
    schema_version: str = CLAIM_MANIFEST_SCHEMA_VERSION


# --------------------------------------------------------------------------
# Generation result (produced by a future provider adapter; not authoritative)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    kind: str
    text: str


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    provider: str
    model: str
    model_version: str
    request_id: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class GenerationCandidate:
    candidate_id: str
    artifacts: tuple[GeneratedArtifact, ...]
    claim_manifest: ClaimManifest
    lead_source_id: str | None = None
    self_report: tuple[tuple[str, str], ...] = ()

    def artifact(self, kind: str) -> GeneratedArtifact | None:
        for item in self.artifacts:
            if item.kind == kind:
                return item
        return None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    status: GenerationStatus
    candidates: tuple[GenerationCandidate, ...] = ()
    reason: str | None = None
    provider_metadata: ProviderMetadata | None = None


# --------------------------------------------------------------------------
# Validation result (produced by the deterministic validator; authoritative)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidatorFinding:
    code: str
    message: str
    severity: ValidatorSeverity = ValidatorSeverity.HARD_FAILURE
    artifact_kind: str | None = None
    span: str | None = None
    claim_id: str | None = None
    concept: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    candidate_id: str
    passed: bool
    findings: tuple[ValidatorFinding, ...] = ()
    validator_version: str = OUTPUT_VALIDATOR_VERSION
    cta_parser_version: str = CTA_PARSER_VERSION

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(sorted({f.code for f in self.findings}))


# Every fail-closed finding code the validator can emit. Named here so the audit
# store, tests, and policy docs share one list.
FAIL_CLOSED_FINDING_CODES: frozenset[str] = frozenset(
    {
        "unlicensed_claim",
        "unknown_asserted",
        "strength_increase",
        "prohibited_claim",
        "availability_upgraded_to_response",
        "disclosure_lost",
        "cta_semantic_conflict",
        "unsupported_number",
        "internal_score_leak",
        "no_company_specific_evidence",
        "injection_derived_instruction",
        "person_or_contact_present",
        "demo_misrepresented",
        "structure_violation",
        "placeholder_resolved_early",
        "subject_exceeds_body_or_source",
        "unsupported_geography",
        "conditional_language_lost",
        # claim-manifest cross-checks (owner refinement, 2026-09-01)
        "undeclared_rendered_claim",
        "claim_manifest_source_mismatch",
        "claim_manifest_strength_mismatch",
        "rendered_claim_exceeds_manifest",
        "material_paraphrase_alteration",
    }
)


@dataclass(frozen=True, slots=True)
class RetentionProposal:
    """Owner decision (2026-09-01): technical maximums pending privacy/legal
    confirmation. 30 days is NOT legally approved; it is the proposed ceiling."""

    raw_provider_response_max_days: int = 30
    rejected_provider_output_max_days: int = 30
    legally_approved: bool = False
    encryption_required: bool = True
    access_controlled: bool = True
    hard_delete_on_expiry: bool = True
    durable_metadata_policy: str = "ai_communication_generation"
    note: str = (
        "raw_provider_response_max_days and rejected_provider_output_max_days are "
        "proposed technical maximums requiring privacy/legal confirmation before "
        "any real provider call. The immutable "
        "hash/metadata/validator-result/normalized-artifact/claim-map/cost record "
        "is retained under the eventual ai_communication_generation policy."
    )


RETENTION_PROPOSAL = RetentionProposal()


@dataclass(frozen=True, slots=True)
class GenerationAttemptOutcome:
    """The deterministic outcome of one attempt, ready for the audit store."""

    envelope_sha256: str
    outcome: CommunicationOutcome
    candidate_validations: tuple[ValidationResult, ...] = ()
    passing_candidate_ids: tuple[str, ...] = ()
    generation_status: GenerationStatus | None = None
    reason: str | None = None
    diagnostics: tuple[tuple[str, str], ...] = field(default_factory=tuple)
