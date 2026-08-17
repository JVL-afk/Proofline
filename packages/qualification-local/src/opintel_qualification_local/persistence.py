"""SQLite persistence isolated to qualification-prefixed M2.5 tables."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from opintel_qualification.domain import (
    CaseEvaluationResult,
    DataClassification,
    DeploymentRecord,
    EvaluationMetrics,
    GateFailure,
    InvocationLedgerEntry,
    ProviderKind,
    QualificationDecision,
    QualificationKey,
    QualificationStatus,
    TaskClass,
)
from sqlalchemy import DateTime, Integer, String, Text, create_engine, event, literal_column, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _key_json(key: QualificationKey) -> str:
    return _json(asdict(key))


def _key_hash(key: QualificationKey) -> str:
    return hashlib.sha256(_key_json(key).encode()).hexdigest()


def _key(value: str) -> QualificationKey:
    item = json.loads(value)
    return QualificationKey(
        UUID(item["deployment_id"]),
        item["deployment_version"],
        item["deployment_config_hash"],
        TaskClass(item["task_class"]),
        item["task_version"],
        item["schema_version"],
        item["policy_version"],
        item["corpus_version"],
        DataClassification(item["data_classification"]),
    )


class Base(DeclarativeBase):
    pass


class DeploymentRow(Base):
    __tablename__ = "qualification_deployments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    provider_key: Mapped[str] = mapped_column(String(100))
    model_key: Mapped[str] = mapped_column(String(160))
    model_version: Mapped[str] = mapped_column(String(160))
    deployment_version: Mapped[str] = mapped_column(String(160))
    config_hash: Mapped[str] = mapped_column(String(64))
    provider_kind: Mapped[str] = mapped_column(String(20))
    capabilities_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionRow(Base):
    __tablename__ = "qualification_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    key_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    previous_decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    evaluation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResultRow(Base):
    __tablename__ = "qualification_case_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(36), index=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    deployment_id: Mapped[str] = mapped_column(String(36), index=True)
    key_json: Mapped[str] = mapped_column(Text)
    metrics_json: Mapped[str] = mapped_column(Text)
    gate_failures_json: Mapped[str] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InvocationRow(Base):
    __tablename__ = "qualification_invocation_ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(36), index=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    deployment_id: Mapped[str] = mapped_column(String(36), index=True)
    task_class: Mapped[str] = mapped_column(String(80))
    task_version: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(160))
    deployment_version: Mapped[str] = mapped_column(String(160))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    config_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(120))
    corpus_version: Mapped[str] = mapped_column(String(120))
    pricing_version: Mapped[str] = mapped_column(String(120))
    attempt: Mapped[int] = mapped_column(Integer)
    fallback_index: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cached_tokens: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    estimated_cost_micros: Mapped[int] = mapped_column(Integer)
    validation_outcome: Mapped[str] = mapped_column(String(40))
    safe_failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyQualificationRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("local M2.5 repository accepts only sqlite:/// URLs")
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

    def add_deployment(self, deployment: DeploymentRecord) -> None:
        with self._sessions.begin() as session:
            session.add(
                DeploymentRow(
                    id=str(deployment.id),
                    workspace_id=str(deployment.workspace_id),
                    provider_key=deployment.provider_key,
                    model_key=deployment.model_key,
                    model_version=deployment.model_version,
                    deployment_version=deployment.deployment_version,
                    config_hash=deployment.config_hash,
                    provider_kind=deployment.provider_kind,
                    capabilities_json=_json(deployment.capabilities),
                    created_at=deployment.created_at,
                )
            )

    def get_deployment(self, workspace_id: UUID, deployment_id: UUID) -> DeploymentRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DeploymentRow).where(
                    DeploymentRow.id == str(deployment_id),
                    DeploymentRow.workspace_id == str(workspace_id),
                )
            )
            return self._deployment(row) if row else None

    def list_deployments(self, workspace_id: UUID) -> tuple[DeploymentRecord, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(DeploymentRow).where(DeploymentRow.workspace_id == str(workspace_id))
                )
            )
            return tuple(self._deployment(row) for row in rows)

    def append_decision(self, decision: QualificationDecision) -> None:
        with self._sessions.begin() as session:
            session.add(
                DecisionRow(
                    id=str(decision.id),
                    workspace_id=str(decision.workspace_id),
                    key_hash=_key_hash(decision.key),
                    key_json=_key_json(decision.key),
                    status=decision.status,
                    previous_decision_id=str(decision.previous_decision_id)
                    if decision.previous_decision_id
                    else None,
                    reason=decision.reason,
                    evaluation_run_id=str(decision.evaluation_run_id)
                    if decision.evaluation_run_id
                    else None,
                    created_at=decision.created_at,
                )
            )

    def latest_decision(
        self, workspace_id: UUID, key: QualificationKey
    ) -> QualificationDecision | None:
        with self._sessions() as session:
            row = session.scalar(
                select(DecisionRow)
                .where(
                    DecisionRow.workspace_id == str(workspace_id),
                    DecisionRow.key_hash == _key_hash(key),
                )
                .order_by(literal_column("rowid").desc())
                .limit(1)
            )
            return self._decision(row) if row else None

    def list_decisions(
        self, workspace_id: UUID, status: QualificationStatus | None = None
    ) -> tuple[QualificationDecision, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(DecisionRow)
                    .where(DecisionRow.workspace_id == str(workspace_id))
                    .order_by(literal_column("rowid"))
                )
            )
        latest: dict[str, QualificationDecision] = {}
        for row in rows:
            latest[row.key_hash] = self._decision(row)
        return tuple(item for item in latest.values() if status is None or item.status == status)

    def save_case_result(self, result: CaseEvaluationResult) -> None:
        with self._sessions.begin() as session:
            session.add(
                ResultRow(
                    id=str(result.id),
                    workspace_id=str(result.workspace_id),
                    evaluation_run_id=str(result.evaluation_run_id),
                    case_id=str(result.case_id),
                    deployment_id=str(result.deployment_id),
                    key_json=_key_json(result.qualification_key),
                    metrics_json=_json(asdict(result.metrics)),
                    gate_failures_json=_json(result.gate_failures),
                    attempt_count=result.attempt_count,
                    output_hash=result.output_hash,
                    created_at=result.created_at,
                )
            )

    def list_case_results(
        self, workspace_id: UUID, evaluation_run_id: UUID
    ) -> tuple[CaseEvaluationResult, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(ResultRow)
                    .where(
                        ResultRow.workspace_id == str(workspace_id),
                        ResultRow.evaluation_run_id == str(evaluation_run_id),
                    )
                    .order_by(ResultRow.created_at, ResultRow.case_id)
                )
            )
            return tuple(self._result(row) for row in rows)

    def save_invocation(self, entry: InvocationLedgerEntry) -> None:
        with self._sessions.begin() as session:
            session.add(InvocationRow(**self._invocation_values(entry)))

    def list_invocations(
        self, workspace_id: UUID, evaluation_run_id: UUID
    ) -> tuple[InvocationLedgerEntry, ...]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(InvocationRow)
                    .where(
                        InvocationRow.workspace_id == str(workspace_id),
                        InvocationRow.evaluation_run_id == str(evaluation_run_id),
                    )
                    .order_by(InvocationRow.created_at, InvocationRow.attempt)
                )
            )
            return tuple(self._invocation(row) for row in rows)

    @staticmethod
    def _deployment(row: DeploymentRow) -> DeploymentRecord:
        return DeploymentRecord(
            UUID(row.id),
            UUID(row.workspace_id),
            row.provider_key,
            row.model_key,
            row.model_version,
            row.deployment_version,
            row.config_hash,
            ProviderKind(row.provider_kind),
            tuple(TaskClass(item) for item in json.loads(row.capabilities_json)),
            _aware(row.created_at),
        )

    @staticmethod
    def _decision(row: DecisionRow) -> QualificationDecision:
        return QualificationDecision(
            UUID(row.id),
            UUID(row.workspace_id),
            _key(row.key_json),
            QualificationStatus(row.status),
            UUID(row.previous_decision_id) if row.previous_decision_id else None,
            row.reason,
            UUID(row.evaluation_run_id) if row.evaluation_run_id else None,
            _aware(row.created_at),
        )

    @staticmethod
    def _result(row: ResultRow) -> CaseEvaluationResult:
        metrics = json.loads(row.metrics_json)
        return CaseEvaluationResult(
            UUID(row.id),
            UUID(row.workspace_id),
            UUID(row.evaluation_run_id),
            UUID(row.case_id),
            UUID(row.deployment_id),
            _key(row.key_json),
            EvaluationMetrics(**metrics),
            tuple(GateFailure(item) for item in json.loads(row.gate_failures_json)),
            row.attempt_count,
            row.output_hash,
            _aware(row.created_at),
        )

    @staticmethod
    def _invocation_values(entry: InvocationLedgerEntry) -> dict[str, object]:
        values = asdict(entry)
        for key in ("id", "workspace_id", "evaluation_run_id", "case_id", "deployment_id"):
            values[key] = str(values[key])
        values["task_class"] = entry.task_class.value
        return values

    @staticmethod
    def _invocation(row: InvocationRow) -> InvocationLedgerEntry:
        return InvocationLedgerEntry(
            UUID(row.id),
            UUID(row.workspace_id),
            UUID(row.evaluation_run_id),
            UUID(row.case_id),
            UUID(row.deployment_id),
            TaskClass(row.task_class),
            row.task_version,
            row.model_version,
            row.deployment_version,
            row.prompt_hash,
            row.config_hash,
            row.policy_version,
            row.corpus_version,
            row.pricing_version,
            row.attempt,
            row.fallback_index,
            row.input_tokens,
            row.output_tokens,
            row.cached_tokens,
            row.latency_ms,
            row.estimated_cost_micros,
            row.validation_outcome,
            row.safe_failure_code,
            _aware(row.created_at),
        )
