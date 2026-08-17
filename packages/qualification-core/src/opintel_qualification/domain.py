"""Provider-neutral M2.5 domain records, deliberately separate from canonical M2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class TaskClass(StrEnum):
    EVIDENCE_INTERPRETATION = "evidence_interpretation"
    INFERENCE_GENERATION = "inference_generation"
    CONTRADICTION_ANALYSIS = "contradiction_analysis"
    OPPORTUNITY_REASONING = "opportunity_reasoning"
    STRUCTURED_AUDIT_COMPOSITION = "structured_audit_composition"
    VISUAL_WEBSITE_ANALYSIS = "visual_website_analysis"
    LOW_LATENCY_DEMO_CONVERSATION = "low_latency_demo_conversation"


ACTIVE_TASKS = frozenset(
    {
        TaskClass.EVIDENCE_INTERPRETATION,
        TaskClass.INFERENCE_GENERATION,
        TaskClass.CONTRADICTION_ANALYSIS,
        TaskClass.OPPORTUNITY_REASONING,
    }
)


class CorpusPartition(StrEnum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    HIDDEN_QUALIFICATION = "hidden_qualification"
    REGRESSION = "regression"
    ROTATING_CHALLENGE = "rotating_challenge"


class QualificationStatus(StrEnum):
    UNASSESSED = "unassessed"
    EVALUATING = "evaluating"
    QUALIFIED = "qualified"
    CONDITIONAL = "conditional"
    DISQUALIFIED = "disqualified"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class RoutingStage(StrEnum):
    EVALUATION_ONLY = "evaluation_only"
    SHADOW = "shadow"
    ADVISORY = "advisory"


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class ProviderKind(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class ExpectedOutcome(StrEnum):
    STRONG = "strong_candidate"
    WEAK = "weak_candidate"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient_evidence"
    NO_OPPORTUNITY = "no_opportunity_supported"


class GateFailure(StrEnum):
    CRITICAL_FABRICATION = "critical_fabrication"
    INVENTED_CITATION = "invented_citation"
    CITATION_NOT_ENTAILED = "citation_not_entailed"
    CITATION_INCOMPLETE = "citation_incomplete"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    OUTCOME_MISMATCH = "outcome_mismatch"
    ALTERNATIVE_EXPLANATION_MISSING = "alternative_explanation_missing"
    FALSE_UNKNOWN_RESOLUTION = "false_unknown_resolution"
    HARD_CONTRADICTION_DOWNGRADED = "hard_contradiction_downgraded"
    PROMPT_INJECTION_COMPLIANCE = "prompt_injection_compliance"
    SCHEMA_INVALID = "schema_invalid"
    PROVIDER_FAILURE = "provider_failure"
    BUDGET_EXCEEDED = "budget_exceeded"


CRITICAL_GATES = frozenset(
    {
        GateFailure.CRITICAL_FABRICATION,
        GateFailure.INVENTED_CITATION,
        GateFailure.FALSE_UNKNOWN_RESOLUTION,
        GateFailure.HARD_CONTRADICTION_DOWNGRADED,
        GateFailure.PROMPT_INJECTION_COMPLIANCE,
        GateFailure.SCHEMA_INVALID,
    }
)


@dataclass(frozen=True, slots=True)
class TaskContract:
    task_class: TaskClass
    task_version: str
    input_schema_version: str
    output_schema_version: str
    allowed_stages: tuple[RoutingStage, ...]
    authoritative: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceDatum:
    id: UUID
    fragment: str
    source_hash: str
    locator: str
    untrusted: bool = True


@dataclass(frozen=True, slots=True)
class ClaimExpectation:
    label: str
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: UUID
    family: str
    partition: CorpusPartition
    corpus_version: str
    task_class: TaskClass
    task_version: str
    evidence: tuple[EvidenceDatum, ...]
    expected_outcome: ExpectedOutcome
    required_claims: tuple[ClaimExpectation, ...]
    prohibited_claim_terms: tuple[str, ...]
    protected_unknowns: tuple[str, ...]
    hard_contradictions: tuple[str, ...]
    acceptable_alternatives: tuple[str, ...]
    prompt_injection_present: bool
    manifest_hash: str


@dataclass(frozen=True, slots=True)
class AtomicClaim:
    label: str
    statement: str
    evidence_ids: tuple[UUID, ...]
    supported: bool
    fact_kind: str = "public_observation"


@dataclass(frozen=True, slots=True)
class IntelligenceOutput:
    outcome: ExpectedOutcome
    claims: tuple[AtomicClaim, ...]
    preserved_unknowns: tuple[str, ...]
    contradictions: tuple[str, ...]
    alternatives: tuple[str, ...]
    injection_followed: bool = False


@dataclass(frozen=True, slots=True)
class IntelligenceRequest:
    id: UUID
    workspace_id: UUID
    evaluation_run_id: UUID
    case_id: UUID
    task_contract: TaskContract
    stage: RoutingStage
    evidence: tuple[EvidenceDatum, ...]
    evidence_allowlist: tuple[UUID, ...]
    policy_version: str
    corpus_version: str
    data_classification: DataClassification
    prompt_hash: str
    config_hash: str
    max_output_tokens: int
    estimated_cost_micros: int
    trace_id: UUID


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    output: IntelligenceOutput | None
    schema_valid: bool
    failure_code: str | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_ms: int
    estimated_cost_micros: int
    pricing_version: str


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    id: UUID
    workspace_id: UUID
    provider_key: str
    model_key: str
    model_version: str
    deployment_version: str
    config_hash: str
    provider_kind: ProviderKind
    capabilities: tuple[TaskClass, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class QualificationKey:
    deployment_id: UUID
    deployment_version: str
    deployment_config_hash: str
    task_class: TaskClass
    task_version: str
    schema_version: str
    policy_version: str
    corpus_version: str
    data_classification: DataClassification


@dataclass(frozen=True, slots=True)
class QualificationDecision:
    id: UUID
    workspace_id: UUID
    key: QualificationKey
    status: QualificationStatus
    previous_decision_id: UUID | None
    reason: str
    evaluation_run_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    evidence_required: int
    evidence_matched: int
    unsupported_claims: int
    citation_pairs: int
    citation_valid: int
    citation_entailed: int
    unknowns_required: int
    unknowns_preserved: int
    contradictions_required: int
    contradictions_recognized: int
    acceptable_alternatives: int
    schema_valid: bool
    consistency_ratio: str
    reasoning_usefulness: str | None = None


@dataclass(frozen=True, slots=True)
class CaseEvaluationResult:
    id: UUID
    workspace_id: UUID
    evaluation_run_id: UUID
    case_id: UUID
    deployment_id: UUID
    qualification_key: QualificationKey
    metrics: EvaluationMetrics
    gate_failures: tuple[GateFailure, ...]
    attempt_count: int
    output_hash: str | None
    created_at: datetime

    @property
    def critically_failed(self) -> bool:
        return bool(CRITICAL_GATES.intersection(self.gate_failures))


@dataclass(frozen=True, slots=True)
class InvocationLedgerEntry:
    id: UUID
    workspace_id: UUID
    evaluation_run_id: UUID
    case_id: UUID
    deployment_id: UUID
    task_class: TaskClass
    task_version: str
    model_version: str
    deployment_version: str
    prompt_hash: str
    config_hash: str
    policy_version: str
    corpus_version: str
    pricing_version: str
    attempt: int
    fallback_index: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_ms: int
    estimated_cost_micros: int
    validation_outcome: str
    safe_failure_code: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    version: str
    max_invocations: int
    max_reserved_tokens: int
    max_cost_micros: int


@dataclass(frozen=True, slots=True)
class LiveEvaluationPolicy:
    version: str
    enabled: bool
    kill_switch_open: bool
    allowed_deployments: tuple[UUID, ...]
    allowed_tasks: tuple[TaskClass, ...]
    allowed_data_classes: tuple[DataClassification, ...]
    approved_data_policy_ref: str | None


@dataclass(frozen=True, slots=True)
class RouteResult:
    stage: RoutingStage
    deployment_id: UUID | None
    output: IntelligenceOutput | None
    deterministic_m2_fallback: bool
    attempts: int
    reason: str


class QualificationError(Exception):
    code = "qualification_error"
    safe_message = "qualification operation failed"


class QualificationAuthorizationError(QualificationError):
    code = "forbidden"
    safe_message = "qualification action is not permitted"


class QualificationValidationError(QualificationError):
    code = "invalid_input"
    safe_message = "qualification input is invalid"


class QualificationNotFoundError(QualificationError):
    code = "not_found"
    safe_message = "qualification resource not found"
