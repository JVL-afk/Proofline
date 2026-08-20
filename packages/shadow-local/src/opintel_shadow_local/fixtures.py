"""Network-free synthetic company and canonical M1-M5 fixture projections."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_audit.domain import AuditRevisionState
from opintel_demo.domain import DemoRevisionState
from opintel_opportunity.domain import AnalysisStatus, HypothesisStatus, ValueState
from opintel_outreach.domain import OutreachRevisionState
from opintel_research.domain import ResearchRunStatus
from opintel_shadow.domain import (
    ArtifactReference,
    CanonicalPipelineSnapshot,
    OrganizationKind,
    RestrictedSnapshotReference,
    StageLineage,
    SyntheticBusinessCandidate,
    stable_hash,
)


def fixture_id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://fixtures.invalid/m6.7a/{value}")


def _artifact(fixture_key: str, context: str) -> ArtifactReference:
    assert context in {"M1", "M2", "M3", "M4", "M5"}
    return ArtifactReference.model_validate(
        {
            "context": context,
            "artifact_id": fixture_id(f"{fixture_key}/{context}"),
            "version": f"synthetic-{context.lower()}@1",
            "artifact_hash": stable_hash((fixture_key, context, "synthetic-canonical")),
        }
    )


def _lineage(fixture_key: str, count: int) -> tuple[StageLineage, ...]:
    contexts = ("M1", "M2", "M3", "M4", "M5")[:count]
    stages: list[StageLineage] = []
    previous: ArtifactReference | None = None
    for context in contexts:
        output = _artifact(fixture_key, context)
        stages.append(
            StageLineage.model_validate(
                {
                    "stage": context,
                    "inputs": () if previous is None else (previous,),
                    "output": output,
                    "code_version": "synthetic-pipeline@1",
                    "configuration_version": "texas-hvac-lead-response@1",
                }
            )
        )
        previous = output
    return tuple(stages)


def build_pipeline_snapshot(
    fixture_key: str,
    outcome_family: str = "approved",
) -> CanonicalPipelineSnapshot:
    count = 5
    m1_status = ResearchRunStatus.SUCCEEDED
    analysis_status: AnalysisStatus | None = AnalysisStatus.SUCCEEDED
    hypothesis_status: HypothesisStatus | None = HypothesisStatus.ACCEPTED
    audit_state: AuditRevisionState | None = AuditRevisionState.APPROVED
    demo_state: DemoRevisionState | None = DemoRevisionState.APPROVED
    outreach_state: OutreachRevisionState | None = OutreachRevisionState.CONTENT_APPROVED
    if outcome_family == "research_failed":
        count, m1_status = 1, ResearchRunStatus.FAILED
        analysis_status = hypothesis_status = None
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "research_partial":
        count, m1_status = 1, ResearchRunStatus.PARTIAL
        analysis_status = hypothesis_status = None
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "insufficient":
        count, analysis_status = 2, AnalysisStatus.INSUFFICIENT_DATA
        hypothesis_status = None
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "no_opportunity":
        count, hypothesis_status = 2, HypothesisStatus.NEEDS_INFORMATION
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "opportunity_review":
        count, hypothesis_status = 2, HypothesisStatus.READY_FOR_REVIEW
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "opportunity_rejected":
        count, hypothesis_status = 2, HypothesisStatus.REJECTED
        audit_state = demo_state = outreach_state = None
    elif outcome_family == "audit_rejected":
        count, audit_state = 3, AuditRevisionState.REJECTED
        demo_state = outreach_state = None
    elif outcome_family == "demo_rejected":
        count, demo_state = 4, DemoRevisionState.REJECTED
        outreach_state = None
    elif outcome_family == "outreach_rejected":
        outreach_state = OutreachRevisionState.REJECTED
    elif outcome_family != "approved":
        raise ValueError(f"unknown synthetic outcome family: {outcome_family}")
    source_hash = stable_hash((fixture_key, "immutable-synthetic-source"))
    return CanonicalPipelineSnapshot(
        fixture_key=fixture_key,
        source_snapshot=RestrictedSnapshotReference(
            snapshot_id=fixture_id(f"{fixture_key}/snapshot"),
            snapshot_version="synthetic-capture@1",
            content_hash=source_hash,
            may_contain_incidental_public_person_data=True,
        ),
        source_configuration_version="synthetic-capture-policy@1",
        deterministic_code_version="m1-m5-deterministic@1",
        economic_value_states=(ValueState.UNKNOWN, ValueState.PROPOSED),
        lineage=_lineage(fixture_key, count),
        m1_status=m1_status,
        m2_analysis_status=analysis_status,
        hypothesis_status=hypothesis_status,
        audit_state=audit_state,
        demo_state=demo_state,
        outreach_state=outreach_state,
    )


class SyntheticCanonicalPipeline:
    """Fixture catalog implementing the read-only canonical-pipeline port."""

    def __init__(self, snapshots: tuple[CanonicalPipelineSnapshot, ...]) -> None:
        self._snapshots = {item.fixture_key: item for item in snapshots}

    def load(self, fixture_key: str) -> CanonicalPipelineSnapshot:
        return self._snapshots[fixture_key]

    def with_snapshot(self, snapshot: CanonicalPipelineSnapshot) -> SyntheticCanonicalPipeline:
        values = {**self._snapshots, snapshot.fixture_key: snapshot}
        return SyntheticCanonicalPipeline(tuple(values.values()))

    def with_source_drift(self, fixture_key: str) -> SyntheticCanonicalPipeline:
        current = self.load(fixture_key)
        drifted = current.model_copy(
            update={
                "source_snapshot": current.source_snapshot.model_copy(
                    update={"content_hash": stable_hash((fixture_key, "changed-source"))}
                )
            }
        )
        return self.with_snapshot(drifted)


def build_synthetic_candidates(count: int = 36) -> tuple[SyntheticBusinessCandidate, ...]:
    """Produce wholly fictional organizations under the reserved invalid TLD."""

    result: list[SyntheticBusinessCandidate] = []
    families = tuple(
        {
            0: "research_failed",
            1: "research_partial",
            2: "insufficient",
            3: "no_opportunity",
            4: "opportunity_review",
            5: "opportunity_rejected",
            6: "audit_rejected",
            7: "demo_rejected",
            8: "outreach_rejected",
        }.get(index, "approved")
        for index in range(count)
    )
    for index, family in enumerate(families):
        key = f"synthetic-{index:02d}-{family}"
        result.append(
            SyntheticBusinessCandidate(
                id=fixture_id(key),
                fixture_key=key,
                display_name=f"Synthetic HVAC Fixture {index:02d}",
                canonical_domain=f"synthetic-hvac-{index:02d}.invalid",
                texas_region=("north", "central", "south", "west")[index % 4],
                organization_kind=OrganizationKind.INDEPENDENT,
                organization_group=f"fixture-group-{index:02d}",
                lead_flow_key=f"fixture-lead-flow-{index:02d}",
                source_ref=f"fixture://m6.7a/{key}",
                in_texas=True,
                commercial_hvac=True,
                b2b=True,
                operational=True,
                permitted_public_url=True,
            )
        )
    return tuple(result)


def build_synthetic_pipeline(
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> SyntheticCanonicalPipeline:
    snapshots = tuple(
        build_pipeline_snapshot(candidate.fixture_key, candidate.fixture_key.split("-", 2)[2])
        for candidate in candidates
    )
    return SyntheticCanonicalPipeline(snapshots)
