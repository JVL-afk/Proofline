"""M4 demo domain: immutable declarative simulations downstream of M1-M3 truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from opintel_audit.domain import AuditBundle, AuditEvidence
from opintel_opportunity.domain import OpportunityBundle


class DemoOperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DemoRevisionState(StrEnum):
    REVIEW_REQUIRED = "review_required"
    QC_FAILED = "qc_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    SUPERSEDED = "superseded"


class DemoValidity(StrEnum):
    CURRENT = "current"
    STALE_INPUTS = "stale_inputs"
    REVOKED = "revoked"
    EXPIRED = "expired"


class DemoReviewDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class DemoStatementKind(StrEnum):
    SOURCE_FACT = "source_fact"
    SOURCE_INFERENCE = "source_inference"
    HYPOTHETICAL_ESTIMATE = "hypothetical_estimate"
    PROPOSED_WORKFLOW = "proposed_workflow"
    SIMULATED_OUTCOME = "simulated_outcome"
    DISCLAIMER = "disclaimer"


class MockClassification(StrEnum):
    MOCK_ONLY = "mock_only"


class QcSeverity(StrEnum):
    WARNING = "warning"
    HARD_FAILURE = "hard_failure"


class SessionState(StrEnum):
    ISSUED = "issued"
    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RuntimeTerminal(StrEnum):
    ACTIVE = "active"
    SUCCESSFUL_SIMULATION = "successful_simulation"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    OUTSIDE_DEMO_SCOPE = "outside_demo_scope"
    SAFETY_HANDOFF = "safety_handoff"
    INVALID_INPUT = "invalid_input"
    MOCK_ACTION_FAILED = "mock_action_failed"
    SESSION_EXPIRED = "session_expired"
    SESSION_REVOKED = "session_revoked"
    USER_ENDED = "user_ended"


@dataclass(frozen=True, slots=True)
class DemoCanonicalInputs:
    audit: AuditBundle
    opportunity: OpportunityBundle
    evidence: tuple[AuditEvidence, ...]
    business_name: str
    business_profile_hash: str


@dataclass(frozen=True, slots=True)
class DemoInputManifest:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    business_profile_hash: str
    opportunity_id: UUID
    opportunity_revision_id: UUID
    opportunity_manifest_hash: str
    opportunity_review_id: UUID
    opportunity_review_manifest_hash: str
    opportunity_definition_version: str
    audit_id: UUID
    audit_revision_id: UUID
    audit_revision_hash: str
    audit_manifest_hash: str
    audit_review_id: UUID
    audit_review_revision_hash: str
    audit_qc_policy_version: str
    audit_claim_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    evidence_fingerprints: tuple[str, ...]
    information_gap_ids: tuple[UUID, ...]
    assumption_revision_ids: tuple[UUID, ...]
    economic_run_id: UUID
    economic_formula_version: str
    score_snapshot_id: UUID
    score_config_version: str
    demo_schema_version: str
    composition_policy_version: str
    component_registry_version: str
    state_machine_version: str
    question_set_version: str
    synthetic_dataset_version: str
    runtime_version: str
    security_profile_version: str
    telemetry_policy_version: str
    disclaimer_policy_version: str
    qc_policy_version: str
    checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DemoStatementBinding:
    id: UUID
    kind: DemoStatementKind
    display_text: str
    audit_claim_id: UUID | None = None
    audit_claim_type: str | None = None
    evidence_ids: tuple[UUID, ...] = ()
    assumption_revision_ids: tuple[UUID, ...] = ()
    economic_run_id: UUID | None = None
    formula_version: str | None = None
    visibly_conditional: bool = False
    dependency_claim_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticPersona:
    id: str
    display_name: str
    role: str
    facility: str
    synthetic_region: str
    synthetic: bool
    fixture_version: str


@dataclass(frozen=True, slots=True)
class ServiceCategoryOption:
    """EVIDENCE_PRESERVING_PERSONALIZATION_V2: a company-derived service option
    bound to the exact evidence row that supports it."""

    label: str
    evidence_id: UUID
    fact_class: str


@dataclass(frozen=True, slots=True)
class ServiceAreaOption:
    label: str
    evidence_id: UUID
    fact_class: str


@dataclass(frozen=True, slots=True)
class SemanticFactInput:
    """demo.commercial_hvac.lead_response@3: the full record of every M2
    CompanyFact class that reached M4 as semantic input, whether or not the demo
    renders it as a synthetic option. ``retention`` and ``non_option_reason``
    make a downstream omission an explicit, policy-driven decision rather than an
    accidental truncation.
    """

    category: str
    phrase: str
    verbatim_phrase: str
    evidence_id: UUID
    fact_class: str
    page_purpose: str
    rendered_as_demo_option: bool
    retention: str
    non_option_reason: str | None = None


@dataclass(frozen=True, slots=True)
class QualificationQuestion:
    id: str
    prompt: str
    input_kind: str
    allowed_values: tuple[str, ...]
    required: bool
    purpose: str
    collects_contact_destination: bool = False


@dataclass(frozen=True, slots=True)
class ComponentInstance:
    id: str
    component_type: str
    props: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class DemoStateNode:
    id: str
    components: tuple[ComponentInstance, ...]
    terminal: RuntimeTerminal = RuntimeTerminal.ACTIVE


@dataclass(frozen=True, slots=True)
class DemoTransition:
    from_state: str
    event: str
    to_state: str
    guard: str = "always"
    guard_value: str | None = None
    mock_action_id: str | None = None


@dataclass(frozen=True, slots=True)
class MockActionDefinition:
    id: str
    action_type: str
    classification: MockClassification
    display_label: str


@dataclass(frozen=True, slots=True)
class MockActionReceipt:
    action_id: str
    classification: MockClassification
    status: str
    receipt_id: str
    display_message: str


@dataclass(frozen=True, slots=True)
class RecordingCue:
    ordinal: int
    state_id: str
    narration: str
    synthetic_event: str | None
    statement_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class TechnicalDemoSpecification:
    trigger: str
    inputs: tuple[str, ...]
    handoff_conditions: tuple[str, ...]
    proposed_integrations: tuple[str, ...]
    safeguards: tuple[str, ...]
    deployment_status: str


@dataclass(frozen=True, slots=True)
class DemoSpecification:
    schema_version: str
    business_display_name: str
    neutral_theme: str
    scenario_id: str
    scenario_version: str
    initial_state: str
    maximum_transitions: int
    components: tuple[str, ...]
    personas: tuple[SyntheticPersona, ...]
    questions: tuple[QualificationQuestion, ...]
    states: tuple[DemoStateNode, ...]
    transitions: tuple[DemoTransition, ...]
    mock_actions: tuple[MockActionDefinition, ...]
    statements: tuple[DemoStatementBinding, ...]
    conversation_utterances: tuple[tuple[str, str], ...]
    recording_cues: tuple[RecordingCue, ...]
    technical_specification: TechnicalDemoSpecification
    # EVIDENCE_PRESERVING_PERSONALIZATION_V2: evidence-derived scenario config.
    service_categories: tuple[ServiceCategoryOption, ...] = ()
    service_area_context: tuple[ServiceAreaOption, ...] = ()
    personalization_provenance: tuple[tuple[str, UUID], ...] = ()
    # demo.commercial_hvac.lead_response@3: full M2 -> M4 fact carry-through.
    semantic_fact_inputs: tuple[SemanticFactInput, ...] = ()


@dataclass(frozen=True, slots=True)
class DemoQcFinding:
    id: UUID
    code: str
    severity: QcSeverity
    message: str


@dataclass(frozen=True, slots=True)
class DemoRevision:
    id: UUID
    demo_id: UUID
    revision: int
    parent_revision_id: UUID | None
    workspace_id: UUID
    business_id: UUID
    opportunity_id: UUID
    audit_id: UUID
    manifest: DemoInputManifest
    specification: DemoSpecification
    qc_findings: tuple[DemoQcFinding, ...]
    state: DemoRevisionState
    validity: DemoValidity
    specification_hash: str
    revision_hash: str
    created_by: str
    created_at: datetime

    @property
    def hard_qc_passed(self) -> bool:
        return not any(item.severity == QcSeverity.HARD_FAILURE for item in self.qc_findings)


@dataclass(frozen=True, slots=True)
class DemoOperation:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    audit_revision_id: UUID
    expected_audit_revision_hash: str
    demo_id: UUID
    parent_revision_id: UUID | None
    status: DemoOperationStatus
    idempotency_key: str
    trace_id: UUID
    attempt_count: int
    max_attempts: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    lease_expires_at: datetime | None = None
    demo_revision_id: UUID | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class DemoReviewDecision:
    id: UUID
    demo_revision_id: UUID
    revision_hash: str
    manifest_hash: str
    specification_hash: str
    decision: DemoReviewDecisionType
    actor: str
    actor_roles: tuple[str, ...]
    reason: str
    self_review: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DemoRevocation:
    id: UUID
    demo_revision_id: UUID
    actor: str
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DemoBundle:
    revision: DemoRevision
    latest_review: DemoReviewDecision | None = None
    review_valid: bool = False
    revocation: DemoRevocation | None = None


@dataclass(frozen=True, slots=True)
class SessionIssuance:
    id: UUID
    demo_revision_id: UUID
    workspace_id: UUID
    audience: str
    capability_hash: str
    state: SessionState
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RuntimeSession:
    id: UUID
    issuance_id: UUID
    demo_revision_id: UUID
    workspace_id: UUID
    audience: str
    session_token_hash: str
    state: SessionState
    current_state: str
    persona_id: str
    seed: str
    transition_count: int
    event_history: tuple[str, ...]
    receipts: tuple[MockActionReceipt, ...]
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RuntimeSessionView:
    session: RuntimeSession
    specification: DemoSpecification
    disclosure: str
    csp: str


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    id: UUID
    session_id: UUID
    demo_revision_id: UUID
    scenario_id: str
    event_type: str
    state_id: str
    outcome: str
    synthetic_fixture_id: str
    duration_ms: int | None
    created_at: datetime


class DemoError(Exception):
    code = "demo_error"
    safe_message = "demo operation failed"


class DemoNotFoundError(DemoError):
    code = "not_found"
    safe_message = "demo resource not found"


class DemoAuthorizationError(DemoError):
    code = "forbidden"
    safe_message = "demo action is not permitted"


class DemoValidationError(DemoError):
    code = "invalid_input"
    safe_message = "demo input is invalid"


class DemoQcError(DemoError):
    code = "qc_failed"
    safe_message = "demo quality checks failed"


class DemoSessionError(DemoError):
    code = "session_invalid"
    safe_message = "demo session is unavailable"


class TransientDemoCompositionError(DemoError):
    code = "composition_transient_failure"
    safe_message = "demo composition failed temporarily"
