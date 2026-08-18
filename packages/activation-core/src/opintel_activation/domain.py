"""Immutable M6.5 governance records and fail-closed readiness projections."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReleaseState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class DecisionStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"


class SourceStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    RESEARCH_ONLY = "research_only"
    IDENTITY_ONLY = "identity_only"
    CONDITIONAL_CONTACT_USE = "conditional_contact_use"
    APPROVED_CONTACT_USE = "approved_contact_use"
    PROHIBITED = "prohibited"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class ProductionProofScope(StrEnum):
    SYNTAX_VALID = "syntax_valid"
    DOMAIN_MAIL_CAPABLE = "domain_mail_capable"
    MAILBOX_ACCEPTANCE_CURRENT = "mailbox_acceptance_current"
    SOURCE_OBSERVED = "source_observed"
    PERSON_CONTACT_ASSOCIATION = "person_contact_association"
    PROFESSIONAL_CONTEXT_CURRENT = "professional_context_current"
    FIRST_PARTY_CONFIRMED = "first_party_confirmed"
    SOURCE_USE_APPROVED = "source_use_approved"


class AttestationState(StrEnum):
    MISSING = "missing"
    EVIDENCED = "evidenced"
    FAILED = "failed"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class ExternalPresenceKind(StrEnum):
    DOMAIN_ACQUIRED = "domain_acquired"
    WEBSITE_READY = "website_ready"
    SENDER_DOMAIN_VERIFIED = "sender_domain_verified"
    EMAIL_DELIVERY_READY = "email_delivery_ready"


class CertificationState(StrEnum):
    UNASSESSED = "unassessed"
    EVALUATING = "evaluating"
    CERTIFIED = "certified"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    DISQUALIFIED = "disqualified"


class PermissionState(StrEnum):
    NOT_AUTHORIZED = "not_authorized"
    AUTHORIZED = "authorized"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class RealDataActivity(StrEnum):
    REAL_COMPANY_RESEARCH = "real_company_research"
    PROFESSIONAL_IDENTITY_RESOLUTION = "professional_identity_resolution"
    REAL_CONTACT_STORAGE = "real_contact_storage"
    CONTACT_VERIFICATION = "contact_verification"
    ELIGIBILITY_EVALUATION = "eligibility_evaluation"
    SHADOW_READY = "shadow_ready"


class ReadinessState(StrEnum):
    NOT_READY = "not_ready"
    READY_FOR_PROVIDER_CERTIFICATION = "ready_for_provider_certification"
    READY_FOR_FIRST_REAL_CONTACT_REVIEW = "ready_for_first_real_contact_review"


class GateState(StrEnum):
    SATISFIED = "satisfied"
    BLOCKED = "blocked"
    WARNING = "warning"


class GatePhase(StrEnum):
    PROVIDER_CERTIFICATION = "provider_certification"
    FIRST_REAL_CONTACT = "first_real_contact"


class ShadowState(StrEnum):
    BLOCKED = "blocked"
    SHADOW_READY = "shadow_ready"


class ActivationRecordBase(FrozenModel):
    record_kind: str
    id: UUID
    workspace_id: UUID
    version: str
    configuration_hash: str
    created_at: datetime


class DecisionEntry(FrozenModel):
    decision_id: str
    status: DecisionStatus
    accountable_role: str
    evidence_refs: tuple[str, ...] = ()
    approval_classes: tuple[str, ...] = ()


class LaunchEnvelopeRelease(ActivationRecordBase):
    record_kind: Literal["launch_envelope"] = "launch_envelope"
    state: ReleaseState
    country: Literal["US"]
    recipient_jurisdictions: tuple[Literal["US-TX"], ...]
    industry: Literal["commercial_hvac"]
    opportunity: Literal["inbound_lead_response_qualification"]
    channel: Literal["b2b_email"]
    content_type: Literal["text/plain"] = "text/plain"
    recipient_count: Literal[1] = 1
    messages_per_authorization: Literal[1] = 1
    links_allowed: Literal[False] = False
    attachments_allowed: Literal[False] = False
    tracking_allowed: Literal[False] = False
    sequences_allowed: Literal[False] = False
    integrations_allowed: tuple[str, ...] = ()
    ai_required: Literal[False] = False
    nationwide_authorization: Literal[False] = False
    delivery_enabled_by_default: Literal[False] = False
    approved_adr: Literal["ADR-0043"] = "ADR-0043"
    effective_at: datetime
    expires_at: datetime


class ActivationDecisionSnapshot(ActivationRecordBase):
    record_kind: Literal["decision_snapshot"] = "decision_snapshot"
    decisions: tuple[DecisionEntry, ...]


class PolicyApproval(FrozenModel):
    approval_class: str
    accountable_role: str
    evidence_ref: str
    approved_at: datetime


class ProductionOutreachPolicyRelease(ActivationRecordBase):
    record_kind: Literal["outreach_policy"] = "outreach_policy"
    state: ReleaseState
    fixture_only: bool
    legal_rules_populated: bool
    sender_legal_entity: str | None
    allowed_sender_jurisdictions: tuple[str, ...]
    allowed_recipient_jurisdictions: tuple[str, ...]
    channel: str
    message_purpose: str
    permitted_source_categories: tuple[str, ...]
    required_proof_scopes: tuple[ProductionProofScope, ...]
    required_disclosure_slots: tuple[str, ...]
    suppression_scope: str | None
    cadence_policy_ref: str | None
    contact_time_policy_ref: str | None
    behavior_policy_ref: str | None
    privacy_rights_policy_ref: str | None
    retention_policy_version: str | None
    provider_constraints_ref: str | None
    security_requirements_ref: str | None
    sender_domain_requirements_ref: str | None
    rollout_limits_ref: str | None
    monitoring_ref: str | None
    emergency_suspension_ref: str | None
    approvals: tuple[PolicyApproval, ...]
    effective_at: datetime
    expires_at: datetime


class SourceRule(FrozenModel):
    category: str
    status: SourceStatus
    permitted_acquisition: str
    permitted_use: str
    provenance_required: bool
    proof_scopes: tuple[ProductionProofScope, ...]
    freshness_policy_ref: str | None
    restrictions: tuple[str, ...]
    real_outreach_allowed: bool


class ContactSourcePolicyRelease(ActivationRecordBase):
    record_kind: Literal["source_policy"] = "source_policy"
    state: ReleaseState
    proposal_only: bool
    live_authorization_allowed: bool
    shadow_authorization_allowed: bool
    rules: tuple[SourceRule, ...]
    approvals: tuple[PolicyApproval, ...]
    effective_at: datetime
    expires_at: datetime


class VerificationProfileRelease(ActivationRecordBase):
    record_kind: Literal["verification_profile"] = "verification_profile"
    state: ReleaseState
    proposal_only: bool
    live_authorization_allowed: bool
    shadow_authorization_allowed: bool
    required_scopes: tuple[ProductionProofScope, ...]
    association_alternatives: tuple[tuple[ProductionProofScope, ...], ...]
    inferred_pattern_sufficient: Literal[False] = False
    third_party_enrichment_allowed: Literal[False] = False
    approvals: tuple[PolicyApproval, ...]
    effective_at: datetime
    expires_at: datetime


class AuthorizationPolicyRelease(ActivationRecordBase):
    record_kind: Literal["authorization_policy"] = "authorization_policy"
    state: ReleaseState
    content_reviewer_separate: bool
    contact_steward_separate: bool
    self_authorization_allowed: bool
    step_up_required: bool
    authorization_expiry_policy_ref: str | None
    reason_required: bool
    exact_one_message_acknowledgement: bool
    hard_gate_override_allowed: bool
    approvals: tuple[PolicyApproval, ...]
    effective_at: datetime
    expires_at: datetime


class RetentionRule(FrozenModel):
    record_category: str
    classification: str
    encrypted: bool
    redacted_display: bool
    routine_logging_allowed: bool
    retention_period_ref: str | None
    deletion_process_ref: str | None
    tombstone_behavior_ref: str | None
    legal_hold_process_ref: str | None


class RetentionPolicyRelease(ActivationRecordBase):
    record_kind: Literal["retention_policy"] = "retention_policy"
    state: ReleaseState
    complete: bool
    rules: tuple[RetentionRule, ...]
    suppression_tombstone_policy_ref: str | None
    approvals: tuple[PolicyApproval, ...]
    effective_at: datetime
    expires_at: datetime


class ExternalPresenceAttestation(ActivationRecordBase):
    record_kind: Literal["external_presence"] = "external_presence"
    kind: ExternalPresenceKind
    state: AttestationState
    subject_ref: str
    evidence_refs: tuple[str, ...]
    attested_by: str
    effective_at: datetime
    expires_at: datetime


class ProviderCertificationRecord(ActivationRecordBase):
    record_kind: Literal["provider_certification"] = "provider_certification"
    provider_ref: str
    deployment_ref: str
    state: CertificationState
    launch_envelope_hash: str
    policy_hash: str
    source_policy_hash: str
    tracking_disabled: bool
    one_message_only: bool
    ambiguous_submit_reconciliation: bool
    signed_webhooks: bool
    replay_protection: bool
    provider_only_egress: bool
    secret_isolation: bool
    test_report_ref: str
    contractual_review_ref: str
    effective_at: datetime
    expires_at: datetime


class InfrastructureControlRequirementSet(ActivationRecordBase):
    record_kind: Literal["infrastructure_requirements"] = "infrastructure_requirements"
    required_controls: tuple[str, ...]


class InfrastructureControlAttestation(ActivationRecordBase):
    record_kind: Literal["infrastructure_attestation"] = "infrastructure_attestation"
    control_id: str
    state: AttestationState
    evidence_refs: tuple[str, ...]
    attested_by: str
    effective_at: datetime
    expires_at: datetime


class OperationalReadinessRecord(ActivationRecordBase):
    record_kind: Literal["operational_readiness"] = "operational_readiness"
    state: AttestationState
    accountable_roles: dict[str, str]
    runbook_ref: str | None
    reply_monitoring_evidenced: bool
    kill_switch_evidenced: bool
    complaint_threshold_suspended: bool
    provider_outage_procedure_ref: str | None
    ambiguous_status_procedure_ref: str | None
    effective_at: datetime
    expires_at: datetime


class GovernanceReviewRecord(ActivationRecordBase):
    record_kind: Literal["governance_review"] = "governance_review"
    review_class: Literal["security", "privacy", "legal", "product"]
    state: AttestationState
    scope_hash: str
    evidence_refs: tuple[str, ...]
    accountable_role: str
    effective_at: datetime
    expires_at: datetime


class ReadinessTestReport(ActivationRecordBase):
    record_kind: Literal["readiness_test_report"] = "readiness_test_report"
    state: AttestationState
    suite_version: str
    passed_case_ids: tuple[str, ...]
    failed_case_ids: tuple[str, ...]
    network_call_count: int
    credential_count: int


class RealDataPermission(FrozenModel):
    activity: RealDataActivity
    state: PermissionState
    approval_refs: tuple[str, ...]
    policy_versions: dict[str, str]


class RealDataPermissionRelease(ActivationRecordBase):
    record_kind: Literal["real_data_permissions"] = "real_data_permissions"
    state: ReleaseState
    permissions: tuple[RealDataPermission, ...]
    effective_at: datetime
    expires_at: datetime


class M66GateRelease(ActivationRecordBase):
    record_kind: Literal["m66_gate"] = "m66_gate"
    state: ReleaseState
    required_conditions: tuple[str, ...]
    live_delivery_readiness_required: Literal[False] = False
    ai_authoritative: Literal[False] = False


class ArtifactReference(FrozenModel):
    record_kind: str
    artifact_id: UUID
    version: str
    configuration_hash: str


class GateResult(FrozenModel):
    gate_id: str
    requirement: str
    state: GateState
    blocking: bool
    phase: GatePhase
    artifact: ArtifactReference | None
    missing_evidence: tuple[str, ...]
    accountable_role: str
    required_approval_class: tuple[str, ...]
    remediation_category: str
    policy_config_version: str


class LiveActivationReadiness(ActivationRecordBase):
    record_kind: Literal["activation_readiness"] = "activation_readiness"
    state: ReadinessState
    launch_envelope_id: UUID | None
    input_manifest: tuple[ArtifactReference, ...]
    gates: tuple[GateResult, ...]
    blocking_gate_ids: tuple[str, ...]
    aggregate_score: None = None
    manually_promoted: Literal[False] = False
    creates_m6_send_state: Literal[False] = False


class ShadowCandidateManifest(FrozenModel):
    candidate_ref: str
    launch_envelope_id: UUID
    country: str
    recipient_jurisdiction: str
    recipient_timezone: str | None
    source_category: str
    source_policy_id: UUID
    verification_profile_id: UUID
    policy_release_id: UUID
    permission_release_id: UUID
    proof_scopes: tuple[ProductionProofScope, ...]
    m5_revision_id: UUID
    m5_revision_hash: str
    expected_m5_revision_hash: str
    policy_hash: str
    expected_policy_hash: str
    compliance_slots: tuple[str, ...]
    suppression_tombstone_active: bool


class ShadowReadinessAssessment(ActivationRecordBase):
    record_kind: Literal["shadow_readiness"] = "shadow_readiness"
    state: ShadowState
    candidate_ref: str
    exact_lineage: tuple[ArtifactReference, ...]
    policy_versions: dict[str, str]
    blockers: tuple[str, ...]
    can_create_m6_send_ready: Literal[False] = False
    can_transition_to_send_authorized: Literal[False] = False
    consumable_by_delivery_worker: Literal[False] = False


ActivationRecord = Annotated[
    LaunchEnvelopeRelease
    | ActivationDecisionSnapshot
    | ProductionOutreachPolicyRelease
    | ContactSourcePolicyRelease
    | VerificationProfileRelease
    | AuthorizationPolicyRelease
    | RetentionPolicyRelease
    | ExternalPresenceAttestation
    | ProviderCertificationRecord
    | InfrastructureControlRequirementSet
    | InfrastructureControlAttestation
    | OperationalReadinessRecord
    | GovernanceReviewRecord
    | ReadinessTestReport
    | RealDataPermissionRelease
    | M66GateRelease
    | LiveActivationReadiness
    | ShadowReadinessAssessment,
    Field(discriminator="record_kind"),
]
ACTIVATION_RECORD_ADAPTER: TypeAdapter[ActivationRecord] = TypeAdapter(ActivationRecord)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ActivationError(Exception):
    code = "activation_error"
    safe_message = "activation-readiness operation failed"


class ActivationNotFoundError(ActivationError):
    code = "not_found"
    safe_message = "activation-readiness resource not found"


class ActivationAuthorizationError(ActivationError):
    code = "forbidden"
    safe_message = "activation-readiness action is not permitted"


class ActivationValidationError(ActivationError):
    code = "invalid_input"
    safe_message = "activation-readiness input is invalid"
