"""M3 audit domain: structured claims are authoritative; prose is a projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AuditOperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditKind(StrEnum):
    FULL = "full"
    INTERNAL_DIAGNOSTIC = "internal_diagnostic"


class AuditRevisionState(StrEnum):
    REVIEW_REQUIRED = "review_required"
    QC_FAILED = "qc_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    SUPERSEDED = "superseded"


class AuditValidity(StrEnum):
    CURRENT = "current"
    STALE_INPUTS = "stale_inputs"
    INVALIDATED = "invalidated"


class ClaimType(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    ESTIMATE = "estimate"
    RECOMMENDATION = "recommendation"


class BindingRelation(StrEnum):
    SUPPORTED_BY = "supported_by"
    CONTRADICTED_BY = "contradicted_by"
    CONTEXTUALIZED_BY = "contextualized_by"
    DERIVED_FROM = "derived_from"
    DEPENDS_ON = "depends_on"
    LIMITED_BY = "limited_by"


class FreshnessState(StrEnum):
    CURRENT = "current"
    STALE_PERMITTED = "stale_permitted"
    STALE_REQUIRES_ACKNOWLEDGMENT = "stale_requires_acknowledgment"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class QcSeverity(StrEnum):
    WARNING = "warning"
    HARD_FAILURE = "hard_failure"


class AuditReviewDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


@dataclass(frozen=True, slots=True)
class AuditEvidence:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    snapshot_id: UUID
    snapshot_version: str
    source_uri: str
    captured_at: datetime
    content_sha256: str
    locator: str
    bounded_excerpt: str
    extractor_name: str
    extractor_version: str
    freshness: FreshnessState = FreshnessState.CURRENT


@dataclass(frozen=True, slots=True)
class AuditInputManifest:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    analysis_run_id: UUID
    hypothesis_id: UUID
    hypothesis_revision_id: UUID
    hypothesis_manifest_checksum: str
    opportunity_review_id: UUID | None
    opportunity_review_manifest_checksum: str | None
    opportunity_definition_version: str
    observation_ids: tuple[UUID, ...]
    inference_revision_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    evidence_fingerprints: tuple[str, ...]
    contradictory_evidence_ids: tuple[UUID, ...]
    information_gap_ids: tuple[UUID, ...]
    assumption_revision_ids: tuple[UUID, ...]
    economic_run_id: UUID
    economic_formula_version: str
    score_snapshot_id: UUID
    score_config_version: str
    audit_schema_version: str
    composition_policy_version: str
    qc_policy_version: str
    checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditSection:
    id: UUID
    key: str
    title: str
    ordinal: int
    claim_ids: tuple[UUID, ...]
    structured_items: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class AuditClaim:
    id: UUID
    section_key: str
    claim_type: ClaimType
    subject_business_id: UUID
    predicate: str
    display_text: str
    evidence_ids: tuple[UUID, ...] = ()
    observation_ids: tuple[UUID, ...] = ()
    inference_revision_ids: tuple[UUID, ...] = ()
    assumption_revision_ids: tuple[UUID, ...] = ()
    economic_run_id: UUID | None = None
    dependency_claim_ids: tuple[UUID, ...] = ()
    contradictory_evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class QcFinding:
    id: UUID
    code: str
    severity: QcSeverity
    message: str
    claim_id: UUID | None = None
    acknowledgment_required: bool = False


@dataclass(frozen=True, slots=True)
class AuditRevision:
    id: UUID
    audit_id: UUID
    revision: int
    parent_revision_id: UUID | None
    workspace_id: UUID
    business_id: UUID
    hypothesis_id: UUID
    kind: AuditKind
    manifest: AuditInputManifest
    sections: tuple[AuditSection, ...]
    claims: tuple[AuditClaim, ...]
    qc_findings: tuple[QcFinding, ...]
    state: AuditRevisionState
    validity: AuditValidity
    revision_hash: str
    rendered_text: str
    created_by: str
    created_at: datetime

    @property
    def hard_qc_passed(self) -> bool:
        return not any(item.severity == QcSeverity.HARD_FAILURE for item in self.qc_findings)


@dataclass(frozen=True, slots=True)
class AuditOperation:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    hypothesis_id: UUID
    expected_hypothesis_revision_id: UUID
    audit_id: UUID
    parent_revision_id: UUID | None
    kind: AuditKind
    status: AuditOperationStatus
    idempotency_key: str
    trace_id: UUID
    attempt_count: int
    max_attempts: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    lease_expires_at: datetime | None = None
    audit_revision_id: UUID | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AuditReviewDecision:
    id: UUID
    audit_revision_id: UUID
    revision_hash: str
    manifest_hash: str
    decision: AuditReviewDecisionType
    actor: str
    actor_roles: tuple[str, ...]
    reason: str
    self_review: bool
    acknowledged_qc_codes: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditBundle:
    revision: AuditRevision
    latest_review: AuditReviewDecision | None = None
    review_valid: bool = False


class AuditError(Exception):
    code = "audit_error"
    safe_message = "audit operation failed"


class AuditNotFoundError(AuditError):
    code = "not_found"
    safe_message = "audit resource not found"


class AuditAuthorizationError(AuditError):
    code = "forbidden"
    safe_message = "audit action is not permitted"


class AuditValidationError(AuditError):
    code = "invalid_input"
    safe_message = "audit input is invalid"


class AuditQcError(AuditError):
    code = "qc_failed"
    safe_message = "audit quality checks failed"


class TransientCompositionError(AuditError):
    code = "composition_transient_failure"
    safe_message = "audit composition failed temporarily"


class CompositionTimeoutError(TransientCompositionError):
    code = "composition_timeout"
