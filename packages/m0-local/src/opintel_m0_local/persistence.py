"""SQLAlchemy-backed local persistence and durable operation queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from opintel_m0.domain import (
    ActivityAttempt,
    AttemptStatus,
    AuditEvent,
    Campaign,
    EvidenceItem,
    Operation,
    OperationStatus,
)
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _uuid(value: UUID) -> str:
    return str(value)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _prepare_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        raw_path = database_url.removeprefix(prefix)
        if raw_path and raw_path != ":memory:":
            Path(raw_path).resolve().parent.mkdir(parents=True, exist_ok=True)


class Base(DeclarativeBase):
    pass


class CampaignRow(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120))
    fixture_uri: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationRow(Base):
    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "campaign_id", "idempotency_key", name="uq_operation_command"
        ),
        Index("ix_operation_claim", "status", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    workflow_name: Mapped[str] = mapped_column(String(80))
    workflow_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(240), nullable=True)


class ActivityAttemptRow(Base):
    __tablename__ = "activity_attempts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_activity_idempotency"),
        UniqueConstraint(
            "operation_id",
            "activity_name",
            "activity_version",
            "attempt_number",
            name="uq_activity_attempt_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("operations.id"), index=True)
    activity_name: Mapped[str] = mapped_column(String(80))
    activity_version: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class EvidenceItemRow(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("operation_id", name="uq_m0_evidence_operation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("operations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_uri: Mapped[str] = mapped_column(String(256))
    final_uri: Mapped[str] = mapped_column(String(256))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(240))
    excerpt: Mapped[str] = mapped_column(Text)
    fragment_locator: Mapped[str] = mapped_column(String(240))
    extractor_name: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(20))
    fixture_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyM0Repository:
    def __init__(self, database_url: str) -> None:
        _prepare_sqlite_parent(database_url)
        self.engine = create_engine(database_url, future=True)
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def create_campaign(self, campaign: Campaign, audit_event: AuditEvent) -> Campaign:
        with self._sessions.begin() as session:
            session.add(self._campaign_row(campaign))
            session.add(self._audit_row(audit_event))
        return campaign

    def get_campaign(self, workspace_id: UUID, campaign_id: UUID) -> Campaign | None:
        with self._sessions() as session:
            row = session.scalar(
                select(CampaignRow).where(
                    CampaignRow.id == _uuid(campaign_id),
                    CampaignRow.workspace_id == _uuid(workspace_id),
                )
            )
            return self._to_campaign(row) if row else None

    def create_or_get_operation(
        self, operation: Operation, audit_event: AuditEvent
    ) -> tuple[Operation, bool]:
        try:
            with self._sessions.begin() as session:
                session.add(self._operation_row(operation))
                session.add(self._audit_row(audit_event))
            return operation, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(OperationRow).where(
                        OperationRow.workspace_id == _uuid(operation.workspace_id),
                        OperationRow.campaign_id == _uuid(operation.campaign_id),
                        OperationRow.idempotency_key == operation.idempotency_key,
                    )
                )
                if row is None:
                    raise
                return self._to_operation(row), False

    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(OperationRow).where(
                    OperationRow.id == _uuid(operation_id),
                    OperationRow.workspace_id == _uuid(workspace_id),
                )
            )
            return self._to_operation(row) if row else None

    def list_attempts(self, operation_id: UUID) -> list[ActivityAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ActivityAttemptRow)
                .where(ActivityAttemptRow.operation_id == _uuid(operation_id))
                .order_by(ActivityAttemptRow.attempt_number)
            ).all()
            return [self._to_attempt(row) for row in rows]

    def list_evidence(self, workspace_id: UUID, operation_id: UUID) -> list[EvidenceItem]:
        with self._sessions() as session:
            rows = session.scalars(
                select(EvidenceItemRow)
                .where(
                    EvidenceItemRow.workspace_id == _uuid(workspace_id),
                    EvidenceItemRow.operation_id == _uuid(operation_id),
                )
                .order_by(EvidenceItemRow.created_at)
            ).all()
            return [self._to_evidence(row) for row in rows]

    def get_evidence(self, workspace_id: UUID, evidence_id: UUID) -> EvidenceItem | None:
        with self._sessions() as session:
            row = session.scalar(
                select(EvidenceItemRow).where(
                    EvidenceItemRow.id == _uuid(evidence_id),
                    EvidenceItemRow.workspace_id == _uuid(workspace_id),
                )
            )
            return self._to_evidence(row) if row else None

    def recover_stale_operations(self, now: datetime) -> int:
        with self._sessions.begin() as session:
            stale_rows = list(
                session.scalars(
                    select(OperationRow).where(
                        OperationRow.status == OperationStatus.RUNNING,
                        OperationRow.lease_expires_at.is_not(None),
                        OperationRow.lease_expires_at <= now,
                    )
                )
            )
            if not stale_rows:
                return 0
            retry_ids = [row.id for row in stale_rows if row.attempt_count < row.max_attempts]
            exhausted_ids = [row.id for row in stale_rows if row.attempt_count >= row.max_attempts]
            stale_ids = retry_ids + exhausted_ids
            session.execute(
                update(ActivityAttemptRow)
                .where(
                    ActivityAttemptRow.operation_id.in_(retry_ids),
                    ActivityAttemptRow.status == AttemptStatus.RUNNING,
                )
                .values(
                    status=AttemptStatus.RETRYABLE_FAILURE,
                    completed_at=now,
                    error_code="worker_lease_expired",
                )
            )
            if retry_ids:
                session.execute(
                    update(OperationRow)
                    .where(OperationRow.id.in_(retry_ids))
                    .values(
                        status=OperationStatus.RETRY_SCHEDULED,
                        next_attempt_at=now,
                        updated_at=now,
                        lease_expires_at=None,
                        last_error_code="worker_lease_expired",
                        last_error_message="worker lease expired; operation recovered",
                    )
                )
            if exhausted_ids:
                session.execute(
                    update(ActivityAttemptRow)
                    .where(
                        ActivityAttemptRow.operation_id.in_(exhausted_ids),
                        ActivityAttemptRow.status == AttemptStatus.RUNNING,
                    )
                    .values(
                        status=AttemptStatus.PERMANENT_FAILURE,
                        completed_at=now,
                        error_code="worker_lease_expired_attempts_exhausted",
                    )
                )
                session.execute(
                    update(OperationRow)
                    .where(OperationRow.id.in_(exhausted_ids))
                    .values(
                        status=OperationStatus.FAILED,
                        updated_at=now,
                        completed_at=now,
                        lease_expires_at=None,
                        last_error_code="worker_lease_expired_attempts_exhausted",
                        last_error_message="worker lease expired after final attempt",
                    )
                )
            return len(stale_ids)

    def claim_next_operation(self, now: datetime, lease_duration: timedelta) -> Operation | None:
        eligible = (OperationStatus.PENDING, OperationStatus.RETRY_SCHEDULED)
        with self._sessions.begin() as session:
            row = session.scalar(
                select(OperationRow)
                .where(
                    OperationRow.status.in_(eligible),
                    OperationRow.next_attempt_at <= now,
                    OperationRow.attempt_count < OperationRow.max_attempts,
                )
                .order_by(OperationRow.created_at, OperationRow.id)
                .limit(1)
            )
            if row is None:
                return None
            result = session.execute(
                update(OperationRow)
                .where(OperationRow.id == row.id, OperationRow.status.in_(eligible))
                .values(
                    status=OperationStatus.RUNNING,
                    started_at=row.started_at or now,
                    updated_at=now,
                    lease_expires_at=now + lease_duration,
                )
                .returning(OperationRow.id)
            )
            claimed_id = result.scalar_one_or_none()
            if claimed_id is None:
                return None
            session.flush()
            claimed = session.get(OperationRow, claimed_id)
            if claimed is None:
                return None
            session.refresh(claimed)
            return self._to_operation(claimed)

    def begin_attempt(self, attempt: ActivityAttempt) -> ActivityAttempt | None:
        try:
            with self._sessions.begin() as session:
                operation = session.get(OperationRow, _uuid(attempt.operation_id))
                if operation is None or operation.status != OperationStatus.RUNNING:
                    return None
                session.add(self._attempt_row(attempt))
                operation.attempt_count = attempt.attempt_number
                operation.updated_at = attempt.started_at
            return attempt
        except IntegrityError:
            return None

    def complete_operation(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        evidence: EvidenceItem,
        audit_event: AuditEvent,
        now: datetime,
    ) -> EvidenceItem:
        with self._sessions.begin() as session:
            operation = session.get(OperationRow, _uuid(operation_id))
            if operation is None:
                raise LookupError("operation disappeared")
            existing = session.scalar(
                select(EvidenceItemRow).where(EvidenceItemRow.operation_id == _uuid(operation_id))
            )
            if operation.status == OperationStatus.SUCCEEDED and existing is not None:
                return self._to_evidence(existing)
            attempt = session.get(ActivityAttemptRow, _uuid(attempt_id))
            if attempt is None:
                raise LookupError("activity attempt disappeared")
            if existing is None:
                session.add(self._evidence_row(evidence))
                persisted = evidence
            else:
                persisted = self._to_evidence(existing)
            attempt.status = AttemptStatus.SUCCEEDED
            attempt.completed_at = now
            attempt.error_code = None
            operation.status = OperationStatus.SUCCEEDED
            operation.updated_at = now
            operation.completed_at = now
            operation.lease_expires_at = None
            operation.last_error_code = None
            operation.last_error_message = None
            session.add(self._audit_row(audit_event))
            return persisted

    def schedule_retry(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        error_code: str,
        safe_message: str,
        next_attempt_at: datetime,
        audit_event: AuditEvent,
    ) -> None:
        with self._sessions.begin() as session:
            operation = session.get(OperationRow, _uuid(operation_id))
            attempt = session.get(ActivityAttemptRow, _uuid(attempt_id))
            if operation is None or attempt is None or OperationStatus(operation.status).terminal:
                return
            attempt.status = AttemptStatus.RETRYABLE_FAILURE
            attempt.completed_at = audit_event.occurred_at
            attempt.error_code = error_code
            operation.status = OperationStatus.RETRY_SCHEDULED
            operation.next_attempt_at = next_attempt_at
            operation.updated_at = audit_event.occurred_at
            operation.lease_expires_at = None
            operation.last_error_code = error_code
            operation.last_error_message = safe_message
            session.add(self._audit_row(audit_event))

    def fail_operation(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        error_code: str,
        safe_message: str,
        audit_event: AuditEvent,
        now: datetime,
    ) -> None:
        with self._sessions.begin() as session:
            operation = session.get(OperationRow, _uuid(operation_id))
            attempt = session.get(ActivityAttemptRow, _uuid(attempt_id))
            if operation is None or attempt is None or OperationStatus(operation.status).terminal:
                return
            attempt.status = AttemptStatus.PERMANENT_FAILURE
            attempt.completed_at = now
            attempt.error_code = error_code
            operation.status = OperationStatus.FAILED
            operation.updated_at = now
            operation.completed_at = now
            operation.lease_expires_at = None
            operation.last_error_code = error_code
            operation.last_error_message = safe_message
            session.add(self._audit_row(audit_event))

    @staticmethod
    def _campaign_row(value: Campaign) -> CampaignRow:
        return CampaignRow(
            id=_uuid(value.id),
            workspace_id=_uuid(value.workspace_id),
            name=value.name,
            fixture_uri=value.fixture_uri,
            created_by=value.created_by,
            created_at=value.created_at,
        )

    @staticmethod
    def _operation_row(value: Operation) -> OperationRow:
        return OperationRow(
            id=_uuid(value.id),
            workspace_id=_uuid(value.workspace_id),
            campaign_id=_uuid(value.campaign_id),
            workflow_name=value.workflow_name,
            workflow_version=value.workflow_version,
            status=value.status,
            idempotency_key=value.idempotency_key,
            trace_id=_uuid(value.trace_id),
            attempt_count=value.attempt_count,
            max_attempts=value.max_attempts,
            next_attempt_at=value.next_attempt_at,
            created_by=value.created_by,
            created_at=value.created_at,
            updated_at=value.updated_at,
            started_at=value.started_at,
            completed_at=value.completed_at,
            lease_expires_at=value.lease_expires_at,
            last_error_code=value.last_error_code,
            last_error_message=value.last_error_message,
        )

    @staticmethod
    def _attempt_row(value: ActivityAttempt) -> ActivityAttemptRow:
        return ActivityAttemptRow(
            id=_uuid(value.id),
            operation_id=_uuid(value.operation_id),
            activity_name=value.activity_name,
            activity_version=value.activity_version,
            idempotency_key=value.idempotency_key,
            attempt_number=value.attempt_number,
            status=value.status,
            started_at=value.started_at,
            completed_at=value.completed_at,
            error_code=value.error_code,
        )

    @staticmethod
    def _evidence_row(value: EvidenceItem) -> EvidenceItemRow:
        return EvidenceItemRow(
            id=_uuid(value.id),
            workspace_id=_uuid(value.workspace_id),
            campaign_id=_uuid(value.campaign_id),
            operation_id=_uuid(value.operation_id),
            source_type=value.source_type,
            source_uri=value.source_uri,
            final_uri=value.final_uri,
            captured_at=value.captured_at,
            content_sha256=value.content_sha256,
            mime_type=value.mime_type,
            title=value.title,
            excerpt=value.excerpt,
            fragment_locator=value.fragment_locator,
            extractor_name=value.extractor_name,
            extractor_version=value.extractor_version,
            fixture_version=value.fixture_version,
            created_at=value.created_at,
        )

    @staticmethod
    def _audit_row(value: AuditEvent) -> AuditEventRow:
        return AuditEventRow(
            id=_uuid(value.id),
            workspace_id=_uuid(value.workspace_id),
            subject=value.subject,
            event_type=value.event_type,
            target_type=value.target_type,
            target_id=_uuid(value.target_id),
            trace_id=_uuid(value.trace_id),
            occurred_at=value.occurred_at,
        )

    @staticmethod
    def _to_campaign(row: CampaignRow) -> Campaign:
        return Campaign(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            name=row.name,
            fixture_uri=row.fixture_uri,
            created_by=row.created_by,
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
        )

    @staticmethod
    def _to_operation(row: OperationRow) -> Operation:
        return Operation(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            campaign_id=UUID(row.campaign_id),
            workflow_name=row.workflow_name,
            workflow_version=row.workflow_version,
            status=OperationStatus(row.status),
            idempotency_key=row.idempotency_key,
            trace_id=UUID(row.trace_id),
            attempt_count=row.attempt_count,
            max_attempts=row.max_attempts,
            next_attempt_at=_aware(row.next_attempt_at),  # type: ignore[arg-type]
            created_by=row.created_by,
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
            updated_at=_aware(row.updated_at),  # type: ignore[arg-type]
            started_at=_aware(row.started_at),
            completed_at=_aware(row.completed_at),
            lease_expires_at=_aware(row.lease_expires_at),
            last_error_code=row.last_error_code,
            last_error_message=row.last_error_message,
        )

    @staticmethod
    def _to_attempt(row: ActivityAttemptRow) -> ActivityAttempt:
        return ActivityAttempt(
            id=UUID(row.id),
            operation_id=UUID(row.operation_id),
            activity_name=row.activity_name,
            activity_version=row.activity_version,
            idempotency_key=row.idempotency_key,
            attempt_number=row.attempt_number,
            status=AttemptStatus(row.status),
            started_at=_aware(row.started_at),  # type: ignore[arg-type]
            completed_at=_aware(row.completed_at),
            error_code=row.error_code,
        )

    @staticmethod
    def _to_evidence(row: EvidenceItemRow) -> EvidenceItem:
        return EvidenceItem(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            campaign_id=UUID(row.campaign_id),
            operation_id=UUID(row.operation_id),
            source_type=row.source_type,
            source_uri=row.source_uri,
            final_uri=row.final_uri,
            captured_at=_aware(row.captured_at),  # type: ignore[arg-type]
            content_sha256=row.content_sha256,
            mime_type=row.mime_type,
            title=row.title,
            excerpt=row.excerpt,
            fragment_locator=row.fragment_locator,
            extractor_name=row.extractor_name,
            extractor_version=row.extractor_version,
            fixture_version=row.fixture_version,
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
        )
