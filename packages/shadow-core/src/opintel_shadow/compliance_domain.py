"""M6.7 Phase 1 counsel-controlled minimization and incident contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import field_validator, model_validator

from opintel_shadow.domain import FrozenModel


class CaptureDisposition(StrEnum):
    DURABLE_MINIMIZED_CAPTURE = "DURABLE_MINIMIZED_CAPTURE"
    QUARANTINE_AND_REVIEW = "QUARANTINE_AND_REVIEW"


class PhaseOneDataClass(StrEnum):
    SUCCESSFUL_MINIMIZED_SNAPSHOT = "successful_minimized_snapshot"
    FAILED_ABORTED_CAPTURE = "failed_aborted_capture"
    EXTRACTED_TEXT = "extracted_text"
    EVIDENCE_EXCERPT_LOCATOR = "evidence_excerpt_locator"
    ANALYSIS_ARTIFACT = "analysis_artifact"
    HUMAN_REVIEW_RECORD = "human_review_record"
    COMPANY_METRIC = "company_metric"
    APPROVED_AGGREGATE_METRIC = "approved_aggregate_metric"
    OPERATIONAL_LOG = "operational_log"
    SECURITY_ACCESS_LOG = "security_access_log"
    ENCRYPTED_BACKUP = "encrypted_backup"
    DELETION_TOMBSTONE = "deletion_tombstone"


class DestructionMethod(StrEnum):
    HARD_DELETE_PRIMARY_AND_DERIVED = "hard_delete_primary_and_derived"
    OBJECT_VERSION_LIFECYCLE_DELETE = "object_version_lifecycle_delete"
    LOG_EXPIRY = "log_expiry"
    CRYPTOGRAPHIC_ERASURE = "cryptographic_erasure"
    CONTENT_FREE_TOMBSTONE = "content_free_tombstone"


class AuthorityVerification(StrEnum):
    STATUTORILY_VERIFIED = "STATUTORILY_VERIFIED"
    ATTORNEY_ASSERTED_CITATION_UNRESOLVED = "ATTORNEY_ASSERTED_CITATION_UNRESOLVED"


class IncidentWorkflowState(StrEnum):
    DETECTED = "DETECTED"
    ASSESSMENT_REQUIRED = "ASSESSMENT_REQUIRED"
    NOTIFICATION_DECISION_READY = "NOTIFICATION_DECISION_READY"
    LEGAL_REVIEW_REQUIRED = "LEGAL_REVIEW_REQUIRED"


class HostReviewState(StrEnum):
    PENDING_PER_HOST_REVIEW = "PENDING_PER_HOST_REVIEW"
    APPROVED = "APPROVED"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"


class MinimizedCapture(FrozenModel):
    source_uri: str
    captured_at: datetime
    raw_content_sha256: str
    minimized_content_sha256: str | None
    minimized_text: str | None
    disposition: CaptureDisposition
    removed_email_count: int
    removed_phone_count: int
    removed_structured_contact_blocks: int
    required_evidence_markers: tuple[str, ...]
    quarantine_reasons: tuple[str, ...]
    raw_body_retained: Literal[False] = False
    person_contact_projection_allowed: Literal[False] = False
    minimizer_version: Literal["phase1-minimizer@1"] = "phase1-minimizer@1"

    @model_validator(mode="after")
    def durable_or_quarantined(self) -> MinimizedCapture:
        if self.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE:
            if not self.minimized_text or not self.minimized_content_sha256:
                raise ValueError("durable minimized capture requires minimized content")
            if self.quarantine_reasons:
                raise ValueError("durable minimized capture cannot have quarantine reasons")
        elif self.minimized_text is not None or self.minimized_content_sha256 is not None:
            raise ValueError("quarantine record cannot retain page content")
        return self


class RetentionRule(FrozenModel):
    data_class: PhaseOneDataClass
    retention_days: int
    backup_overhang_days: int
    maximum_effective_retention_days: int
    destruction_methods: tuple[DestructionMethod, ...]
    applies_to_stores: tuple[str, ...]
    redacted_excerpts_only: bool = False

    @model_validator(mode="after")
    def effective_maximum_is_explicit(self) -> RetentionRule:
        if self.maximum_effective_retention_days != (
            self.retention_days + self.backup_overhang_days
        ):
            raise ValueError("maximum effective retention must include backup overhang")
        return self


class RedactedReviewArtifact(FrozenModel):
    review_id: str
    minimized_capture_sha256: str
    evidence_locator: str
    redacted_excerpt: str
    raw_source_body_retained: Literal[False] = False
    person_contact_fields_present: Literal[False] = False


class PhaseOneRetentionPolicy(FrozenModel):
    policy_id: str
    state: Literal["APPROVED_POLICY_NOT_LIVE_EFFECTIVE"]
    rules: tuple[RetentionRule, ...]
    tombstone_allowed_fields: tuple[str, ...]
    tombstone_source_uri_allowed: Literal[False] = False
    legal_hold_scoped_expiring_reapproval_required: Literal[True] = True
    approval_actor_binding: Literal["OWNER_SUBJECT_PENDING_IDP_BINDING"]

    @field_validator("rules")
    @classmethod
    def exact_classes(cls, value: tuple[RetentionRule, ...]) -> tuple[RetentionRule, ...]:
        if tuple(item.data_class for item in value) != tuple(PhaseOneDataClass):
            raise ValueError("retention policy must govern every Phase 1 data class exactly once")
        return value


class StatutoryAuthority(FrozenModel):
    authority_id: str
    official_url: str
    section: str
    subsection: str
    retrieved_at: datetime
    proposition: str
    verification: AuthorityVerification


class IncidentAssessment(FrozenModel):
    incident_id: str
    detected_at: datetime
    detection_summary: str
    sensitive_information_maintained: bool | None
    breach_determined: bool | None
    breach_determined_at: datetime | None
    affected_texas_residents: int | None
    affected_subjects_determined: bool
    notification_required: bool | None


class IncidentDeadline(FrozenModel):
    recipient_class: Literal["AFFECTED_INDIVIDUAL", "TEXAS_ATTORNEY_GENERAL"]
    deadline_at: datetime
    authority_id: str
    authority_section: str


class IncidentDecision(FrozenModel):
    incident_id: str
    state: IncidentWorkflowState
    deadlines: tuple[IncidentDeadline, ...]
    authority_ids: tuple[str, ...]
    unresolved_rules: tuple[str, ...]
    external_notification_sent: Literal[False] = False
    immutable_record_hash: str


class PerHostSourceReview(FrozenModel):
    source_id: str
    exact_host: str
    reviewed_at: datetime
    reviewer_actor_binding: str
    terms_reviewed: bool
    robots_reviewed: bool
    access_restrictions_reviewed: bool
    automated_access_restrictions_reviewed: bool
    capture_storage_reuse_reviewed: bool
    unresolved_copyright_or_contract_issue: bool
    material_prohibition: bool
    robots_is_technical_not_legal_authority: Literal[True] = True
    state: HostReviewState

    @model_validator(mode="after")
    def derived_state_is_honest(self) -> PerHostSourceReview:
        completed = all(
            (
                self.terms_reviewed,
                self.robots_reviewed,
                self.access_restrictions_reviewed,
                self.automated_access_restrictions_reviewed,
                self.capture_storage_reuse_reviewed,
            )
        )
        expected = (
            HostReviewState.SOURCE_BLOCKED
            if self.material_prohibition or self.unresolved_copyright_or_contract_issue
            else HostReviewState.APPROVED
            if completed
            else HostReviewState.PENDING_PER_HOST_REVIEW
        )
        if self.state is not expected:
            raise ValueError("host review state does not match recorded review evidence")
        return self


__all__ = [
    "AuthorityVerification",
    "CaptureDisposition",
    "DestructionMethod",
    "HostReviewState",
    "IncidentAssessment",
    "IncidentDeadline",
    "IncidentDecision",
    "IncidentWorkflowState",
    "MinimizedCapture",
    "PerHostSourceReview",
    "PhaseOneDataClass",
    "PhaseOneRetentionPolicy",
    "RedactedReviewArtifact",
    "RetentionRule",
    "StatutoryAuthority",
]
