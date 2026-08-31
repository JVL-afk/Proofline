"""M1 evidence catalog and deterministic mock-reasoner adapters."""

from __future__ import annotations

from uuid import UUID

from opintel_opportunity.domain import EvidenceReference, ResearchRunStats
from opintel_research.domain import PageStatus
from opintel_research.ports import ResearchRepository


class ResearchEvidenceCatalog:
    def __init__(self, repository: ResearchRepository) -> None:
        self._repository = repository

    def _page_purposes(self, workspace_id: UUID, research_run_id: UUID) -> dict[UUID, str]:
        return {
            page.id: page.page_purpose
            for page in self._repository.list_pages(workspace_id, research_run_id)
        }

    def list_evidence(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> tuple[EvidenceReference, ...]:
        run = self._repository.get_run(workspace_id, research_run_id)
        if run is None or run.business_id != business_id:
            return ()
        purposes = self._page_purposes(workspace_id, research_run_id)
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
                fact_class=item.fact_class,
                page_purpose=purposes.get(item.page_id, "unclassified"),
            )
            for item in self._repository.list_evidence(workspace_id, research_run_id)
        )

    def research_run_stats(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> ResearchRunStats | None:
        run = self._repository.get_run(workspace_id, research_run_id)
        if run is None or run.business_id != business_id:
            return None
        evidence = self._repository.list_evidence(workspace_id, research_run_id)
        pages = self._repository.list_pages(workspace_id, research_run_id)
        histogram: dict[str, int] = {}
        for item in evidence:
            histogram[item.fact_class] = histogram.get(item.fact_class, 0) + 1
        purposes = sorted(
            (page.normalized_url, page.page_purpose)
            for page in pages
            if page.status is not PageStatus.FAILED
        )
        return ResearchRunStats(
            research_run_id=run.id,
            status=run.status.value,
            pages_attempted=run.pages_attempted,
            pages_succeeded=run.pages_succeeded,
            fact_class_histogram=tuple(sorted(histogram.items())),
            captured_page_purposes=tuple(purposes),
        )

    def business_display_name(self, workspace_id: UUID, business_id: UUID) -> str | None:
        business = self._repository.get_business(workspace_id, business_id)
        return business.name if business is not None else None


class EchoMockReasoner:
    """Proves the port contract without inference, network, tools, prompts, or providers."""

    def validate(self, supplied_evidence_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return supplied_evidence_ids
