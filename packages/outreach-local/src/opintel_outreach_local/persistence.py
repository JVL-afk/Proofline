"""Append-oriented SQLAlchemy persistence for local SQLite and Phase 1 PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from opintel_outreach.domain import (
    ArtifactAudience,
    ArtifactKind,
    ArtifactSegment,
    FollowUpUsability,
    InternalEconomicContext,
    OutreachArtifact,
    OutreachBundle,
    OutreachClaimProjection,
    OutreachInputManifest,
    OutreachInvalidation,
    OutreachOperation,
    OutreachOperationStatus,
    OutreachQcFinding,
    OutreachReviewDecision,
    OutreachReviewDecisionType,
    OutreachRevision,
    OutreachRevisionState,
    OutreachRisk,
    OutreachValidationQuestion,
    OutreachValidity,
    PersonalizationAssessment,
    ProjectionDisposition,
    ProjectionMode,
    QcSeverity,
    SegmentKind,
    TargetRole,
    TargetRoleSelection,
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
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class OutreachOperationRow(Base):
    __tablename__ = "outreach_package_operations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "demo_revision_id",
            "expected_demo_revision_hash",
            "idempotency_key",
            name="uq_outreach_operation_command",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    demo_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    expected_demo_revision_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(40), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outreach_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    data_json: Mapped[str] = mapped_column(Text)


class OutreachRevisionRow(Base):
    __tablename__ = "outreach_package_revisions"
    __table_args__ = (UniqueConstraint("package_id", "revision", name="uq_outreach_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    package_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    demo_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(40))
    validity: Mapped[str] = mapped_column(String(40))
    data_json: Mapped[str] = mapped_column(Text)


class OutreachReviewRow(Base):
    __tablename__ = "outreach_review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    outreach_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_json: Mapped[str] = mapped_column(Text)


class OutreachInvalidationRow(Base):
    __tablename__ = "outreach_invalidations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    outreach_revision_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_json: Mapped[str] = mapped_column(Text)


class SqlAlchemyOutreachRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("M5 repository requires sqlite or postgresql+psycopg")
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

    def create_or_get_operation(
        self, operation: OutreachOperation
    ) -> tuple[OutreachOperation, bool]:
        try:
            with self._sessions.begin() as session:
                session.add(self._operation_row(operation))
            return operation, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(OutreachOperationRow).where(
                        OutreachOperationRow.workspace_id == str(operation.workspace_id),
                        OutreachOperationRow.demo_revision_id == str(operation.demo_revision_id),
                        OutreachOperationRow.expected_demo_revision_hash
                        == operation.expected_demo_revision_hash,
                        OutreachOperationRow.idempotency_key == operation.idempotency_key,
                    )
                )
                assert row is not None
                return self._operation(row), False

    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> OutreachOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(OutreachOperationRow).where(
                    OutreachOperationRow.id == str(operation_id),
                    OutreachOperationRow.workspace_id == str(workspace_id),
                )
            )
            return self._operation(row) if row else None

    def claim_operation(self, now: datetime, lease: timedelta) -> OutreachOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(OutreachOperationRow)
                .where(
                    ~OutreachOperationRow.idempotency_key.like("m67:%"),
                    or_(
                        OutreachOperationRow.status.in_(("pending", "retry_scheduled")),
                        (OutreachOperationRow.status == "running")
                        & (OutreachOperationRow.lease_expires_at <= now),
                    )
                )
                .order_by(OutreachOperationRow.updated_at, OutreachOperationRow.id)
                .limit(1)
            )
            if row is None:
                return None
            value = replace(
                self._operation(row),
                status=OutreachOperationStatus.RUNNING,
                attempt_count=row.attempt_count + 1,
                updated_at=now,
                lease_expires_at=now + lease,
            )
            self._update_operation_row(row, value)
            return value

    def claim_exact_operation(
        self, operation_id: UUID, expected_created_by: str, now: datetime, lease: timedelta
    ) -> OutreachOperation | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(OutreachOperationRow).where(
                    OutreachOperationRow.id == str(operation_id),
                    OutreachOperationRow.idempotency_key.like("m67:%"),
                    or_(
                        OutreachOperationRow.status.in_(("pending", "retry_scheduled")),
                        (OutreachOperationRow.status == "running")
                        & (OutreachOperationRow.lease_expires_at <= now),
                    ),
                )
            )
            if row is None:
                return None
            operation = self._operation(row)
            if operation.created_by != expected_created_by:
                raise ValueError("exact outreach operation creator mismatch")
            value = replace(
                operation,
                status=OutreachOperationStatus.RUNNING,
                attempt_count=row.attempt_count + 1,
                updated_at=now,
                lease_expires_at=now + lease,
            )
            self._update_operation_row(row, value)
            return value

    def retry_operation(self, operation: OutreachOperation, error_code: str, now: datetime) -> None:
        self._set_operation(
            replace(
                operation,
                status=OutreachOperationStatus.RETRY_SCHEDULED,
                error_code=error_code,
                updated_at=now,
                lease_expires_at=None,
            )
        )

    def fail_operation(self, operation: OutreachOperation, error_code: str, now: datetime) -> None:
        self._set_operation(
            replace(
                operation,
                status=OutreachOperationStatus.FAILED,
                error_code=error_code,
                updated_at=now,
                lease_expires_at=None,
            )
        )

    def save_revision(self, operation: OutreachOperation, revision: OutreachRevision) -> None:
        with self._sessions.begin() as session:
            session.add(
                OutreachRevisionRow(
                    id=str(revision.id),
                    package_id=str(revision.package_id),
                    workspace_id=str(revision.workspace_id),
                    demo_id=str(revision.demo_id),
                    revision=revision.revision,
                    state=str(revision.state),
                    validity=str(revision.validity),
                    data_json=_dump(revision),
                )
            )
            row = session.get(OutreachOperationRow, str(operation.id))
            assert row is not None
            complete = replace(
                operation,
                status=(
                    OutreachOperationStatus.QC_FAILED
                    if revision.state == OutreachRevisionState.QC_FAILED
                    else OutreachOperationStatus.SUCCEEDED
                ),
                outreach_revision_id=revision.id,
                updated_at=revision.created_at,
                lease_expires_at=None,
            )
            self._update_operation_row(row, complete)

    def get_revision(self, workspace_id: UUID, revision_id: UUID) -> OutreachBundle | None:
        with self._sessions() as session:
            row = session.scalar(
                select(OutreachRevisionRow).where(
                    OutreachRevisionRow.id == str(revision_id),
                    OutreachRevisionRow.workspace_id == str(workspace_id),
                )
            )
            return self._bundle(session, row) if row else None

    def list_revisions(self, workspace_id: UUID, package_id: UUID) -> tuple[OutreachBundle, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(OutreachRevisionRow)
                .where(
                    OutreachRevisionRow.workspace_id == str(workspace_id),
                    OutreachRevisionRow.package_id == str(package_id),
                )
                .order_by(OutreachRevisionRow.revision)
            ).all()
            return tuple(self._bundle(session, row) for row in rows)

    def save_review(
        self, bundle: OutreachBundle, decision: OutreachReviewDecision
    ) -> OutreachBundle:
        states = {
            OutreachReviewDecisionType.APPROVE_CONTENT: OutreachRevisionState.CONTENT_APPROVED,
            OutreachReviewDecisionType.REJECT: OutreachRevisionState.REJECTED,
            OutreachReviewDecisionType.REQUEST_REVISION: OutreachRevisionState.REVISION_REQUESTED,
        }
        updated = replace(bundle.revision, state=states[decision.decision])
        with self._sessions.begin() as session:
            session.add(
                OutreachReviewRow(
                    id=str(decision.id),
                    outreach_revision_id=str(decision.outreach_revision_id),
                    created_at=decision.created_at,
                    data_json=_dump(decision),
                )
            )
            row = session.get(OutreachRevisionRow, str(updated.id))
            assert row is not None
            row.state = str(updated.state)
            row.data_json = _dump(updated)
        return OutreachBundle(
            updated,
            decision,
            decision.decision == OutreachReviewDecisionType.APPROVE_CONTENT,
            bundle.invalidation,
        )

    def save_invalidation(
        self, bundle: OutreachBundle, invalidation: OutreachInvalidation
    ) -> OutreachBundle:
        updated = replace(bundle.revision, validity=OutreachValidity.INVALIDATED)
        with self._sessions.begin() as session:
            session.add(
                OutreachInvalidationRow(
                    id=str(invalidation.id),
                    outreach_revision_id=str(invalidation.outreach_revision_id),
                    created_at=invalidation.created_at,
                    data_json=_dump(invalidation),
                )
            )
            row = session.get(OutreachRevisionRow, str(updated.id))
            assert row is not None
            row.validity = str(updated.validity)
            row.data_json = _dump(updated)
        return OutreachBundle(updated, bundle.latest_review, False, invalidation)

    def _set_operation(self, operation: OutreachOperation) -> None:
        with self._sessions.begin() as session:
            row = session.get(OutreachOperationRow, str(operation.id))
            assert row is not None
            self._update_operation_row(row, operation)

    @staticmethod
    def _operation_row(value: OutreachOperation) -> OutreachOperationRow:
        return OutreachOperationRow(
            id=str(value.id),
            workspace_id=str(value.workspace_id),
            demo_revision_id=str(value.demo_revision_id),
            expected_demo_revision_hash=value.expected_demo_revision_hash,
            idempotency_key=value.idempotency_key,
            status=str(value.status),
            attempt_count=value.attempt_count,
            updated_at=value.updated_at,
            lease_expires_at=value.lease_expires_at,
            outreach_revision_id=str(value.outreach_revision_id)
            if value.outreach_revision_id
            else None,
            error_code=value.error_code,
            data_json=_dump(value),
        )

    @staticmethod
    def _update_operation_row(row: OutreachOperationRow, value: OutreachOperation) -> None:
        row.status = str(value.status)
        row.attempt_count = value.attempt_count
        row.updated_at = value.updated_at
        row.lease_expires_at = value.lease_expires_at
        row.outreach_revision_id = (
            str(value.outreach_revision_id) if value.outreach_revision_id else None
        )
        row.error_code = value.error_code
        row.data_json = _dump(value)

    @staticmethod
    def _operation(row: OutreachOperationRow) -> OutreachOperation:
        item = json.loads(row.data_json)
        return OutreachOperation(
            UUID(item["id"]),
            UUID(item["workspace_id"]),
            UUID(item["business_id"]),
            UUID(item["demo_revision_id"]),
            item["expected_demo_revision_hash"],
            UUID(item["package_id"]),
            _uuid(item["parent_revision_id"]),
            OutreachOperationStatus(item["status"]),
            item["idempotency_key"],
            UUID(item["trace_id"]),
            item["attempt_count"],
            item["max_attempts"],
            item["created_by"],
            _dt(item["created_at"]),
            _dt(item["updated_at"]),
            _optional_dt(item["lease_expires_at"]),
            _uuid(item["outreach_revision_id"]),
            item["error_code"],
        )

    @staticmethod
    def _bundle(session: Any, row: OutreachRevisionRow) -> OutreachBundle:
        revision = _revision(json.loads(row.data_json))
        review_row = session.scalar(
            select(OutreachReviewRow)
            .where(OutreachReviewRow.outreach_revision_id == row.id)
            .order_by(OutreachReviewRow.created_at.desc())
            .limit(1)
        )
        invalidation_row = session.scalar(
            select(OutreachInvalidationRow).where(
                OutreachInvalidationRow.outreach_revision_id == row.id
            )
        )
        review = _review(json.loads(review_row.data_json)) if review_row else None
        invalidation = (
            _invalidation(json.loads(invalidation_row.data_json)) if invalidation_row else None
        )
        valid = (
            review is not None
            and review.decision == OutreachReviewDecisionType.APPROVE_CONTENT
            and review.revision_hash == revision.revision_hash
            and review.manifest_hash == revision.manifest.checksum
            and review.content_hash == revision.content_hash
            and invalidation is None
            and revision.validity == OutreachValidity.CURRENT
        )
        return OutreachBundle(revision, review, valid, invalidation)


def _dump(value: Any) -> str:
    return json.dumps(asdict(value), sort_keys=True, separators=(",", ":"), default=str)


def _uuid(value: str | None) -> UUID | None:
    return UUID(value) if value else None


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _optional_dt(value: str | None) -> datetime | None:
    return _dt(value) if value else None


def _manifest(item: dict[str, Any]) -> OutreachInputManifest:
    return OutreachInputManifest(
        UUID(item["id"]),
        UUID(item["workspace_id"]),
        UUID(item["business_id"]),
        item["business_profile_hash"],
        UUID(item["opportunity_revision_id"]),
        item["opportunity_manifest_hash"],
        UUID(item["opportunity_review_id"]),
        item["opportunity_review_manifest_hash"],
        UUID(item["audit_revision_id"]),
        item["audit_revision_hash"],
        item["audit_manifest_hash"],
        UUID(item["audit_review_id"]),
        UUID(item["demo_revision_id"]),
        item["demo_revision_hash"],
        item["demo_manifest_hash"],
        item["demo_specification_hash"],
        UUID(item["demo_review_id"]),
        tuple(UUID(value) for value in item["evidence_ids"]),
        tuple(item["evidence_fingerprints"]),
        tuple(UUID(value) for value in item["information_gap_ids"]),
        tuple(UUID(value) for value in item["assumption_revision_ids"]),
        UUID(item["economic_run_id"]),
        item["economic_formula_version"],
        UUID(item["score_snapshot_id"]),
        item["score_config_version"],
        item["outreach_schema_version"],
        item["template_version"],
        item["projection_policy_version"],
        item["target_role_policy_version"],
        item["cta_policy_version"],
        item["qc_policy_version"],
        item["checksum"],
        _dt(item["created_at"]),
    )


def _projection(item: dict[str, Any]) -> OutreachClaimProjection:
    return OutreachClaimProjection(
        UUID(item["id"]),
        UUID(item["source_claim_id"]),
        item["source_claim_type"],
        ProjectionMode(item["mode"]),
        ProjectionDisposition(item["disposition"]),
        item["rendered_text"],
        tuple(UUID(value) for value in item["evidence_ids"]),
        tuple(UUID(value) for value in item["observation_ids"]),
        tuple(UUID(value) for value in item["inference_revision_ids"]),
        tuple(UUID(value) for value in item["assumption_revision_ids"]),
        _uuid(item["economic_run_id"]),
        tuple(UUID(value) for value in item["dependency_claim_ids"]),
        tuple(UUID(value) for value in item["contradictory_evidence_ids"]),
        tuple(item["required_qualifiers"]),
    )


def _artifact(item: dict[str, Any]) -> OutreachArtifact:
    return OutreachArtifact(
        UUID(item["id"]),
        ArtifactKind(item["kind"]),
        ArtifactAudience(item["audience"]),
        item["title"],
        tuple(
            ArtifactSegment(
                UUID(value["id"]),
                SegmentKind(value["kind"]),
                value["text"],
                _uuid(value["projection_id"]),
            )
            for value in item["segments"]
        ),
        item["rendered_text"],
        item["content_hash"],
        FollowUpUsability(item["follow_up_usability"]) if item["follow_up_usability"] else None,
        item["external_precondition"],
    )


def _revision(item: dict[str, Any]) -> OutreachRevision:
    role = item["target_role"]
    economic = item["economic_context"]
    return OutreachRevision(
        UUID(item["id"]),
        UUID(item["package_id"]),
        item["revision"],
        _uuid(item["parent_revision_id"]),
        UUID(item["workspace_id"]),
        UUID(item["business_id"]),
        UUID(item["opportunity_id"]),
        UUID(item["audit_id"]),
        UUID(item["demo_id"]),
        _manifest(item["manifest"]),
        TargetRoleSelection(
            TargetRole(role["role"]),
            role["priority"],
            role["rationale"],
            role["person_identified"],
            role["person_marker"],
        ),
        tuple(_projection(value) for value in item["projections"]),
        tuple(_artifact(value) for value in item["artifacts"]),
        tuple(
            OutreachValidationQuestion(
                UUID(value["gap_id"]),
                value["priority"],
                value["affected_component"],
                value["economic_effect"],
                value["wording"],
                value["safe_for_first_contact"],
            )
            for value in item["validation_questions"]
        ),
        tuple(
            OutreachRisk(
                UUID(value["id"]),
                value["kind"],
                value["description"],
                tuple(UUID(source_id) for source_id in value["source_ids"]),
                value["disposition"],
            )
            for value in item["risks"]
        ),
        InternalEconomicContext(
            economic["status"],
            economic["formula_version"],
            economic["result_label"],
            tuple((UUID(value[0]), value[1], value[2]) for value in economic["assumption_states"]),
            economic["monthly_value"],
            economic["annualized_value"],
            economic["currency"],
            economic["external_use_permitted"],
        ),
        tuple(
            OutreachQcFinding(
                UUID(value["id"]),
                value["code"],
                QcSeverity(value["severity"]),
                value["message"],
                _uuid(value["projection_id"]),
                _uuid(value["artifact_id"]),
            )
            for value in item["qc_findings"]
        ),
        OutreachRevisionState(item["state"]),
        OutreachValidity(item["validity"]),
        item["content_hash"],
        item["revision_hash"],
        item["created_by"],
        _dt(item["created_at"]),
        _personalization(item.get("personalization")),
        tuple(item.get("unresolved_slot_kinds", ())),
    )


def _personalization(item: dict[str, Any] | None) -> PersonalizationAssessment | None:
    if not item:
        return None
    return PersonalizationAssessment(
        item["company_specific_segment_count"],
        item["distinct_fact_classes"],
        tuple(UUID(value) for value in item["rendered_evidence_ids"]),
        item["passes_gate"],
    )


def _review(item: dict[str, Any]) -> OutreachReviewDecision:
    return OutreachReviewDecision(
        UUID(item["id"]),
        UUID(item["outreach_revision_id"]),
        item["revision_hash"],
        item["manifest_hash"],
        item["content_hash"],
        OutreachReviewDecisionType(item["decision"]),
        item["actor"],
        tuple(item["actor_roles"]),
        item["reason"],
        item["self_review"],
        _dt(item["created_at"]),
    )


def _invalidation(item: dict[str, Any]) -> OutreachInvalidation:
    return OutreachInvalidation(
        UUID(item["id"]),
        UUID(item["outreach_revision_id"]),
        item["reason"],
        item["actor"],
        _dt(item["created_at"]),
    )
