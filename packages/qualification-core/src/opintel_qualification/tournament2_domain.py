"""Immutable M6.6A Tournament II contracts with no live-provider authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from opintel_qualification.domain import CorpusPartition, QualificationStatus


class TournamentTask(StrEnum):
    EVIDENCE_INTERPRETATION = "evidence_interpretation"
    INFERENCE_GENERATION = "inference_generation"
    CONTRADICTION_ANALYSIS = "contradiction_analysis"
    OPPORTUNITY_REASONING = "opportunity_reasoning"
    INFORMATION_GAP_PRIORITIZATION = "information_gap_prioritization"
    AUDIT_WORDING = "audit_wording"
    AUDIT_SUMMARIZATION = "audit_summarization"
    DEMO_CONVERSATIONAL_WORDING = "demo_conversational_wording"
    DEMO_NARRATION_WORDING = "demo_narration_wording"
    OUTREACH_WORDING = "outreach_wording"
    VALIDATION_QUESTION_WORDING = "validation_question_wording"
    CALL_OPENING_WORDING = "call_opening_wording"
    REPLY_CLASSIFICATION = "reply_classification"
    FIRST_PARTY_STATEMENT_EXTRACTION = "first_party_statement_extraction"
    REANALYSIS_SUGGESTION = "reanalysis_suggestion"


CORE_TASKS = frozenset(
    {
        TournamentTask.EVIDENCE_INTERPRETATION,
        TournamentTask.CONTRADICTION_ANALYSIS,
        TournamentTask.OPPORTUNITY_REASONING,
        TournamentTask.AUDIT_WORDING,
        TournamentTask.OUTREACH_WORDING,
        TournamentTask.REPLY_CLASSIFICATION,
        TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
    }
)
EXTENSION_TASKS = frozenset(TournamentTask) - CORE_TASKS


class AuthorityClass(StrEnum):
    AUTHORITATIVE_INELIGIBLE = "authoritative_ineligible"
    ADVISORY_ONLY = "advisory_only"
    WORDING_ONLY = "wording_only"


class CandidateKind(StrEnum):
    DETERMINISTIC_FAKE = "deterministic_fake"


class IntakeState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    FROZEN = "frozen"


class FailureBlastRadius(StrEnum):
    TASK_LOCAL_FAILURE = "task_local_failure"
    CONFIGURATION_WIDE_FAILURE = "configuration_wide_failure"
    PROVIDER_SECURITY_FAILURE = "provider_security_failure"


class HardGate(StrEnum):
    INVENTED_EVIDENCE = "invented_evidence"
    UNSUPPORTED_FACTUAL_CLAIM = "unsupported_factual_claim"
    UNKNOWN_TO_KNOWN = "unknown_to_known"
    INFERENCE_TO_FACT = "inference_to_fact"
    SCOPED_ABSENCE_BROADENED = "scoped_absence_broadened"
    CONTRADICTION_DOWNGRADED = "contradiction_downgraded"
    FABRICATED_ECONOMICS = "fabricated_economics"
    AUTHORITATIVE_CALCULATION_ALTERED = "authoritative_calculation_altered"
    INVENTED_PERSON_OR_CONTACT = "invented_person_or_contact"
    FABRICATED_RELATIONSHIP = "fabricated_relationship"
    PROMPT_INJECTION_COMPLIANCE = "prompt_injection_compliance"
    TOOL_NETWORK_ACTION_ATTEMPT = "tool_network_action_attempt"
    CLAIM_INVENTORY_CHANGED = "claim_inventory_changed"
    CTA_CHANGED = "cta_changed"
    AUTHORITY_ESCALATION = "authority_escalation"
    UNSAFE_REPLY_HANDLING = "unsafe_reply_handling"
    INVENTED_FIRST_PARTY_STATEMENT = "invented_first_party_statement"
    SAFETY_SCHEMA_POLICY_VIOLATION = "safety_schema_policy_violation"
    MATERIAL_QUALIFIER_DILUTION = "material_qualifier_dilution"
    CROSS_CASE_CONTAMINATION = "cross_case_contamination"


class RecommendationDisposition(StrEnum):
    QUALIFIED_WITH_MATERIAL_GAIN = "qualified_with_material_gain"
    SAFE_BUT_NO_MATERIAL_GAIN = "safe_but_no_material_gain"
    DETERMINISTIC_SUPERIOR = "deterministic_superior"
    CONDITIONAL = "conditional"
    DISQUALIFIED = "disqualified"


class PostTournamentState(StrEnum):
    NO_ROUTE = "no_route"
    EVALUATION_ONLY = "evaluation_only"
    SHADOW_CANDIDATE = "shadow_candidate"
    ADVISORY_CANDIDATE = "advisory_candidate"


class ProviderOutcome(StrEnum):
    VALID = "valid"
    MALFORMED_SCHEMA = "malformed_schema"
    TIMEOUT = "timeout"
    TRANSIENT_FAILURE = "transient_failure"
    REFUSAL = "refusal"
    SAFETY_FILTERED = "safety_filtered"
    UNSUPPORTED_FIELD = "unsupported_field"
    HARD_GATE_VIOLATION = "hard_gate_violation"
    CROSS_CASE_CONTAMINATION = "cross_case_contamination"
    PROMPT_INJECTION_COMPLIANCE = "prompt_injection_compliance"


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    task: TournamentTask
    authority: AuthorityClass
    core_execution: bool
    contract_version: str
    input_schema_version: str
    output_schema_version: str
    deterministic_baseline_required: bool = True


@dataclass(frozen=True, slots=True)
class ClaimAtom:
    claim_id: str
    semantic_label: str
    text: str
    evidence_ids: tuple[str, ...]
    qualifiers: tuple[str, ...] = ()
    economic_binding_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticGraph:
    claims: tuple[ClaimAtom, ...]
    protected_unknown_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    entity_ids: tuple[str, ...]
    person_ids: tuple[str, ...] = ()
    contact_ids: tuple[str, ...] = ()
    cta_id: str | None = None
    action_authorities: tuple[str, ...] = ()
    first_party_statement_ids: tuple[str, ...] = ()
    reply_safety_label: str | None = None


@dataclass(frozen=True, slots=True)
class TournamentCaseBundle:
    id: UUID
    family: str
    partition: CorpusPartition
    corpus_version: str
    synthetic: bool
    business_fixture_id: str
    deterministic_graph: SemanticGraph
    allowed_evidence_ids: tuple[str, ...]
    prompt_injection_present: bool
    manifest_hash: str


@dataclass(frozen=True, slots=True)
class TaskProjection:
    id: UUID
    case_id: UUID
    task: TournamentTask
    contract_version: str
    synthetic: bool
    baseline: SemanticGraph
    allowed_evidence_ids: tuple[str, ...]
    untrusted_content_markers: tuple[str, ...]
    projection_hash: str


@dataclass(frozen=True, slots=True)
class CandidateIntake:
    id: UUID
    state: IntakeState
    kind: CandidateKind
    provider_key: str
    deployment_key: str
    deployment_version: str
    configuration_hash: str
    supported_tasks: tuple[TournamentTask, ...]
    structured_output_supported: bool
    retention_profile: str
    data_handling_policy: str
    pricing_version: str | None
    terms_version: str
    approval_refs: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class QualificationIdentity:
    provider_key: str
    deployment_key: str
    deployment_version: str
    configuration_hash: str
    task: TournamentTask
    contract_version: str
    input_schema_version: str
    output_schema_version: str
    prompt_policy_version: str
    corpus_version: str
    evaluator_version: str
    safety_policy_version: str
    data_classification_policy: str


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    case_id: UUID
    task: TournamentTask
    graph: SemanticGraph | None
    schema_valid: bool
    injection_followed: bool
    attempted_capabilities: tuple[str, ...]
    provider_failure: str | None = None
    unsupported_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateFinding:
    gate: HardGate
    blast_radius: FailureBlastRadius
    detail_code: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    case_id: UUID
    task: TournamentTask
    findings: tuple[GateFinding, ...]
    schema_valid: bool
    provider_failure: str | None

    @property
    def safety_passed(self) -> bool:
        return not self.findings and self.schema_valid and self.provider_failure is None


@dataclass(frozen=True, slots=True)
class QualificationOutcome:
    identity: QualificationIdentity
    status: QualificationStatus
    disposition: RecommendationDisposition
    deterministic_preferred: bool
    post_tournament_state: PostTournamentState
    findings: tuple[GateFinding, ...]
    human_review_required: bool


@dataclass(frozen=True, slots=True)
class TournamentQualificationRecord:
    id: UUID
    identity: QualificationIdentity
    status: QualificationStatus
    disposition: RecommendationDisposition | None
    previous_record_id: UUID | None
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BlindedReviewArtifact:
    id: UUID
    case_id: UUID
    task: TournamentTask
    left_artifact_hash: str
    right_artifact_hash: str
    presentation_order_hash: str
    provider_identity_hidden: bool


@dataclass(frozen=True, slots=True)
class ReviewerScores:
    review_artifact_id: UUID
    reviewer_pseudonym: str
    clarity: int
    naturalness: int
    concision: int
    usefulness: int
    relevance: int
    trustworthiness: int
    preferred_side: str
    material_defect_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UsageLedgerEntry:
    candidate_id: UUID
    task: TournamentTask
    stage: str
    case_id: UUID
    attempt: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    reserved_cost_micros: int
    actual_cost_micros: int
    pricing_version: str
    validation_outcome: str
