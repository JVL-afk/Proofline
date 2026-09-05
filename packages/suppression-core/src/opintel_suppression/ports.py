"""Ports implemented by persistence adapters."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from opintel_suppression.domain import (
    OwnerUnsuppressionRecord,
    SuppressionEntry,
    SuppressionKind,
)


class SuppressionRepository(Protocol):
    def initialize(self) -> None: ...

    def add_entry(self, entry: SuppressionEntry) -> SuppressionEntry: ...

    def get_active_entry(
        self, workspace_id: UUID, kind: SuppressionKind, normalized_value: str
    ) -> SuppressionEntry | None:
        """None if no matching entry exists, or if an ``OwnerUnsuppressionRecord``
        references the matching entry (eligible again)."""
        ...

    def add_owner_unsuppression(
        self, record: OwnerUnsuppressionRecord
    ) -> OwnerUnsuppressionRecord: ...

    def list_entries(self, workspace_id: UUID) -> tuple[SuppressionEntry, ...]: ...
