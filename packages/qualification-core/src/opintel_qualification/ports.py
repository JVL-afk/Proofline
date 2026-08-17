"""M2.5 provider, registry, ledger, and budget ports."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from opintel_qualification.domain import (
    CaseEvaluationResult,
    DeploymentRecord,
    EvaluationCase,
    IntelligenceOutput,
    IntelligenceRequest,
    InvocationLedgerEntry,
    LiveEvaluationPolicy,
    ProviderKind,
    ProviderResponse,
    QualificationDecision,
    QualificationKey,
    QualificationStatus,
)


class ProviderAdapter(Protocol):
    deployment_id: UUID
    provider_kind: ProviderKind

    def invoke(self, request: IntelligenceRequest, attempt: int) -> ProviderResponse: ...


class ProviderCatalog(Protocol):
    def get(self, deployment_id: UUID) -> ProviderAdapter | None: ...


class QualificationRepository(Protocol):
    def initialize(self) -> None: ...
    def add_deployment(self, deployment: DeploymentRecord) -> None: ...
    def get_deployment(
        self, workspace_id: UUID, deployment_id: UUID
    ) -> DeploymentRecord | None: ...
    def list_deployments(self, workspace_id: UUID) -> tuple[DeploymentRecord, ...]: ...
    def append_decision(self, decision: QualificationDecision) -> None: ...
    def latest_decision(
        self, workspace_id: UUID, key: QualificationKey
    ) -> QualificationDecision | None: ...
    def list_decisions(
        self, workspace_id: UUID, status: QualificationStatus | None = None
    ) -> tuple[QualificationDecision, ...]: ...
    def save_case_result(self, result: CaseEvaluationResult) -> None: ...
    def list_case_results(
        self, workspace_id: UUID, evaluation_run_id: UUID
    ) -> tuple[CaseEvaluationResult, ...]: ...
    def save_invocation(self, entry: InvocationLedgerEntry) -> None: ...
    def list_invocations(
        self, workspace_id: UUID, evaluation_run_id: UUID
    ) -> tuple[InvocationLedgerEntry, ...]: ...


class BudgetGuard(Protocol):
    def reserve(
        self,
        workspace_id: UUID,
        evaluation_run_id: UUID,
        requested_tokens: int,
        estimated_cost_micros: int,
    ) -> bool: ...

    def record_actual(
        self,
        workspace_id: UUID,
        evaluation_run_id: UUID,
        actual_tokens: int,
        actual_cost_micros: int,
    ) -> bool: ...


class LiveEvaluationGate(Protocol):
    def authorize(
        self,
        policy: LiveEvaluationPolicy,
        request: IntelligenceRequest,
        deployment: DeploymentRecord,
    ) -> bool: ...


class ReasoningUsefulnessHook(Protocol):
    def rate(self, case: EvaluationCase, output: IntelligenceOutput) -> str | None: ...
