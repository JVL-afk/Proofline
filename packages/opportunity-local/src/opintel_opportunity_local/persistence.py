"""SQLite M2 persistence with append-only semantic revisions."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import overload
from uuid import UUID

from opintel_opportunity.domain import (
    AnalysisStatus,
    AssumptionRevision,
    Band,
    EconomicEffect,
    EconomicRun,
    EconomicStatus,
    FactorResult,
    GapPriority,
    HypothesisStatus,
    InferenceRevision,
    InformationGap,
    MissingBehavior,
    Observation,
    OpportunityAnalysisRun,
    OpportunityBundle,
    OpportunityHypothesisRevision,
    ReviewDecision,
    ReviewDecisionType,
    RevisionStatus,
    ScoreSnapshot,
    ValueState,
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
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _ids(value: str) -> tuple[UUID, ...]:
    return tuple(UUID(item) for item in json.loads(value))


@overload
def _aware(value: datetime) -> datetime: ...


@overload
def _aware(value: None) -> None: ...


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class AnalysisRow(Base):
    __tablename__ = "opportunity_analysis_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "business_id",
            "research_run_id",
            "idempotency_key",
            name="uq_opportunity_analysis_command",
        ),
        Index("ix_opportunity_analysis_claim", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    research_run_id: Mapped[str] = mapped_column(String(36), index=True)
    operation_id: Mapped[str] = mapped_column(String(36), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    definition_version: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    current_hypothesis_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ObservationRow(Base):
    __tablename__ = "opportunity_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("opportunity_analysis_runs.id"), index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(36), index=True)
    predicate: Mapped[str] = mapped_column(String(160))
    value: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(240))
    normalizer_version: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InferenceRow(Base):
    __tablename__ = "opportunity_inference_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    logical_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("opportunity_analysis_runs.id"), index=True
    )
    statement: Mapped[str] = mapped_column(Text)
    observation_ids_json: Mapped[str] = mapped_column(Text)
    evidence_ids_json: Mapped[str] = mapped_column(Text)
    contradictory_evidence_ids_json: Mapped[str] = mapped_column(Text)
    alternatives_json: Mapped[str] = mapped_column(Text)
    rule_version: Mapped[str] = mapped_column(String(120))
    confidence_band: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HypothesisRow(Base):
    __tablename__ = "opportunity_hypothesis_revisions"
    __table_args__ = (UniqueConstraint("logical_id", "revision", name="uq_hypothesis_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    logical_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("opportunity_analysis_runs.id"), index=True
    )
    definition_version: Mapped[str] = mapped_column(String(120))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    observation_ids_json: Mapped[str] = mapped_column(Text)
    inference_revision_ids_json: Mapped[str] = mapped_column(Text)
    supporting_evidence_ids_json: Mapped[str] = mapped_column(Text)
    contradictory_evidence_ids_json: Mapped[str] = mapped_column(Text)
    alternatives_json: Mapped[str] = mapped_column(Text)
    feasibility_dependencies_json: Mapped[str] = mapped_column(Text)
    assumption_revision_ids_json: Mapped[str] = mapped_column(Text)
    economic_run_id: Mapped[str] = mapped_column(String(36))
    score_snapshot_id: Mapped[str] = mapped_column(String(36))
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GapRow(Base):
    __tablename__ = "opportunity_information_gaps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    gap_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))
    affected_component: Mapped[str] = mapped_column(String(80))
    economic_effect: Mapped[str] = mapped_column(String(50))
    blocks_review_readiness: Mapped[bool] = mapped_column(Boolean)
    suggested_validation_question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AssumptionRow(Base):
    __tablename__ = "opportunity_assumption_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    value_state: Mapped[str] = mapped_column(String(30))
    decimal_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    time_basis: Mapped[str] = mapped_column(String(40))
    source_kind: Mapped[str] = mapped_column(String(80))
    provenance: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EconomicRow(Base):
    __tablename__ = "opportunity_economic_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    formula_version: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40))
    assumption_revision_ids_json: Mapped[str] = mapped_column(Text)
    monthly_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    annualized_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    result_label: Mapped[str] = mapped_column(String(240))
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScoreRow(Base):
    __tablename__ = "opportunity_score_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    config_version: Mapped[str] = mapped_column(String(160))
    factors_json: Mapped[str] = mapped_column(Text)
    review_priority_band: Mapped[str] = mapped_column(String(30))
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewRow(Base):
    __tablename__ = "opportunity_review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), index=True)
    hypothesis_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    inference_revision_ids_json: Mapped[str] = mapped_column(Text)
    assumption_revision_ids_json: Mapped[str] = mapped_column(Text)
    economic_run_id: Mapped[str] = mapped_column(String(36))
    score_snapshot_id: Mapped[str] = mapped_column(String(36))
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    actor_roles_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    self_review: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewInvalidationRow(Base):
    __tablename__ = "opportunity_review_invalidations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("opportunity_review_decisions.id"), index=True
    )
    invalidated_by_change_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyOpportunityRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("local M2 repository accepts only sqlite:/// URLs")
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

    def create_or_get_run(
        self, run: OpportunityAnalysisRun, idempotency_key: str
    ) -> tuple[OpportunityAnalysisRun, bool]:
        row = self._analysis_row(run, idempotency_key)
        try:
            with self._sessions.begin() as session:
                session.add(row)
            return run, True
        except IntegrityError:
            with self._sessions() as session:
                existing = session.scalar(
                    select(AnalysisRow).where(
                        AnalysisRow.workspace_id == str(run.workspace_id),
                        AnalysisRow.business_id == str(run.business_id),
                        AnalysisRow.research_run_id == str(run.research_run_id),
                        AnalysisRow.idempotency_key == idempotency_key,
                    )
                )
                assert existing is not None
                return self._run(existing), False

    def get_run(self, workspace_id: UUID, run_id: UUID) -> OpportunityAnalysisRun | None:
        with self._sessions() as session:
            row = session.scalar(
                select(AnalysisRow).where(
                    AnalysisRow.id == str(run_id), AnalysisRow.workspace_id == str(workspace_id)
                )
            )
            return self._run(row) if row else None

    def invalidate_reviews_for_new_evidence(
        self,
        workspace_id: UUID,
        business_id: UUID,
        definition_version: str,
        new_analysis_run_id: UUID,
        now: datetime,
    ) -> None:
        with self._sessions.begin() as session:
            hypothesis_ids = tuple(
                row[0]
                for row in session.execute(
                    select(AnalysisRow.hypothesis_id).where(
                        AnalysisRow.workspace_id == str(workspace_id),
                        AnalysisRow.business_id == str(business_id),
                        AnalysisRow.definition_version == definition_version,
                        AnalysisRow.hypothesis_id.is_not(None),
                        AnalysisRow.id != str(new_analysis_run_id),
                    )
                )
                if row[0]
            )
            if not hypothesis_ids:
                return
            reviews = tuple(
                session.scalars(
                    select(ReviewRow).where(ReviewRow.hypothesis_id.in_(hypothesis_ids))
                )
            )
            for review in reviews:
                already = session.scalar(
                    select(ReviewInvalidationRow).where(
                        ReviewInvalidationRow.review_id == review.id
                    )
                )
                if already is None:
                    session.add(
                        ReviewInvalidationRow(
                            id=str(UUID(int=(UUID(review.id).int ^ new_analysis_run_id.int))),
                            review_id=review.id,
                            invalidated_by_change_id=str(new_analysis_run_id),
                            reason="new_research_evidence_run",
                            created_at=now,
                        )
                    )

    def claim_run(self, now: datetime, lease: timedelta) -> OpportunityAnalysisRun | None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(AnalysisRow)
                .where(
                    or_(
                        AnalysisRow.status == AnalysisStatus.PENDING,
                        (
                            (AnalysisRow.status == AnalysisStatus.RUNNING)
                            & (AnalysisRow.lease_expires_at.is_not(None))
                            & (AnalysisRow.lease_expires_at <= now)
                        ),
                    )
                )
                .order_by(AnalysisRow.created_at)
                .limit(1)
            )
            if row is None:
                return None
            row.status = AnalysisStatus.RUNNING
            row.updated_at = now
            row.lease_expires_at = now + lease
            session.flush()
            return self._run(row)

    def save_bundle(self, bundle: OpportunityBundle) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(AnalysisRow)
                .where(AnalysisRow.id == str(bundle.run.id))
                .values(
                    status=bundle.run.status,
                    updated_at=bundle.run.updated_at,
                    lease_expires_at=bundle.run.lease_expires_at,
                    hypothesis_id=str(bundle.run.hypothesis_id)
                    if bundle.run.hypothesis_id
                    else None,
                    current_hypothesis_revision_id=(
                        str(bundle.run.current_hypothesis_revision_id)
                        if bundle.run.current_hypothesis_revision_id
                        else None
                    ),
                )
            )
            session.add_all(self._observation_row(item) for item in bundle.observations)
            if bundle.inference:
                session.add(self._inference_row(bundle.inference))
            if bundle.hypothesis:
                session.add(self._hypothesis_row(bundle.hypothesis))
                session.add_all(self._gap_row(item) for item in bundle.gaps)
                session.add_all(self._assumption_row(item) for item in bundle.assumptions)
                assert bundle.economic_run and bundle.score_snapshot
                session.add(self._economic_row(bundle.economic_run))
                session.add(self._score_row(bundle.score_snapshot))

    def fail_run(self, run_id: UUID, error_code: str, now: datetime) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(AnalysisRow)
                .where(AnalysisRow.id == str(run_id))
                .values(
                    status=AnalysisStatus.FAILED,
                    error_code=error_code,
                    updated_at=now,
                    lease_expires_at=None,
                )
            )

    def get_bundle_by_run(self, workspace_id: UUID, run_id: UUID) -> OpportunityBundle | None:
        run = self.get_run(workspace_id, run_id)
        return self._load_bundle(run) if run else None

    def get_bundle_by_hypothesis(
        self, workspace_id: UUID, hypothesis_id: UUID
    ) -> OpportunityBundle | None:
        with self._sessions() as session:
            row = session.scalar(
                select(AnalysisRow).where(
                    AnalysisRow.workspace_id == str(workspace_id),
                    AnalysisRow.hypothesis_id == str(hypothesis_id),
                )
            )
            return self._load_bundle(self._run(row)) if row else None

    def save_recalculation(
        self,
        previous: OpportunityBundle,
        hypothesis: OpportunityHypothesisRevision,
        assumptions: tuple[AssumptionRevision, ...],
        economic_run: EconomicRun,
        score_snapshot: ScoreSnapshot,
    ) -> OpportunityBundle:
        with self._sessions.begin() as session:
            session.add_all(self._assumption_row(item) for item in assumptions)
            session.add(self._economic_row(economic_run))
            session.add(self._score_row(score_snapshot))
            session.add(self._hypothesis_row(hypothesis))
            session.execute(
                update(AnalysisRow)
                .where(AnalysisRow.id == str(previous.run.id))
                .values(
                    current_hypothesis_revision_id=str(hypothesis.id),
                    updated_at=hypothesis.created_at,
                )
            )
            if previous.latest_review and previous.review_valid:
                session.add(
                    ReviewInvalidationRow(
                        id=str(UUID(int=(hypothesis.id.int ^ previous.latest_review.id.int))),
                        review_id=str(previous.latest_review.id),
                        invalidated_by_change_id=str(hypothesis.id),
                        reason="material_recalculation",
                        created_at=hypothesis.created_at,
                    )
                )
        run = replace(
            previous.run,
            current_hypothesis_revision_id=hypothesis.id,
            updated_at=hypothesis.created_at,
        )
        return OpportunityBundle(
            run,
            previous.observations,
            previous.inference,
            hypothesis,
            previous.gaps,
            assumptions,
            economic_run,
            score_snapshot,
            previous.latest_review,
            False,
        )

    def save_review(
        self, previous: OpportunityBundle, decision: ReviewDecision
    ) -> OpportunityBundle:
        with self._sessions.begin() as session:
            session.add(self._review_row(decision))
        hypothesis = previous.hypothesis
        assert hypothesis is not None
        effective = {
            ReviewDecisionType.ACCEPT: HypothesisStatus.ACCEPTED,
            ReviewDecisionType.REJECT: HypothesisStatus.REJECTED,
            ReviewDecisionType.REQUEST_INFORMATION: HypothesisStatus.NEEDS_INFORMATION,
        }[decision.decision]
        return replace(
            previous,
            hypothesis=replace(hypothesis, status=effective),
            latest_review=decision,
            review_valid=True,
        )

    def save_inference_rejection(
        self,
        previous: OpportunityBundle,
        inference: InferenceRevision,
        hypothesis: OpportunityHypothesisRevision,
    ) -> OpportunityBundle:
        with self._sessions.begin() as session:
            session.add(self._inference_row(inference))
            session.add(self._hypothesis_row(hypothesis))
            session.execute(
                update(AnalysisRow)
                .where(AnalysisRow.id == str(previous.run.id))
                .values(
                    current_hypothesis_revision_id=str(hypothesis.id),
                    updated_at=hypothesis.created_at,
                )
            )
            if previous.latest_review and previous.review_valid:
                session.add(
                    ReviewInvalidationRow(
                        id=str(UUID(int=(hypothesis.id.int ^ previous.latest_review.id.int))),
                        review_id=str(previous.latest_review.id),
                        invalidated_by_change_id=str(hypothesis.id),
                        reason="inference_rejected",
                        created_at=hypothesis.created_at,
                    )
                )
        return replace(
            previous,
            run=replace(
                previous.run,
                current_hypothesis_revision_id=hypothesis.id,
                updated_at=hypothesis.created_at,
            ),
            inference=inference,
            hypothesis=hypothesis,
            review_valid=False,
        )

    def _load_bundle(self, run: OpportunityAnalysisRun) -> OpportunityBundle:
        with self._sessions() as session:
            observations = tuple(
                self._observation(row)
                for row in session.scalars(
                    select(ObservationRow).where(ObservationRow.analysis_run_id == str(run.id))
                )
            )
            inference_row = session.scalar(
                select(InferenceRow)
                .where(InferenceRow.analysis_run_id == str(run.id))
                .order_by(InferenceRow.revision.desc())
            )
            hypothesis_row = (
                session.get(HypothesisRow, str(run.current_hypothesis_revision_id))
                if run.current_hypothesis_revision_id
                else None
            )
            if hypothesis_row is None:
                return OpportunityBundle(
                    run,
                    observations,
                    self._inference(inference_row) if inference_row else None,
                    None,
                    (),
                    (),
                    None,
                    None,
                )
            hypothesis = self._hypothesis(hypothesis_row)
            gaps = tuple(
                self._gap(row)
                for row in session.scalars(
                    select(GapRow).where(GapRow.hypothesis_id == str(hypothesis.logical_id))
                )
            )
            assumptions = tuple(
                self._assumption(row)
                for row in session.scalars(
                    select(AssumptionRow).where(
                        AssumptionRow.id.in_(
                            [str(item) for item in hypothesis.assumption_revision_ids]
                        )
                    )
                )
            )
            by_id = {item.id: item for item in assumptions}
            assumptions = tuple(by_id[item] for item in hypothesis.assumption_revision_ids)
            economic_row = session.get(EconomicRow, str(hypothesis.economic_run_id))
            score_row = session.get(ScoreRow, str(hypothesis.score_snapshot_id))
            review_row = session.scalar(
                select(ReviewRow)
                .where(ReviewRow.hypothesis_id == str(hypothesis.logical_id))
                .order_by(ReviewRow.created_at.desc())
                .limit(1)
            )
            decision = self._review(review_row) if review_row else None
            invalidated = False
            if review_row:
                invalidated = (
                    session.scalar(
                        select(ReviewInvalidationRow).where(
                            ReviewInvalidationRow.review_id == review_row.id
                        )
                    )
                    is not None
                )
            valid = bool(
                decision and decision.hypothesis_revision_id == hypothesis.id and not invalidated
            )
            if valid and decision:
                effective = {
                    ReviewDecisionType.ACCEPT: HypothesisStatus.ACCEPTED,
                    ReviewDecisionType.REJECT: HypothesisStatus.REJECTED,
                    ReviewDecisionType.REQUEST_INFORMATION: HypothesisStatus.NEEDS_INFORMATION,
                }[decision.decision]
                hypothesis = replace(hypothesis, status=effective)
            return OpportunityBundle(
                run,
                observations,
                self._inference(inference_row) if inference_row else None,
                hypothesis,
                gaps,
                assumptions,
                self._economic(economic_row) if economic_row else None,
                self._score(score_row) if score_row else None,
                decision,
                valid,
            )

    @staticmethod
    def _analysis_row(value: OpportunityAnalysisRun, key: str) -> AnalysisRow:
        data = asdict(value)
        for name in (
            "id",
            "workspace_id",
            "business_id",
            "research_run_id",
            "operation_id",
            "trace_id",
            "hypothesis_id",
            "current_hypothesis_revision_id",
        ):
            data[name] = str(data[name]) if data[name] else None
        data["status"] = value.status
        data["idempotency_key"] = key
        return AnalysisRow(**data)

    @staticmethod
    def _run(row: AnalysisRow) -> OpportunityAnalysisRun:
        return OpportunityAnalysisRun(
            id=UUID(row.id),
            workspace_id=UUID(row.workspace_id),
            business_id=UUID(row.business_id),
            research_run_id=UUID(row.research_run_id),
            operation_id=UUID(row.operation_id),
            trace_id=UUID(row.trace_id),
            definition_version=row.definition_version,
            status=AnalysisStatus(row.status),
            created_by=row.created_by,
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
            lease_expires_at=_aware(row.lease_expires_at),
            hypothesis_id=UUID(row.hypothesis_id) if row.hypothesis_id else None,
            current_hypothesis_revision_id=UUID(row.current_hypothesis_revision_id)
            if row.current_hypothesis_revision_id
            else None,
            error_code=row.error_code,
        )

    @staticmethod
    def _observation_row(value: Observation) -> ObservationRow:
        data = asdict(value)
        for name in ("id", "workspace_id", "business_id", "analysis_run_id", "evidence_id"):
            data[name] = str(data[name])
        return ObservationRow(**data)

    @staticmethod
    def _observation(row: ObservationRow) -> Observation:
        return Observation(
            UUID(row.id),
            UUID(row.workspace_id),
            UUID(row.business_id),
            UUID(row.analysis_run_id),
            UUID(row.evidence_id),
            row.predicate,
            row.value,
            row.scope,
            row.normalizer_version,
            _aware(row.created_at),
        )

    @staticmethod
    def _inference_row(value: InferenceRevision) -> InferenceRow:
        return InferenceRow(
            id=str(value.id),
            logical_id=str(value.logical_id),
            revision=value.revision,
            analysis_run_id=str(value.analysis_run_id),
            statement=value.statement,
            observation_ids_json=_json(value.observation_ids),
            evidence_ids_json=_json(value.evidence_ids),
            contradictory_evidence_ids_json=_json(value.contradictory_evidence_ids),
            alternatives_json=_json(value.alternatives),
            rule_version=value.rule_version,
            confidence_band=value.confidence_band,
            status=value.status,
            created_at=value.created_at,
        )

    @staticmethod
    def _inference(row: InferenceRow) -> InferenceRevision:
        return InferenceRevision(
            UUID(row.id),
            UUID(row.logical_id),
            row.revision,
            UUID(row.analysis_run_id),
            row.statement,
            _ids(row.observation_ids_json),
            _ids(row.evidence_ids_json),
            _ids(row.contradictory_evidence_ids_json),
            tuple(json.loads(row.alternatives_json)),
            row.rule_version,
            Band(row.confidence_band),
            RevisionStatus(row.status),
            _aware(row.created_at),
        )

    @staticmethod
    def _hypothesis_row(value: OpportunityHypothesisRevision) -> HypothesisRow:
        return HypothesisRow(
            id=str(value.id),
            logical_id=str(value.logical_id),
            revision=value.revision,
            workspace_id=str(value.workspace_id),
            business_id=str(value.business_id),
            analysis_run_id=str(value.analysis_run_id),
            definition_version=value.definition_version,
            statement=value.statement,
            status=value.status,
            observation_ids_json=_json(value.observation_ids),
            inference_revision_ids_json=_json(value.inference_revision_ids),
            supporting_evidence_ids_json=_json(value.supporting_evidence_ids),
            contradictory_evidence_ids_json=_json(value.contradictory_evidence_ids),
            alternatives_json=_json(value.alternative_explanations),
            feasibility_dependencies_json=_json(value.feasibility_dependencies),
            assumption_revision_ids_json=_json(value.assumption_revision_ids),
            economic_run_id=str(value.economic_run_id),
            score_snapshot_id=str(value.score_snapshot_id),
            manifest_checksum=value.manifest_checksum,
            created_by=value.created_by,
            created_at=value.created_at,
        )

    @staticmethod
    def _hypothesis(row: HypothesisRow) -> OpportunityHypothesisRevision:
        return OpportunityHypothesisRevision(
            UUID(row.id),
            UUID(row.logical_id),
            row.revision,
            UUID(row.workspace_id),
            UUID(row.business_id),
            UUID(row.analysis_run_id),
            row.definition_version,
            row.statement,
            HypothesisStatus(row.status),
            _ids(row.observation_ids_json),
            _ids(row.inference_revision_ids_json),
            _ids(row.supporting_evidence_ids_json),
            _ids(row.contradictory_evidence_ids_json),
            tuple(json.loads(row.alternatives_json)),
            tuple(json.loads(row.feasibility_dependencies_json)),
            _ids(row.assumption_revision_ids_json),
            UUID(row.economic_run_id),
            UUID(row.score_snapshot_id),
            row.manifest_checksum,
            row.created_by,
            _aware(row.created_at),
        )

    @staticmethod
    def _gap_row(value: InformationGap) -> GapRow:
        return GapRow(
            id=str(value.id),
            hypothesis_id=str(value.hypothesis_id),
            gap_type=value.gap_type,
            description=value.description,
            priority=value.priority,
            affected_component=value.affected_component,
            economic_effect=value.economic_effect,
            blocks_review_readiness=value.blocks_review_readiness,
            suggested_validation_question=value.suggested_validation_question,
            created_at=value.created_at,
        )

    @staticmethod
    def _gap(row: GapRow) -> InformationGap:
        return InformationGap(
            UUID(row.id),
            UUID(row.hypothesis_id),
            row.gap_type,
            row.description,
            GapPriority(row.priority),
            row.affected_component,
            EconomicEffect(row.economic_effect),
            row.blocks_review_readiness,
            row.suggested_validation_question,
            _aware(row.created_at),
        )

    @staticmethod
    def _assumption_row(value: AssumptionRevision) -> AssumptionRow:
        return AssumptionRow(
            id=str(value.id),
            hypothesis_id=str(value.hypothesis_id),
            key=value.key,
            revision=value.revision,
            value_state=value.value_state,
            decimal_value=value.decimal_value,
            unit=value.unit,
            currency=value.currency,
            time_basis=value.time_basis,
            source_kind=value.source_kind,
            provenance=value.provenance,
            created_by=value.created_by,
            created_at=value.created_at,
        )

    @staticmethod
    def _assumption(row: AssumptionRow) -> AssumptionRevision:
        return AssumptionRevision(
            UUID(row.id),
            UUID(row.hypothesis_id),
            row.key,
            row.revision,
            ValueState(row.value_state),
            row.decimal_value,
            row.unit,
            row.currency,
            row.time_basis,
            row.source_kind,
            row.provenance,
            row.created_by,
            _aware(row.created_at),
        )

    @staticmethod
    def _economic_row(value: EconomicRun) -> EconomicRow:
        return EconomicRow(
            id=str(value.id),
            hypothesis_id=str(value.hypothesis_id),
            formula_version=value.formula_version,
            status=value.status,
            assumption_revision_ids_json=_json(value.assumption_revision_ids),
            monthly_value=value.monthly_potential_incremental_revenue,
            annualized_value=value.annualized_potential_incremental_revenue,
            currency=value.currency,
            result_label=value.result_label,
            manifest_checksum=value.manifest_checksum,
            created_at=value.created_at,
        )

    @staticmethod
    def _economic(row: EconomicRow) -> EconomicRun:
        return EconomicRun(
            UUID(row.id),
            UUID(row.hypothesis_id),
            row.formula_version,
            EconomicStatus(row.status),
            _ids(row.assumption_revision_ids_json),
            row.monthly_value,
            row.annualized_value,
            row.currency,
            row.result_label,
            row.manifest_checksum,
            _aware(row.created_at),
        )

    @staticmethod
    def _score_row(value: ScoreSnapshot) -> ScoreRow:
        return ScoreRow(
            id=str(value.id),
            hypothesis_id=str(value.hypothesis_id),
            config_version=value.config_version,
            factors_json=_json([asdict(item) for item in value.factors]),
            review_priority_band=value.review_priority_band,
            manifest_checksum=value.manifest_checksum,
            created_at=value.created_at,
        )

    @staticmethod
    def _score(row: ScoreRow) -> ScoreSnapshot:
        factors = tuple(
            FactorResult(
                item["name"],
                Band(item["band"]),
                MissingBehavior(item["missing_behavior"]),
                item["rationale"],
            )
            for item in json.loads(row.factors_json)
        )
        return ScoreSnapshot(
            UUID(row.id),
            UUID(row.hypothesis_id),
            row.config_version,
            factors,
            row.review_priority_band,
            row.manifest_checksum,
            _aware(row.created_at),
        )

    @staticmethod
    def _review_row(value: ReviewDecision) -> ReviewRow:
        return ReviewRow(
            id=str(value.id),
            hypothesis_id=str(value.hypothesis_id),
            hypothesis_revision_id=str(value.hypothesis_revision_id),
            inference_revision_ids_json=_json(value.inference_revision_ids),
            assumption_revision_ids_json=_json(value.assumption_revision_ids),
            economic_run_id=str(value.economic_run_id),
            score_snapshot_id=str(value.score_snapshot_id),
            manifest_checksum=value.manifest_checksum,
            decision=value.decision,
            actor=value.actor,
            actor_roles_json=_json(value.actor_roles),
            reason=value.reason,
            self_review=value.self_review,
            created_at=value.created_at,
        )

    @staticmethod
    def _review(row: ReviewRow) -> ReviewDecision:
        return ReviewDecision(
            UUID(row.id),
            UUID(row.hypothesis_id),
            UUID(row.hypothesis_revision_id),
            _ids(row.inference_revision_ids_json),
            _ids(row.assumption_revision_ids_json),
            UUID(row.economic_run_id),
            UUID(row.score_snapshot_id),
            row.manifest_checksum,
            ReviewDecisionType(row.decision),
            row.actor,
            tuple(json.loads(row.actor_roles_json)),
            row.reason,
            row.self_review,
            _aware(row.created_at),
        )
