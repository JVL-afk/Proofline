"""Append-only SQLite persistence for immutable M6.5 governance records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from opintel_activation.domain import (
    ACTIVATION_RECORD_ADAPTER,
    ActivationRecord,
)
from sqlalchemy import DateTime, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ActivationRecordRow(Base):
    __tablename__ = "m65_activation_records"
    __table_args__ = (UniqueConstraint("workspace_id", "record_kind", "record_id"),)

    key: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    record_kind: Mapped[str] = mapped_column(String(50), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyActivationRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)

    def save(self, record: ActivationRecord) -> None:
        with self._sessions.begin() as session:
            session.add(
                ActivationRecordRow(
                    workspace_id=str(record.workspace_id),
                    record_kind=record.record_kind,
                    record_id=str(record.id),
                    created_at=record.created_at,
                    data_json=record.model_dump_json(),
                )
            )

    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> ActivationRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ActivationRecordRow).where(
                    ActivationRecordRow.workspace_id == str(workspace_id),
                    ActivationRecordRow.record_kind == record_kind,
                    ActivationRecordRow.record_id == str(record_id),
                )
            )
            return ACTIVATION_RECORD_ADAPTER.validate_json(row.data_json) if row else None

    def list(self, workspace_id: UUID, record_kind: str) -> tuple[ActivationRecord, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ActivationRecordRow)
                .where(
                    ActivationRecordRow.workspace_id == str(workspace_id),
                    ActivationRecordRow.record_kind == record_kind,
                )
                .order_by(ActivationRecordRow.created_at, ActivationRecordRow.key)
            ).all()
            return tuple(ACTIVATION_RECORD_ADAPTER.validate_json(row.data_json) for row in rows)
