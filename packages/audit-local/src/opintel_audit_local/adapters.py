"""Read-only M1/M2 source catalog for deterministic audits."""

from __future__ import annotations

from uuid import UUID

from opintel_audit.domain import AuditEvidence, FreshnessState
from opintel_opportunity.domain import OpportunityBundle
from opintel_opportunity.ports import OpportunityRepository
from opintel_research.ports import ResearchRepository


class CanonicalAuditSourceCatalog:
    def __init__(
        self,
        opportunities: OpportunityRepository,
        research: ResearchRepository,
    ) -> None:
        self._opportunities = opportunities
        self._research = research

    def get_opportunity_bundle(
        self, workspace_id: UUID, hypothesis_id: UUID
    ) -> OpportunityBundle | None:
        return self._opportunities.get_bundle_by_hypothesis(workspace_id, hypothesis_id)

    def list_evidence(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> tuple[AuditEvidence, ...]:
        run = self._research.get_run(workspace_id, research_run_id)
        if run is None or run.business_id != business_id:
            return ()
        return tuple(
            AuditEvidence(
                id=item.id,
                workspace_id=item.workspace_id,
                business_id=item.business_id,
                research_run_id=item.research_run_id,
                snapshot_id=item.snapshot_id,
                snapshot_version=item.snapshot_version,
                source_uri=item.source_uri,
                captured_at=item.captured_at,
                content_sha256=item.content_sha256,
                locator=item.locator,
                bounded_excerpt=item.extracted_fragment,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
                freshness=FreshnessState.CURRENT,
            )
            for item in self._research.list_evidence(workspace_id, research_run_id)
        )
