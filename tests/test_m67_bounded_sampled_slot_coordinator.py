from __future__ import annotations

import hashlib
from dataclasses import replace
from uuid import UUID

import pytest
from opintel_intelligence_worker.orchestration import (
    BoundedSampledSlotCoordinator,
    CoordinatedStageArtifact,
    ShadowStage,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _coordinator(existing: tuple[CoordinatedStageArtifact, ...] = ()):
    return BoundedSampledSlotCoordinator(
        ordered_package_sha256="3" * 64,
        slot_number=1,
        business_identity="903 HVAC",
        exact_hostname="903hvac.com",
        work_item_identity_sha256="4" * 64,
        activation_sha256="5" * 64,
        authorization_release_id=UUID("20000000-0000-4000-8000-000000000001"),
        runtime_revision="sha256:" + "6" * 64,
        existing=existing,
    )


def test_synthetic_exact_chain_reaches_contact_phase_not_authorized() -> None:
    coordinator = _coordinator()
    artifacts = []
    for index, stage in enumerate(ShadowStage, start=1):
        artifact, created = coordinator.accept_stage(
            stage=stage,
            revision_id=UUID(int=index),
            output_sha256=_digest(stage.value),
            authority_effective=True,
            kill_switch_tripped=False,
        )
        assert created is True
        artifacts.append(artifact)
    assert artifacts[-1].stage is ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED
    assert artifacts[-1].predecessor_artifact_sha256 == artifacts[-2].artifact_sha256


def test_direct_m2_m3_and_stage_skip_are_rejected() -> None:
    for stage in (ShadowStage.M2_OPPORTUNITY_ECONOMICS, ShadowStage.M3_EVIDENCE_LINKED_AUDIT):
        with pytest.raises(ValueError, match="stage skip"):
            _coordinator().accept_stage(
                stage=stage,
                revision_id=UUID(int=22),
                output_sha256=_digest("forged"),
                authority_effective=True,
                kill_switch_tripped=False,
            )


def test_revision_mismatch_and_forged_work_item_fail_closed_on_restart() -> None:
    coordinator = _coordinator()
    m1, _ = coordinator.accept_stage(
        stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
        revision_id=UUID(int=1),
        output_sha256=_digest("m1"),
        authority_effective=True,
        kill_switch_tripped=False,
    )
    with pytest.raises(ValueError, match="lineage"):
        _coordinator((replace(m1, predecessor_revision_id=UUID(int=99)),))
    with pytest.raises(ValueError, match="forged"):
        _coordinator((replace(m1, work_item_identity_sha256="f" * 64),))


def test_duplicate_queue_delivery_is_idempotent_but_divergence_is_rejected() -> None:
    coordinator = _coordinator()
    m1, created = coordinator.accept_stage(
        stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
        revision_id=UUID(int=1),
        output_sha256=_digest("m1"),
        authority_effective=True,
        kill_switch_tripped=False,
    )
    duplicate, duplicate_created = coordinator.accept_stage(
        stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
        revision_id=UUID(int=1),
        output_sha256=_digest("m1"),
        authority_effective=True,
        kill_switch_tripped=False,
    )
    assert created is True and duplicate_created is False and duplicate == m1
    with pytest.raises(ValueError, match="duplicate divergence"):
        coordinator.accept_stage(
            stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
            revision_id=UUID(int=2),
            output_sha256=_digest("different"),
            authority_effective=True,
            kill_switch_tripped=False,
        )


@pytest.mark.parametrize(
    ("authority_effective", "kill_switch_tripped"),
    [(False, False), (True, True)],
)
def test_authority_change_and_kill_switch_block_every_stage_boundary(
    authority_effective: bool, kill_switch_tripped: bool
) -> None:
    with pytest.raises(ValueError, match="authority or kill switch"):
        _coordinator().accept_stage(
            stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
            revision_id=UUID(int=1),
            output_sha256=_digest("m1"),
            authority_effective=authority_effective,
            kill_switch_tripped=kill_switch_tripped,
        )
