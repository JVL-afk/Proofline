"""M2 semantic domain. Evidence, observations, inferences, and estimates stay distinct."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INSUFFICIENT_DATA = "insufficient_data"
    FAILED = "failed"


class HypothesisStatus(StrEnum):
    CANDIDATE = "candidate"
    NEEDS_INFORMATION = "needs_information"
    READY_FOR_REVIEW = "ready_for_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RevisionStatus(StrEnum):
    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ValueState(StrEnum):
    KNOWN = "known"
    PROPOSED = "proposed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EconomicStatus(StrEnum):
    COMPLETE = "complete"
    HYPOTHETICAL = "hypothetical"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_INPUT = "invalid_input"


class Band(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class MissingBehavior(StrEnum):
    BLOCK = "block"
    CAP_BAND = "cap_band"
    LOWER_BAND = "lower_band"
    INCOMPLETE = "incomplete"


class GapPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EconomicEffect(StrEnum):
    BLOCKS_MODEL = "blocks_model"
    MATERIALLY_CHANGES_MODEL = "materially_changes_model"
    NO_DIRECT_EFFECT = "no_direct_effect"


class ReviewDecisionType(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    REQUEST_INFORMATION = "request_information"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
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
    fragment: str
    extractor_name: str
    extractor_version: str


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisRun:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    operation_id: UUID
    trace_id: UUID
    definition_version: str
    status: AnalysisStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    lease_expires_at: datetime | None = None
    hypothesis_id: UUID | None = None
    current_hypothesis_revision_id: UUID | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    analysis_run_id: UUID
    evidence_id: UUID
    predicate: str
    value: str
    scope: str
    normalizer_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InferenceRevision:
    id: UUID
    logical_id: UUID
    revision: int
    analysis_run_id: UUID
    statement: str
    observation_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    contradictory_evidence_ids: tuple[UUID, ...]
    alternatives: tuple[str, ...]
    rule_version: str
    confidence_band: Band
    status: RevisionStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InformationGap:
    id: UUID
    hypothesis_id: UUID
    gap_type: str
    description: str
    priority: GapPriority
    affected_component: str
    economic_effect: EconomicEffect
    blocks_review_readiness: bool
    suggested_validation_question: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AssumptionRevision:
    id: UUID
    hypothesis_id: UUID
    key: str
    revision: int
    value_state: ValueState
    decimal_value: str | None
    unit: str
    currency: str | None
    time_basis: str
    source_kind: str
    provenance: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EconomicRun:
    id: UUID
    hypothesis_id: UUID
    formula_version: str
    status: EconomicStatus
    assumption_revision_ids: tuple[UUID, ...]
    monthly_potential_incremental_revenue: str | None
    annualized_potential_incremental_revenue: str | None
    currency: str
    result_label: str
    manifest_checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FactorResult:
    name: str
    band: Band
    missing_behavior: MissingBehavior
    rationale: str


@dataclass(frozen=True, slots=True)
class ScoreSnapshot:
    id: UUID
    hypothesis_id: UUID
    config_version: str
    factors: tuple[FactorResult, ...]
    review_priority_band: str
    manifest_checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OpportunityHypothesisRevision:
    id: UUID
    logical_id: UUID
    revision: int
    workspace_id: UUID
    business_id: UUID
    analysis_run_id: UUID
    definition_version: str
    statement: str
    status: HypothesisStatus
    observation_ids: tuple[UUID, ...]
    inference_revision_ids: tuple[UUID, ...]
    supporting_evidence_ids: tuple[UUID, ...]
    contradictory_evidence_ids: tuple[UUID, ...]
    alternative_explanations: tuple[str, ...]
    feasibility_dependencies: tuple[str, ...]
    assumption_revision_ids: tuple[UUID, ...]
    economic_run_id: UUID
    score_snapshot_id: UUID
    manifest_checksum: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    id: UUID
    hypothesis_id: UUID
    hypothesis_revision_id: UUID
    inference_revision_ids: tuple[UUID, ...]
    assumption_revision_ids: tuple[UUID, ...]
    economic_run_id: UUID
    score_snapshot_id: UUID
    manifest_checksum: str
    decision: ReviewDecisionType
    actor: str
    actor_roles: tuple[str, ...]
    reason: str
    self_review: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OpportunityBundle:
    run: OpportunityAnalysisRun
    observations: tuple[Observation, ...]
    inference: InferenceRevision | None
    hypothesis: OpportunityHypothesisRevision | None
    gaps: tuple[InformationGap, ...]
    assumptions: tuple[AssumptionRevision, ...]
    economic_run: EconomicRun | None
    score_snapshot: ScoreSnapshot | None
    latest_review: ReviewDecision | None = None
    review_valid: bool = False


class OpportunityError(Exception):
    code = "opportunity_error"
    safe_message = "opportunity operation failed"


class OpportunityNotFoundError(OpportunityError):
    code = "not_found"
    safe_message = "opportunity resource not found"


class OpportunityAuthorizationError(OpportunityError):
    code = "forbidden"
    safe_message = "opportunity action is not permitted"


class OpportunityValidationError(OpportunityError):
    code = "invalid_input"
    safe_message = "opportunity input is invalid"
