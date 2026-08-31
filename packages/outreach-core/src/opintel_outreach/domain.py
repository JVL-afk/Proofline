"""M5 outreach domain: communication is a projection, never new business truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from opintel_audit.domain import AuditBundle, AuditEvidence
from opintel_demo.domain import DemoBundle
from opintel_opportunity.domain import OpportunityBundle


class OutreachOperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    QC_FAILED = "qc_failed"
    FAILED = "failed"


class OutreachRevisionState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    DRAFT_INCOMPLETE = "draft_incomplete"
    QC_FAILED = "qc_failed"
    CONTENT_APPROVED = "content_approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    SUPERSEDED = "superseded"


class OutreachValidity(StrEnum):
    CURRENT = "current"
    STALE_INPUTS = "stale_inputs"
    INVALIDATED = "invalidated"


class OutreachReviewDecisionType(StrEnum):
    APPROVE_CONTENT = "approve_content"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class ArtifactAudience(StrEnum):
    EXTERNAL = "external"
    INTERNAL = "internal"


class ArtifactKind(StrEnum):
    SUBJECT = "subject"
    FIRST_CONTACT_EMAIL = "first_contact_email"
    FOLLOW_UP_DRAFT = "follow_up_draft"
    CALL_OPENING_SCRIPT = "call_opening_script"
    VALIDATION_QUESTIONS = "validation_questions"
    INTERNAL_CALL_PREP = "internal_call_prep"
    INTERNAL_ECONOMIC_CONTEXT = "internal_economic_context"
    INTERNAL_RISK_REGISTER = "internal_risk_register"


class SegmentKind(StrEnum):
    BOUND_CLAIM = "bound_claim"
    SIMULATION_DISCLOSURE = "simulation_disclosure"
    CTA = "cta"
    SALUTATION = "salutation"
    VERIFIED_SENDER_SLOT = "verified_sender_slot"
    REQUIRED_POSTAL_DISCLOSURE_SLOT = "required_postal_disclosure_slot"
    APPROVED_OPT_OUT_INSTRUCTION_SLOT = "approved_opt_out_instruction_slot"
    TRANSITION = "transition"
    INTERNAL_CONTEXT = "internal_context"


class ProjectionDisposition(StrEnum):
    EXTERNAL_ALLOWED = "external_allowed"
    INTERNAL_ONLY = "internal_only"
    EXCLUDED = "excluded"


class ProjectionMode(StrEnum):
    DIRECT_FACT_RESTATEMENT = "direct_fact_restatement"
    EVIDENCE_DERIVED_FACT = "evidence_derived_fact"
    CONDITIONAL_INFERENCE = "conditional_inference"
    SCOPED_ABSENCE = "scoped_absence"
    CONDITIONAL_RECOMMENDATION = "conditional_recommendation"
    ECONOMIC_CONTEXT_INTERNAL_ONLY = "economic_context_internal_only"


class FollowUpUsability(StrEnum):
    CONDITIONALLY_USABLE = "conditionally_usable"


class TargetRole(StrEnum):
    SERVICE_OPERATIONS_LEAD = "service_operations_lead"
    COMMERCIAL_SERVICE_LEAD = "commercial_service_lead"
    DISPATCH_OR_INTAKE_LEAD = "dispatch_or_intake_lead"
    OWNER_OR_EXECUTIVE = "owner_or_executive"
    BUSINESS_DEVELOPMENT_LEAD = "business_development_lead"
    UNKNOWN_RELEVANT_ROLE = "unknown_relevant_role"


class QcSeverity(StrEnum):
    WARNING = "warning"
    HARD_FAILURE = "hard_failure"


@dataclass(frozen=True, slots=True)
class OutreachCanonicalInputs:
    demo: DemoBundle
    audit: AuditBundle
    opportunity: OpportunityBundle
    evidence: tuple[AuditEvidence, ...]
    business_name: str
    business_profile_hash: str


@dataclass(frozen=True, slots=True)
class OutreachInputManifest:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    business_profile_hash: str
    opportunity_revision_id: UUID
    opportunity_manifest_hash: str
    opportunity_review_id: UUID
    opportunity_review_manifest_hash: str
    audit_revision_id: UUID
    audit_revision_hash: str
    audit_manifest_hash: str
    audit_review_id: UUID
    demo_revision_id: UUID
    demo_revision_hash: str
    demo_manifest_hash: str
    demo_specification_hash: str
    demo_review_id: UUID
    evidence_ids: tuple[UUID, ...]
    evidence_fingerprints: tuple[str, ...]
    information_gap_ids: tuple[UUID, ...]
    assumption_revision_ids: tuple[UUID, ...]
    economic_run_id: UUID
    economic_formula_version: str
    score_snapshot_id: UUID
    score_config_version: str
    outreach_schema_version: str
    template_version: str
    projection_policy_version: str
    target_role_policy_version: str
    cta_policy_version: str
    qc_policy_version: str
    checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutreachClaimProjection:
    id: UUID
    source_claim_id: UUID
    source_claim_type: str
    mode: ProjectionMode
    disposition: ProjectionDisposition
    rendered_text: str
    evidence_ids: tuple[UUID, ...] = ()
    observation_ids: tuple[UUID, ...] = ()
    inference_revision_ids: tuple[UUID, ...] = ()
    assumption_revision_ids: tuple[UUID, ...] = ()
    economic_run_id: UUID | None = None
    dependency_claim_ids: tuple[UUID, ...] = ()
    contradictory_evidence_ids: tuple[UUID, ...] = ()
    required_qualifiers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactSegment:
    id: UUID
    kind: SegmentKind
    text: str
    projection_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class OutreachArtifact:
    id: UUID
    kind: ArtifactKind
    audience: ArtifactAudience
    title: str
    segments: tuple[ArtifactSegment, ...]
    rendered_text: str
    content_hash: str
    follow_up_usability: FollowUpUsability | None = None
    external_precondition: str | None = None


@dataclass(frozen=True, slots=True)
class TargetRoleSelection:
    role: TargetRole
    priority: int
    rationale: str
    person_identified: bool
    person_marker: str


@dataclass(frozen=True, slots=True)
class OutreachValidationQuestion:
    gap_id: UUID
    priority: str
    affected_component: str
    economic_effect: str
    wording: str
    safe_for_first_contact: bool


@dataclass(frozen=True, slots=True)
class OutreachRisk:
    id: UUID
    kind: str
    description: str
    source_ids: tuple[UUID, ...]
    disposition: str


@dataclass(frozen=True, slots=True)
class InternalEconomicContext:
    status: str
    formula_version: str
    result_label: str
    assumption_states: tuple[tuple[UUID, str, str], ...]
    monthly_value: str | None
    annualized_value: str | None
    currency: str
    external_use_permitted: bool


@dataclass(frozen=True, slots=True)
class PersonalizationAssessment:
    """EVIDENCE_PRESERVING_PERSONALIZATION_V2 personalization-gate result."""

    company_specific_segment_count: int
    distinct_fact_classes: int
    rendered_evidence_ids: tuple[UUID, ...]
    passes_gate: bool


@dataclass(frozen=True, slots=True)
class OutreachQcFinding:
    id: UUID
    code: str
    severity: QcSeverity
    message: str
    projection_id: UUID | None = None
    artifact_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class OutreachRevision:
    id: UUID
    package_id: UUID
    revision: int
    parent_revision_id: UUID | None
    workspace_id: UUID
    business_id: UUID
    opportunity_id: UUID
    audit_id: UUID
    demo_id: UUID
    manifest: OutreachInputManifest
    target_role: TargetRoleSelection
    projections: tuple[OutreachClaimProjection, ...]
    artifacts: tuple[OutreachArtifact, ...]
    validation_questions: tuple[OutreachValidationQuestion, ...]
    risks: tuple[OutreachRisk, ...]
    economic_context: InternalEconomicContext
    qc_findings: tuple[OutreachQcFinding, ...]
    state: OutreachRevisionState
    validity: OutreachValidity
    content_hash: str
    revision_hash: str
    created_by: str
    created_at: datetime
    personalization: PersonalizationAssessment | None = None
    unresolved_slot_kinds: tuple[str, ...] = ()

    @property
    def hard_qc_passed(self) -> bool:
        return not any(item.severity == QcSeverity.HARD_FAILURE for item in self.qc_findings)


@dataclass(frozen=True, slots=True)
class OutreachOperation:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    demo_revision_id: UUID
    expected_demo_revision_hash: str
    package_id: UUID
    parent_revision_id: UUID | None
    status: OutreachOperationStatus
    idempotency_key: str
    trace_id: UUID
    attempt_count: int
    max_attempts: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    lease_expires_at: datetime | None = None
    outreach_revision_id: UUID | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class OutreachReviewDecision:
    id: UUID
    outreach_revision_id: UUID
    revision_hash: str
    manifest_hash: str
    content_hash: str
    decision: OutreachReviewDecisionType
    actor: str
    actor_roles: tuple[str, ...]
    reason: str
    self_review: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutreachInvalidation:
    id: UUID
    outreach_revision_id: UUID
    reason: str
    actor: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutreachBundle:
    revision: OutreachRevision
    latest_review: OutreachReviewDecision | None = None
    review_valid: bool = False
    invalidation: OutreachInvalidation | None = None


class OutreachError(Exception):
    code = "outreach_error"
    safe_message = "outreach operation failed"


class OutreachNotFoundError(OutreachError):
    code = "not_found"
    safe_message = "outreach resource not found"


class OutreachAuthorizationError(OutreachError):
    code = "forbidden"
    safe_message = "outreach action is not permitted"


class OutreachValidationError(OutreachError):
    code = "invalid_input"
    safe_message = "outreach input is invalid"


class OutreachQcError(OutreachError):
    code = "qc_failed"
    safe_message = "outreach quality checks failed"


class TransientOutreachCompositionError(OutreachError):
    code = "composition_transient_failure"
    safe_message = "outreach composition failed temporarily"
