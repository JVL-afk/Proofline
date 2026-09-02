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
# M6.8-3 remediation contract: the SAME validator / parser code, run under the
# ``contract="v2"`` flag. ``@1`` behaviour is byte-identical when the flag is off.
# ``@2`` (Attempt-6 prep + round-2) = negation-aware demo/availability/response
# concepts, envelope-authorized-text exemption, strength reconciliation, business
# identity vocabulary, disclosure negation grammar, bounded semantic 15c,
# licensed-numeric exemption, claim_type reconciliation, advisory severities.
# ``@3`` (post-Attempt-6 remediation, owner authorization 2026-09-02 "COMPLETE
# M6.8-3 REMEDIATION"): possessive/contraction-safe v2 tokenization + framing /
# epistemic-connective vocabulary + tense-variant coverage in rule 12;
# simulation-mechanics sentences classify as DISCLOSURE; business-identity spans
# in the manifest are identity grammar not evidence.
# ``@4`` (Haiku track, owner authorization 2026-09-02 "SWITCH ... TO HAIKU 4.5"):
# a bare evidentiary framing lead-in with no business predicate is source-free
# (D1); "<Business Name> publishes / lists / describes X", optionally after an
# "I noticed" framing prefix, classifies as a public-text FACT.
# ``@5`` (return-to-Sonnet-5, owner authorization 2026-09-02 "AUTHORIZE BOUNDED
# REDUNDANT-MANIFEST RECONCILIATION"): a source-less manifest entry escapes
# claim_manifest_source_mismatch ONLY as a redundant wrapper - every substantive
# unit of its span is independently and validly licensed by finer-grained
# sibling entries at equal-or-stronger evidentiary support, and the wrapper-only
# residual adds no fact / inference / recommendation / number / process /
# response / economic / deployment / person claim or meaning-changing qualifier.
# Deterministic; never trusts the provider's declared claim_type.
OUTPUT_VALIDATOR_V2_VERSION = "comm.output_validator@5"
# ``@6`` (final M6.8-3 architectural correction, owner authorization 2026-09-02):
# the provider-authored claim manifest is NON-AUTHORITATIVE. The rendered prose
# is the object of deterministic canonical claim reconciliation
# (comm.canonical_claim_reconciler@1). rule 15's manifest cross-checks are
# replaced by: every substantive rendered clause is independently discovered,
# classified, source-licensed and strength-checked; 100% substantive coverage is
# required; an unresolved substantive span fails closed. A provider-manifest
# disagreement is advisory diagnostic only. All prose-level zero-tolerance rules
# (1-14, 16, 17) are unchanged.
OUTPUT_VALIDATOR_V3_VERSION = "comm.output_validator@6"
CTA_PARSER_V2_VERSION = "comm.cta_parser@2"
# M6.8-2 additions
CANDIDATE_RANKER_VERSION = "comm.candidate_ranker@1"
GENERATION_STORE_VERSION = "comm.generation_store@1"
GENERATION_ORCHESTRATOR_VERSION = "comm.generation_orchestrator@1"
HUMAN_REVIEW_SCHEMA_VERSION = "comm.human_review@1"
STUB_PROVIDER_ADAPTER_VERSION = "comm.stub_provider_adapter@1"


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
    # Advisory (owner authorization 2026-09-02, sections 5/6): a finding that
    # affects COMMUNICATION_QUALITY but is NOT a safety/validation failure and
    # does not by itself cause a candidate FAIL or NOT_CERTIFIED. Used only under
    # the validator's v2 contract.
    ADVISORY = "advisory"


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
    stop_reason: str = ""


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
    # canonical reconciliation (contract="v3" only; defaults keep v1/v2 identical)
    canonical_reconciliation_coverage: float = 1.0
    unresolved_substantive_claims: int = 0
    canonical_substantive_claims: int = 0
    canonical_licensed_claims: int = 0
    canonical_rejected_claims: int = 0
    provider_manifest_disagreements: tuple[str, ...] = ()
    canonical_claim_map: object | None = None

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

