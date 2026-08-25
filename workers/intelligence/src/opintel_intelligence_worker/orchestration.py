"""Immutable one-business M1-M5 stage boundary for the Phase 1 shadow runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class ShadowStage(StrEnum):
    M1_MINIMIZED_EVIDENCE = "M1_MINIMIZED_EVIDENCE"
    M2_OPPORTUNITY_ECONOMICS = "M2_OPPORTUNITY_ECONOMICS"
    M3_EVIDENCE_LINKED_AUDIT = "M3_EVIDENCE_LINKED_AUDIT"
    M4_DETERMINISTIC_DEMO = "M4_DETERMINISTIC_DEMO"
    M5_SHADOW_OUTREACH_PACKAGE = "M5_SHADOW_OUTREACH_PACKAGE"
    CONTACT_PHASE_NOT_AUTHORIZED = "CONTACT_PHASE_NOT_AUTHORIZED"


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
