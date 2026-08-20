"""M6.7A immutable synthetic shadow-validation control-plane contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from opintel_audit.domain import AuditRevisionState
from opintel_demo.domain import DemoRevisionState
from opintel_opportunity.domain import AnalysisStatus, HypothesisStatus, ValueState
from opintel_outreach.domain import OutreachRevisionState
from opintel_research.domain import ResearchRunStatus
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class PermissionActivity(StrEnum):
    REAL_BUSINESS_DISCOVERY = "real_business_discovery"
    REAL_PUBLIC_RESEARCH = "real_public_research"
    PROFESSIONAL_IDENTITY_RESOLUTION = "professional_identity_resolution"
    REAL_CONTACT_STORAGE = "real_contact_storage"
    CONTACT_VERIFICATION = "contact_verification"
    SHADOW_ELIGIBILITY_EVALUATION = "shadow_eligibility_evaluation"
    SHADOW_READY_ASSESSMENT = "shadow_ready_assessment"


class PermissionState(StrEnum):
    NOT_AUTHORIZED = "not_authorized"
    AUTHORIZED = "authorized"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class ShadowPhase(StrEnum):
    PHASE_1_COMPANY_ONLY = "phase_1_company_only"
    LATER_CONTACT_EVALUATION = "later_contact_evaluation"


class ReleaseState(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"


class OrganizationKind(StrEnum):
    INDEPENDENT = "independent"
    FRANCHISE = "franchise"
    MULTI_LOCATION = "multi_location"


class EligibilityState(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    REVIEW_REQUIRED = "review_required"


class IneligibilityReason(StrEnum):
    OUTSIDE_TEXAS = "outside_texas"
    NOT_COMMERCIAL_HVAC = "not_commercial_hvac"
    NOT_B2B = "not_b2b"
    CLOSED_OR_INACTIVE = "closed_or_inactive"
    NO_PERMITTED_PUBLIC_URL = "no_permitted_public_url"
    DUPLICATE_OR_CLUSTER_CAP = "duplicate_or_cluster_cap"


PREDETERMINED_REPLACEMENT_REASONS = frozenset(IneligibilityReason)


class CompanyOutcome(StrEnum):
    RESEARCH_FAILED = "research_failed"
    RESEARCH_PARTIAL_REVIEW_REQUIRED = "research_partial_review_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SUPPORTED_OPPORTUNITY = "no_supported_opportunity"
    OPPORTUNITY_REVIEW_REQUIRED = "opportunity_review_required"
    OPPORTUNITY_REJECTED = "opportunity_rejected"
    AUDIT_REJECTED = "audit_rejected"
    DEMO_REJECTED = "demo_rejected"
    OUTREACH_REJECTED = "outreach_rejected"
    CONTACT_PHASE_NOT_AUTHORIZED = "contact_phase_not_authorized"
    SHADOW_BLOCKED = "shadow_blocked"
    SHADOW_READY = "shadow_ready"


PHASE_1_OUTCOMES = frozenset(
    {
        CompanyOutcome.RESEARCH_FAILED,
        CompanyOutcome.RESEARCH_PARTIAL_REVIEW_REQUIRED,
        CompanyOutcome.INSUFFICIENT_EVIDENCE,
        CompanyOutcome.NO_SUPPORTED_OPPORTUNITY,
        CompanyOutcome.OPPORTUNITY_REVIEW_REQUIRED,
        CompanyOutcome.OPPORTUNITY_REJECTED,
        CompanyOutcome.AUDIT_REJECTED,
        CompanyOutcome.DEMO_REJECTED,
        CompanyOutcome.OUTREACH_REJECTED,
        CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED,
    }
)


class ReviewKind(StrEnum):
    COHORT_IDENTITY = "cohort_identity"
    OPPORTUNITY_ACCEPTANCE = "opportunity_acceptance"
    OPPORTUNITY_SECOND_REVIEW = "opportunity_second_review"
    CONTRADICTION = "contradiction"
    ENTITY_AMBIGUITY = "entity_ambiguity"
    SCOPED_ABSENCE = "scoped_absence"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    AUDIT_APPROVAL = "audit_approval"
    DEMO_APPROVAL = "demo_approval"
    OUTREACH_APPROVAL = "outreach_approval"
    NEGATIVE_OUTCOME_QA = "negative_outcome_qa"


class ReviewState(StrEnum):
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFORMATION = "request_information"
    CONFIRM_NEGATIVE = "confirm_negative"
    FALSE_NEGATIVE_FOUND = "false_negative_found"


class MetricState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"
    UNDEFINED_ZERO_DENOMINATOR = "undefined_zero_denominator"
    BLOCKED = "blocked"


class MetricName(StrEnum):
    DISCOVERY_SUCCESS = "discovery_success"
    RESEARCH_SUCCESS = "research_success"
    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"
    OPPORTUNITY_YIELD = "opportunity_yield"
    OPPORTUNITY_REJECTION_RATE = "opportunity_rejection_rate"
    CONTRADICTION_RATE = "contradiction_rate"
    AUDIT_APPROVAL_RATE = "audit_approval_rate"
    DEMO_APPROVAL_RATE = "demo_approval_rate"
    OUTREACH_APPROVAL_RATE = "outreach_approval_rate"
    PERSON_RESOLUTION_RATE = "person_resolution_rate"
    VERIFIED_CONTACT_RATE = "verified_contact_rate"
    SHADOW_ELIGIBILITY_RATE = "shadow_eligibility_rate"
    SHADOW_READY_YIELD = "shadow_ready_yield"
    UNSUPPORTED_CLAIM_INCIDENCE = "unsupported_claim_incidence"
    PRIVACY_SOURCE_VIOLATIONS = "privacy_source_violations"
    CROSS_BUSINESS_CONTAMINATION = "cross_business_contamination"
    HUMAN_REVIEW_DURATION_SECONDS = "human_review_duration_seconds"


PERSON_CONTACT_METRICS = frozenset(
    {
        MetricName.PERSON_RESOLUTION_RATE,
        MetricName.VERIFIED_CONTACT_RATE,
        MetricName.SHADOW_ELIGIBILITY_RATE,
        MetricName.SHADOW_READY_YIELD,
    }
)


class CostCategory(StrEnum):
    DISCOVERY = "discovery"
    RESEARCH = "research"
    STORAGE_COMPUTE = "storage_compute"
    HUMAN_REVIEW_TIME = "human_review_time"
    AI = "ai"
    SHARED_COHORT_OVERHEAD = "shared_cohort_overhead"


class SafetyEventType(StrEnum):
    CROSS_BUSINESS_EVIDENCE_CONTAMINATION = "cross_business_evidence_contamination"
    FABRICATED_COMPANY_FACT = "fabricated_company_fact"
    INVENTED_REAL_PERSON = "invented_real_person"
    INCORRECT_VERIFIED_PERSON_CONTACT_ASSOCIATION = "incorrect_verified_person_contact_association"
    PROHIBITED_CONTACT_SOURCE_USAGE = "prohibited_contact_source_usage"
    PRIVACY_OR_SUPPRESSION_VIOLATION = "privacy_or_suppression_violation"
    UNAUTHORIZED_SEND_PROGRESSION = "unauthorized_send_progression"
    REAL_EXTERNAL_COMMUNICATION = "real_external_communication"
    UNAPPROVED_DATA_RETENTION = "unapproved_data_retention"
    UNSUPPORTED_FACTUAL_OUTREACH_CLAIM = "unsupported_factual_outreach_claim"
    DELIVERY_CAPABILITY_EXPOSURE = "delivery_capability_exposure"
    AI_ARTIFACT_INTERFERENCE = "ai_artifact_interference"


class StopScope(StrEnum):
    COMPANY_QUARANTINE = "company_quarantine"
    COHORT_PAUSE = "cohort_pause"
    RUN_TERMINATION = "run_termination"


RUN_TERMINATING_EVENTS = frozenset(
    {
        SafetyEventType.CROSS_BUSINESS_EVIDENCE_CONTAMINATION,
        SafetyEventType.UNAUTHORIZED_SEND_PROGRESSION,
        SafetyEventType.REAL_EXTERNAL_COMMUNICATION,
        SafetyEventType.DELIVERY_CAPABILITY_EXPOSURE,
        SafetyEventType.AI_ARTIFACT_INTERFERENCE,
    }
)


class RunState(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"
    COMPLETE = "complete"


class ReplayState(StrEnum):
    IDENTICAL = "capture_replay_deterministic"
    SOURCE_DRIFT = "source_drift"
    CONFIGURATION_DRIFT = "configuration_drift"


class ShadowRecordBase(FrozenModel):
    record_kind: str
    id: UUID
    workspace_id: UUID
    version: str
    configuration_hash: str
    created_at: datetime


class PermissionEntry(FrozenModel):
    activity: PermissionActivity
    state: PermissionState
    approval_refs: tuple[str, ...] = ()
    policy_versions: dict[str, str] = Field(default_factory=dict)


class RealDataPermissionRelease(ShadowRecordBase):
    record_kind: Literal["real_data_permissions"] = "real_data_permissions"
    state: ReleaseState
    phase: ShadowPhase
    legacy_real_company_research_grants_successors: Literal[False] = False
    permissions: tuple[PermissionEntry, ...]

    @field_validator("permissions")
    @classmethod
    def exact_taxonomy(cls, value: tuple[PermissionEntry, ...]) -> tuple[PermissionEntry, ...]:
        if tuple(item.activity for item in value) != tuple(PermissionActivity):
            raise ValueError(
                "permission release must contain the exact successor taxonomy in order"
            )
        return value


class CohortPolicy(ShadowRecordBase):
    record_kind: Literal["cohort_policy"] = "cohort_policy"
    state: ReleaseState
    synthetic_only: Literal[True] = True
    country: Literal["US"] = "US"
    jurisdiction: Literal["US-TX"] = "US-TX"
    industry: Literal["commercial_hvac"] = "commercial_hvac"
    opportunity: Literal["inbound_lead_response_qualification"] = (
        "inbound_lead_response_qualification"
    )
    b2b_only: Literal[True] = True
    target_size: Literal[24] = 24
    future_real_frame_owner_approval_required: Literal[True] = True
    franchise_shared_brand_cap: Literal[1] = 1
    distinct_lead_flow_required_for_location_split: Literal[True] = True
    replacement_reasons: tuple[IneligibilityReason, ...] = tuple(IneligibilityReason)


class SyntheticBusinessCandidate(FrozenModel):
    id: UUID
    fixture_key: str
    synthetic: Literal[True] = True
    display_name: str
    canonical_domain: str
    texas_region: str
    organization_kind: OrganizationKind
    organization_group: str
    lead_flow_key: str
    source_ref: str
    in_texas: bool
    commercial_hvac: bool
    b2b: bool
    operational: bool
    permitted_public_url: bool
    identity_ambiguous: bool = False


class EligibilityDecisionRecord(FrozenModel):
    candidate_id: UUID
    state: EligibilityState
    reasons: tuple[IneligibilityReason, ...]
    unit_key: str
    organization_cluster: str


class SamplingFrame(ShadowRecordBase):
    record_kind: Literal["sampling_frame"] = "sampling_frame"
    state: Literal[ReleaseState.FROZEN] = ReleaseState.FROZEN
    synthetic_only: Literal[True] = True
    cohort_policy_id: UUID
    cohort_policy_hash: str
    frozen_seed: str
    candidates: tuple[SyntheticBusinessCandidate, ...]
    eligibility: tuple[EligibilityDecisionRecord, ...]
    frame_hash: str


class SlotAttempt(FrozenModel):
    candidate_id: UUID
    attempted_at: datetime
    replacement_reason: IneligibilityReason | None = None
    terminal_outcome: CompanyOutcome | None = None


class CohortSlot(FrozenModel):
    slot_number: int
    selected_candidate_id: UUID
    current_candidate_id: UUID
    attempts: tuple[SlotAttempt, ...]


class CohortSelectionManifest(ShadowRecordBase):
    record_kind: Literal["cohort_selection"] = "cohort_selection"
    state: Literal[ReleaseState.FROZEN] = ReleaseState.FROZEN
    synthetic_only: Literal[True] = True
    frame_id: UUID
    frame_hash: str
    selection_algorithm_version: str
    frozen_seed: str
    slots: tuple[CohortSlot, ...]
    reserve_order: tuple[UUID, ...]
    owner_approval_for_future_real_frame: Literal[False] = False


class ArtifactReference(FrozenModel):
    context: Literal["M1", "M2", "M3", "M4", "M5"]
    artifact_id: UUID
    version: str
    artifact_hash: str


class StageLineage(FrozenModel):
    stage: Literal["M1", "M2", "M3", "M4", "M5"]
    inputs: tuple[ArtifactReference, ...]
    output: ArtifactReference
    code_version: str
    configuration_version: str


class RestrictedSnapshotReference(FrozenModel):
    snapshot_id: UUID
    snapshot_version: str
    content_hash: str
    storage_class: Literal["restricted_source_snapshot"] = "restricted_source_snapshot"
    may_contain_incidental_public_person_data: bool
    person_contact_indexing_allowed: Literal[False] = False
    m6_projection_allowed: Literal[False] = False
    ordinary_log_values_allowed: Literal[False] = False
    retention_policy_status: Literal["UNRESOLVED_ADR_0071_A08"] = "UNRESOLVED_ADR_0071_A08"


class CanonicalPipelineSnapshot(FrozenModel):
    fixture_key: str
    synthetic: Literal[True] = True
    source_snapshot: RestrictedSnapshotReference
    source_configuration_version: str
    deterministic_code_version: str
    m1_status: ResearchRunStatus
    m2_analysis_status: AnalysisStatus | None = None
    hypothesis_status: HypothesisStatus | None = None
    economic_value_states: tuple[ValueState, ...] = ()
    audit_state: AuditRevisionState | None = None
    demo_state: DemoRevisionState | None = None
    outreach_state: OutreachRevisionState | None = None
    lineage: tuple[StageLineage, ...]
    contradiction_present: bool = False
    entity_ambiguous: bool = False
    scoped_absence_present: bool = False
    unsupported_claim_present: bool = False
    ai_assistance_used: Literal[False] = False
    economics_engine: Literal["deterministic"] = "deterministic"


class ShadowRunManifest(ShadowRecordBase):
    record_kind: Literal["shadow_run"] = "shadow_run"
    state: RunState
    phase: Literal[ShadowPhase.PHASE_1_COMPANY_ONLY] = ShadowPhase.PHASE_1_COMPANY_ONLY
    synthetic_only: Literal[True] = True
    selection_manifest_id: UUID
    selection_manifest_hash: str
    permission_release_id: UUID
    permission_release_hash: str
    actual_business_count: Literal[0] = 0
    real_web_research_count: Literal[0] = 0
    real_person_count: Literal[0] = 0
    real_contact_count: Literal[0] = 0
    external_communication_count: Literal[0] = 0


class CompanyOutcomeProjection(ShadowRecordBase):
    record_kind: Literal["company_outcome"] = "company_outcome"
    run_id: UUID
    candidate_id: UUID
    phase: Literal[ShadowPhase.PHASE_1_COMPANY_ONLY] = ShadowPhase.PHASE_1_COMPANY_ONLY
    outcome: CompanyOutcome
    determining_reference: ArtifactReference
    stage_lineage: tuple[StageLineage, ...]
    source_snapshot_hash: str
    replay_result_hash: str
    can_create_real_person_candidate: Literal[False] = False
    can_store_real_contact: Literal[False] = False
    can_verify_contact: Literal[False] = False
    can_evaluate_shadow_eligibility: Literal[False] = False
    can_produce_shadow_ready: Literal[False] = False
    can_create_m6_send_ready: Literal[False] = False
    can_transition_to_send_authorized: Literal[False] = False
    consumable_by_delivery_worker: Literal[False] = False

    @field_validator("outcome")
    @classmethod
    def phase_one_ceiling(cls, value: CompanyOutcome) -> CompanyOutcome:
        if value not in PHASE_1_OUTCOMES:
            raise ValueError("Phase 1 cannot produce shadow contact/readiness outcomes")
        return value


class ReviewAssignment(ShadowRecordBase):
    record_kind: Literal["review_assignment"] = "review_assignment"
    run_id: UUID
    candidate_id: UUID
    kind: ReviewKind
    state: ReviewState
    reviewer_pseudonym: str
    independent_from_reviewer: str | None = None
    required: bool
    seeded_qa: bool = False
    stratum_keys: tuple[str, ...] = ()
    decision: ReviewDecision | None = None
    duration_seconds: int | None = None
    warning_codes: tuple[str, ...] = ()

    @field_validator("duration_seconds")
    @classmethod
    def duration_is_measured(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("completed review duration must be measured and positive")
        return value


class QaSelection(FrozenModel):
    candidate_id: UUID
    outcome: CompanyOutcome
    stratum_keys: tuple[str, ...]
    order_hash: str


class QaPlan(ShadowRecordBase):
    record_kind: Literal["qa_plan"] = "qa_plan"
    run_id: UUID
    seed: str
    negative_only: Literal[True] = True
    selections: tuple[QaSelection, ...]
    observed_strata: tuple[str, ...]


class MetricObservation(FrozenModel):
    name: MetricName
    state: MetricState
    numerator: int | None
    denominator: int | None
    value: Decimal | None
    reason: str | None = None


class MetricSnapshot(ShadowRecordBase):
    record_kind: Literal["metric_snapshot"] = "metric_snapshot"
    run_id: UUID
    phase: Literal[ShadowPhase.PHASE_1_COMPANY_ONLY] = ShadowPhase.PHASE_1_COMPANY_ONLY
    observations: tuple[MetricObservation, ...]


class CostEntry(FrozenModel):
    category: CostCategory
    company_id: UUID | None
    operation_ref: str
    currency: Literal["USD"] = "USD"
    monetary_cost: Decimal | None
    duration_seconds: int | None
    pricing_version: str | None
    reason: str | None = None


class CostLedger(ShadowRecordBase):
    record_kind: Literal["cost_ledger"] = "cost_ledger"
    run_id: UUID
    entries: tuple[CostEntry, ...]
    review_time_converted_to_money: Literal[False] = False
    ai_provider_cost: Decimal
    ai_cost_reason: Literal["NO_M6_6_BINDING_ELIGIBLE_FOR_M6_7"] = (
        "NO_M6_6_BINDING_ELIGIBLE_FOR_M6_7"
    )

    @field_validator("ai_provider_cost")
    @classmethod
    def ai_cost_must_be_zero(cls, value: Decimal) -> Decimal:
        if value != Decimal("0"):
            raise ValueError("M6.7A AI provider cost must be USD 0")
        return value


class SafetyIncident(ShadowRecordBase):
    record_kind: Literal["safety_incident"] = "safety_incident"
    run_id: UUID
    candidate_id: UUID | None
    event_type: SafetyEventType
    evidence_refs: tuple[str, ...]
    zero_tolerance: Literal[True] = True


class StopDecision(ShadowRecordBase):
    record_kind: Literal["stop_decision"] = "stop_decision"
    run_id: UUID
    incident_id: UUID
    scope: StopScope
    resulting_run_state: RunState
    commercial_performance_considered: Literal[False] = False
    resumable_without_review: Literal[False] = False


class ReplayAssessment(FrozenModel):
    state: ReplayState
    baseline_result_hash: str
    replay_result_hash: str
    baseline_snapshot_hash: str
    replay_snapshot_hash: str


class M68EvidencePackage(ShadowRecordBase):
    record_kind: Literal["m68_evidence_package"] = "m68_evidence_package"
    run_id: UUID
    synthetic_only: Literal[True] = True
    input_manifest: tuple[str, ...]
    permission_states: dict[PermissionActivity, PermissionState]
    cohort_policy_hash: str
    sampling_frame_hash: str
    selection_manifest_hash: str
    outcome_projection_hashes: tuple[str, ...]
    review_record_hashes: tuple[str, ...]
    metric_snapshot_hash: str
    cost_ledger_hash: str
    safety_incident_hashes: tuple[str, ...]
    stop_decision_hashes: tuple[str, ...]
    capture_replay_assessments: tuple[ReplayAssessment, ...]
    known_limitations: tuple[str, ...]
    unresolved_approvals: tuple[str, ...]
    actual_business_count: Literal[0] = 0
    real_web_research_count: Literal[0] = 0
    real_person_count: Literal[0] = 0
    real_contact_count: Literal[0] = 0
    external_communication_count: Literal[0] = 0
    ai_provider_cost_usd: Decimal = Decimal("0")
    can_create_m6_send_ready: Literal[False] = False
    can_transition_to_send_authorized: Literal[False] = False
    consumable_by_delivery_worker: Literal[False] = False

    @field_validator("ai_provider_cost_usd")
    @classmethod
    def m68_ai_cost_must_be_zero(cls, value: Decimal) -> Decimal:
        if value != Decimal("0"):
            raise ValueError("M6.8 evidence must preserve the M6.7A USD 0 AI cost")
        return value


ShadowRecord = Annotated[
    RealDataPermissionRelease
    | CohortPolicy
    | SamplingFrame
    | CohortSelectionManifest
    | ShadowRunManifest
    | CompanyOutcomeProjection
    | ReviewAssignment
    | QaPlan
    | MetricSnapshot
    | CostLedger
    | SafetyIncident
    | StopDecision
    | M68EvidencePackage,
    Field(discriminator="record_kind"),
]
SHADOW_RECORD_ADAPTER: TypeAdapter[ShadowRecord] = TypeAdapter(ShadowRecord)


class ShadowValidationError(Exception):
    code = "shadow_validation_error"
    safe_message = "shadow-validation operation failed"


class ShadowAuthorizationError(ShadowValidationError):
    code = "forbidden"
    safe_message = "shadow-validation action is not permitted"


class ShadowValidationInputError(ShadowValidationError):
    code = "invalid_input"
    safe_message = "shadow-validation input is invalid"


class ShadowNotFoundError(ShadowValidationError):
    code = "not_found"
    safe_message = "shadow-validation resource not found"
