"""M6.7C live-research gate contracts; implementation confers no live authority."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import Field, TypeAdapter, field_validator, model_validator

from opintel_shadow.domain import FrozenModel, PermissionActivity, PermissionState


class ApprovalState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class GovernedDataClass(StrEnum):
    RESTRICTED_SOURCE_CAPTURE = "restricted_source_capture"
    EXTRACTED_TEXT = "extracted_text"
    EVIDENCE = "evidence"
    REVIEW_ARTIFACT = "review_artifact"
    METRIC = "metric"
    OPERATIONAL_LOG = "operational_log"
    ACCESS_AUDIT_LOG = "access_audit_log"
    BACKUP = "backup"
    DELETION_TOMBSTONE = "deletion_tombstone"


class Sensitivity(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class DeletionBehavior(StrEnum):
    DELETE_CONTENT_RETAIN_TOMBSTONE = "delete_content_retain_tombstone"
    EXPIRE_LOG_RECORD = "expire_log_record"
    CRYPTOGRAPHIC_OR_PHYSICAL_EXPIRY = "cryptographic_or_physical_expiry"


class BackupHandling(StrEnum):
    SAME_OR_SHORTER_EXPIRY = "same_or_shorter_expiry"
    EXCLUDED_FROM_BACKUP = "excluded_from_backup"
    ENCRYPTED_EXPIRY_BOUND = "encrypted_expiry_bound"


class LegalHoldBehavior(StrEnum):
    BLOCK_DELETION_WHILE_ACTIVE = "block_deletion_while_active"
    NOT_ELIGIBLE_FOR_HOLD = "not_eligible_for_hold"


class SourceKind(StrEnum):
    DISCOVERY_SOURCE = "discovery_source"
    RESEARCH_SOURCE = "research_source"


class SourceAccessMethod(StrEnum):
    PUBLIC_HTTP_GET_HEAD = "public_http_get_head"
    PUBLIC_READ_ONLY_API = "public_read_only_api"


class TermsReviewState(StrEnum):
    NOT_REVIEWED = "not_reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class RobotsTreatment(StrEnum):
    REQUIRED_FAIL_CLOSED = "required_fail_closed"
    PROVIDER_API_NOT_APPLICABLE = "provider_api_not_applicable"


class OperationalRole(StrEnum):
    PROJECT_OWNER = "project_owner"
    OPPORTUNITY_REVIEWER = "opportunity_reviewer"
    INDEPENDENT_SECOND_REVIEWER = "independent_second_reviewer"
    INCIDENT_OWNER = "incident_owner"
    PRIVACY_DATA_OWNER = "privacy_data_owner"
    KILL_SWITCH_OPERATOR = "kill_switch_operator"
    SECURITY_ENVIRONMENT_OWNER = "security_environment_owner"
    QUALIFIED_LEGAL_REVIEWER = "qualified_legal_reviewer"


class KillSwitchState(StrEnum):
    CLEAR = "clear"
    TRIPPED = "tripped"


class WorkState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkStage(StrEnum):
    DISCOVERY = "discovery"
    RESEARCH = "research"
    CAPTURE_PERSISTENCE = "capture_persistence"
    DOWNSTREAM_REPLAY = "downstream_replay"


class StageProgression(StrEnum):
    STAGE_0_PREFLIGHT = "stage_0_preflight"
    STAGE_1_SLOT_ONE = "stage_1_slot_one"
    STAGE_1_PAUSED = "stage_1_paused"
    STAGE_2_SMALL_BATCH = "stage_2_small_batch"
    STAGE_2_PAUSED = "stage_2_paused"
    STAGE_3_REMAINDER = "stage_3_remainder"
    COMPLETE = "complete"


class ReadinessState(StrEnum):
    NOT_READY_FOR_REAL_RESEARCH_AUTHORIZATION = "not_ready_for_real_research_authorization"
    READY_FOR_REAL_RESEARCH_AUTHORIZATION = "ready_for_real_research_authorization"


class CheckState(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class GateRecordBase(FrozenModel):
    record_kind: str
    id: UUID
    workspace_id: UUID
    version: str
    configuration_hash: str
    created_at: datetime


class DataHandlingPolicyRevision(GateRecordBase):
    record_kind: Literal["data_handling_policy"] = "data_handling_policy"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    data_classes: tuple[GovernedDataClass, ...] = tuple(GovernedDataClass)
    restricted_captures_immutable: Literal[True] = True
    incidental_public_person_data_capture_only: Literal[True] = True
    person_contact_domain_extraction_allowed: Literal[False] = False
    person_contact_indexing_allowed: Literal[False] = False
    person_contact_search_allowed: Literal[False] = False
    m6_projection_allowed: Literal[False] = False
    contact_values_in_ordinary_logs_allowed: Literal[False] = False
    person_contact_metrics_allowed: Literal[False] = False

    @field_validator("data_classes")
    @classmethod
    def exact_governed_classes(
        cls, value: tuple[GovernedDataClass, ...]
    ) -> tuple[GovernedDataClass, ...]:
        if value != tuple(GovernedDataClass):
            raise ValueError("data-handling policy requires every governed class exactly once")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> DataHandlingPolicyRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("data policy expiry must follow its effective time")
        return self


class RetentionDecision(FrozenModel):
    data_class: GovernedDataClass
    purpose: str
    sensitivity: Sensitivity
    retention_seconds: int
    deletion_behavior: DeletionBehavior
    backup_handling: BackupHandling
    legal_hold_behavior: LegalHoldBehavior
    allowed_consumers: tuple[OperationalRole, ...]
    extension_requires_successor_approval: Literal[True] = True

    @field_validator("retention_seconds")
    @classmethod
    def positive_explicit_duration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("retention duration must be explicitly positive")
        return value


class RetentionPolicyRevision(GateRecordBase):
    record_kind: Literal["retention_policy"] = "retention_policy"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    decisions: tuple[RetentionDecision, ...]

    @field_validator("decisions")
    @classmethod
    def exact_data_class_schedule(
        cls, value: tuple[RetentionDecision, ...]
    ) -> tuple[RetentionDecision, ...]:
        if tuple(item.data_class for item in value) != tuple(GovernedDataClass):
            raise ValueError("retention policy requires every governed data class exactly once")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> RetentionPolicyRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("retention policy expiry must follow its effective time")
        return self


class SourceInstance(FrozenModel):
    source_id: str
    kind: SourceKind
    exact_identity: str
    scheme: Literal["http", "https"]
    host: str
    provider: str
    purpose: str
    access_method: SourceAccessMethod
    publicly_accessible: Literal[True] = True
    authenticated: Literal[False] = False
    terms_review_state: TermsReviewState
    terms_review_id: str
    robots_treatment: RobotsTreatment
    max_logical_fetches: int
    max_total_attempts: int
    max_response_bytes: int
    minimum_delay_milliseconds: int
    browser_allowed: Literal[False] = False
    allowed_data_categories: tuple[str, ...]
    storage_restrictions: tuple[str, ...]
    reuse_restrictions: tuple[str, ...]
    person_contact_extraction_allowed: Literal[False] = False
    interactive_operations_allowed: Literal[False] = False
    effective_at: datetime
    expires_at: datetime
    accountable_approval_id: str

    @model_validator(mode="after")
    def valid_source(self) -> SourceInstance:
        if not self.host or self.host != self.host.lower() or self.host.endswith("."):
            raise ValueError("source host must be an exact lowercase DNS name")
        if self.expires_at <= self.effective_at:
            raise ValueError("source expiry must follow its effective time")
        if (
            min(
                self.max_logical_fetches,
                self.max_total_attempts,
                self.max_response_bytes,
            )
            <= 0
        ):
            raise ValueError("source budgets must be explicitly positive")
        if self.max_total_attempts < self.max_logical_fetches:
            raise ValueError("source attempt cap cannot be below logical fetch cap")
        return self


class SourceRegistryRevision(GateRecordBase):
    record_kind: Literal["source_registry"] = "source_registry"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    browser_policy: Literal["DISABLED"] = "DISABLED"
    sources: tuple[SourceInstance, ...]

    @field_validator("sources")
    @classmethod
    def unique_sources(cls, value: tuple[SourceInstance, ...]) -> tuple[SourceInstance, ...]:
        identities = [(item.source_id, item.kind) for item in value]
        if len(identities) != len(set(identities)):
            raise ValueError("source instances must be unique by ID and kind")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> SourceRegistryRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("source registry expiry must follow its effective time")
        return self


class EnvironmentAttestationRevision(GateRecordBase):
    record_kind: Literal["environment_attestation"] = "environment_attestation"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    tenancy_boundary_ref: str
    environment_identity: str
    region: str
    encryption_at_rest_ref: str
    encryption_in_transit_ref: str
    storage_isolation_ref: str
    research_egress_identity_ref: str
    workload_identity_ref: str
    operator_access_ref: str
    mfa_oidc_ref: str
    secrets_isolation_ref: str
    audit_logging_ref: str
    backup_policy_ref: str
    kill_switch_owner_ref: str
    synthetic_attestation: bool

    @model_validator(mode="after")
    def valid_window(self) -> EnvironmentAttestationRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("environment attestation expiry must follow its effective time")
        return self


class RoleAssignment(FrozenModel):
    role: OperationalRole
    subject_ref: str
    assignment_approval_id: str


class RoleAssignmentRevision(GateRecordBase):
    record_kind: Literal["role_assignments"] = "role_assignments"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    synthetic_assignments: bool
    assignments: tuple[RoleAssignment, ...]

    @field_validator("assignments")
    @classmethod
    def exact_roles_and_independence(
        cls, value: tuple[RoleAssignment, ...]
    ) -> tuple[RoleAssignment, ...]:
        if tuple(item.role for item in value) != tuple(OperationalRole):
            raise ValueError("every operational role must be assigned exactly once in order")
        by_role = {item.role: item.subject_ref for item in value}
        if (
            by_role[OperationalRole.OPPORTUNITY_REVIEWER]
            == by_role[OperationalRole.INDEPENDENT_SECOND_REVIEWER]
        ):
            raise ValueError("second opportunity reviewer must be a different human")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> RoleAssignmentRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("role assignment expiry must follow its effective time")
        return self


class BudgetPolicyRevision(GateRecordBase):
    record_kind: Literal["budget_policy"] = "budget_policy"
    state: ApprovalState
    approval_ids: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime
    cohort_hard_cap_usd: Decimal | None
    discovery_sub_budget_usd: Decimal | None
    research_sub_budget_usd: Decimal | None
    storage_compute_sub_budget_usd: Decimal | None
    shared_overhead_sub_budget_usd: Decimal | None
    max_logical_page_fetches: Literal[120] = 120
    max_total_attempts: Literal[360] = 360
    max_response_bytes: Literal[36_000_000] = 36_000_000
    max_retries_per_logical_fetch: int
    ai_budget_usd: Decimal = Decimal("0")

    @field_validator("ai_budget_usd")
    @classmethod
    def ai_zero(cls, value: Decimal) -> Decimal:
        if value != Decimal("0"):
            raise ValueError("M6.7C AI budget must remain USD 0")
        return value

    @field_validator("max_retries_per_logical_fetch")
    @classmethod
    def bounded_retries(cls, value: int) -> int:
        if value < 0 or value > 2:
            raise ValueError("Phase 1 permits at most two retries per logical fetch")
        return value

    @model_validator(mode="after")
    def valid_window_and_money(self) -> BudgetPolicyRevision:
        if self.expires_at <= self.effective_at:
            raise ValueError("budget expiry must follow its effective time")
        values = (
            self.cohort_hard_cap_usd,
            self.discovery_sub_budget_usd,
            self.research_sub_budget_usd,
            self.storage_compute_sub_budget_usd,
            self.shared_overhead_sub_budget_usd,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("monetary budgets cannot be negative")
        return self

    @property
    def monetary_approval_complete(self) -> bool:
        values = (
            self.cohort_hard_cap_usd,
            self.discovery_sub_budget_usd,
            self.research_sub_budget_usd,
            self.storage_compute_sub_budget_usd,
            self.shared_overhead_sub_budget_usd,
        )
        if any(value is None for value in values):
            return False
        sub_budgets = (cast(Decimal, value) for value in values[1:])
        return self.cohort_hard_cap_usd == sum(sub_budgets, Decimal("0"))


class LiveResearchPermissionRelease(GateRecordBase):
    record_kind: Literal["live_research_permission"] = "live_research_permission"
    activity: PermissionActivity
    state: PermissionState
    jurisdiction: Literal["US-TX"] = "US-TX"
    vertical: Literal["COMMERCIAL_HVAC"] = "COMMERCIAL_HVAC"
    purpose: Literal["B2B_INBOUND_LEAD_RESPONSE_ANALYSIS"] = "B2B_INBOUND_LEAD_RESPONSE_ANALYSIS"
    source_registry_id: UUID
    source_registry_hash: str
    retention_policy_id: UUID
    retention_policy_hash: str
    environment_id: UUID
    environment_hash: str
    cohort_policy_id: UUID
    cohort_or_run_restriction: str
    starts_at: datetime
    expires_at: datetime
    approval_ids: tuple[str, ...]
    kill_switch_id: UUID
    suspended_reason: str | None = None
    revoked_at: datetime | None = None

    @field_validator("activity")
    @classmethod
    def only_discovery_or_research(cls, value: PermissionActivity) -> PermissionActivity:
        if value not in {
            PermissionActivity.REAL_BUSINESS_DISCOVERY,
            PermissionActivity.REAL_PUBLIC_RESEARCH,
        }:
            raise ValueError("M6.7C release supports only discovery or public research")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> LiveResearchPermissionRelease:
        if self.expires_at <= self.starts_at:
            raise ValueError("permission expiry must follow its start")
        if self.state is PermissionState.SUSPENDED and not self.suspended_reason:
            raise ValueError("suspended permission requires a reason")
        return self


class KillSwitchRecord(GateRecordBase):
    record_kind: Literal["kill_switch"] = "kill_switch"
    state: KillSwitchState
    operator_ref: str
    reason: str
    activated_at: datetime | None
    blocks_discovery: Literal[True] = True
    blocks_research: Literal[True] = True
    blocks_retries: Literal[True] = True
    preserves_captured_evidence: Literal[True] = True


class EgressRequest(FrozenModel):
    workspace_id: UUID
    activity: PermissionActivity
    source_id: str
    url: str
    method: Literal["GET", "HEAD"] = "GET"
    expected_release_id: UUID
    expected_configuration_hash: str


class EgressReceipt(FrozenModel):
    source_id: str
    normalized_url: str
    final_url: str
    status_code: int
    response_bytes: int
    transport_calls: int
    live_provider: Literal[False] = False


class SyntheticStoredArtifact(FrozenModel):
    artifact_ref: str
    data_class: GovernedDataClass
    created_at: datetime
    retention_policy_id: UUID
    content_hash: str
    superseded: bool = False


class WorkItem(FrozenModel):
    id: UUID
    workspace_id: UUID
    idempotency_key: str
    stage: WorkStage
    payload_hash: str
    state: WorkState
    attempt_count: int
    max_attempts: int
    version: int
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    side_effectful_operation: Literal[False] = False


class StageLineageRecord(GateRecordBase):
    record_kind: Literal["stage_lineage"] = "stage_lineage"
    work_item_id: UUID
    event: str
    input_hash: str
    output_hash: str | None
    attempt_number: int
    worker_ref: str | None


class BudgetReservation(GateRecordBase):
    record_kind: Literal["budget_reservation"] = "budget_reservation"
    budget_policy_id: UUID
    operation_ref: str
    logical_fetches: int
    total_attempts: int
    response_bytes: int
    monetary_usd: Decimal | None
    reconciled: bool = False


class LegalHold(FrozenModel):
    hold_id: str
    data_class: GovernedDataClass
    reason: str
    approval_id: str
    effective_at: datetime
    expires_at: datetime


class DeletionAuditRecord(GateRecordBase):
    record_kind: Literal["deletion_audit"] = "deletion_audit"
    data_class: GovernedDataClass
    artifact_ref: str
    retention_policy_id: UUID
    eligible_at: datetime
    deleted_at: datetime
    deletion_behavior: DeletionBehavior
    backup_handling: BackupHandling
    content_deleted: Literal[True] = True
    tombstone_ref: str
    superseded_artifact: bool
    legal_hold_checked: Literal[True] = True


class CohortGateResult(GateRecordBase):
    record_kind: Literal["cohort_gate_result"] = "cohort_gate_result"
    target_size: Literal[24] = 24
    can_freeze: bool
    blockers: tuple[str, ...]
    discovery_release_id: UUID | None
    research_release_required_for_fetch: Literal[True] = True


class StagedExecutionManifest(GateRecordBase):
    record_kind: Literal["staged_execution"] = "staged_execution"
    synthetic_only: Literal[True] = True
    frozen_cohort_hash: str
    frozen_candidate_order: tuple[str, ...]
    progression: StageProgression
    small_batch_size: int
    completed_candidate_ids: tuple[str, ...]
    recorded_outcomes: dict[str, str]
    continuation_approval_ids: tuple[str, ...]

    @field_validator("small_batch_size")
    @classmethod
    def bounded_small_batch(cls, value: int) -> int:
        if value < 2 or value >= 24:
            raise ValueError("small batch must be between 2 and 23")
        return value


class PreflightCheck(FrozenModel):
    code: str
    state: CheckState
    evidence_refs: tuple[str, ...]


class SyntheticPreflightResult(GateRecordBase):
    record_kind: Literal["synthetic_preflight"] = "synthetic_preflight"
    synthetic_only: Literal[True] = True
    checks: tuple[PreflightCheck, ...]
    readiness: ReadinessState
    authorization_blockers: tuple[str, ...]
    permission_states: dict[PermissionActivity, PermissionState]
    real_businesses_accessed: Literal[0] = 0
    real_business_urls_fetched: Literal[0] = 0
    real_people_processed: Literal[0] = 0
    real_contacts_processed: Literal[0] = 0
    live_source_provider_calls: Literal[0] = 0
    external_communications: Literal[0] = 0
    delivery_capabilities: Literal[0] = 0
    ai_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def exact_disabled_permissions(self) -> SyntheticPreflightResult:
        if set(self.permission_states) != set(PermissionActivity):
            raise ValueError("preflight must report every successor permission")
        if any(
            state is not PermissionState.NOT_AUTHORIZED for state in self.permission_states.values()
        ):
            raise ValueError("M6.7C preflight cannot authorize real-data permissions")
        if self.readiness is ReadinessState.READY_FOR_REAL_RESEARCH_AUTHORIZATION and any(
            check.state is CheckState.FAIL for check in self.checks
        ):
            raise ValueError("technical readiness requires every synthetic check to pass")
        return self


GateRecord = Annotated[
    DataHandlingPolicyRevision
    | RetentionPolicyRevision
    | SourceRegistryRevision
    | EnvironmentAttestationRevision
    | RoleAssignmentRevision
    | BudgetPolicyRevision
    | LiveResearchPermissionRelease
    | KillSwitchRecord
    | StageLineageRecord
    | BudgetReservation
    | DeletionAuditRecord
    | CohortGateResult
    | StagedExecutionManifest
    | SyntheticPreflightResult,
    Field(discriminator="record_kind"),
]
GATE_RECORD_ADAPTER: TypeAdapter[GateRecord] = TypeAdapter(GateRecord)


class LiveResearchGateError(Exception):
    code = "live_research_gate_error"
    safe_message = "live research gate rejected the operation"


class LiveResearchNotAuthorized(LiveResearchGateError):
    code = "live_research_not_authorized"


class LiveResearchPolicyError(LiveResearchGateError):
    code = "live_research_policy_error"


class LiveResearchStopped(LiveResearchGateError):
    code = "live_research_stopped"


class BudgetExceeded(LiveResearchGateError):
    code = "budget_exceeded"


class WorkLeaseError(LiveResearchGateError):
    code = "work_lease_error"
