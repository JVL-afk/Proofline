"""Append-oriented SQLAlchemy persistence for local SQLite and Phase 1 PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from opintel_demo.domain import (
    ComponentInstance,
    DemoBundle,
    DemoInputManifest,
    DemoOperation,
    DemoOperationStatus,
    DemoQcFinding,
    DemoReviewDecision,
    DemoReviewDecisionType,
    DemoRevision,
    DemoRevisionState,
    DemoRevocation,
    DemoSpecification,
    DemoStatementBinding,
    DemoStatementKind,
    DemoStateNode,
    DemoTransition,
    DemoValidity,
    MockActionDefinition,
    MockActionReceipt,
    MockClassification,
    QcSeverity,
    QualificationQuestion,
    RecordingCue,
    RuntimeSession,
    RuntimeTerminal,
    ServiceAreaOption,
    ServiceCategoryOption,
    SessionIssuance,
    SessionState,
    SyntheticPersona,
    TechnicalDemoSpecification,
    TelemetryEvent,
)
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class DemoOperationRow(Base):
    __tablename__ = "demo_operations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "audit_revision_id",
            "expected_audit_revision_hash",
            "idempotency_key",
            name="uq_demo_operation_command",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    audit_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    expected_audit_revision_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(40), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    demo_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    data_json: Mapped[str] = mapped_column(Text)


class DemoRevisionRow(Base):
    __tablename__ = "demo_revisions"
    __table_args__ = (UniqueConstraint("demo_id", "revision", name="uq_demo_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    audit_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(40))
    validity: Mapped[str] = mapped_column(String(40))
    data_json: Mapped[str] = mapped_column(Text)


class DemoReviewRow(Base):
    __tablename__ = "demo_review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_json: Mapped[str] = mapped_column(Text)


class DemoRevocationRow(Base):
    __tablename__ = "demo_revision_revocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_json: Mapped[str] = mapped_column(Text)


class DemoIssuanceRow(Base):
    __tablename__ = "demo_session_issuances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    audience: Mapped[str] = mapped_column(String(200))
    capability_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(40))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DemoSessionRow(Base):
    __tablename__ = "demo_runtime_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(40))
    data_json: Mapped[str] = mapped_column(Text)


class DemoSessionRevocationRow(Base):
    __tablename__ = "demo_session_revocations"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DemoTelemetryRow(Base):
    __tablename__ = "demo_telemetry_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyDemoRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("M4 repository requires sqlite or postgresql+psycopg")
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

    def create_or_get_operation(self, operation: DemoOperation) -> tuple[DemoOperation, bool]:
        try:
            with self._sessions.begin() as session:
                session.add(self._operation_row(operation))
            return operation, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(DemoOperationRow).where(
                        DemoOperationRow.workspace_id == str(operation.workspace_id),
                        DemoOperationRow.audit_revision_id == str(operation.audit_revision_id),
                        DemoOperationRow.expected_audit_revision_hash
                        == operation.expected_audit_revision_hash,
                        DemoOperationRow.idempotency_key == operation.idempotency_key,
                    )
                )
                assert row is not None
                return self._operation(row), False

    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> DemoOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DemoOperationRow).where(
                    DemoOperationRow.id == str(operation_id),
                    DemoOperationRow.workspace_id == str(workspace_id),
                )
            )
            return self._operation(row) if row else None

    def claim_operation(self, now: datetime, lease: timedelta) -> DemoOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(DemoOperationRow)
                .where(
                    ~DemoOperationRow.idempotency_key.like("m67:%"),
                    or_(
                        DemoOperationRow.status.in_(("pending", "retry_scheduled")),
                        (DemoOperationRow.status == "running")
                        & (DemoOperationRow.lease_expires_at <= now),
                    )
                )
                .order_by(DemoOperationRow.updated_at)
                .limit(1)
            )
            if row is None:
                return None
            row.status = DemoOperationStatus.RUNNING
            row.attempt_count += 1
            row.updated_at = now
            row.lease_expires_at = now + lease
            return self._operation(row)

    def claim_exact_operation(
        self, operation_id: UUID, expected_created_by: str, now: datetime, lease: timedelta
    ) -> DemoOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(DemoOperationRow).where(
                    DemoOperationRow.id == str(operation_id),
                    DemoOperationRow.idempotency_key.like("m67:%"),
                    or_(
                        DemoOperationRow.status.in_(("pending", "retry_scheduled")),
                        (DemoOperationRow.status == "running")
                        & (DemoOperationRow.lease_expires_at <= now),
                    ),
                )
            )
            if row is None:
                return None
            operation = self._operation(row)
            if operation.created_by != expected_created_by:
                raise ValueError("exact demo operation creator mismatch")
            row.status = DemoOperationStatus.RUNNING
            row.attempt_count += 1
            row.updated_at = now
            row.lease_expires_at = now + lease
            session.flush()
            return replace(
                operation,
                status=DemoOperationStatus.RUNNING,
                attempt_count=row.attempt_count,
                updated_at=now,
                lease_expires_at=now + lease,
            )

    def retry_operation(self, operation: DemoOperation, error_code: str, now: datetime) -> None:
        self._update_operation(operation.id, DemoOperationStatus.RETRY_SCHEDULED, error_code, now)

    def fail_operation(self, operation: DemoOperation, error_code: str, now: datetime) -> None:
        self._update_operation(operation.id, DemoOperationStatus.FAILED, error_code, now)

    def _update_operation(
        self, operation_id: UUID, status: DemoOperationStatus, error_code: str, now: datetime
    ) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(DemoOperationRow)
                .where(DemoOperationRow.id == str(operation_id))
                .values(status=status, error_code=error_code, updated_at=now, lease_expires_at=None)
            )

    def save_revision(self, operation: DemoOperation, revision: DemoRevision) -> None:
        with self._sessions.begin() as session:
            session.add(
                DemoRevisionRow(
                    id=str(revision.id),
                    demo_id=str(revision.demo_id),
                    workspace_id=str(revision.workspace_id),
                    audit_id=str(revision.audit_id),
                    revision=revision.revision,
                    state=revision.state,
                    validity=revision.validity,
                    data_json=_json(asdict(revision)),
                )
            )
            if revision.parent_revision_id is not None:
                session.execute(
                    update(DemoRevisionRow)
                    .where(DemoRevisionRow.id == str(revision.parent_revision_id))
                    .values(state=DemoRevisionState.SUPERSEDED)
                )
            session.execute(
                update(DemoOperationRow)
                .where(DemoOperationRow.id == str(operation.id))
                .values(
                    status=DemoOperationStatus.SUCCEEDED,
                    demo_revision_id=str(revision.id),
                    updated_at=revision.created_at,
                    lease_expires_at=None,
                    error_code=None,
                )
            )

    def get_revision(self, workspace_id: UUID, revision_id: UUID) -> DemoBundle | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DemoRevisionRow).where(
                    DemoRevisionRow.id == str(revision_id),
                    DemoRevisionRow.workspace_id == str(workspace_id),
                )
            )
            return self._bundle(session, row) if row else None

    def list_revisions(self, workspace_id: UUID, demo_id: UUID) -> tuple[DemoBundle, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(DemoRevisionRow)
                    .where(
                        DemoRevisionRow.workspace_id == str(workspace_id),
                        DemoRevisionRow.demo_id == str(demo_id),
                    )
                    .order_by(DemoRevisionRow.revision)
                )
            )
            return tuple(self._bundle(session, row) for row in rows)

    def save_review(self, bundle: DemoBundle, decision: DemoReviewDecision) -> DemoBundle:
        state = {
            DemoReviewDecisionType.APPROVE: DemoRevisionState.APPROVED,
            DemoReviewDecisionType.REJECT: DemoRevisionState.REJECTED,
            DemoReviewDecisionType.REQUEST_REVISION: DemoRevisionState.REVISION_REQUESTED,
        }[decision.decision]
        with self._sessions.begin() as session:
            session.add(
                DemoReviewRow(
                    id=str(decision.id),
                    demo_revision_id=str(decision.demo_revision_id),
                    created_at=decision.created_at,
                    data_json=_json(asdict(decision)),
                )
            )
            session.execute(
                update(DemoRevisionRow)
                .where(DemoRevisionRow.id == str(bundle.revision.id))
                .values(state=state)
            )
        return DemoBundle(replace(bundle.revision, state=state), decision, True, bundle.revocation)

    def save_revocation(self, bundle: DemoBundle, revocation: DemoRevocation) -> DemoBundle:
        with self._sessions.begin() as session:
            session.add(
                DemoRevocationRow(
                    id=str(revocation.id),
                    demo_revision_id=str(revocation.demo_revision_id),
                    created_at=revocation.created_at,
                    data_json=_json(asdict(revocation)),
                )
            )
        return DemoBundle(
            replace(bundle.revision, validity=DemoValidity.REVOKED),
            bundle.latest_review,
            False,
            revocation,
        )

    def create_issuance(self, issuance: SessionIssuance) -> None:
        with self._sessions.begin() as session:
            session.add(
                DemoIssuanceRow(
                    id=str(issuance.id),
                    demo_revision_id=str(issuance.demo_revision_id),
                    workspace_id=str(issuance.workspace_id),
                    audience=issuance.audience,
                    capability_hash=issuance.capability_hash,
                    state=issuance.state,
                    issued_at=issuance.issued_at,
                    expires_at=issuance.expires_at,
                    used_at=issuance.used_at,
                    revoked_at=issuance.revoked_at,
                )
            )

    def get_issuance_by_capability_hash(self, capability_hash: str) -> SessionIssuance | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DemoIssuanceRow).where(DemoIssuanceRow.capability_hash == capability_hash)
            )
            return self._issuance(row) if row else None

    def consume_issuance(
        self, issuance: SessionIssuance, runtime: RuntimeSession, now: datetime
    ) -> None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(DemoIssuanceRow).where(
                    DemoIssuanceRow.id == str(issuance.id),
                    DemoIssuanceRow.used_at.is_(None),
                )
            )
            if row is None:
                raise ValueError("issuance already consumed")
            row.state = SessionState.ACTIVE
            row.used_at = now
            session.add(self._session_row(runtime))

    def get_session_by_token_hash(self, token_hash: str) -> RuntimeSession | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DemoSessionRow).where(DemoSessionRow.session_token_hash == token_hash)
            )
            return self._runtime_session(row) if row else None

    def get_session(self, workspace_id: UUID, session_id: UUID) -> RuntimeSession | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DemoSessionRow).where(
                    DemoSessionRow.id == str(session_id),
                    DemoSessionRow.workspace_id == str(workspace_id),
                )
            )
            return self._runtime_session(row) if row else None

    def save_session(self, runtime: RuntimeSession) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(DemoSessionRow)
                .where(DemoSessionRow.id == str(runtime.id))
                .values(state=runtime.state, data_json=_json(asdict(runtime)))
            )

    def revoke_session(self, session_id: UUID, actor: str, now: datetime) -> None:
        with self._sessions.begin() as session:
            row = session.scalar(select(DemoSessionRow).where(DemoSessionRow.id == str(session_id)))
            if row is None:
                return
            runtime = replace(self._runtime_session(row), state=SessionState.REVOKED, ended_at=now)
            row.state = SessionState.REVOKED
            row.data_json = _json(asdict(runtime))
            session.add(
                DemoSessionRevocationRow(
                    id=f"{session_id}:{now.isoformat()}",
                    session_id=str(session_id),
                    actor=actor,
                    created_at=now,
                )
            )

    def save_telemetry(self, value: TelemetryEvent) -> None:
        with self._sessions.begin() as session:
            session.add(
                DemoTelemetryRow(
                    id=str(value.id),
                    demo_revision_id=str(value.demo_revision_id),
                    session_id=str(value.session_id),
                    created_at=value.created_at,
                    data_json=_json(asdict(value)),
                )
            )

    def list_telemetry(self, workspace_id: UUID, revision_id: UUID) -> tuple[TelemetryEvent, ...]:
        if self.get_revision(workspace_id, revision_id) is None:
            return ()
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(DemoTelemetryRow)
                    .where(DemoTelemetryRow.demo_revision_id == str(revision_id))
                    .order_by(DemoTelemetryRow.created_at)
                )
            )
            return tuple(self._telemetry(row) for row in rows)

    @staticmethod
    def _operation_row(value: DemoOperation) -> DemoOperationRow:
        return DemoOperationRow(
            id=str(value.id),
            workspace_id=str(value.workspace_id),
            audit_revision_id=str(value.audit_revision_id),
            expected_audit_revision_hash=value.expected_audit_revision_hash,
            idempotency_key=value.idempotency_key,
            status=value.status,
            attempt_count=value.attempt_count,
            updated_at=value.updated_at,
            lease_expires_at=value.lease_expires_at,
            demo_revision_id=str(value.demo_revision_id) if value.demo_revision_id else None,
            error_code=value.error_code,
            data_json=_json(asdict(value)),
        )

    @staticmethod
    def _operation(row: DemoOperationRow) -> DemoOperation:
        item = json.loads(row.data_json)
        return DemoOperation(
            UUID(item["id"]),
            UUID(item["workspace_id"]),
            UUID(item["business_id"]),
            UUID(item["audit_revision_id"]),
            item["expected_audit_revision_hash"],
            UUID(item["demo_id"]),
            UUID(item["parent_revision_id"]) if item["parent_revision_id"] else None,
            DemoOperationStatus(row.status),
            item["idempotency_key"],
            UUID(item["trace_id"]),
            row.attempt_count,
            item["max_attempts"],
            item["created_by"],
            _dt(item["created_at"]),
            _required_aware(row.updated_at),
            _aware(row.lease_expires_at),
            UUID(row.demo_revision_id) if row.demo_revision_id else None,
            row.error_code,
        )

    @staticmethod
    def _issuance(row: DemoIssuanceRow) -> SessionIssuance:
        return SessionIssuance(
            UUID(row.id),
            UUID(row.demo_revision_id),
            UUID(row.workspace_id),
            row.audience,
            row.capability_hash,
            SessionState(row.state),
            _required_aware(row.issued_at),
            _required_aware(row.expires_at),
            _aware(row.used_at),
            _aware(row.revoked_at),
        )

    @staticmethod
    def _session_row(value: RuntimeSession) -> DemoSessionRow:
        return DemoSessionRow(
            id=str(value.id),
            workspace_id=str(value.workspace_id),
            demo_revision_id=str(value.demo_revision_id),
            session_token_hash=value.session_token_hash,
            state=value.state,
            data_json=_json(asdict(value)),
        )

    @staticmethod
    def _runtime_session(row: DemoSessionRow) -> RuntimeSession:
        item = json.loads(row.data_json)
        receipts = tuple(
            MockActionReceipt(
                value["action_id"],
                MockClassification(value["classification"]),
                value["status"],
                value["receipt_id"],
                value["display_message"],
            )
            for value in item["receipts"]
        )
        return RuntimeSession(
            UUID(item["id"]),
            UUID(item["issuance_id"]),
            UUID(item["demo_revision_id"]),
            UUID(item["workspace_id"]),
            item["audience"],
            item["session_token_hash"],
            SessionState(row.state),
            item["current_state"],
            item["persona_id"],
            item["seed"],
            item["transition_count"],
            tuple(item["event_history"]),
            receipts,
            _dt(item["started_at"]),
            _dt(item["expires_at"]),
            _dt(item["ended_at"]) if item["ended_at"] else None,
        )

    @staticmethod
    def _telemetry(row: DemoTelemetryRow) -> TelemetryEvent:
        item = json.loads(row.data_json)
        return TelemetryEvent(
            UUID(item["id"]),
            UUID(item["session_id"]),
            UUID(item["demo_revision_id"]),
            item["scenario_id"],
            item["event_type"],
            item["state_id"],
            item["outcome"],
            item["synthetic_fixture_id"],
            item["duration_ms"],
            _dt(item["created_at"]),
        )

    @staticmethod
    def _revision(row: DemoRevisionRow) -> DemoRevision:
        item = json.loads(row.data_json)
        manifest_data = item["manifest"]
        singular_uuids = {
            "id",
            "workspace_id",
            "business_id",
            "opportunity_id",
            "opportunity_revision_id",
            "opportunity_review_id",
            "audit_id",
            "audit_revision_id",
            "audit_review_id",
            "economic_run_id",
            "score_snapshot_id",
        }
        tuple_uuids = {
            "audit_claim_ids",
            "evidence_ids",
            "information_gap_ids",
            "assumption_revision_ids",
        }
        for field in singular_uuids:
            manifest_data[field] = UUID(manifest_data[field])
        for field in tuple_uuids:
            manifest_data[field] = tuple(UUID(value) for value in manifest_data[field])
        manifest_data["evidence_fingerprints"] = tuple(manifest_data["evidence_fingerprints"])
        manifest_data["created_at"] = _dt(manifest_data["created_at"])
        manifest = DemoInputManifest(**manifest_data)
        specification = _specification(item["specification"])
        findings = tuple(
            DemoQcFinding(
                UUID(value["id"]), value["code"], QcSeverity(value["severity"]), value["message"]
            )
            for value in item["qc_findings"]
        )
        return DemoRevision(
            UUID(item["id"]),
            UUID(item["demo_id"]),
            item["revision"],
            UUID(item["parent_revision_id"]) if item["parent_revision_id"] else None,
            UUID(item["workspace_id"]),
            UUID(item["business_id"]),
            UUID(item["opportunity_id"]),
            UUID(item["audit_id"]),
            manifest,
            specification,
            findings,
            DemoRevisionState(row.state),
            DemoValidity(row.validity),
            item["specification_hash"],
            item["revision_hash"],
            item["created_by"],
            _dt(item["created_at"]),
        )

    @staticmethod
    def _review(row: DemoReviewRow) -> DemoReviewDecision:
        item = json.loads(row.data_json)
        return DemoReviewDecision(
            UUID(item["id"]),
            UUID(item["demo_revision_id"]),
            item["revision_hash"],
            item["manifest_hash"],
            item["specification_hash"],
            DemoReviewDecisionType(item["decision"]),
            item["actor"],
            tuple(item["actor_roles"]),
            item["reason"],
            item["self_review"],
            _dt(item["created_at"]),
        )

    @staticmethod
    def _revocation(row: DemoRevocationRow) -> DemoRevocation:
        item = json.loads(row.data_json)
        return DemoRevocation(
            UUID(item["id"]),
            UUID(item["demo_revision_id"]),
            item["actor"],
            item["reason"],
            _dt(item["created_at"]),
        )

    def _bundle(self, session: object, row: DemoRevisionRow) -> DemoBundle:
        review = session.scalar(  # type: ignore[attr-defined]
            select(DemoReviewRow)
            .where(DemoReviewRow.demo_revision_id == row.id)
            .order_by(DemoReviewRow.created_at.desc())
            .limit(1)
        )
        revocation = session.scalar(  # type: ignore[attr-defined]
            select(DemoRevocationRow).where(DemoRevocationRow.demo_revision_id == row.id)
        )
        return DemoBundle(
            self._revision(row),
            self._review(review) if review else None,
            bool(review and not revocation),
            self._revocation(revocation) if revocation else None,
        )


def _specification(item: dict[str, Any]) -> DemoSpecification:
    personas = tuple(SyntheticPersona(**value) for value in item["personas"])
    questions = tuple(
        QualificationQuestion(
            value["id"],
            value["prompt"],
            value["input_kind"],
            tuple(value["allowed_values"]),
            value["required"],
            value["purpose"],
            value["collects_contact_destination"],
        )
        for value in item["questions"]
    )
    states = tuple(
        DemoStateNode(
            value["id"],
            tuple(
                ComponentInstance(
                    component["id"],
                    component["component_type"],
                    tuple(tuple(prop) for prop in component["props"]),
                )
                for component in value["components"]
            ),
            RuntimeTerminal(value["terminal"]),
        )
        for value in item["states"]
    )
    transitions = tuple(DemoTransition(**value) for value in item["transitions"])
    actions = tuple(
        MockActionDefinition(
            value["id"],
            value["action_type"],
            MockClassification(value["classification"]),
            value["display_label"],
        )
        for value in item["mock_actions"]
    )
    statements = tuple(
        DemoStatementBinding(
            UUID(value["id"]),
            DemoStatementKind(value["kind"]),
            value["display_text"],
            UUID(value["audit_claim_id"]) if value["audit_claim_id"] else None,
            value["audit_claim_type"],
            tuple(UUID(identifier) for identifier in value["evidence_ids"]),
            tuple(UUID(identifier) for identifier in value["assumption_revision_ids"]),
            UUID(value["economic_run_id"]) if value["economic_run_id"] else None,
            value["formula_version"],
            value["visibly_conditional"],
            tuple(UUID(identifier) for identifier in value["dependency_claim_ids"]),
        )
        for value in item["statements"]
    )
    cues = tuple(
        RecordingCue(
            value["ordinal"],
            value["state_id"],
            value["narration"],
            value["synthetic_event"],
            tuple(UUID(identifier) for identifier in value["statement_ids"]),
        )
        for value in item["recording_cues"]
    )
    technical_raw = item["technical_specification"]
    technical = TechnicalDemoSpecification(
        technical_raw["trigger"],
        tuple(technical_raw["inputs"]),
        tuple(technical_raw["handoff_conditions"]),
        tuple(technical_raw["proposed_integrations"]),
        tuple(technical_raw["safeguards"]),
        technical_raw["deployment_status"],
    )
    return DemoSpecification(
        item["schema_version"],
        item["business_display_name"],
        item["neutral_theme"],
        item["scenario_id"],
        item["scenario_version"],
        item["initial_state"],
        item["maximum_transitions"],
        tuple(item["components"]),
        personas,
        questions,
        states,
        transitions,
        actions,
        statements,
        tuple(tuple(value) for value in item["conversation_utterances"]),
        cues,
        technical,
        tuple(
            ServiceCategoryOption(v["label"], UUID(v["evidence_id"]), v["fact_class"])
            for v in item.get("service_categories", [])
        ),
        tuple(
            ServiceAreaOption(v["label"], UUID(v["evidence_id"]), v["fact_class"])
            for v in item.get("service_area_context", [])
        ),
        tuple(
            (pair[0], UUID(pair[1])) for pair in item.get("personalization_provenance", [])
        ),
    )


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _required_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
