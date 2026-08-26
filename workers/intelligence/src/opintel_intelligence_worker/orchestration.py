"""Immutable one-business M1-M5 stage boundary for the Phase 1 shadow runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ShadowStage(StrEnum):
    M1_MINIMIZED_EVIDENCE = "M1_MINIMIZED_EVIDENCE"
    M2_OPPORTUNITY_ECONOMICS = "M2_OPPORTUNITY_ECONOMICS"
    M3_EVIDENCE_LINKED_AUDIT = "M3_EVIDENCE_LINKED_AUDIT"
    M4_DETERMINISTIC_DEMO = "M4_DETERMINISTIC_DEMO"
    M5_SHADOW_OUTREACH_PACKAGE = "M5_SHADOW_OUTREACH_PACKAGE"
    CONTACT_PHASE_NOT_AUTHORIZED = "CONTACT_PHASE_NOT_AUTHORIZED"


class CoordinatorStageState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


_ORDER = (
    ShadowStage.M1_MINIMIZED_EVIDENCE,
    ShadowStage.M2_OPPORTUNITY_ECONOMICS,
    ShadowStage.M3_EVIDENCE_LINKED_AUDIT,
    ShadowStage.M4_DETERMINISTIC_DEMO,
    ShadowStage.M5_SHADOW_OUTREACH_PACKAGE,
    ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED,
)


@dataclass(frozen=True, slots=True)
class StageArtifact:
    slot_number: int
    business_id: str
    stage: ShadowStage
    predecessor_sha256: str | None
    output_sha256: str
    accepted: bool
    runtime_revision: str

    @property
    def artifact_sha256(self) -> str:
        value = {
            "accepted": self.accepted,
            "business_id": self.business_id,
            "output_sha256": self.output_sha256,
            "predecessor_sha256": self.predecessor_sha256,
            "runtime_revision": self.runtime_revision,
            "slot_number": self.slot_number,
            "stage": self.stage.value,
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class OneBusinessShadowWorkflow:
    """Reject skips, cross-business inputs, unaccepted artifacts, and post-M5 delivery."""

    def __init__(self, slot_number: int, business_id: str, runtime_revision: str) -> None:
        if slot_number < 1 or not business_id or not runtime_revision:
            raise ValueError("exact slot, business, and runtime revision are required")
        self._slot = slot_number
        self._business = business_id
        self._runtime = runtime_revision

    def first(self, minimized_evidence_sha256: str) -> StageArtifact:
        return self._artifact(ShadowStage.M1_MINIMIZED_EVIDENCE, None, minimized_evidence_sha256)

    def advance(
        self, predecessor: StageArtifact, stage: ShadowStage, output_sha256: str
    ) -> StageArtifact:
        if predecessor.slot_number != self._slot or predecessor.business_id != self._business:
            raise ValueError("cross-slot or cross-business predecessor is prohibited")
        if predecessor.runtime_revision != self._runtime or not predecessor.accepted:
            raise ValueError("only an accepted current-runtime predecessor may advance")
        expected = _ORDER[_ORDER.index(predecessor.stage) + 1]
        if stage is not expected:
            raise ValueError("stage skip or replay is prohibited")
        if stage is ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED:
            output_sha256 = hashlib.sha256(stage.value.encode()).hexdigest()
        return self._artifact(stage, predecessor.artifact_sha256, output_sha256)

    def _artifact(
        self, stage: ShadowStage, predecessor_sha256: str | None, output_sha256: str
    ) -> StageArtifact:
        if len(output_sha256) != 64:
            raise ValueError("stage output must be an immutable SHA-256")
        return StageArtifact(
            self._slot,
            self._business,
            stage,
            predecessor_sha256,
            output_sha256,
            True,
            self._runtime,
        )


@dataclass(frozen=True, slots=True)
class CoordinatedStageArtifact:
    """Exact predecessor-bound state used by the production activation coordinator."""

    ordered_package_sha256: str
    slot_number: int
    business_identity: str
    exact_hostname: str
    work_item_identity_sha256: str
    activation_sha256: str
    authorization_release_id: UUID
    runtime_revision: str
    stage: ShadowStage
    state: CoordinatorStageState
    revision_id: UUID
    predecessor_revision_id: UUID | None
    predecessor_artifact_sha256: str | None
    output_sha256: str

    @property
    def artifact_sha256(self) -> str:
        payload = {
            "activation_sha256": self.activation_sha256,
            "authorization_release_id": str(self.authorization_release_id),
            "business_identity": self.business_identity,
            "exact_hostname": self.exact_hostname,
            "ordered_package_sha256": self.ordered_package_sha256,
            "output_sha256": self.output_sha256,
            "predecessor_artifact_sha256": self.predecessor_artifact_sha256,
            "predecessor_revision_id": (
                str(self.predecessor_revision_id) if self.predecessor_revision_id else None
            ),
            "revision_id": str(self.revision_id),
            "runtime_revision": self.runtime_revision,
            "slot_number": self.slot_number,
            "stage": self.stage.value,
            "state": self.state.value,
            "work_item_identity_sha256": self.work_item_identity_sha256,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class BoundedSampledSlotCoordinator:
    """Deterministic no-skip stage gate for one exact activated sampled work item."""

    def __init__(
        self,
        *,
        ordered_package_sha256: str,
        slot_number: int,
        business_identity: str,
        exact_hostname: str,
        work_item_identity_sha256: str,
        activation_sha256: str,
        authorization_release_id: UUID,
        runtime_revision: str,
        existing: tuple[CoordinatedStageArtifact, ...] = (),
    ) -> None:
        values = (
            ordered_package_sha256,
            work_item_identity_sha256,
            activation_sha256,
        )
        if any(len(value) != 64 for value in values):
            raise ValueError("coordinator requires immutable SHA-256 identities")
        if slot_number < 1 or not business_identity or not exact_hostname or not runtime_revision:
            raise ValueError("coordinator exact work-item binding is incomplete")
        self._binding = (
            ordered_package_sha256,
            slot_number,
            business_identity,
            exact_hostname,
            work_item_identity_sha256,
            activation_sha256,
            authorization_release_id,
            runtime_revision,
        )
        self._artifacts: list[CoordinatedStageArtifact] = []
        for artifact in existing:
            self._append_existing(artifact)

    def accept_stage(
        self,
        *,
        stage: ShadowStage,
        revision_id: UUID,
        output_sha256: str,
        authority_effective: bool,
        kill_switch_tripped: bool,
    ) -> tuple[CoordinatedStageArtifact, bool]:
        if not authority_effective or kill_switch_tripped:
            raise ValueError("current authority or kill switch blocks stage acceptance")
        if len(output_sha256) != 64:
            raise ValueError("stage output requires an immutable SHA-256")
        predecessor = self._artifacts[-1] if self._artifacts else None
        expected = _ORDER[0] if predecessor is None else _ORDER[_ORDER.index(predecessor.stage) + 1]
        if stage is not expected:
            existing = next((item for item in self._artifacts if item.stage is stage), None)
            if existing and existing.revision_id == revision_id and existing.output_sha256 == output_sha256:
                return existing, False
            raise ValueError("stage skip, duplicate divergence, or replay is prohibited")
        if predecessor is not None and predecessor.state is not CoordinatorStageState.ACCEPTED:
            raise ValueError("downstream stage requires the exact accepted predecessor")
        if stage is ShadowStage.CONTACT_PHASE_NOT_AUTHORIZED:
            output_sha256 = hashlib.sha256(stage.value.encode()).hexdigest()
        artifact = CoordinatedStageArtifact(
            ordered_package_sha256=self._binding[0],
            slot_number=self._binding[1],
            business_identity=self._binding[2],
            exact_hostname=self._binding[3],
            work_item_identity_sha256=self._binding[4],
            activation_sha256=self._binding[5],
            authorization_release_id=self._binding[6],
            runtime_revision=self._binding[7],
            stage=stage,
            state=CoordinatorStageState.ACCEPTED,
            revision_id=revision_id,
            predecessor_revision_id=predecessor.revision_id if predecessor else None,
            predecessor_artifact_sha256=predecessor.artifact_sha256 if predecessor else None,
            output_sha256=output_sha256,
        )
        self._artifacts.append(artifact)
        return artifact, True

    @property
    def artifacts(self) -> tuple[CoordinatedStageArtifact, ...]:
        return tuple(self._artifacts)

    def _append_existing(self, artifact: CoordinatedStageArtifact) -> None:
        binding = (
            artifact.ordered_package_sha256,
            artifact.slot_number,
            artifact.business_identity,
            artifact.exact_hostname,
            artifact.work_item_identity_sha256,
            artifact.activation_sha256,
            artifact.authorization_release_id,
            artifact.runtime_revision,
        )
        if binding != self._binding:
            raise ValueError("forged or cross-work-item coordinator artifact")
        predecessor = self._artifacts[-1] if self._artifacts else None
        expected = _ORDER[0] if predecessor is None else _ORDER[_ORDER.index(predecessor.stage) + 1]
        if (
            artifact.stage is not expected
            or artifact.state is not CoordinatorStageState.ACCEPTED
            or artifact.predecessor_revision_id
            != (predecessor.revision_id if predecessor else None)
            or artifact.predecessor_artifact_sha256
            != (predecessor.artifact_sha256 if predecessor else None)
        ):
            raise ValueError("persisted stage lineage is incomplete, skipped, or mismatched")
        self._artifacts.append(artifact)
