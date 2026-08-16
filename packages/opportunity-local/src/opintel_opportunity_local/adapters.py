"""M1 evidence catalog and deterministic mock-reasoner adapters."""

from __future__ import annotations

from uuid import UUID

from opintel_opportunity.domain import EvidenceReference
from opintel_research.ports import ResearchRepository


class ResearchEvidenceCatalog:
    def __init__(self, repository: ResearchRepository) -> None:
        self._repository = repository

    def list_evidence(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> tuple[EvidenceReference, ...]:
        run = self._repository.get_run(workspace_id, research_run_id)
        if run is None or run.business_id != business_id:
            return ()
        return tuple(
            EvidenceReference(
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
                fragment=item.extracted_fragment,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
            )
            for item in self._repository.list_evidence(workspace_id, research_run_id)
        )


class EchoMockReasoner:
    """Proves the port contract without inference, network, tools, prompts, or providers."""

    def validate(self, supplied_evidence_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return supplied_evidence_ids