# The genuine zero-tolerance SAFETY / truth / manifest-honesty finding codes:
# a subset of FAIL_CLOSED_FINDING_CODES that excludes purely structural / quality
# codes (structure_violation, no_company_specific_evidence,
# subject_exceeds_body_or_source, ...). One occurrence anywhere in a run forces
# NOT_CERTIFIED, and one on a provider candidate cannot be laundered away by the
# deterministic body compactor (owner authorization 2026-09-02, section D2).
ZERO_TOLERANCE_SAFETY_CODES: frozenset[str] = frozenset(
    {
        "prohibited_claim",
        "unsupported_number",
        "availability_upgraded_to_response",
        "unknown_asserted",
        "internal_score_leak",
        "injection_derived_instruction",
        "disclosure_lost",
        "cta_semantic_conflict",
        "claim_manifest_source_mismatch",
        "claim_manifest_strength_mismatch",
        "undeclared_rendered_claim",
        "rendered_claim_exceeds_manifest",
        "material_paraphrase_alteration",
        "demo_misrepresented",
        "person_or_contact_present",
        "unlicensed_claim",
        "strength_increase",
        # (@6 canonical) an unresolved substantive rendered span, or overall
        # reconciliation coverage < 100%, fails closed.
        "unresolved_substantive_claim",
        "canonical_reconciliation_incomplete",
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


# ==========================================================================
# M6.8-2 - stubbed generation lifecycle, audit store, candidate ranker
# ==========================================================================


@dataclass(frozen=True, slots=True)
class NormalizedCandidate:
    """The deterministic normalization of one candidate's subject + body.

    Subject and body are one unit for validation and versioning (owner
    refinement, 2026-09-01): a safe body with an unsupported subject is one
    failed candidate, not a partially-usable one.
    """

    candidate_id: str
    normalized_subject: str
    normalized_body: str
    body_word_count: int
    content_sha256: str


@dataclass(frozen=True, slots=True)
class RankComponent:
    """One bounded feature the ranker considered. ``normalized`` is in [0, 1]
    where higher is always better; ``contribution = normalized * weight``.
    ``penalty`` marks a feature whose raw value counts against the candidate
    (the normalization already inverts it)."""

    name: str
    raw_value: str
    normalized: float
    weight: float
    contribution: float
    penalty: bool = False


@dataclass(frozen=True, slots=True)
class RankScore:
    candidate_id: str
    components: tuple[RankComponent, ...]
    total: float
    ranker_version: str = CANDIDATE_RANKER_VERSION


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A PASS-validation candidate placed in deterministic rank order. The
    ranker never sees a FAILED candidate and never changes send eligibility."""

    rank: int
    candidate_id: str
    score: RankScore


class HumanReviewState(StrEnum):
    PENDING = "PENDING"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    ALL_REJECTED = "ALL_REJECTED"
    ACCEPTED_NOT_DISTINCTIVE = "ACCEPTED_NOT_DISTINCTIVE"


class HumanReviewAction(StrEnum):
    SELECT_CANDIDATE = "SELECT_CANDIDATE"
    REJECT_CANDIDATE = "REJECT_CANDIDATE"
    REJECT_ALL = "REJECT_ALL"
    ACCEPT_NOT_DISTINCTIVE = "ACCEPT_NOT_DISTINCTIVE"


# States from which no further transition is allowed.
TERMINAL_REVIEW_STATES: frozenset[HumanReviewState] = frozenset(
    {
        HumanReviewState.CANDIDATE_SELECTED,
        HumanReviewState.ALL_REJECTED,
        HumanReviewState.ACCEPTED_NOT_DISTINCTIVE,
    }
)


@dataclass(frozen=True, slots=True)
class HumanReviewEvent:
    action: HumanReviewAction
    candidate_id: str | None
    at_epoch_seconds: int
    reviewer_ref: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class HumanReview:
    """Immutable, exact-version-bound review of one generation record.

    It carries no rendered content of its own and cannot select a candidate
    that is not in ``selectable_candidate_ids`` (which the store populates only
    from PASS-validation ranked candidates). It never creates facts and never
    overrides a validator finding.
    """

    review_id: str
    envelope_sha256: str
    generation_record_hash: str
    selectable_candidate_ids: tuple[str, ...]
    terminal_outcome: CommunicationOutcome
    state: HumanReviewState
    history: tuple[HumanReviewEvent, ...] = ()
    selected_candidate_id: str | None = None
    schema_version: str = HUMAN_REVIEW_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class RawResponseRetention:
    """Per-record retention metadata for the raw provider response only. The
    duration is a proposed technical maximum; ``policy_status`` stays
    POLICY_PENDING until privacy/legal confirms it."""

    stored_at_epoch_seconds: int
    max_retention_days: int
    expires_at_epoch_seconds: int
    policy_status: str = "POLICY_PENDING"
    erased_at_epoch_seconds: int | None = None
    erase_method: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimEvidenceLink:
    claim_id: str
    claim_type: ClaimType
    rendered_span: str
    licensed_source_ids: tuple[str, ...]
    resolved_source_kinds: tuple[str, ...]
    asserted_strength: FactStrength | None


@dataclass(frozen=True, slots=True)
class CandidateAuditRow:
    """Everything the audit store keeps about one candidate, immutably. Survives
    raw-response erasure - none of this depends on the raw text."""

    candidate_id: str
    normalized: NormalizedCandidate
    claim_manifest: ClaimManifest
    validation: ValidationResult
    claim_evidence_map: tuple[ClaimEvidenceLink, ...]
    rank: int | None = None
    rank_score: RankScore | None = None
    # (Haiku track D2) populated only when the deterministic body compactor
    # changed this candidate. ``normalized`` / ``claim_manifest`` / ``validation``
    # then describe the COMPACTED revision; the fields below preserve the raw
    # provider candidate's normalization and its own validation, and record any
    # zero-tolerance safety finding that compaction removed (still run-visible).
    compaction: object | None = None
    original_normalized: NormalizedCandidate | None = None
    original_validation: ValidationResult | None = None
    laundered_safety_codes: tuple[str, ...] = ()
    quality: object | None = None


@dataclass(frozen=True, slots=True)
class GenerationRecord:
    """One append-only, hash-chained audit record for a single generation
    attempt. Never mutated once written; a later attempt appends a new record."""

    record_id: str
    sequence: int
    previous_record_hash: str
    record_hash: str

    envelope_sha256: str
    envelope_schema_version: str
    source_lineage_bundle_sha256: str

    provider_adapter_identity: str
    provider_certification_key: str
    model_placeholder: str
    provider_placeholder: str
    config_placeholder: str
    prompt_template_id: str
    prompt_template_sha256: str
    prompt_bundle_sha256: str

    raw_provider_response_sha256: str | None
    raw_provider_response_ref: str | None
    raw_response_retention: RawResponseRetention | None

    requested_candidate_count: int
    returned_candidate_count: int
    candidates: tuple[CandidateAuditRow, ...]
    passing_candidate_ids: tuple[str, ...]
    ranked_candidate_ids: tuple[str, ...]

    validator_version: str
    cta_parser_version: str
    ranker_version: str
    orchestrator_version: str
    store_version: str

    terminal_outcome: CommunicationOutcome
    generation_status: GenerationStatus | None
    reason: str | None

    input_tokens: int
    output_tokens: int
    cost_usd: str

    human_review_state: HumanReviewState
    human_review_id: str | None

    created_at_epoch_seconds: int
    diagnostics: tuple[tuple[str, str], ...] = ()
    compactor_version: str = ""  # "" when the deterministic body compactor is off

    def selectable_candidate_ids(self) -> tuple[str, ...]:
        """Only PASS-validation ranked candidates are selectable in review."""

        return self.ranked_candidate_ids


@dataclass(frozen=True, slots=True)
class ProviderDriftDescriptor:
    """How a *live* provider's output would be checked for drift at
    certification time (M6.8-3). Recorded now so replay and future
    live-certification use the same fields. The stub adapter has a fixed
    ``response_fingerprint_sha256`` by construction."""

    certification_key: str
    prompt_bundle_sha256: str
    response_fingerprint_sha256: str
    normalized_candidate_shas: tuple[str, ...]
    validator_finding_signature: str
    ranking_signature: str
    note: str = (
        "Replay compares these across identical (envelope, adapter corpus, "
        "validator/ranker versions) runs and requires exact equality. Live "
        "provider certification (M6.8-3) compares response_fingerprint_sha256 "
        "and normalized_candidate_shas across repeated real calls and allows "
        "only bounded, documented drift."
    )
