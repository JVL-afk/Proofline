"""M6.7C ports. Production network and delivery adapters are intentionally absent."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from opintel_research.ports import HttpTransport, Resolver

from opintel_shadow.gate_domain import (
    GateRecord,
    GovernedDataClass,
    SyntheticStoredArtifact,
    WorkItem,
)


class GateRepository(Protocol):
    def initialize(self) -> None: ...
    def save(self, record: GateRecord) -> None: ...
    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> GateRecord | None: ...
    def list(self, workspace_id: UUID, record_kind: str) -> tuple[GateRecord, ...]: ...


class WorkRepository(Protocol):
    def enqueue(self, item: WorkItem) -> tuple[WorkItem, bool]: ...
    def claim(
        self, workspace_id: UUID, worker_ref: str, now: datetime, lease_seconds: int
    ) -> WorkItem | None: ...
    def save_work(self, item: WorkItem, expected_version: int) -> WorkItem: ...
    def recover_stale(self, workspace_id: UUID, now: datetime) -> int: ...
    def get_work(self, workspace_id: UUID, work_id: UUID) -> WorkItem | None: ...


class SyntheticArtifactStore(Protocol):
    def put(
        self, workspace_id: UUID, artifact: SyntheticStoredArtifact, content: bytes
    ) -> None: ...
    def exists(self, workspace_id: UUID, artifact_ref: str) -> bool: ...
    def delete(self, workspace_id: UUID, artifact_ref: str) -> None: ...
    def list_by_class(
        self, workspace_id: UUID, data_class: GovernedDataClass
    ) -> tuple[SyntheticStoredArtifact, ...]: ...


__all__ = [
    "GateRepository",
    "HttpTransport",
    "Resolver",
    "SyntheticArtifactStore",
    "WorkRepository",
]
