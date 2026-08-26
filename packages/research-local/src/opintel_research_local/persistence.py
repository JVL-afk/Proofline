"""SQLite-backed local M1 research repository."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import overload
from uuid import UUID

from opintel_research.domain import (
    Business,
    CaptureDisposition,
    CaptureQuarantine,
    CrawlPolicy,
    DurablePageBundle,
    ExtractedMaterial,
    FetchAttempt,
    MinimizedPageSnapshot,
    PageStatus,
    ResearchEvidence,
    ResearchPage,
    ResearchRun,
    ResearchRunStatus,
    RobotsPolicyEvidence,
    SampledSlotActivation,
    SampledSlotIdentity,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _id(value: UUID) -> str:
    return str(value)


@overload
def _aware(value: datetime) -> datetime: ...


@overload
def _aware(value: None) -> None: ...


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Base(DeclarativeBase):
    pass


class SchemaRevisionRow(Base):
    __tablename__ = "research_schema_revisions"
    revision: Mapped[str] = mapped_column(String(80), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BusinessRow(Base):
    __tablename__ = "research_businesses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200))
    canonical_url: Mapped[str] = mapped_column(String(2048))
    permitted_host: Mapped[str] = mapped_column(String(253))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunRow(Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "business_id", "idempotency_key", name="uq_research_run_command"
        ),
        Index("ix_research_run_claim", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("research_businesses.id"), index=True)
    operation_id: Mapped[str] = mapped_column(String(36), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    start_url: Mapped[str] = mapped_column(String(2048))
    permitted_host: Mapped[str] = mapped_column(String(253))
    policy_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pages_attempted: Mapped[int] = mapped_column(Integer, default=0)
    pages_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    bytes_stored: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(240), nullable=True)


class FetchAttemptRow(Base):
    __tablename__ = "research_fetch_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    normalized_url: Mapped[str] = mapped_column(String(2048))
    attempt_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class RobotsPolicyEvidenceRow(Base):
    __tablename__ = "research_robots_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    host: Mapped[str] = mapped_column(String(253))
    requested_path: Mapped[str] = mapped_column(String(2048))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    body_length: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str] = mapped_column(String(80))
    allowed: Mapped[bool] = mapped_column(Boolean)


class SnapshotRow(Base):
    __tablename__ = "page_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("research_businesses.id"), index=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    operation_id: Mapped[str] = mapped_column(String(36), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048), index=True)
    final_url: Mapped[str] = mapped_column(String(2048))
    snapshot_version: Mapped[str] = mapped_column(String(96))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_content_sha256: Mapped[str] = mapped_column(String(64))
    content_sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(100))
    charset: Mapped[str] = mapped_column(String(40))
    status_code: Mapped[int] = mapped_column(Integer)
    content_length: Mapped[int] = mapped_column(Integer)
    minimized_text: Mapped[str] = mapped_column(Text)
    minimizer_version: Mapped[str] = mapped_column(String(80))
    minimization_event_sha256: Mapped[str] = mapped_column(String(64))
    removed_email_count: Mapped[int] = mapped_column(Integer)
    removed_phone_count: Mapped[int] = mapped_column(Integer)
    removed_structured_contact_blocks: Mapped[int] = mapped_column(Integer)
    required_evidence_markers_json: Mapped[str] = mapped_column(Text)
    disposition: Mapped[str] = mapped_column(String(40))


class CaptureQuarantineRow(Base):
    __tablename__ = "research_capture_quarantines"
    page_id: Mapped[str] = mapped_column(ForeignKey("research_pages.id"), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    research_run_id: Mapped[str] = mapped_column(String(36), index=True)
    source_uri: Mapped[str] = mapped_column(String(2048))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_content_sha256: Mapped[str] = mapped_column(String(64))
    required_evidence_markers_json: Mapped[str] = mapped_column(Text)
    quarantine_reasons_json: Mapped[str] = mapped_column(Text)
    minimizer_version: Mapped[str] = mapped_column(String(80))
    minimization_event_sha256: Mapped[str] = mapped_column(String(64))
    disposition: Mapped[str] = mapped_column(String(40))


class MaterialRow(Base):
    __tablename__ = "extracted_material"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("page_snapshots.id"), unique=True, index=True
    )
    extractor_name: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    material_json: Mapped[str] = mapped_column(Text)
    visible_text: Mapped[str] = mapped_column(Text)
    prompt_injection_suspected: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PageRow(Base):
    __tablename__ = "research_pages"
    __table_args__ = (
        UniqueConstraint("research_run_id", "normalized_url", name="uq_run_page_url"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("research_businesses.id"), index=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    requested_url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str] = mapped_column(String(2048))
    depth: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("page_snapshots.id"), nullable=True)
    material_id: Mapped[str | None] = mapped_column(
        ForeignKey("extracted_material.id"), nullable=True
    )
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class EvidenceRow(Base):
    __tablename__ = "research_evidence"
    __table_args__ = (
        UniqueConstraint(
            "research_run_id", "snapshot_id", "locator", name="uq_research_evidence_locator"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("research_businesses.id"), index=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    operation_id: Mapped[str] = mapped_column(String(36), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("research_pages.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("page_snapshots.id"), index=True)
    snapshot_version: Mapped[str] = mapped_column(String(96))
    source_uri: Mapped[str] = mapped_column(String(2048))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64))
    locator: Mapped[str] = mapped_column(String(240))
    extracted_fragment: Mapped[str] = mapped_column(Text)
    extractor_name: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyResearchRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
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
                connection.execute(text("SELECT pg_advisory_xact_lock(670001)"))
            inspector = inspect(connection)
            if "page_snapshots" in inspector.get_table_names():
                columns = {item["name"] for item in inspector.get_columns("page_snapshots")}
                if "content" in columns or "minimized_text" not in columns:
                    raise RuntimeError(
                        "legacy raw snapshot schema is prohibited; migrate to minimized schema"
                    )
            Base.metadata.create_all(connection)
            existing = connection.execute(
                select(SchemaRevisionRow.revision).where(
                    SchemaRevisionRow.revision == "research-schema@2-minimized"
                )
            ).scalar_one_or_none()
            if existing is None:
                connection.execute(
                    SchemaRevisionRow.__table__.insert().values(  # type: ignore[attr-defined]
                        revision="research-schema@2-minimized", applied_at=datetime.now(UTC)
                    )
                )

    def create_business(self, business: Business) -> Business:
        data = asdict(business)
        data["id"] = _id(business.id)
        data["workspace_id"] = _id(business.workspace_id)
        with self._sessions.begin() as session:
            session.add(BusinessRow(**data))
        return business

    def get_business(self, workspace_id: UUID, business_id: UUID) -> Business | None:
        with self._sessions() as session:
            row = session.scalar(
                select(BusinessRow).where(
                    BusinessRow.id == _id(business_id),
                    BusinessRow.workspace_id == _id(workspace_id),
                )
            )
            return self._business(row) if row else None

    def create_or_get_run(self, run: ResearchRun, idempotency_key: str) -> tuple[ResearchRun, bool]:
        try:
            with self._sessions.begin() as session:
                session.add(self._run_row(run, idempotency_key))
            return run, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(RunRow).where(
                        RunRow.workspace_id == _id(run.workspace_id),
                        RunRow.business_id == _id(run.business_id),
                        RunRow.idempotency_key == idempotency_key,
                    )
                )
                if row is None:
                    raise
                return self._run(row), False

    def activate_sampled_run(
        self, business: Business, run: ResearchRun, idempotency_key: str
    ) -> tuple[ResearchRun, bool]:
        """Atomically persist the registry-derived business and its one immutable run."""

        if run.sampled_slot_identity is None or run.sampled_slot_activation is None:
            raise ValueError("sampled activation and identity are required")
        if run.id != run.sampled_slot_identity.work_item_id:
            raise ValueError("sampled work-item ID must equal the research-run ID")
        try:
            with self._sessions.begin() as session:
                existing_business = session.get(BusinessRow, _id(business.id))
                if existing_business is None:
                    data = asdict(business)
                    data["id"] = _id(business.id)
                    data["workspace_id"] = _id(business.workspace_id)
                    session.add(BusinessRow(**data))
                elif self._business(existing_business) != business:
                    raise ValueError("existing sampled business differs from frozen identity")
                session.add(self._run_row(run, idempotency_key))
            return run, True
        except IntegrityError:
            with self._sessions() as session:
                row = session.scalar(
                    select(RunRow).where(
                        RunRow.workspace_id == _id(run.workspace_id),
                        RunRow.business_id == _id(run.business_id),
                        RunRow.idempotency_key == idempotency_key,
                    )
                )
                if row is None:
                    raise
                existing = self._run(row)
                existing_activation = existing.sampled_slot_activation
                requested_activation = run.sampled_slot_activation
                if (
                    existing.sampled_slot_identity != run.sampled_slot_identity
                    or existing.business_id != run.business_id
                    or existing.start_url != run.start_url
                    or existing.permitted_host != run.permitted_host
                    or existing.policy != run.policy
                    or existing_activation is None
                    or requested_activation is None
                    or existing_activation.authorization_release_id
                    != requested_activation.authorization_release_id
                    or existing_activation.authorization_configuration_hash
                    != requested_activation.authorization_configuration_hash
                    or existing_activation.a09_decision_sha256
                    != requested_activation.a09_decision_sha256
                    or existing_activation.research_runtime_revision
                    != requested_activation.research_runtime_revision
                    or existing_activation.execution_ceilings_sha256
                    != requested_activation.execution_ceilings_sha256
                ):
                    raise ValueError("duplicate sampled activation differs from immutable run")
                return existing, False

    def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None:
        with self._sessions() as session:
            row = session.scalar(
                select(RunRow).where(
                    RunRow.id == _id(run_id), RunRow.workspace_id == _id(workspace_id)
                )
            )
            return self._run(row) if row else None

    def claim_run(self, now: datetime, lease: timedelta) -> ResearchRun | None:
        with self._sessions.begin() as session:
            statement = (
                select(RunRow)
                .where(RunRow.status == ResearchRunStatus.PENDING)
                .order_by(RunRow.created_at)
                .limit(1)
            )
            if self.engine.dialect.name == "postgresql":
                statement = statement.with_for_update(skip_locked=True)
            row = session.scalar(statement)
            if row is None:
                return None
            result = session.execute(
                update(RunRow)
                .where(RunRow.id == row.id, RunRow.status == ResearchRunStatus.PENDING)
                .values(
                    status=ResearchRunStatus.RUNNING,
                    started_at=row.started_at or now,
                    updated_at=now,
                    lease_expires_at=now + lease,
                )
                .returning(RunRow.id)
            )
            claimed = result.scalar_one_or_none()
            if claimed is None:
                return None
            session.flush()
            claimed_row = session.get(RunRow, claimed)
            return self._run(claimed_row) if claimed_row is not None else None

    def recover_stale_runs(self, now: datetime) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                update(RunRow)
                .where(RunRow.status == ResearchRunStatus.RUNNING, RunRow.lease_expires_at <= now)
                .values(
                    status=ResearchRunStatus.PENDING,
                    updated_at=now,
                    lease_expires_at=None,
                    last_error_code="worker_lease_expired",
                    last_error_message="research worker lease expired; run recovered",
                )
            )
            return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def record_attempt(self, attempt: FetchAttempt) -> None:
        data = asdict(attempt)
        data["id"] = _id(attempt.id)
        data["research_run_id"] = _id(attempt.research_run_id)
        with self._sessions.begin() as session:
            session.add(FetchAttemptRow(**data))

    def record_robots_evidence(self, evidence: RobotsPolicyEvidence) -> None:
        data = asdict(evidence)
        data["id"] = _id(evidence.id)
        data["research_run_id"] = _id(evidence.research_run_id)
        with self._sessions.begin() as session:
            session.add(RobotsPolicyEvidenceRow(**data))

    def list_attempts(self, workspace_id: UUID, run_id: UUID) -> list[FetchAttempt]:
        with self._sessions() as session:
            authorized = session.scalar(
                select(RunRow.id).where(
                    RunRow.id == _id(run_id), RunRow.workspace_id == _id(workspace_id)
                )
            )
            if authorized is None:
                return []
            rows = session.scalars(
                select(FetchAttemptRow)
                .where(FetchAttemptRow.research_run_id == _id(run_id))
                .order_by(
                    FetchAttemptRow.started_at,
                    FetchAttemptRow.normalized_url,
                    FetchAttemptRow.attempt_number,
                )
            ).all()
            return [self._attempt(row) for row in rows]

    def save_page_bundle(
        self,
        page: ResearchPage,
        bundle: DurablePageBundle,
    ) -> None:
        if not isinstance(bundle, DurablePageBundle):
            raise TypeError("persistence accepts only a durable minimized page bundle")
        snapshot = bundle.snapshot
        material = bundle.material
        evidence = bundle.evidence
        with self._sessions.begin() as session:
            existing_page = session.scalar(
                select(PageRow.id).where(
                    PageRow.research_run_id == _id(page.research_run_id),
                    PageRow.normalized_url == page.normalized_url,
                )
            )
            if existing_page is not None:
                return
            if session.get(SnapshotRow, _id(snapshot.id)) is None:
                session.add(self._snapshot_row(snapshot))
            if session.get(MaterialRow, _id(material.id)) is None:
                session.add(self._material_row(material))
            session.add(self._page_row(page))
            session.flush()
            session.add_all(self._evidence_row(item) for item in evidence)

    def save_quarantined_page(
        self, page: ResearchPage, quarantine: CaptureQuarantine, attempt: FetchAttempt
    ) -> None:
        if not isinstance(quarantine, CaptureQuarantine):
            raise TypeError("quarantine persistence requires a content-free quarantine record")
        with self._sessions.begin() as session:
            existing_page = session.scalar(
                select(PageRow.id).where(
                    PageRow.research_run_id == _id(page.research_run_id),
                    PageRow.normalized_url == page.normalized_url,
                )
            )
            if existing_page is not None:
                return
            session.add(self._page_row(page))
            session.flush()
            session.add(
                CaptureQuarantineRow(
                    page_id=_id(page.id),
                    workspace_id=_id(page.workspace_id),
                    business_id=_id(page.business_id),
                    research_run_id=_id(page.research_run_id),
                    source_uri=quarantine.source_uri,
                    captured_at=quarantine.captured_at,
                    raw_content_sha256=quarantine.raw_content_sha256,
                    required_evidence_markers_json=_json(quarantine.required_evidence_markers),
                    quarantine_reasons_json=_json(quarantine.quarantine_reasons),
                    minimizer_version=quarantine.minimizer_version,
                    minimization_event_sha256=quarantine.minimization_event_sha256,
                    disposition=quarantine.disposition.value,
                )
            )
            data = asdict(attempt)
            data["id"] = _id(attempt.id)
            data["research_run_id"] = _id(attempt.research_run_id)
            session.add(FetchAttemptRow(**data))

    def save_failed_page(self, page: ResearchPage, attempt: FetchAttempt) -> None:
        data = asdict(attempt)
        data["id"] = _id(attempt.id)
        data["research_run_id"] = _id(attempt.research_run_id)
        with self._sessions.begin() as session:
            existing_page = session.scalar(
                select(PageRow.id).where(
                    PageRow.research_run_id == _id(page.research_run_id),
                    PageRow.normalized_url == page.normalized_url,
                )
            )
            if existing_page is not None:
                return
            session.add(self._page_row(page))
            session.add(FetchAttemptRow(**data))

    def find_cached_snapshot(
        self, workspace_id: UUID, business_id: UUID, normalized_url: str, not_before: datetime
    ) -> tuple[MinimizedPageSnapshot, ExtractedMaterial] | None:
        with self._sessions() as session:
            row = session.scalar(
                select(SnapshotRow)
                .where(
                    SnapshotRow.workspace_id == _id(workspace_id),
                    SnapshotRow.business_id == _id(business_id),
                    SnapshotRow.canonical_url == normalized_url,
                    SnapshotRow.captured_at >= not_before,
                )
                .order_by(SnapshotRow.captured_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            material = session.scalar(select(MaterialRow).where(MaterialRow.snapshot_id == row.id))
            return (self._snapshot(row), self._material(material)) if material else None

    def complete_run(
        self,
        run_id: UUID,
        status: str,
        pages_attempted: int,
        pages_succeeded: int,
        bytes_stored: int,
        now: datetime,
        error_code: str | None = None,
        safe_message: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(RunRow)
                .where(RunRow.id == _id(run_id))
                .values(
                    status=status,
                    pages_attempted=pages_attempted,
                    pages_succeeded=pages_succeeded,
                    bytes_stored=bytes_stored,
                    updated_at=now,
                    completed_at=now,
                    lease_expires_at=None,
                    last_error_code=error_code,
                    last_error_message=safe_message,
                )
            )

    def list_pages(self, workspace_id: UUID, run_id: UUID) -> list[ResearchPage]:
        with self._sessions() as session:
            rows = session.scalars(
                select(PageRow)
                .where(
                    PageRow.workspace_id == _id(workspace_id),
                    PageRow.research_run_id == _id(run_id),
                )
                .order_by(PageRow.depth, PageRow.normalized_url)
            ).all()
            return [self._page(row) for row in rows]

    def get_page(self, workspace_id: UUID, page_id: UUID) -> ResearchPage | None:
        with self._sessions() as session:
            row = session.scalar(
                select(PageRow).where(
                    PageRow.id == _id(page_id), PageRow.workspace_id == _id(workspace_id)
                )
            )
            return self._page(row) if row else None

    def get_snapshot(self, workspace_id: UUID, snapshot_id: UUID) -> MinimizedPageSnapshot | None:
        with self._sessions() as session:
            row = session.scalar(
                select(SnapshotRow).where(
                    SnapshotRow.id == _id(snapshot_id),
                    SnapshotRow.workspace_id == _id(workspace_id),
                )
            )
            return self._snapshot(row) if row else None

    def get_material(self, workspace_id: UUID, material_id: UUID) -> ExtractedMaterial | None:
        with self._sessions() as session:
            row = session.scalar(
                select(MaterialRow)
                .join(SnapshotRow, MaterialRow.snapshot_id == SnapshotRow.id)
                .where(
                    MaterialRow.id == _id(material_id),
                    SnapshotRow.workspace_id == _id(workspace_id),
                )
            )
            return self._material(row) if row else None

    def list_evidence(self, workspace_id: UUID, run_id: UUID) -> list[ResearchEvidence]:
        with self._sessions() as session:
            rows = session.scalars(
                select(EvidenceRow)
                .where(
                    EvidenceRow.workspace_id == _id(workspace_id),
                    EvidenceRow.research_run_id == _id(run_id),
                )
                .order_by(EvidenceRow.created_at, EvidenceRow.locator)
            ).all()
            return [self._evidence(row) for row in rows]

    def get_evidence(self, workspace_id: UUID, evidence_id: UUID) -> ResearchEvidence | None:
        with self._sessions() as session:
            row = session.scalar(
                select(EvidenceRow).where(
                    EvidenceRow.id == _id(evidence_id),
                    EvidenceRow.workspace_id == _id(workspace_id),
                )
            )
            return self._evidence(row) if row else None

    @staticmethod
    def _business(row: BusinessRow) -> Business:
        return Business(
            UUID(row.id),
            UUID(row.workspace_id),
            row.name,
            row.canonical_url,
            row.permitted_host,
            row.created_by,
            _aware(row.created_at),
        )

    @staticmethod
    def _attempt(row: FetchAttemptRow) -> FetchAttempt:
        return FetchAttempt(
            id=UUID(row.id),
            research_run_id=UUID(row.research_run_id),
            normalized_url=row.normalized_url,
            attempt_number=row.attempt_number,
            started_at=_aware(row.started_at),
            completed_at=_aware(row.completed_at),
            outcome=row.outcome,
            error_code=row.error_code,
        )

    @staticmethod
    def _run_row(value: ResearchRun, key: str) -> RunRow:
        policy_payload: dict[str, object] = {
            "schema_version": "research-run-policy@3-authorized-sampled-slot",
            "crawl_policy": asdict(value.policy),
            "sampled_slot_identity": (
                {
                    **asdict(value.sampled_slot_identity),
                    "work_item_id": str(value.sampled_slot_identity.work_item_id),
                }
                if value.sampled_slot_identity is not None
                else None
            ),
            "sampled_slot_activation": (
                {
                    **asdict(value.sampled_slot_activation),
                    "activation_id": str(value.sampled_slot_activation.activation_id),
                    "authorization_release_id": str(
                        value.sampled_slot_activation.authorization_release_id
                    ),
                    "activated_at": value.sampled_slot_activation.activated_at.isoformat(),
                    "sampled_slot_identity": {
                        **asdict(value.sampled_slot_activation.sampled_slot_identity),
                        "work_item_id": str(
                            value.sampled_slot_activation.sampled_slot_identity.work_item_id
                        ),
                    },
                }
                if value.sampled_slot_activation is not None
                else None
            ),
        }
        return RunRow(
            id=_id(value.id),
            workspace_id=_id(value.workspace_id),
            business_id=_id(value.business_id),
            operation_id=_id(value.operation_id),
            trace_id=_id(value.trace_id),
            start_url=value.start_url,
            permitted_host=value.permitted_host,
            policy_json=_json(policy_payload),
            status=value.status,
            idempotency_key=key,
            created_by=value.created_by,
            created_at=value.created_at,
            updated_at=value.updated_at,
            started_at=value.started_at,
            completed_at=value.completed_at,
            lease_expires_at=value.lease_expires_at,
            pages_attempted=value.pages_attempted,
            pages_succeeded=value.pages_succeeded,
            bytes_stored=value.bytes_stored,
            last_error_code=value.last_error_code,
            last_error_message=value.last_error_message,
        )

    @staticmethod
    def _run(row: RunRow) -> ResearchRun:
        policy_payload = json.loads(row.policy_json)
        schema_version = policy_payload.get("schema_version")
        if schema_version in {
            "research-run-policy@2-sampled-slot",
            "research-run-policy@3-authorized-sampled-slot",
        }:
            identity_payload = policy_payload.get("sampled_slot_identity")
            identity = (
                SampledSlotIdentity(
                    **{
                        **identity_payload,
                        "work_item_id": UUID(identity_payload["work_item_id"]),
                    }
                )
                if identity_payload is not None
                else None
            )
            activation_payload = policy_payload.get("sampled_slot_activation")
            activation = (
                SampledSlotActivation(
                    **{
                        **activation_payload,
                        "activation_id": UUID(activation_payload["activation_id"]),
                        "authorization_release_id": UUID(
                            activation_payload["authorization_release_id"]
                        ),
                        "activated_at": datetime.fromisoformat(
                            activation_payload["activated_at"]
                        ),
                        "sampled_slot_identity": SampledSlotIdentity(
                            **{
                                **activation_payload["sampled_slot_identity"],
                                "work_item_id": UUID(
                                    activation_payload["sampled_slot_identity"]["work_item_id"]
                                ),
                            }
                        ),
                    }
                )
                if activation_payload is not None
                else None
            )
            crawl_policy = policy_payload["crawl_policy"]
        else:
            # Historical V2 work items remain readable but fail closed at authorization.
            identity = None
            activation = None
            crawl_policy = policy_payload
        return ResearchRun(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            business_id=UUID(row.business_id),
            operation_id=UUID(row.operation_id),
            trace_id=UUID(row.trace_id),
            start_url=row.start_url,
            permitted_host=row.permitted_host,
            policy=CrawlPolicy(**crawl_policy),
            status=ResearchRunStatus(row.status),
            created_by=row.created_by,
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
            started_at=_aware(row.started_at),
            completed_at=_aware(row.completed_at),
            lease_expires_at=_aware(row.lease_expires_at),
            pages_attempted=row.pages_attempted,
            pages_succeeded=row.pages_succeeded,
            bytes_stored=row.bytes_stored,
            last_error_code=row.last_error_code,
            last_error_message=row.last_error_message,
            sampled_slot_identity=identity,
            sampled_slot_activation=activation,
        )

    @staticmethod
    def _snapshot_row(value: MinimizedPageSnapshot) -> SnapshotRow:
        if not isinstance(value, MinimizedPageSnapshot):
            raise TypeError("raw PageSnapshot cannot be persisted")
        return SnapshotRow(
            id=_id(value.id),
            workspace_id=_id(value.workspace_id),
            business_id=_id(value.business_id),
            research_run_id=_id(value.research_run_id),
            operation_id=_id(value.operation_id),
            trace_id=_id(value.trace_id),
            source_url=value.source_url,
            canonical_url=value.canonical_url,
            final_url=value.final_url,
            snapshot_version=value.snapshot_version,
            captured_at=value.captured_at,
            source_content_sha256=value.source_content_sha256,
            content_sha256=value.content_sha256,
            content_type=value.content_type,
            charset=value.charset,
            status_code=value.status_code,
            content_length=value.content_length,
            minimized_text=value.minimized_text,
            minimizer_version=value.minimizer_version,
            minimization_event_sha256=value.minimization_event_sha256,
            removed_email_count=value.removed_email_count,
            removed_phone_count=value.removed_phone_count,
            removed_structured_contact_blocks=value.removed_structured_contact_blocks,
            required_evidence_markers_json=_json(value.required_evidence_markers),
            disposition=value.disposition.value,
        )

    @staticmethod
    def _snapshot(row: SnapshotRow) -> MinimizedPageSnapshot:
        return MinimizedPageSnapshot(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            business_id=UUID(row.business_id),
            research_run_id=UUID(row.research_run_id),
            operation_id=UUID(row.operation_id),
            trace_id=UUID(row.trace_id),
            source_url=row.source_url,
            canonical_url=row.canonical_url,
            final_url=row.final_url,
            snapshot_version=row.snapshot_version,
            captured_at=_aware(row.captured_at),
            source_content_sha256=row.source_content_sha256,
            content_sha256=row.content_sha256,
            content_type=row.content_type,
            charset=row.charset,
            status_code=row.status_code,
            content_length=row.content_length,
            minimized_text=row.minimized_text,
            minimizer_version=row.minimizer_version,
            minimization_event_sha256=row.minimization_event_sha256,
            removed_email_count=row.removed_email_count,
            removed_phone_count=row.removed_phone_count,
            removed_structured_contact_blocks=row.removed_structured_contact_blocks,
            required_evidence_markers=tuple(json.loads(row.required_evidence_markers_json)),
            disposition=CaptureDisposition(row.disposition),
        )

    @staticmethod
    def _material_row(value: ExtractedMaterial) -> MaterialRow:
        payload = {
            name: getattr(value, name)
            for name in (
                "metadata",
                "headings",
                "links",
                "forms",
                "buttons",
                "contacts",
                "structured_data",
                "technology_signals",
            )
        }
        return MaterialRow(
            id=_id(value.id),
            snapshot_id=_id(value.snapshot_id),
            extractor_name=value.extractor_name,
            extractor_version=value.extractor_version,
            title=value.title,
            material_json=_json(payload),
            visible_text=value.visible_text,
            prompt_injection_suspected=value.prompt_injection_suspected,
            created_at=value.created_at,
        )

    @staticmethod
    def _material(row: MaterialRow) -> ExtractedMaterial:
        payload = json.loads(row.material_json)
        tuples = {
            key: tuple(tuple(item) if isinstance(item, list) else item for item in value)
            for key, value in payload.items()
        }
        return ExtractedMaterial(
            id=UUID(row.id),
            snapshot_id=UUID(row.snapshot_id),
            extractor_name=row.extractor_name,
            extractor_version=row.extractor_version,
            title=row.title,
            metadata=tuples["metadata"],
            headings=tuples["headings"],
            visible_text=row.visible_text,
            links=tuples["links"],
            forms=tuples["forms"],
            buttons=tuples["buttons"],
            contacts=tuples["contacts"],
            structured_data=tuple(payload["structured_data"]),
            technology_signals=tuples["technology_signals"],
            prompt_injection_suspected=row.prompt_injection_suspected,
            created_at=_aware(row.created_at),
        )

    @staticmethod
    def _page_row(value: ResearchPage) -> PageRow:
        return PageRow(
            id=_id(value.id),
            workspace_id=_id(value.workspace_id),
            business_id=_id(value.business_id),
            research_run_id=_id(value.research_run_id),
            requested_url=value.requested_url,
            normalized_url=value.normalized_url,
            depth=value.depth,
            status=value.status,
            snapshot_id=_id(value.snapshot_id) if value.snapshot_id else None,
            material_id=_id(value.material_id) if value.material_id else None,
            fetched_at=value.fetched_at,
            error_code=value.error_code,
        )

    @staticmethod
    def _page(row: PageRow) -> ResearchPage:
        return ResearchPage(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            business_id=UUID(row.business_id),
            research_run_id=UUID(row.research_run_id),
            requested_url=row.requested_url,
            normalized_url=row.normalized_url,
            depth=row.depth,
            status=PageStatus(row.status),
            snapshot_id=UUID(row.snapshot_id) if row.snapshot_id else None,
            material_id=UUID(row.material_id) if row.material_id else None,
            fetched_at=_aware(row.fetched_at),
            error_code=row.error_code,
        )

    @staticmethod
    def _evidence_row(value: ResearchEvidence) -> EvidenceRow:
        data = asdict(value)
        for key in (
            "id",
            "workspace_id",
            "business_id",
            "research_run_id",
            "operation_id",
            "trace_id",
            "page_id",
            "snapshot_id",
        ):
            data[key] = _id(getattr(value, key))
        return EvidenceRow(**data)

    @staticmethod
    def _evidence(row: EvidenceRow) -> ResearchEvidence:
        return ResearchEvidence(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            business_id=UUID(row.business_id),
            research_run_id=UUID(row.research_run_id),
            operation_id=UUID(row.operation_id),
            trace_id=UUID(row.trace_id),
            page_id=UUID(row.page_id),
            snapshot_id=UUID(row.snapshot_id),
            snapshot_version=row.snapshot_version,
            source_uri=row.source_uri,
            captured_at=_aware(row.captured_at),
            content_sha256=row.content_sha256,
            locator=row.locator,
            extracted_fragment=row.extracted_fragment,
            extractor_name=row.extractor_name,
            extractor_version=row.extractor_version,
            created_at=_aware(row.created_at),
        )
