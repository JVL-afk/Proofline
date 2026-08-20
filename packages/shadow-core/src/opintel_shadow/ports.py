"""M6.7A ports; intentionally no network, AI, person/contact, or delivery port."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from opintel_shadow.domain import CanonicalPipelineSnapshot, ShadowRecord


class ShadowRepository(Protocol):
    def initialize(self) -> None: ...
    def save(self, record: ShadowRecord) -> None: ...
    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> ShadowRecord | None: ...
    def list(self, workspace_id: UUID, record_kind: str) -> tuple[ShadowRecord, ...]: ...


class CanonicalPipelinePort(Protocol):
    """Supplies exact synthetic M1-M5 canonical projections; it cannot mutate them."""

    def load(self, fixture_key: str) -> CanonicalPipelineSnapshot: ...
