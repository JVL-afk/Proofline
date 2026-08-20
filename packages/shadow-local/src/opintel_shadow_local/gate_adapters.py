"""SQLite and fake-only adapters for the M6.7C synthetic preflight."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from opintel_research.domain import RawHttpResponse, ValidatedUrl
from opintel_shadow.gate_domain import (
    GATE_RECORD_ADAPTER,
    GateRecord,
    GovernedDataClass,
    SyntheticStoredArtifact,
    WorkItem,
    WorkState,
)
from sqlalchemy import String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class GateBase(DeclarativeBase):
    pass


class GateRecordRow(GateBase):
    __tablename__ = "m67c_gate_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "record_kind", "record_id", name="uq_m67c_gate_record"),
    )

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    record_kind: Mapped[str] = mapped_column(String(64), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class GateWorkRow(GateBase):
    __tablename__ = "m67c_work_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_m67c_work_idempotency"),
    )

    work_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    state: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int]
    lease_expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyGateRepository:
    """M6.7C-owned SQLite control store with atomic work claims and no M6 tables."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("local M6.7C repository accepts only sqlite:/// URLs")
        path = database_url.removeprefix("sqlite:///")
        if path != ":memory:":
            Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url, future=True)
        event.listen(self.engine, "connect", self._configure_sqlite)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(connection: object, record: object) -> None:
        del record
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def initialize(self) -> None:
        GateBase.metadata.create_all(self.engine)

    def save(self, record: GateRecord) -> None:
        payload = record.model_dump(mode="json")
        with self._sessions.begin() as session:
            session.add(
                GateRecordRow(
                    workspace_id=str(record.workspace_id),
                    record_kind=record.record_kind,
                    record_id=str(record.id),
                    data_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                )
            )

    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> GateRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(GateRecordRow).where(
                    GateRecordRow.workspace_id == str(workspace_id),
                    GateRecordRow.record_kind == record_kind,
                    GateRecordRow.record_id == str(record_id),
                )
            )
            return None if row is None else GATE_RECORD_ADAPTER.validate_json(row.data_json)

    def list(self, workspace_id: UUID, record_kind: str) -> tuple[GateRecord, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(GateRecordRow)
                .where(
                    GateRecordRow.workspace_id == str(workspace_id),
                    GateRecordRow.record_kind == record_kind,
                )
                .order_by(GateRecordRow.row_id)
            )
            return tuple(GATE_RECORD_ADAPTER.validate_json(row.data_json) for row in rows)

    def enqueue(self, item: WorkItem) -> tuple[WorkItem, bool]:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(GateWorkRow).where(
                    GateWorkRow.workspace_id == str(item.workspace_id),
                    GateWorkRow.idempotency_key == item.idempotency_key,
                )
            )
            if existing is not None:
                return WorkItem.model_validate_json(existing.data_json), False
            session.add(self._work_row(item))
        return item, True

    def claim(
        self, workspace_id: UUID, worker_ref: str, now: datetime, lease_seconds: int
    ) -> WorkItem | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(GateWorkRow)
                .where(
                    GateWorkRow.workspace_id == str(workspace_id),
                    GateWorkRow.state == WorkState.QUEUED.value,
                )
                .order_by(GateWorkRow.work_id)
                .limit(1)
            )
            if row is None:
                return None
            current = WorkItem.model_validate_json(row.data_json)
            leased = current.model_copy(
                update={
                    "state": WorkState.LEASED,
                    "attempt_count": current.attempt_count + 1,
                    "version": current.version + 1,
                    "lease_owner": worker_ref,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                }
            )
            self._replace_work_row(row, leased)
            return leased

    def save_work(self, item: WorkItem, expected_version: int) -> WorkItem:
        with self._sessions.begin() as session:
            row = session.get(GateWorkRow, str(item.id))
            if row is None or row.workspace_id != str(item.workspace_id):
                raise ValueError("work item not found")
            if row.version != expected_version:
                raise ValueError("work item version conflict")
            self._replace_work_row(row, item)
        return item

    def recover_stale(self, workspace_id: UUID, now: datetime) -> int:
        recovered = 0
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(GateWorkRow).where(
                    GateWorkRow.workspace_id == str(workspace_id),
                    GateWorkRow.state == WorkState.LEASED.value,
                )
            )
            for row in rows:
                item = WorkItem.model_validate_json(row.data_json)
                if item.lease_expires_at is None or item.lease_expires_at > now:
                    continue
                state = (
                    WorkState.QUEUED if item.attempt_count < item.max_attempts else WorkState.FAILED
                )
                recovered_item = item.model_copy(
                    update={
                        "state": state,
                        "version": item.version + 1,
                        "lease_owner": None,
                        "lease_expires_at": None,
                    }
                )
                self._replace_work_row(row, recovered_item)
                recovered += 1
        return recovered

    def get_work(self, workspace_id: UUID, work_id: UUID) -> WorkItem | None:
        with self._sessions() as session:
            row = session.get(GateWorkRow, str(work_id))
            if row is None or row.workspace_id != str(workspace_id):
                return None
            return WorkItem.model_validate_json(row.data_json)

    @staticmethod
    def _work_row(item: WorkItem) -> GateWorkRow:
        return GateWorkRow(
            work_id=str(item.id),
            workspace_id=str(item.workspace_id),
            idempotency_key=item.idempotency_key,
            state=item.state.value,
            version=item.version,
            lease_expires_at=(
                None if item.lease_expires_at is None else item.lease_expires_at.isoformat()
            ),
            data_json=item.model_dump_json(),
        )

    @staticmethod
    def _replace_work_row(row: GateWorkRow, item: WorkItem) -> None:
        row.state = item.state.value
        row.version = item.version
        row.lease_expires_at = (
            None if item.lease_expires_at is None else item.lease_expires_at.isoformat()
        )
        row.data_json = item.model_dump_json()


