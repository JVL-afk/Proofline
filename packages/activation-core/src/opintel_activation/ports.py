"""M6.5 persistence port. No provider, network, delivery, or real-data port exists."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from opintel_activation.domain import ActivationRecord


class ActivationRepository(Protocol):
    def initialize(self) -> None: ...
    def save(self, record: ActivationRecord) -> None: ...
    def get(
        self, workspace_id: UUID, record_kind: str, record_id: UUID
    ) -> ActivationRecord | None: ...
    def list(self, workspace_id: UUID, record_kind: str) -> tuple[ActivationRecord, ...]: ...
