"""SQLAlchemy persistence for the M6.9 suppression / opt-out registry.

Append-only: rows are never updated or deleted. An owner-authorized
unsuppession is its own row referencing the suppressed entry, never a mutation
of it, so the append-only audit trail is preserved even when a suppression is
later lifted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from opintel_suppression.domain import (
    OwnerUnsuppressionRecord,
    SuppressionEntry,
    SuppressionKind,
    SuppressionSourceMechanism,
)
from sqlalchemy import DateTime, String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class SuppressionEntryRow(Base):
    __tablename__ = "suppression_entries"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "kind", "normalized_value", name="uq_suppression_entry_key"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    normalized_value: Mapped[str] = mapped_column(String(320), index=True)
    normalized_domain: Mapped[str] = mapped_column(String(255), index=True)
    reason: Mapped[str] = mapped_column(Text)
    source_mechanism: Mapped[str] = mapped_column(String(40))
    opt_out_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    suppression_effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_ref: Mapped[str] = mapped_column(Text)
    audit_event_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OwnerUnsuppressionRow(Base):
    __tablename__ = "suppression_owner_unsuppressions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    suppressed_entry_id: Mapped[str] = mapped_column(String(36), index=True)
    authorized_by: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemySuppressionRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("suppression repository requires sqlite or postgresql+psycopg")
        self.engine = create_engine(database_url, future=True)
        if database_url.startswith("sqlite"):
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

    def add_entry(self, entry: SuppressionEntry) -> SuppressionEntry:
        row = SuppressionEntryRow(
            id=str(entry.id),
            workspace_id=str(entry.workspace_id),
            kind=str(entry.kind),
            normalized_value=entry.normalized_value,
            normalized_domain=entry.normalized_domain,
            reason=entry.reason,
            source_mechanism=str(entry.source_mechanism),
            opt_out_received_at=_aware(entry.opt_out_received_at),
            suppression_effective_at=_aware(entry.suppression_effective_at),
            evidence_ref=entry.evidence_ref,
            audit_event_hash=entry.audit_event_hash,
            created_at=_aware(entry.created_at),
        )
        try:
            with self._sessions.begin() as session:
                session.add(row)
            return entry
        except IntegrityError:
            existing = self.get_active_entry(entry.workspace_id, entry.kind, entry.normalized_value)
            assert existing is not None
            return existing

    def get_active_entry(
        self, workspace_id: UUID, kind: SuppressionKind, normalized_value: str
    ) -> SuppressionEntry | None:
        with self._sessions() as session:
            row = session.scalar(
                select(SuppressionEntryRow).where(
                    SuppressionEntryRow.workspace_id == str(workspace_id),
                    SuppressionEntryRow.kind == str(kind),
                    SuppressionEntryRow.normalized_value == normalized_value,
                )
            )
            if row is None:
                return None
            lifted = session.scalar(
                select(OwnerUnsuppressionRow).where(
                    OwnerUnsuppressionRow.suppressed_entry_id == row.id
                )
            )
            if lifted is not None:
                return None
            return _entry(row)

    def add_owner_unsuppression(self, record: OwnerUnsuppressionRecord) -> OwnerUnsuppressionRecord:
        row = OwnerUnsuppressionRow(
            id=str(record.id),
            workspace_id=str(record.workspace_id),
            suppressed_entry_id=str(record.suppressed_entry_id),
            authorized_by=record.authorized_by,
            reason=record.reason,
            created_at=_aware(record.created_at),
        )
        with self._sessions.begin() as session:
            session.add(row)
        return record

    def list_entries(self, workspace_id: UUID) -> tuple[SuppressionEntry, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SuppressionEntryRow)
                .where(SuppressionEntryRow.workspace_id == str(workspace_id))
                .order_by(SuppressionEntryRow.created_at)
            ).all()
            return tuple(_entry(row) for row in rows)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _entry(row: SuppressionEntryRow) -> SuppressionEntry:
    return SuppressionEntry(
        id=UUID(row.id),
        workspace_id=UUID(row.workspace_id),
        kind=SuppressionKind(row.kind),
        normalized_value=row.normalized_value,
        normalized_domain=row.normalized_domain,
        reason=row.reason,
        source_mechanism=SuppressionSourceMechanism(row.source_mechanism),
        opt_out_received_at=_aware(row.opt_out_received_at),
        suppression_effective_at=_aware(row.suppression_effective_at),
        evidence_ref=row.evidence_ref,
        audit_event_hash=row.audit_event_hash,
        created_at=_aware(row.created_at),
    )
