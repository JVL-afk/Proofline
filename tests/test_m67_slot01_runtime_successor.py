from __future__ import annotations

import hashlib

import pytest
from opintel_intelligence_worker.orchestration import (
    OneBusinessShadowWorkflow,
    ShadowStage,
    StageArtifact,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def run_chain() -> tuple[StageArtifact, ...]:
    workflow = OneBusinessShadowWorkflow(1, "synthetic-business-01", "runtime-sha256")
    artifacts = [workflow.first(digest("minimized-m1"))]
    for stage, value in (
        (ShadowStage.M2_OPPORTUNITY_ECONOMICS, "m2"),
        (ShadowStage.M3_EVIDENCE_LINKED_AUDIT, "m3"),
        (ShadowStage.M4_DETERMINISTIC_DEMO, "m4"),
        (ShadowStage.M5_SHADOW_OUTREACH_PACKAGE, "m5-content-only"),
        (ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED, "ignored-no-delivery"),
    ):
        artifacts.append(workflow.advance(artifacts[-1], stage, digest(value)))
    return tuple(artifacts)


def test_fixed_minimized_capture_replays_deterministically_through_m2_m5() -> None:
    first = run_chain()
    second = run_chain()
    assert tuple(item.artifact_sha256 for item in first) == tuple(
        item.artifact_sha256 for item in second
    )
    assert first[-1].stage is ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED


def test_stage_skip_and_unaccepted_predecessor_fail_closed() -> None:
    workflow = OneBusinessShadowWorkflow(1, "synthetic-business-01", "runtime-sha256")
    m1 = workflow.first(digest("minimized-m1"))
    with pytest.raises(ValueError, match="stage skip"):
        workflow.advance(m1, ShadowStage.M3_EVIDENCE_LINKED_AUDIT, digest("m3"))
    with pytest.raises(ValueError, match="accepted"):
        workflow.advance(
            StageArtifact(
                m1.slot_number,
                m1.business_id,
                m1.stage,
                m1.predecessor_sha256,
                m1.output_sha256,
                False,
                m1.runtime_revision,
            ),
            ShadowStage.M2_OPPORTUNITY_ECONOMICS,
            digest("m2"),
        )


def test_business_isolation_prevents_cross_business_predecessor() -> None:
    first = OneBusinessShadowWorkflow(1, "business-a", "runtime-sha256")
    second = OneBusinessShadowWorkflow(1, "business-b", "runtime-sha256")
    with pytest.raises(ValueError, match="cross-slot or cross-business"):
        second.advance(
            first.first(digest("minimized")),
            ShadowStage.M2_OPPORTUNITY_ECONOMICS,
            digest("m2"),
        )
