"""Read-only canonical M1-M4 source adapter for M5."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from opintel_audit.domain import AuditEvidence, FreshnessState
from opintel_audit.ports import AuditRepository
from opintel_demo.ports import DemoRepository
from opintel_opportunity.ports import OpportunityRepository
from opintel_outreach.domain import OutreachCanonicalInputs
from opintel_research.ports import ResearchRepository


class CanonicalOutreachSourceCatalog:
    def __init__(
        self,
        demos: DemoRepository,
        audits: AuditRepository,
        opportunities: OpportunityRepository,
        research: ResearchRepository,
    ) -> None:
        self._demos = demos
        self._audits = audits
        self._opportunities = opportunities
        self._research = research

    def get_inputs(
        self, workspace_id: UUID, demo_revision_id: UUID
    ) -> OutreachCanonicalInputs | None:
        demo = self._demos.get_revision(workspace_id, demo_revision_id)
        if demo is None:
            return None
        audit = self._audits.get_revision(workspace_id, demo.revision.manifest.audit_revision_id)
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
                item.id,
                item.workspace_id,
                item.business_id,
                item.research_run_id,
                item.snapshot_id,
                item.snapshot_version,
                item.source_uri,
                item.captured_at,
                item.content_sha256,
                item.locator,
                item.extracted_fragment,
                item.extractor_name,
                item.extractor_version,
                FreshnessState.CURRENT,
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
        return OutreachCanonicalInputs(
            demo, audit, opportunity, evidence, business.name, profile_hash
        )
