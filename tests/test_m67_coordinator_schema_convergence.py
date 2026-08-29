"""Repair #4 schema-convergence completion.

_migrate_repair_attempt_lineage() must judge migration completion by the actual
schema invariants (lineage column present, column NOT NULL, both uniqueness
constraints being the intended composite), never by the mere existence of the
marker column. These tests cover every convergence state the production database
can be in, including the latent-partial state that blocked the Repair #5 resume
(column present, constraints still legacy single-column).
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from opintel_intelligence_worker.coordinator_persistence import (
    _INTENDED_UNIQUE_CONSTRAINTS,
    LEGACY_ATTEMPT_LINEAGE_SHA256,
    CoordinatorRunBinding,
    SqlAlchemyCoordinatorRepository,
    _lineage_convergence_plan,
)
from sqlalchemy import create_engine, inspect, text

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)
_RELEASE = UUID("375a88da-da88-5ebf-9daf-cb09934e02b8")
_RELEASE_COMPOSITE = ("authorization_release_id", "repair_attempt_lineage_sha256")
_WORK_ITEM_COMPOSITE = ("work_item_identity_sha256", "repair_attempt_lineage_sha256")


def _sql(plan: list[tuple[str, dict[str, object]]]) -> list[str]:
    return [statement for statement, _ in plan]


# --- 1. no lineage column + legacy constraints -> complete convergence ---------

def test_fresh_legacy_schema_converges_completely() -> None:
    plan = _lineage_convergence_plan(
        has_lineage_column=False,
        lineage_column_nullable=True,
        unique_constraints={
            "uq_m67_coordinator_release": ("authorization_release_id",),
            "uq_m67_coordinator_work_item": ("work_item_identity_sha256",),
        },
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    statements = _sql(plan)
    assert any("ADD COLUMN repair_attempt_lineage_sha256" in s for s in statements)
    assert any("SET repair_attempt_lineage_sha256 = :legacy" in s for s in statements)
    assert any("SET NOT NULL" in s for s in statements)
    assert statements.count("ALTER TABLE m67_sampled_slot_coordinator_runs "
                            "DROP CONSTRAINT IF EXISTS uq_m67_coordinator_release") == 1
    assert any("ADD CONSTRAINT uq_m67_coordinator_release UNIQUE "
               "(authorization_release_id, repair_attempt_lineage_sha256)" in s
               for s in statements)
    assert any("ADD CONSTRAINT uq_m67_coordinator_work_item UNIQUE "
               "(work_item_identity_sha256, repair_attempt_lineage_sha256)" in s
               for s in statements)


# --- 2. column present + legacy constraints -> constraints still migrated ------

def test_latent_partial_schema_still_migrates_the_constraints() -> None:
    """The exact production state that blocked the Repair #5 resume: the marker
    column exists (added by a superseded Repair #4 iteration) but the uniqueness
    constraints were never re-scoped."""
    plan = _lineage_convergence_plan(
        has_lineage_column=True,
        lineage_column_nullable=False,
        unique_constraints={
            "uq_m67_coordinator_release": ("authorization_release_id",),
            "uq_m67_coordinator_work_item": ("work_item_identity_sha256",),
        },
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    statements = _sql(plan)
    assert not any("ADD COLUMN" in s for s in statements)
    assert not any("SET NOT NULL" in s for s in statements)
    assert not any("UPDATE" in s for s in statements)  # already NOT NULL -> no backfill
    for name, intended in _INTENDED_UNIQUE_CONSTRAINTS.items():
        assert f"DROP CONSTRAINT IF EXISTS {name}" in " ".join(statements)
        assert (f"ADD CONSTRAINT {name} UNIQUE ({intended[0]}, {intended[1]})"
                in " ".join(statements))


def test_column_present_but_nullable_backfills_then_sets_not_null() -> None:
    plan = _lineage_convergence_plan(
        has_lineage_column=True,
        lineage_column_nullable=True,
        unique_constraints={
            "uq_m67_coordinator_release": ("authorization_release_id",),
            "uq_m67_coordinator_work_item": ("work_item_identity_sha256",),
        },
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    statements = _sql(plan)
    assert not any("ADD COLUMN" in s for s in statements)
    assert any("SET repair_attempt_lineage_sha256 = :legacy" in s for s in statements)
    assert any("SET NOT NULL" in s for s in statements)


# --- 3. one composite / one legacy -> only the missing invariant converges -----

def test_only_the_still_legacy_constraint_is_rebuilt() -> None:
    plan = _lineage_convergence_plan(
        has_lineage_column=True,
        lineage_column_nullable=False,
        unique_constraints={
            "uq_m67_coordinator_release": _RELEASE_COMPOSITE,  # already correct
            "uq_m67_coordinator_work_item": ("work_item_identity_sha256",),  # legacy
        },
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    statements = " ".join(_sql(plan))
    assert "uq_m67_coordinator_release" not in statements
    assert "DROP CONSTRAINT IF EXISTS uq_m67_coordinator_work_item" in statements
    assert ("ADD CONSTRAINT uq_m67_coordinator_work_item UNIQUE "
            "(work_item_identity_sha256, repair_attempt_lineage_sha256)") in statements


# --- 4. fully migrated schema -> strict no-op ---------------------------------

def test_fully_converged_schema_is_a_strict_no_op() -> None:
    plan = _lineage_convergence_plan(
        has_lineage_column=True,
        lineage_column_nullable=False,
        unique_constraints={
            "uq_m67_coordinator_release": _RELEASE_COMPOSITE,
            "uq_m67_coordinator_work_item": _WORK_ITEM_COMPOSITE,
        },
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    assert plan == []


def test_sqlite_create_all_schema_needs_no_migration(tmp_path) -> None:
    repo = SqlAlchemyCoordinatorRepository(f"sqlite:///{tmp_path / 'c.db'}")
    repo.initialize()
    repo.initialize()  # idempotent
    inspector = inspect(repo.engine)
    constraints = {
        c["name"]: tuple(c["column_names"])
        for c in inspector.get_unique_constraints("m67_sampled_slot_coordinator_runs")
    }
    assert constraints["uq_m67_coordinator_release"] == _RELEASE_COMPOSITE
    assert constraints["uq_m67_coordinator_work_item"] == _WORK_ITEM_COMPOSITE
    assert repo.verify_repair_attempt_lineage_schema()["converged"] is True


# --- 5. backfill only touches NULL rows --------------------------------------

def test_backfill_statement_only_targets_null_lineage_rows() -> None:
    plan = _lineage_convergence_plan(
        has_lineage_column=False,
        lineage_column_nullable=True,
        unique_constraints={},
        legacy_lineage=LEGACY_ATTEMPT_LINEAGE_SHA256,
    )
    updates = [(s, p) for s, p in plan if s.startswith("UPDATE")]
    assert len(updates) == 1
    statement, params = updates[0]
    assert statement.endswith("WHERE repair_attempt_lineage_sha256 IS NULL")
    assert params == {"legacy": LEGACY_ATTEMPT_LINEAGE_SHA256}
    # No unconditional UPDATE / DELETE that could mutate historical rows.
    assert not any(s.startswith("DELETE") for s in _sql(plan))
    assert all("IS NULL" in s for s in _sql(plan) if s.startswith("UPDATE"))


# --- 6. two different-lineage attempts for the same release coexist ----------

def _binding(**over) -> CoordinatorRunBinding:
    base = CoordinatorRunBinding(
        coordinator_run_id=UUID("30000000-0000-4000-8000-000000000001"),
        authorization_release_id=_RELEASE,
        ordered_package_sha256="3" * 64,
        slot_number=1,
        business_identity="903 HVAC",
        exact_hostname="903hvac.com",
        work_item_identity_sha256="4" * 64,
        activation_sha256="5" * 64,
        runtime_revision="sha256:" + "a" * 64,
        created_at=NOW,
        repair_attempt_lineage_sha256="6" * 64,
    )
    return replace(base, **over)


def test_two_repair_attempts_same_release_different_lineage_coexist(tmp_path) -> None:
    repo = SqlAlchemyCoordinatorRepository(f"sqlite:///{tmp_path / 'coexist.db'}")
    repo.initialize()
    first = _binding()
    assert repo.create_or_get(first)[1] is True
    repo.mark_terminal(first.coordinator_run_id, "M1_RESEARCH_FAILED", NOW)

    second = _binding(
        coordinator_run_id=UUID("30000000-0000-4000-8000-000000000002"),
        repair_attempt_lineage_sha256="7" * 64,
    )
    binding, created = repo.create_or_get(second)
    assert created is True
    assert binding.coordinator_run_id == second.coordinator_run_id
    # Prior terminal attempt is untouched.
    assert repo.create_or_get(first)[1] is False


# --- 7. duplicate same-lineage attempt stays idempotent / rejected on divergence

def test_duplicate_same_lineage_attempt_is_idempotent_and_divergence_rejected(
    tmp_path,
) -> None:
    repo = SqlAlchemyCoordinatorRepository(f"sqlite:///{tmp_path / 'dup.db'}")
    repo.initialize()
    binding = _binding()
    assert repo.create_or_get(binding)[1] is True

    again, created = repo.create_or_get(binding)
    assert created is False
    assert again == binding

    diverged = replace(binding, activation_sha256="0" * 64)
    with pytest.raises(ValueError, match="differs from immutable run"):
        repo.create_or_get(diverged)


# --- PostgreSQL end-to-end convergence (opt-in) -----------------------------

_PG_URL = os.environ.get("OPINTEL_TEST_POSTGRES_URL")


@pytest.mark.skipif(not _PG_URL, reason="set OPINTEL_TEST_POSTGRES_URL for PostgreSQL convergence")
def test_postgres_latent_partial_schema_converges_and_verifies() -> None:
    engine = create_engine(_PG_URL, future=True)
    table = "m67_sampled_slot_coordinator_runs"
    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        # Reproduce the latent-partial production state: the marker column exists
        # but the uniqueness constraints are still legacy single-column.
        connection.execute(text(
            f"CREATE TABLE {table} ("
            "coordinator_run_id VARCHAR(36) PRIMARY KEY,"
            "authorization_release_id VARCHAR(36) NOT NULL,"
            "repair_attempt_lineage_sha256 VARCHAR(64),"
            "ordered_package_sha256 VARCHAR(64) NOT NULL,"
            "slot_number INTEGER NOT NULL,"
            "business_identity VARCHAR(200) NOT NULL,"
            "exact_hostname VARCHAR(253) NOT NULL,"
            "work_item_identity_sha256 VARCHAR(64) NOT NULL,"
            "activation_sha256 VARCHAR(64) NOT NULL,"
            "runtime_revision VARCHAR(80) NOT NULL,"
            "state VARCHAR(32) NOT NULL,"
            "terminal_reason VARCHAR(120),"
            "created_at TIMESTAMPTZ NOT NULL,"
            "updated_at TIMESTAMPTZ NOT NULL,"
            "CONSTRAINT uq_m67_coordinator_release UNIQUE (authorization_release_id),"
            "CONSTRAINT uq_m67_coordinator_work_item UNIQUE (work_item_identity_sha256))"
        ))
        connection.execute(text(
            f"INSERT INTO {table} VALUES ('c0','r0',NULL,'p',1,'b','h','w0','a0','x','TERMINAL',"
            "'M1_RESEARCH_FAILED', now(), now())"
        ))
    try:
        repo = SqlAlchemyCoordinatorRepository(_PG_URL)
        repo.initialize()
        verdict = repo.verify_repair_attempt_lineage_schema()
        assert verdict["converged"] is True
        assert tuple(verdict["observed_unique_constraints"]["uq_m67_coordinator_release"]) == (
            "authorization_release_id",
            "repair_attempt_lineage_sha256",
        )
        assert tuple(verdict["observed_unique_constraints"]["uq_m67_coordinator_work_item"]) == (
            "work_item_identity_sha256",
            "repair_attempt_lineage_sha256",
        )
        # Historical row survived; its NULL lineage was backfilled with the legacy value.
        with engine.connect() as connection:
            row = connection.execute(text(
                f"SELECT repair_attempt_lineage_sha256, terminal_reason FROM {table} "
                "WHERE coordinator_run_id = 'c0'"
            )).one()
        assert row[0] == LEGACY_ATTEMPT_LINEAGE_SHA256
        assert row[1] == "M1_RESEARCH_FAILED"
        # Re-running is a strict no-op.
        repo.initialize()
        assert repo.verify_repair_attempt_lineage_schema()["converged"] is True
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
