"""M2 ports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from opintel_opportunity.domain import (
    AssumptionRevision,
    EconomicRun,
    EvidenceReference,
    InferenceRevision,
    OpportunityAnalysisRun,
    OpportunityBundle,
    OpportunityHypothesisRevision,
    ReviewDecision,
    ScoreSnapshot,
)


class EvidenceCatalog(Protocol):
    def list_evidence(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> tuple[EvidenceReference, ...]: ...


class OpportunityRepository(Protocol):
    def initialize(self) -> None: ...
    def create_or_get_run(
        self, run: OpportunityAnalysisRun, idempotency_key: str
    ) -> tuple[OpportunityAnalysisRun, bool]: ...
    def invalidate_reviews_for_new_evidence(
        self,
        workspace_id: UUID,
        business_id: UUID,
        definition_version: str,
        new_analysis_run_id: UUID,
        now: datetime,
    ) -> None: ...
    def get_run(self, workspace_id: UUID, run_id: UUID) -> OpportunityAnalysisRun | None: ...
    def claim_run(self, now: datetime, lease: timedelta) -> OpportunityAnalysisRun | None: ...
    def save_bundle(self, bundle: OpportunityBundle) -> None: ...
    def fail_run(self, run_id: UUID, error_code: str, now: datetime) -> None: ...
    def get_bundle_by_run(self, workspace_id: UUID, run_id: UUID) -> OpportunityBundle | None: ...
    def get_bundle_by_hypothesis(
        self, workspace_id: UUID, hypothesis_id: UUID
    ) -> OpportunityBundle | None: ...
    def save_recalculation(
        self,
        previous: OpportunityBundle,
        hypothesis: OpportunityHypothesisRevision,
        assumptions: tuple[AssumptionRevision, ...],
        economic_run: EconomicRun,
        score_snapshot: ScoreSnapshot,
    ) -> OpportunityBundle: ...
    def save_review(
        self, previous: OpportunityBundle, decision: ReviewDecision
    ) -> OpportunityBundle: ...
    def save_inference_rejection(
        self,
        previous: OpportunityBundle,
        inference: InferenceRevision,
        hypothesis: OpportunityHypothesisRevision,
    ) -> OpportunityBundle: ...


class MockReasoner(Protocol):
    def validate(self, supplied_evidence_ids: tuple[UUID, ...]) -> tuple[UUID, ...]: ...
