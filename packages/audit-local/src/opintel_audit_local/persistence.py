"""SQLAlchemy M3 persistence for local SQLite and Phase 1 PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import overload
from uuid import UUID

from opintel_audit.domain import (
    AuditBundle,
    AuditClaim,
    AuditFinding,
    AuditInputManifest,
    AuditKind,
    AuditOperation,
    AuditOperationStatus,
    AuditReviewDecision,
    AuditReviewDecisionType,
    AuditRevision,
    AuditRevisionState,
    AuditSection,
    AuditValidity,
    ClaimType,
    FindingKind,
    QcFinding,
    QcSeverity,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@overload
def _aware(value: datetime) -> datetime: ...


@overload
def _aware(value: None) -> None: ...


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class AuditOperationRow(Base):
    __tablename__ = "audit_operations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "hypothesis_id",
            "expected_hypothesis_revision_id",
            "idempotency_key",
            name="uq_audit_operation_command",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    expected_hypothesis_revision_id: Mapped[str] = mapped_column(String(36))
    audit_id: Mapped[str] = mapped_column(String(36), index=True)
    parent_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    trace_id: Mapped[str] = mapped_column(String(36))
    attempt_count: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    audit_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AuditRevisionRow(Base):
    __tablename__ = "audit_revisions"
    __table_args__ = (UniqueConstraint("audit_id", "revision", name="uq_audit_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    audit_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    parent_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    manifest_json: Mapped[str] = mapped_column(Text)
    sections_json: Mapped[str] = mapped_column(Text)
    claims_json: Mapped[str] = mapped_column(Text)
    qc_json: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40))
    validity: Mapped[str] = mapped_column(String(40))
    revision_hash: Mapped[str] = mapped_column(String(64))
    rendered_text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # EVIDENCE_PRESERVING_PERSONALIZATION_V2: concise finding taxonomy + coverage.
    findings_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditReviewRow(Base):
    __tablename__ = "audit_review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    audit_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    revision_hash: Mapped[str] = mapped_column(String(64))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    actor_roles_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    self_review: Mapped[bool] = mapped_column(Boolean)
    acknowledged_qc_codes_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditReviewInvalidationRow(Base):
    __tablename__ = "audit_review_invalidations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(36), index=True)
    changed_input_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyAuditRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("M3 repository requires sqlite or postgresql+psycopg")
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
        with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(670003)"))
            Base.metadata.create_all(connection)
            inspector = inspect(connection)
            if "audit_revisions" in inspector.get_table_names():
                present = {item["name"] for item in inspector.get_columns("audit_revisions")}
                if "findings_json" not in present:
                    connection.execute(
                        text("ALTER TABLE audit_revisions ADD COLUMN findings_json TEXT")
                    )

    def create_or_get_operation(self, operation: AuditOperation) -> tuple[AuditOperation, bool]:
        try:
            with self._sessions.begin() as session:
                session.add(self._operation_row(operation))
            return operation, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(AuditOperationRow).where(
                        AuditOperationRow.workspace_id == str(operation.workspace_id),
                        AuditOperationRow.hypothesis_id == str(operation.hypothesis_id),
                        AuditOperationRow.expected_hypothesis_revision_id
                        == str(operation.expected_hypothesis_revision_id),
                        AuditOperationRow.idempotency_key == operation.idempotency_key,
                    )
                )
                assert row is not None
                return self._operation(row), False

    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> AuditOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(AuditOperationRow).where(
                    AuditOperationRow.id == str(operation_id),
                    AuditOperationRow.workspace_id == str(workspace_id),
                )
            )
            return self._operation(row) if row else None

    def claim_operation(self, now: datetime, lease: timedelta) -> AuditOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(AuditOperationRow)
                .where(
                    AuditOperationRow.created_by != "m67-bounded-sampled-slot-coordinator",
                    or_(
                        AuditOperationRow.status.in_(("pending", "retry_scheduled")),
                        (AuditOperationRow.status == "running")
                        & (AuditOperationRow.lease_expires_at <= now),
                    )
                )
                .order_by(AuditOperationRow.created_at)
                .limit(1)
            )
            if row is None:
                return None
            row.status = AuditOperationStatus.RUNNING
            row.attempt_count += 1
            row.updated_at = now
            row.lease_expires_at = now + lease
            return self._operation(row)

    def claim_exact_operation(
        self, operation_id: UUID, expected_created_by: str, now: datetime, lease: timedelta
    ) -> AuditOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(AuditOperationRow).where(
                    AuditOperationRow.id == str(operation_id),
                    AuditOperationRow.created_by == expected_created_by,
                    or_(
                        AuditOperationRow.status.in_(("pending", "retry_scheduled")),
                        (AuditOperationRow.status == "running")
                        & (AuditOperationRow.lease_expires_at <= now),
                    ),
                )
            )
            if row is None:
                return None
            row.status = AuditOperationStatus.RUNNING
            row.attempt_count += 1
            row.updated_at = now
            row.lease_expires_at = now + lease
            session.flush()
            return self._operation(row)

    def retry_operation(self, operation: AuditOperation, error_code: str, now: datetime) -> None:
        self._update_operation(operation.id, AuditOperationStatus.RETRY_SCHEDULED, error_code, now)

    def fail_operation(self, operation: AuditOperation, error_code: str, now: datetime) -> None:
        self._update_operation(operation.id, AuditOperationStatus.FAILED, error_code, now)

    def _update_operation(
        self, operation_id: UUID, status: AuditOperationStatus, error_code: str, now: datetime
    ) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(AuditOperationRow)
                .where(AuditOperationRow.id == str(operation_id))
                .values(status=status, error_code=error_code, updated_at=now, lease_expires_at=None)
            )

    def save_revision(self, operation: AuditOperation, revision: AuditRevision) -> None:
        with self._sessions.begin() as session:
            session.add(self._revision_row(revision))
            if revision.parent_revision_id is not None:
                session.execute(
                    update(AuditRevisionRow)
                    .where(AuditRevisionRow.id == str(revision.parent_revision_id))
                    .values(state=AuditRevisionState.SUPERSEDED)
                )
            session.execute(
                update(AuditOperationRow)
                .where(AuditOperationRow.id == str(operation.id))
                .values(
                    status=AuditOperationStatus.SUCCEEDED,
                    audit_revision_id=str(revision.id),
                    updated_at=revision.created_at,
                    lease_expires_at=None,
                    error_code=None,
                )
            )

    def get_revision(self, workspace_id: UUID, revision_id: UUID) -> AuditBundle | None:
        with self._sessions() as session:
            row = session.scalar(
                select(AuditRevisionRow).where(
                    AuditRevisionRow.id == str(revision_id),
                    AuditRevisionRow.workspace_id == str(workspace_id),
                )
            )
            return self._bundle(session, row) if row else None

    def list_revisions(self, workspace_id: UUID, audit_id: UUID) -> tuple[AuditBundle, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(AuditRevisionRow)
                    .where(
                        AuditRevisionRow.workspace_id == str(workspace_id),
                        AuditRevisionRow.audit_id == str(audit_id),
                    )
                    .order_by(AuditRevisionRow.revision)
                )
            )
            return tuple(self._bundle(session, row) for row in rows)

    def save_review(self, bundle: AuditBundle, decision: AuditReviewDecision) -> AuditBundle:
        state = {
            AuditReviewDecisionType.APPROVE: AuditRevisionState.APPROVED,
            AuditReviewDecisionType.REJECT: AuditRevisionState.REJECTED,
            AuditReviewDecisionType.REQUEST_REVISION: AuditRevisionState.REVISION_REQUESTED,
        }[decision.decision]
        with self._sessions.begin() as session:
            session.add(self._review_row(decision))
            session.execute(
                update(AuditRevisionRow)
                .where(AuditRevisionRow.id == str(bundle.revision.id))
                .values(state=state)
            )
        return AuditBundle(replace(bundle.revision, state=state), decision, True)

    def invalidate_review(
        self, review_id: UUID, changed_input_id: UUID, reason: str, now: datetime
    ) -> None:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(AuditReviewInvalidationRow).where(
                    AuditReviewInvalidationRow.review_id == str(review_id)
                )
            )
            if existing is None:
                session.add(
                    AuditReviewInvalidationRow(
                        id=str(UUID(int=review_id.int ^ changed_input_id.int)),
                        review_id=str(review_id),
                        changed_input_id=str(changed_input_id),
                        reason=reason,
                        created_at=now,
                    )
                )

    @staticmethod
    def _operation_row(value: AuditOperation) -> AuditOperationRow:
        return AuditOperationRow(
            **{
                **asdict(value),
                "id": str(value.id),
                "workspace_id": str(value.workspace_id),
                "business_id": str(value.business_id),
                "hypothesis_id": str(value.hypothesis_id),
                "expected_hypothesis_revision_id": str(value.expected_hypothesis_revision_id),
                "audit_id": str(value.audit_id),
                "parent_revision_id": str(value.parent_revision_id)
                if value.parent_revision_id
                else None,
                "trace_id": str(value.trace_id),
                "audit_revision_id": str(value.audit_revision_id)
                if value.audit_revision_id
                else None,
            }
        )

    @staticmethod
    def _operation(row: AuditOperationRow) -> AuditOperation:
        return AuditOperation(
            UUID(row.id),
            UUID(row.workspace_id),
            UUID(row.business_id),
            UUID(row.hypothesis_id),
            UUID(row.expected_hypothesis_revision_id),
            UUID(row.audit_id),
            UUID(row.parent_revision_id) if row.parent_revision_id else None,
            AuditKind(row.kind),
            AuditOperationStatus(row.status),
            row.idempotency_key,
            UUID(row.trace_id),
            row.attempt_count,
            row.max_attempts,
            row.created_by,
            _aware(row.created_at),
            _aware(row.updated_at),
            _aware(row.lease_expires_at),
            UUID(row.audit_revision_id) if row.audit_revision_id else None,
            row.error_code,
        )

    @staticmethod
    def _revision_row(value: AuditRevision) -> AuditRevisionRow:
        return AuditRevisionRow(
            id=str(value.id),
            audit_id=str(value.audit_id),
            revision=value.revision,
            parent_revision_id=str(value.parent_revision_id) if value.parent_revision_id else None,
            workspace_id=str(value.workspace_id),
            business_id=str(value.business_id),
            hypothesis_id=str(value.hypothesis_id),
            kind=value.kind,
            manifest_json=_json(asdict(value.manifest)),
            sections_json=_json([asdict(item) for item in value.sections]),
            claims_json=_json([asdict(item) for item in value.claims]),
            qc_json=_json([asdict(item) for item in value.qc_findings]),
            state=value.state,
            validity=value.validity,
            revision_hash=value.revision_hash,
            rendered_text=value.rendered_text,
            created_by=value.created_by,
            created_at=value.created_at,
            findings_json=_json([asdict(item) for item in value.findings]),
        )

    @staticmethod
    def _revision(row: AuditRevisionRow) -> AuditRevision:
        raw_manifest = json.loads(row.manifest_json)
        uuid_fields = {
            "id",
            "workspace_id",
            "business_id",
            "research_run_id",
            "analysis_run_id",
            "hypothesis_id",
            "hypothesis_revision_id",
            "economic_run_id",
            "score_snapshot_id",
        }
        tuple_uuid_fields = {
            "observation_ids",
            "inference_revision_ids",
            "evidence_ids",
            "contradictory_evidence_ids",
            "information_gap_ids",
            "assumption_revision_ids",
        }
        for field in uuid_fields:
            raw_manifest[field] = UUID(raw_manifest[field])
        if raw_manifest["opportunity_review_id"] is not None:
            raw_manifest["opportunity_review_id"] = UUID(raw_manifest["opportunity_review_id"])
        for field in tuple_uuid_fields:
            raw_manifest[field] = tuple(UUID(item) for item in raw_manifest[field])
        raw_manifest["evidence_fingerprints"] = tuple(raw_manifest["evidence_fingerprints"])
        raw_manifest["created_at"] = datetime.fromisoformat(raw_manifest["created_at"])
        manifest = AuditInputManifest(**raw_manifest)
        sections = tuple(
            AuditSection(
                UUID(item["id"]),
                item["key"],
                item["title"],
                item["ordinal"],
                tuple(UUID(value) for value in item["claim_ids"]),
                tuple(item["structured_items"]),
            )
            for item in json.loads(row.sections_json)
        )
        claims = []
        for item in json.loads(row.claims_json):
            claims.append(
                AuditClaim(
                    UUID(item["id"]),
                    item["section_key"],
                    ClaimType(item["claim_type"]),
                    UUID(item["subject_business_id"]),
                    item["predicate"],
                    item["display_text"],
                    tuple(UUID(value) for value in item["evidence_ids"]),
                    tuple(UUID(value) for value in item["observation_ids"]),
                    tuple(UUID(value) for value in item["inference_revision_ids"]),
                    tuple(UUID(value) for value in item["assumption_revision_ids"]),
                    UUID(item["economic_run_id"]) if item["economic_run_id"] else None,
                    tuple(UUID(value) for value in item["dependency_claim_ids"]),
                    tuple(UUID(value) for value in item["contradictory_evidence_ids"]),
                )
            )
        findings = tuple(
            QcFinding(
                UUID(item["id"]),
                item["code"],
                QcSeverity(item["severity"]),
                item["message"],
                UUID(item["claim_id"]) if item["claim_id"] else None,
                item["acknowledgment_required"],
            )
            for item in json.loads(row.qc_json)
        )
        audit_findings = tuple(
            AuditFinding(
                UUID(item["id"]),
                FindingKind(item["kind"]),
                item["text"],
                UUID(item["claim_id"]) if item.get("claim_id") else None,
                tuple(UUID(value) for value in item.get("evidence_ids", ())),
                tuple(UUID(value) for value in item.get("observation_ids", ())),
                item.get("fact_class"),
                item.get("supporting_excerpt"),
            )
            for item in json.loads(row.findings_json or "[]")
        )
        return AuditRevision(
            UUID(row.id),
            UUID(row.audit_id),
            row.revision,
            UUID(row.parent_revision_id) if row.parent_revision_id else None,
            UUID(row.workspace_id),
            UUID(row.business_id),
            UUID(row.hypothesis_id),
            AuditKind(row.kind),
            manifest,
            sections,
            tuple(claims),
            findings,
            AuditRevisionState(row.state),
            AuditValidity(row.validity),
            row.revision_hash,
            row.rendered_text,
            row.created_by,
            _aware(row.created_at),
            audit_findings,
        )

    @staticmethod
    def _review_row(value: AuditReviewDecision) -> AuditReviewRow:
        return AuditReviewRow(
            id=str(value.id),
            audit_revision_id=str(value.audit_revision_id),
            revision_hash=value.revision_hash,
            manifest_hash=value.manifest_hash,
            decision=value.decision,
            actor=value.actor,
            actor_roles_json=_json(value.actor_roles),
            reason=value.reason,
            self_review=value.self_review,
            acknowledged_qc_codes_json=_json(value.acknowledged_qc_codes),
            created_at=value.created_at,
        )

    @staticmethod
    def _review(row: AuditReviewRow) -> AuditReviewDecision:
        return AuditReviewDecision(
            UUID(row.id),
            UUID(row.audit_revision_id),
            row.revision_hash,
            row.manifest_hash,
            AuditReviewDecisionType(row.decision),
            row.actor,
            tuple(json.loads(row.actor_roles_json)),
            row.reason,
            row.self_review,
            tuple(json.loads(row.acknowledged_qc_codes_json)),
            _aware(row.created_at),
        )

    def _bundle(self, session: object, row: AuditRevisionRow) -> AuditBundle:
        review = session.scalar(  # type: ignore[attr-defined]
            select(AuditReviewRow)
            .where(AuditReviewRow.audit_revision_id == row.id)
            .order_by(AuditReviewRow.created_at.desc())
            .limit(1)
        )
        invalidated = bool(
            review
            and session.scalar(  # type: ignore[attr-defined]
                select(AuditReviewInvalidationRow).where(
                    AuditReviewInvalidationRow.review_id == review.id
                )
            )
        )
        return AuditBundle(
            self._revision(row),
            self._review(review) if review else None,
            bool(review and not invalidated),
        )
