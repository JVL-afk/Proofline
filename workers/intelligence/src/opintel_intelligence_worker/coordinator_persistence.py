"""Durable exact-lineage repository for one bounded sampled-slot production chain."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Inspector
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from opintel_intelligence_worker.orchestration import (
    CoordinatedStageArtifact,
    CoordinatorStageState,
    ShadowStage,
)

# Attempt-lineage value recorded for coordinator runs that were persisted before
# the repair-attempt identity model existed (they predate Repair #4).
LEGACY_ATTEMPT_LINEAGE_SHA256 = hashlib.sha256(
    b"m67.phase1.repair-attempt@1:pre-repair-4-legacy"
).hexdigest()

_COORDINATOR_RUNS_TABLE = "m67_sampled_slot_coordinator_runs"
_LINEAGE_COLUMN = "repair_attempt_lineage_sha256"
# The attempt-scoped uniqueness the coordinator-runs table must carry: each
# release / work-item identity is unique *within one repair-attempt lineage*, so a
# superseded bounded-repair attempt never blocks a legitimate repaired successor.
_INTENDED_UNIQUE_CONSTRAINTS: dict[str, tuple[str, ...]] = {
    "uq_m67_coordinator_release": ("authorization_release_id", _LINEAGE_COLUMN),
    "uq_m67_coordinator_work_item": ("work_item_identity_sha256", _LINEAGE_COLUMN),
}


def _named_unique_constraints(inspector: Inspector) -> dict[str, tuple[str, ...]]:
    """Named unique constraints on the coordinator-runs table, column sets in
    definition order. Unnamed constraints are ignored (the model always names
    both attempt-scoped constraints explicitly)."""

    result: dict[str, tuple[str, ...]] = {}
    for constraint in inspector.get_unique_constraints(_COORDINATOR_RUNS_TABLE):
        name = constraint.get("name")
        if name:
            result[name] = tuple(constraint["column_names"])
    return result


def _lineage_convergence_plan(
    *,
    has_lineage_column: bool,
    lineage_column_nullable: bool,
    unique_constraints: dict[str, tuple[str, ...]],
    legacy_lineage: str,
    table: str = _COORDINATOR_RUNS_TABLE,
) -> list[tuple[str, dict[str, object]]]:
    """Deterministic ordered (sql, params) statements that converge the coordinator
    runs table to the attempt-scoped identity model, given its current schema state.

    Completion is judged by the actual schema invariants - lineage column present,
    column NOT NULL, and both uniqueness constraints being the intended composite -
    never by the mere existence of the marker column. A schema that already meets
    every invariant yields an empty plan (strict no-op). A schema that has the
    column but still carries a legacy single-column constraint converges only the
    missing invariant(s). The backfill only ever assigns the legacy lineage to rows
    whose lineage is NULL; existing non-NULL rows are never touched.
    """

    plan: list[tuple[str, dict[str, object]]] = []
    needs_backfill_and_not_null = False

    if not has_lineage_column:
        plan.append(
            (f"ALTER TABLE {table} ADD COLUMN {_LINEAGE_COLUMN} VARCHAR(64)", {})
        )
        needs_backfill_and_not_null = True
    elif lineage_column_nullable:
        needs_backfill_and_not_null = True

    if needs_backfill_and_not_null:
        plan.append(
            (
                f"UPDATE {table} SET {_LINEAGE_COLUMN} = :legacy "
                f"WHERE {_LINEAGE_COLUMN} IS NULL",
                {"legacy": legacy_lineage},
            )
        )
        plan.append(
            (f"ALTER TABLE {table} ALTER COLUMN {_LINEAGE_COLUMN} SET NOT NULL", {})
        )

    for name, intended in _INTENDED_UNIQUE_CONSTRAINTS.items():
        if unique_constraints.get(name) == intended:
            continue
        plan.append((f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}", {}))
        plan.append(
            (
                f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                f"UNIQUE ({intended[0]}, {intended[1]})",
                {},
            )
        )

    return plan


@dataclass(frozen=True, slots=True)
class CoordinatorRunBinding:
    coordinator_run_id: UUID
    authorization_release_id: UUID
    ordered_package_sha256: str
    slot_number: int
    business_identity: str
    exact_hostname: str
    work_item_identity_sha256: str
    activation_sha256: str
    runtime_revision: str
    created_at: datetime
    # Execution-attempt identity within the same frozen experiment. The
    # release-id and work-item uniqueness are scoped to this so a prior terminal
    # coordinator (a superseded bounded-repair attempt) never blocks or
    # short-circuits a legitimate repaired successor.
    repair_attempt_lineage_sha256: str


class Base(DeclarativeBase):
    pass


class CoordinatorRunRow(Base):
    __tablename__ = "m67_sampled_slot_coordinator_runs"
    __table_args__ = (
        UniqueConstraint(
            "authorization_release_id",
            "repair_attempt_lineage_sha256",
            name="uq_m67_coordinator_release",
        ),
        UniqueConstraint(
            "work_item_identity_sha256",
            "repair_attempt_lineage_sha256",
            name="uq_m67_coordinator_work_item",
        ),
    )

    coordinator_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    authorization_release_id: Mapped[str] = mapped_column(String(36), nullable=False)
    repair_attempt_lineage_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ordered_package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    slot_number: Mapped[int]
    business_identity: Mapped[str] = mapped_column(String(200), nullable=False)
    exact_hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    work_item_identity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    activation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_revision: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    terminal_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CoordinatorArtifactRow(Base):
    __tablename__ = "m67_sampled_slot_coordinator_artifacts"
    __table_args__ = (
        UniqueConstraint("coordinator_run_id", "stage", name="uq_m67_coordinator_stage"),
        UniqueConstraint("revision_id", name="uq_m67_coordinator_revision"),
    )

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    coordinator_run_id: Mapped[str] = mapped_column(
        ForeignKey("m67_sampled_slot_coordinator_runs.coordinator_run_id"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    predecessor_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    predecessor_artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlAlchemyCoordinatorRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("coordinator repository requires sqlite or postgresql+psycopg")
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
        self._migrate_repair_attempt_lineage()

    def _migrate_repair_attempt_lineage(self) -> None:
        """Converge the coordinator-runs table to the attempt-scoped identity model.

        Every required schema invariant is inspected and converged independently:
        the presence of the marker column is never taken as proof that the
        constraint migration ran. A PostgreSQL database that already has
        ``repair_attempt_lineage_sha256`` but still carries the pre-Repair-4
        single-column ``uq_m67_coordinator_release`` / ``uq_m67_coordinator_work_item``
        constraints is brought fully up to date; a schema that already meets every
        invariant is a strict no-op. ``create_all`` produces the current schema on
        every other dialect, so this only runs on PostgreSQL.
        """

        if self.engine.dialect.name != "postgresql":
            return

        with self.engine.begin() as connection:
            inspector = inspect(connection)
            columns = {
                column["name"]: column
                for column in inspector.get_columns(_COORDINATOR_RUNS_TABLE)
            }
            lineage_column = columns.get(_LINEAGE_COLUMN)
            unique_constraints = _named_unique_constraints(inspector)
            plan = _lineage_convergence_plan(
                has_lineage_column=lineage_column is not None,
                lineage_column_nullable=(
                    lineage_column is None or bool(lineage_column.get("nullable", True))
                ),
                unique_constraints=unique_constraints,
                legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
            )
            for statement, params in plan:
                connection.execute(text(statement), params)

    def verify_repair_attempt_lineage_schema(self) -> dict[str, object]:
        """Read-only PostgreSQL catalog check that the attempt-scoped schema
        invariants actually hold. Returns the observed constraint column sets and a
        ``converged`` verdict; a no-op ``{"dialect": ...}`` result off PostgreSQL."""

        if self.engine.dialect.name != "postgresql":
            return {"dialect": self.engine.dialect.name, "converged": True}
        with self.engine.connect() as connection:
            inspector = inspect(connection)
            columns = {
                column["name"]: column
                for column in inspector.get_columns(_COORDINATOR_RUNS_TABLE)
            }
            observed = _named_unique_constraints(inspector)
        lineage_column = columns.get(_LINEAGE_COLUMN)
        converged = (
            lineage_column is not None
            and not bool(lineage_column.get("nullable", True))
            and all(
                observed.get(name) == intended
                for name, intended in _INTENDED_UNIQUE_CONSTRAINTS.items()
            )
        )
        return {
            "dialect": "postgresql",
            "lineage_column_present": lineage_column is not None,
            "lineage_column_not_null": lineage_column is not None
            and not bool(lineage_column.get("nullable", True)),
            "observed_unique_constraints": {k: list(v) for k, v in observed.items()},
            "intended_unique_constraints": {
                k: list(v) for k, v in _INTENDED_UNIQUE_CONSTRAINTS.items()
            },
            "converged": converged,
        }

    def create_or_get(self, binding: CoordinatorRunBinding) -> tuple[CoordinatorRunBinding, bool]:
        row = CoordinatorRunRow(
            **{
                **asdict(binding),
                "coordinator_run_id": str(binding.coordinator_run_id),
                "authorization_release_id": str(binding.authorization_release_id),
                "state": "ACTIVE",
                "terminal_reason": None,
                "updated_at": binding.created_at,
            }
        )
        try:
            with self._sessions.begin() as session:
                session.add(row)
            return binding, True
        except IntegrityError as error:
            with self._sessions() as session:
                existing = session.scalar(
                    select(CoordinatorRunRow).where(
                        CoordinatorRunRow.authorization_release_id
                        == str(binding.authorization_release_id),
                        CoordinatorRunRow.repair_attempt_lineage_sha256
                        == binding.repair_attempt_lineage_sha256,
                    )
                )
                if existing is None:
                    raise
                value = self._binding(existing)
                if value != binding:
                    raise ValueError(
                        "duplicate coordinator activation differs from immutable run"
                    ) from error
                return value, False

    def load(self, coordinator_run_id: UUID) -> tuple[CoordinatedStageArtifact, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(CoordinatorArtifactRow)
                .where(CoordinatorArtifactRow.coordinator_run_id == str(coordinator_run_id))
                .order_by(CoordinatorArtifactRow.row_id)
            ).all()
            return tuple(self._artifact(row) for row in rows)

    def append(self, artifact: CoordinatedStageArtifact, now: datetime) -> bool:
        payload = self._artifact_payload(artifact)
        try:
            with self._sessions.begin() as session:
                run = session.get(CoordinatorRunRow, str(artifact.coordinator_run_id))
                if run is None or run.state != "ACTIVE":
                    raise ValueError("coordinator run is absent or terminal")
                existing = tuple(
                    session.scalars(
                        select(CoordinatorArtifactRow)
                        .where(
                            CoordinatorArtifactRow.coordinator_run_id
                            == str(artifact.coordinator_run_id)
                        )
                        .order_by(CoordinatorArtifactRow.row_id)
                    )
                )
                duplicate = next(
                    (row for row in existing if row.stage == artifact.stage.value), None
                )
                if duplicate is not None:
                    if duplicate.artifact_sha256 != artifact.artifact_sha256:
                        raise ValueError(
                            "duplicate stage delivery diverges from durable artifact"
                        )
                    return False
                predecessor = existing[-1] if existing else None
                if artifact.predecessor_revision_id != (
                    UUID(predecessor.revision_id) if predecessor else None
                ) or artifact.predecessor_artifact_sha256 != (
                    predecessor.artifact_sha256 if predecessor else None
                ):
                    raise ValueError("durable predecessor lineage mismatch")
                session.add(
                    CoordinatorArtifactRow(
                        coordinator_run_id=str(artifact.coordinator_run_id),
                        stage=artifact.stage.value,
                        revision_id=str(artifact.revision_id),
                        predecessor_revision_id=(
                            str(artifact.predecessor_revision_id)
                            if artifact.predecessor_revision_id
                            else None
                        ),
                        predecessor_artifact_sha256=artifact.predecessor_artifact_sha256,
                        artifact_sha256=artifact.artifact_sha256,
                        data_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        created_at=now,
                    )
                )
                run.updated_at = now
            return True
        except IntegrityError as error:
            with self._sessions() as session:
                existing = session.scalar(
                    select(CoordinatorArtifactRow).where(
                        CoordinatorArtifactRow.coordinator_run_id
                        == str(artifact.coordinator_run_id),
                        CoordinatorArtifactRow.stage == artifact.stage.value,
                    )
                )
                if existing is None or existing.artifact_sha256 != artifact.artifact_sha256:
                    raise ValueError(
                        "duplicate stage delivery diverges from durable artifact"
                    ) from error
                return False

    def mark_terminal(self, coordinator_run_id: UUID, reason: str, now: datetime) -> None:
        with self._sessions.begin() as session:
            row = session.get(CoordinatorRunRow, str(coordinator_run_id))
            if row is None:
                raise ValueError("coordinator run is absent")
            if row.state == "TERMINAL":
                if row.terminal_reason != reason:
                    raise ValueError("terminal replay reason mismatch")
                return
            row.state = "TERMINAL"
            row.terminal_reason = reason
            row.updated_at = now

    @staticmethod
    def _binding(row: CoordinatorRunRow) -> CoordinatorRunBinding:
        created_at = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
        return CoordinatorRunBinding(
            UUID(row.coordinator_run_id),
            UUID(row.authorization_release_id),
            row.ordered_package_sha256,
            row.slot_number,
            row.business_identity,
            row.exact_hostname,
            row.work_item_identity_sha256,
            row.activation_sha256,
            row.runtime_revision,
            created_at,
            row.repair_attempt_lineage_sha256,
        )

    @staticmethod
    def _artifact_payload(value: CoordinatedStageArtifact) -> dict[str, object]:
        return {
            **asdict(value),
            "authorization_release_id": str(value.authorization_release_id),
            "coordinator_run_id": str(value.coordinator_run_id),
            "revision_id": str(value.revision_id),
            "predecessor_revision_id": (
                str(value.predecessor_revision_id) if value.predecessor_revision_id else None
            ),
            "stage": value.stage.value,
            "state": value.state.value,
        }

    @staticmethod
    def _artifact(row: CoordinatorArtifactRow) -> CoordinatedStageArtifact:
        value = json.loads(row.data_json)
        return CoordinatedStageArtifact(
            **{
                **value,
                "authorization_release_id": UUID(value["authorization_release_id"]),
                "coordinator_run_id": UUID(value["coordinator_run_id"]),
                "revision_id": UUID(value["revision_id"]),
                "predecessor_revision_id": (
                    UUID(value["predecessor_revision_id"])
                    if value["predecessor_revision_id"]
                    else None
                ),
                "stage": ShadowStage(value["stage"]),
                "state": CoordinatorStageState(value["state"]),
            }
        )
