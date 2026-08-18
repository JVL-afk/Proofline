"""Append-only SQLite persistence for immutable M6 records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from opintel_contact.domain import (
    M6_RECORD_ADAPTER,
    ContactVerification,
    DeliveryReceipt,
    InboundReply,
    M6Record,
    OutreachPolicyRelease,
)
from sqlalchemy import DateTime, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ContactRecordRow(Base):
    __tablename__ = "m6_contact_records"
    __table_args__ = (UniqueConstraint("workspace_id", "record_kind", "record_id"),)

    key: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    record_kind: Mapped[str] = mapped_column(String(40), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyContactRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)

    def save(self, record: M6Record) -> None:
        created_at = _record_time(record)
        with self._sessions.begin() as session:
            session.add(
                ContactRecordRow(
                    workspace_id=str(record.workspace_id),
                    record_kind=record.record_kind,
                    record_id=str(record.id),
                    created_at=created_at,
                    data_json=record.model_dump_json(),
                )
            )

    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> M6Record | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ContactRecordRow).where(
                    ContactRecordRow.workspace_id == str(workspace_id),
                    ContactRecordRow.record_kind == record_kind,
                    ContactRecordRow.record_id == str(record_id),
                )
            )
            return M6_RECORD_ADAPTER.validate_json(row.data_json) if row else None

    def list(self, workspace_id: UUID, record_kind: str) -> tuple[M6Record, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ContactRecordRow)
                .where(
                    ContactRecordRow.workspace_id == str(workspace_id),
                    ContactRecordRow.record_kind == record_kind,
                )
                .order_by(ContactRecordRow.created_at, ContactRecordRow.key)
            ).all()
            return tuple(M6_RECORD_ADAPTER.validate_json(row.data_json) for row in rows)


def _record_time(record: M6Record) -> datetime:
    if isinstance(record, ContactVerification):
        return record.verified_at
    if isinstance(record, OutreachPolicyRelease):
        return record.effective_at
    if isinstance(record, (DeliveryReceipt, InboundReply)):
        return record.received_at
    return record.created_at
