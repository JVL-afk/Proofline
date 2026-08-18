"""Read-only canonical source and local capability adapters for M4."""

from __future__ import annotations

import hashlib
import json
import secrets
from uuid import UUID

from opintel_audit.domain import AuditEvidence, FreshnessState
from opintel_audit.ports import AuditRepository
from opintel_demo.domain import DemoCanonicalInputs
from opintel_opportunity.ports import OpportunityRepository
from opintel_research.ports import ResearchRepository


class CanonicalDemoSourceCatalog:
    def __init__(
        self,
        audits: AuditRepository,
        opportunities: OpportunityRepository,
        research: ResearchRepository,
    ) -> None:
        self._audits = audits
        self._opportunities = opportunities
        self._research = research

    def get_inputs(self, workspace_id: UUID, audit_revision_id: UUID) -> DemoCanonicalInputs | None:
        audit = self._audits.get_revision(workspace_id, audit_revision_id)
        if audit is None:
            return None
        opportunity = self._opportunities.get_bundle_by_hypothesis(
            workspace_id, audit.revision.hypothesis_id
        )
        if opportunity is None or opportunity.hypothesis is None:
            return None
        business = self._research.get_business(workspace_id, audit.revision.business_id)
        if business is None:
            return None
        raw_evidence = self._research.list_evidence(
            workspace_id, audit.revision.manifest.research_run_id
        )
        evidence = tuple(
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
            for item in raw_evidence
        )
        profile_hash = hashlib.sha256(
            json.dumps(
                {
                    "id": str(business.id),
                    "workspace_id": str(business.workspace_id),
                    "name": business.name,
                    "canonical_url": business.canonical_url,
                    "created_at": business.created_at.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return DemoCanonicalInputs(audit, opportunity, evidence, business.name, profile_hash)


class SecureLocalCapabilityFactory:
    """Opaque local capabilities; persistence receives only SHA-256 digests."""

    def issue(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()
