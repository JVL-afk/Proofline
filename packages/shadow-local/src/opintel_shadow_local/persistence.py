"""Append-only local SQLite persistence for synthetic M6.7A records."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from opintel_shadow.domain import SHADOW_RECORD_ADAPTER, ShadowRecord
from sqlalchemy import String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ShadowRecordRow(Base):
    __tablename__ = "m67_shadow_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "record_kind", "record_id", name="uq_m67_shadow_record"),
    )

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    record_kind: Mapped[str] = mapped_column(String(64), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyShadowRepository:
    """M6.7A-owned store; it has no mapping or write path to any M6 table."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("local M6.7A repository accepts only sqlite:/// URLs")
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
        Base.metadata.create_all(self.engine)

    def save(self, record: ShadowRecord) -> None:
        payload = record.model_dump(mode="json")
        with self._sessions.begin() as session:
            session.add(
                ShadowRecordRow(
                    workspace_id=str(record.workspace_id),
                    record_kind=record.record_kind,
                    record_id=str(record.id),
                    data_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                )
            )

    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> ShadowRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ShadowRecordRow).where(
                    ShadowRecordRow.workspace_id == str(workspace_id),
                    ShadowRecordRow.record_kind == record_kind,
                    ShadowRecordRow.record_id == str(record_id),
                )
            )
            return self._record(row) if row is not None else None

    def list(self, workspace_id: UUID, record_kind: str) -> tuple[ShadowRecord, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ShadowRecordRow)
                .where(
                    ShadowRecordRow.workspace_id == str(workspace_id),
                    ShadowRecordRow.record_kind == record_kind,
                )
                .order_by(ShadowRecordRow.row_id)
            )
            return tuple(self._record(row) for row in rows)

    @staticmethod
    def _record(row: ShadowRecordRow) -> ShadowRecord:
        return SHADOW_RECORD_ADAPTER.validate_json(row.data_json)
