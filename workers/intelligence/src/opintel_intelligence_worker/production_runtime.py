"""Exact-ID canonical M1-M5 adapter for the bounded sampled-slot coordinator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_audit import AuditApplicationService, AuditReviewDecisionType, AuditWorkflowRunner
from opintel_demo import DemoApplicationService, DemoReviewDecisionType, DemoWorkflowRunner
from opintel_m0.domain import Principal
from opintel_opportunity import OpportunityApplicationService, OpportunityWorkflowRunner
from opintel_opportunity.domain import AnalysisStatus, ReviewDecisionType
from opintel_outreach import (
    OutreachApplicationService,
    OutreachReviewDecisionType,
    OutreachWorkflowRunner,
)
from opintel_research import ResearchWorkflowRunner
from opintel_research.domain import PageStatus, ResearchRunStatus
from opintel_research_local import SqlAlchemyResearchRepository

from opintel_intelligence_worker.orchestration import CoordinatedStageArtifact, ShadowStage

COORDINATOR_ACTOR = "m67-bounded-sampled-slot-coordinator"


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class TruthfulTerminal(RuntimeError):
    def __init__(self, reason: str, revision_id: UUID, output_sha256: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.revision_id = revision_id
        self.output_sha256 = output_sha256


@dataclass(frozen=True, slots=True)
class StageResult:
    revision_id: UUID
    output_sha256: str


class CanonicalSampledSlotStageRuntime:
    """Run only exact coordinator-created IDs; ordinary polling is never used."""

    def __init__(
        self,
        *,
        workspace_id: UUID,
        work_item_id: UUID,
        business_id: UUID,
        principal: Principal,
        research_repository: SqlAlchemyResearchRepository,
        research_runner: ResearchWorkflowRunner,
        opportunity_service: OpportunityApplicationService,
        opportunity_runner: OpportunityWorkflowRunner,
        audit_service: AuditApplicationService,
        audit_runner: AuditWorkflowRunner,
        demo_service: DemoApplicationService,
        demo_runner: DemoWorkflowRunner,
        outreach_service: OutreachApplicationService,
        outreach_runner: OutreachWorkflowRunner,
    ) -> None:
        if principal.subject != COORDINATOR_ACTOR or principal.workspace_id != workspace_id:
            raise ValueError("production stage runtime requires the bounded coordinator principal")
        self._workspace = workspace_id
        self._work_item = work_item_id
        self._business = business_id
        self._principal = principal
        self._research_repository = research_repository
        self._research_runner = research_runner
        self._opportunity_service = opportunity_service
        self._opportunity_runner = opportunity_runner
        self._audit_service = audit_service
        self._audit_runner = audit_runner
        self._demo_service = demo_service
        self._demo_runner = demo_runner
        self._outreach_service = outreach_service
        self._outreach_runner = outreach_runner

    def execute(
        self, stage: ShadowStage, predecessor: CoordinatedStageArtifact | None
    ) -> StageResult:
        if stage is ShadowStage.M1_MINIMIZED_EVIDENCE:
            return self._m1(predecessor)
        if predecessor is None:
            raise ValueError("downstream canonical stage requires exact predecessor")
        if stage is ShadowStage.M2_OPPORTUNITY_ECONOMICS:
            return self._m2(predecessor)
        if stage is ShadowStage.M3_EVIDENCE_LINKED_AUDIT:
            return self._m3(predecessor)
        if stage is ShadowStage.M4_DETERMINISTIC_DEMO:
            return self._m4(predecessor)
        if stage is ShadowStage.M5_SHADOW_OUTREACH_PACKAGE:
            return self._m5(predecessor)
        if stage is ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED:
            return StageResult(
                uuid5(NAMESPACE_URL, f"m67-terminal:{self._work_item}"),
                hashlib.sha256(stage.value.encode()).hexdigest(),
            )
        raise ValueError("unsupported bounded stage")

    def _m1(self, predecessor: CoordinatedStageArtifact | None) -> StageResult:
        if predecessor is not None:
            raise ValueError("M1 cannot have a predecessor")
        if not self._research_runner.run_exact_sampled(self._work_item):
            run = self._research_repository.get_run(self._workspace, self._work_item)
            if run is None or not run.status.terminal:
                raise ValueError("exact sampled M1 work item was not claimable")
        run = self._research_repository.get_run(self._workspace, self._work_item)
        if run is None or not run.status.terminal:
            raise ValueError("exact sampled M1 did not reach a terminal state")
        evidence = self._research_repository.list_evidence(self._workspace, self._work_item)
        pages = self._research_repository.list_pages(self._workspace, self._work_item)
        output = _sha(
            {
                "bytes_stored": run.bytes_stored,
                "coverage_record_sha256": run.coverage_record_sha256,
                "crawl_protocol_version": run.crawl_protocol_version,
                "evidence": [
                    (
                        str(item.id),
                        item.content_sha256,
                        item.locator,
                        item.snapshot_version,
                        item.fact_class,
                    )
                    for item in evidence
                ],
                "page_purposes": sorted(
                    (page.normalized_url, page.page_purpose)
                    for page in pages
                    if page.status is not PageStatus.FAILED
                ),
                "pages_attempted": run.pages_attempted,
                "pages_succeeded": run.pages_succeeded,
                "research_run_id": str(run.id),
                "status": run.status.value,
            }
        )
        if run.status is ResearchRunStatus.FAILED:
            raise TruthfulTerminal("M1_RESEARCH_FAILED", run.id, output)
        return StageResult(run.id, output)

    def _m2(self, predecessor: CoordinatedStageArtifact) -> StageResult:
        if predecessor.revision_id != self._work_item:
            raise ValueError("M2 predecessor is not the exact M1 research revision")
        run, _ = self._opportunity_service.start_run(
            self._principal,
            self._business,
            self._work_item,
            f"m67:{self._work_item}:m2",
        )
        if not self._opportunity_runner.run_exact(run.id, COORDINATOR_ACTOR):
            bundle = self._opportunity_service.get_bundle_by_run(self._principal, run.id)
        else:
            bundle = self._opportunity_service.get_bundle_by_run(self._principal, run.id)
        if bundle.run.status is AnalysisStatus.INSUFFICIENT_DATA or bundle.hypothesis is None:
            output = _sha(
                {
                    "analysis_run_id": str(bundle.run.id),
                    "observations": [str(item.id) for item in bundle.observations],
                    "status": bundle.run.status.value,
                }
            )
            raise TruthfulTerminal("M2_INSUFFICIENT_EVIDENCE", bundle.run.id, output)
        reviewed = self._opportunity_service.review(
            self._principal,
            bundle.hypothesis.logical_id,
            bundle.hypothesis.id,
            ReviewDecisionType.ACCEPT,
            "Deterministic Phase 1 predecessor acceptance under the exact execution authority.",
        )
        assert reviewed.hypothesis is not None and reviewed.latest_review is not None
        return StageResult(
            reviewed.hypothesis.id,
            _sha(
                {
                    "analysis_run_id": str(reviewed.run.id),
                    "hypothesis_revision_id": str(reviewed.hypothesis.id),
                    "manifest": reviewed.hypothesis.manifest_checksum,
                    "review_id": str(reviewed.latest_review.id),
                    "status": reviewed.hypothesis.status.value,
                }
            ),
        )

    def _m3(self, predecessor: CoordinatedStageArtifact) -> StageResult:
        opportunity = self._opportunity_service.get_bundle_by_hypothesis_revision(
            self._principal, predecessor.revision_id
        )
        if opportunity.hypothesis is None or opportunity.hypothesis.id != predecessor.revision_id:
            raise ValueError("M3 predecessor is not the exact accepted M2 revision")
        operation, _ = self._audit_service.start_generation(
            self._principal,
            opportunity.hypothesis.logical_id,
            opportunity.hypothesis.id,
            f"m67:{self._work_item}:m3:{predecessor.artifact_sha256}",
        )
        self._audit_runner.run_exact(operation.id, COORDINATOR_ACTOR)
        revisions = self._audit_service.list_revisions(self._principal, operation.audit_id)
        if len(revisions) != 1:
            raise ValueError("exact M3 operation did not produce one revision")
        revision = revisions[0].revision
        reviewed = self._audit_service.review(
            self._principal,
            revision.id,
            revision.revision_hash,
            revision.manifest.checksum,
            AuditReviewDecisionType.APPROVE,
            "Deterministic Phase 1 predecessor acceptance under the exact execution authority.",
            tuple(
                item.code for item in revision.qc_findings if item.acknowledgment_required
            ),
        )
        return StageResult(
            reviewed.revision.id,
            _sha(
                {
                    "manifest": reviewed.revision.manifest.checksum,
                    "review_id": str(reviewed.latest_review.id) if reviewed.latest_review else None,
                    "revision_hash": reviewed.revision.revision_hash,
                    "revision_id": str(reviewed.revision.id),
                    "state": reviewed.revision.state.value,
                }
            ),
        )

    def _m4(self, predecessor: CoordinatedStageArtifact) -> StageResult:
        audit = self._audit_service.get_revision(self._principal, predecessor.revision_id)
        if audit.revision.id != predecessor.revision_id or not audit.review_valid:
            raise ValueError("M4 predecessor is not the exact accepted M3 revision")
        operation, _ = self._demo_service.start_generation(
            self._principal,
            audit.revision.id,
            audit.revision.revision_hash,
            f"m67:{self._work_item}:m4:{predecessor.artifact_sha256}",
        )
        self._demo_runner.run_exact(operation.id, COORDINATOR_ACTOR)
        revisions = self._demo_service.list_revisions(self._principal, operation.demo_id)
        if len(revisions) != 1:
            raise ValueError("exact M4 operation did not produce one revision")
        revision = revisions[0].revision
        reviewed = self._demo_service.review(
            self._principal,
            revision.id,
            revision.revision_hash,
            revision.manifest.checksum,
            revision.specification_hash,
            DemoReviewDecisionType.APPROVE,
            "Deterministic Phase 1 predecessor acceptance under the exact execution authority.",
        )
        return StageResult(
            reviewed.revision.id,
            _sha(
                {
                    "manifest": reviewed.revision.manifest.checksum,
                    "review_id": str(reviewed.latest_review.id) if reviewed.latest_review else None,
                    "revision_hash": reviewed.revision.revision_hash,
                    "revision_id": str(reviewed.revision.id),
                    "specification_hash": reviewed.revision.specification_hash,
                    "state": reviewed.revision.state.value,
                }
            ),
        )

    def _m5(self, predecessor: CoordinatedStageArtifact) -> StageResult:
        demo = self._demo_service.get_revision(self._principal, predecessor.revision_id)
        if demo.revision.id != predecessor.revision_id or not demo.review_valid:
            raise ValueError("M5 predecessor is not the exact accepted M4 revision")
        operation, _ = self._outreach_service.start_generation(
            self._principal,
            demo.revision.id,
            demo.revision.revision_hash,
            f"m67:{self._work_item}:m5:{predecessor.artifact_sha256}",
        )
        self._outreach_runner.run_exact(operation.id, COORDINATOR_ACTOR)
        revisions = self._outreach_service.list_revisions(self._principal, operation.package_id)
        if len(revisions) != 1:
            raise ValueError("exact M5 operation did not produce one revision")
        revision = revisions[0].revision
        reviewed = self._outreach_service.review(
            self._principal,
            revision.id,
            revision.revision_hash,
            revision.manifest.checksum,
            revision.content_hash,
            OutreachReviewDecisionType.APPROVE_CONTENT,
            "Deterministic Phase 1 predecessor acceptance under the exact execution authority.",
        )
        return StageResult(
            reviewed.revision.id,
            _sha(
                {
                    "content_hash": reviewed.revision.content_hash,
                    "manifest": reviewed.revision.manifest.checksum,
                    "review_id": str(reviewed.latest_review.id) if reviewed.latest_review else None,
                    "revision_hash": reviewed.revision.revision_hash,
                    "revision_id": str(reviewed.revision.id),
                    "state": reviewed.revision.state.value,
                }
            ),
        )
