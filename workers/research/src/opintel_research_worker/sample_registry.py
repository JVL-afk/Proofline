"""Immutable Phase 1 sampled-slot registry and work-item identity verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from opintel_research.domain import SampledSlotIdentity
from opintel_shadow import LiveResearchPermissionRelease

REGISTRY_SCHEMA = "m67-phase1-frozen-slot-registry-v1"
ORDERED_PACKAGE_FILE_SHA256 = "0283f0a6956f6bd11e9326419d9671a61cc57dac0b6d376b9e2b7a11f0507a70"
ORDERED_PACKAGE_SEMANTIC_SHA256 = (
    "3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b"
)


class FrozenPhaseOneSampleRegistry:
    """Fail-closed verifier for caller work-item identities and permission releases."""

    def __init__(self, path: str | Path) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        supplied_hash = payload.pop("registry_sha256", None)
        computed_hash = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        if supplied_hash != computed_hash:
            raise ValueError("frozen sampled-slot registry hash mismatch")
        if (
            payload.get("schema_version") != REGISTRY_SCHEMA
            or payload.get("source_ordered_package_file_sha256")
            != ORDERED_PACKAGE_FILE_SHA256
            or payload.get("source_ordered_package_semantic_sha256")
            != ORDERED_PACKAGE_SEMANTIC_SHA256
        ):
            raise ValueError("frozen sampled-slot registry source identity mismatch")
        slots = payload.get("slots")
        if not isinstance(slots, list) or [item.get("slot_number") for item in slots] != list(
            range(1, 25)
        ):
            raise ValueError("frozen sampled-slot registry must contain exact slots 1-24")
        self.registry_sha256 = computed_hash
        self.ordered_package_file_sha256 = ORDERED_PACKAGE_FILE_SHA256
        self.ordered_package_semantic_sha256 = ORDERED_PACKAGE_SEMANTIC_SHA256
        self._slots = {int(item["slot_number"]): item for item in slots}

    def issue(self, work_item_id: UUID, slot_number: int) -> SampledSlotIdentity:
        slot = self._slots.get(slot_number)
        if slot is None:
            raise ValueError("slot is absent from the frozen sampled-slot registry")
        return SampledSlotIdentity.create(
            ordered_package_file_sha256=ORDERED_PACKAGE_FILE_SHA256,
            ordered_package_semantic_sha256=ORDERED_PACKAGE_SEMANTIC_SHA256,
            slot_registry_sha256=self.registry_sha256,
            slot_number=slot_number,
            business_identity=slot["business_identity"],
            exact_hostname=slot["exact_hostname"],
            source_row_sha256=slot["source_row_sha256"],
            work_item_id=work_item_id,
        )

    def verify_identity(self, identity: SampledSlotIdentity, work_item_id: UUID) -> None:
        expected = self.issue(work_item_id, identity.slot_number)
        if identity != expected:
            raise ValueError("work item does not match the immutable sampled-slot registry")

    def verify_release(self, release: LiveResearchPermissionRelease) -> None:
        if release.slot_number is None:
            raise ValueError("release has no sampled-slot identity")
        slot = self._slots.get(release.slot_number)
        if (
            slot is None
            or release.ordered_package_sha256 != ORDERED_PACKAGE_SEMANTIC_SHA256
            or release.business_identity != slot["business_identity"]
            or release.exact_hostname != slot["exact_hostname"]
        ):
            raise ValueError("release does not match the immutable sampled-slot registry")