class InMemorySyntheticArtifactStore:
    """Content-bearing store used only by controlled synthetic deletion fixtures."""

    def __init__(self) -> None:
        self._values: dict[tuple[UUID, str], tuple[SyntheticStoredArtifact, bytes]] = {}

    def put(self, workspace_id: UUID, artifact: SyntheticStoredArtifact, content: bytes) -> None:
        key = (workspace_id, artifact.artifact_ref)
        if key in self._values:
            raise ValueError("synthetic artifact is immutable")
        self._values[key] = (artifact, content)

    def exists(self, workspace_id: UUID, artifact_ref: str) -> bool:
        return (workspace_id, artifact_ref) in self._values

    def delete(self, workspace_id: UUID, artifact_ref: str) -> None:
        del self._values[(workspace_id, artifact_ref)]

    def list_by_class(
        self, workspace_id: UUID, data_class: GovernedDataClass
    ) -> tuple[SyntheticStoredArtifact, ...]:
        return tuple(
            artifact
            for (candidate_workspace, _), (artifact, _) in self._values.items()
            if candidate_workspace == workspace_id and artifact.data_class is data_class
        )


class FakeResolver:
    """Deterministic resolver with optional per-call answers for rebinding tests."""

    def __init__(self, answers: dict[str, tuple[tuple[str, ...], ...]]) -> None:
        self._answers = answers
        self.calls: list[tuple[str, int]] = []

    def resolve(self, host: str, port: int) -> tuple[str, ...]:
        self.calls.append((host, port))
        sequences = self._answers.get(host, ())
        if not sequences:
            return ()
        index = min(len([item for item in self.calls if item[0] == host]) - 1, len(sequences) - 1)
        return sequences[index]


class FakeHttpTransport:
    """Scripted transport that has no socket, DNS, or external-provider implementation."""

    def __init__(self, responses: tuple[RawHttpResponse, ...]) -> None:
        self._responses = responses
        self.calls: list[ValidatedUrl] = []

    def request(
        self, target: ValidatedUrl, timeout_seconds: float, max_bytes: int
    ) -> RawHttpResponse:
        del timeout_seconds, max_bytes
        self.calls.append(target)
        if len(self.calls) > len(self._responses):
            raise ValueError("fake transport script exhausted")
        return self._responses[len(self.calls) - 1]


__all__ = [
    "FakeHttpTransport",
    "FakeResolver",
    "InMemorySyntheticArtifactStore",
    "SqlAlchemyGateRepository",
]
