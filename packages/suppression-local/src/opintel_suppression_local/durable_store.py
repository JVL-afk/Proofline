"""Durable suppression store wiring for the bounded A-Plus first-contact pilot.

The pilot's authoritative pre-send suppression check MUST run against a
persistent registry that survives a process restart - never an in-memory one.
This module is thin wiring over the existing ``SqlAlchemySuppressionRepository``
/ ``SuppressionRegistryService``; it adds no second suppression implementation
and no override path (``gate.enforce_pre_send_suppression_gate`` stays the only
pre-send gate and re-checks eligibility on every call).
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from opintel_m0.ports import Clock, IdentifierFactory
from opintel_suppression.application import SuppressionRegistryService

from opintel_suppression_local.persistence import SqlAlchemySuppressionRepository

# Fixed namespace for the one bounded A-Plus pilot. Stable across runs and
# restarts so a suppression written once is seen by every later pre-send check
# (a per-run random workspace id would silently query an empty namespace).
APLUS_PILOT_WORKSPACE_ID = UUID("a91b0000-0000-4000-8000-0000000006a9")

# Repo-relative location of the durable pilot registry, in the gitignored
# ``local-data`` tree (same convention as every other local store).
APLUS_PILOT_SUPPRESSION_DB_RELPATH = "local-data/aplus-pilot/suppression.db"


class InMemorySuppressionForRealSendError(RuntimeError):
    """Raised when a real-send suppression authority is handed a non-persistent
    (in-memory) database. There is no in-memory fallback for a real send."""


def require_persistent_database_url(database_url: str) -> str:
    """Return ``database_url`` unchanged if it names a persistent store; raise
    otherwise. An on-disk sqlite file or a postgres URL is accepted; a
    ``:memory:`` sqlite URL (or anything unrecognised) is refused."""
    url = database_url.strip()
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path in ("", ":memory:", "/:memory:"):
            raise InMemorySuppressionForRealSendError(
                "the A-Plus pilot pre-send suppression check requires a persistent "
                "database; an in-memory sqlite URL is refused"
            )
        return url
    if url.startswith("postgresql+psycopg://"):
        return url
    raise InMemorySuppressionForRealSendError(
        f"unsupported suppression database URL for a real send: {database_url!r}"
    )


def aplus_pilot_database_url(repo_root: Path) -> str:
    """The durable sqlite URL for the bounded A-Plus pilot registry."""
    db_path = (repo_root / APLUS_PILOT_SUPPRESSION_DB_RELPATH).resolve()
    return f"sqlite:///{db_path.as_posix()}"


def build_durable_suppression_service(
    *,
    database_url: str,
    clock: Clock,
    identifiers: IdentifierFactory,
) -> SuppressionRegistryService:
    """Build the one authoritative pre-send suppression authority for the pilot,
    backed by a persistent database. Fails closed if handed an in-memory URL."""
    url = require_persistent_database_url(database_url)
    repo = SqlAlchemySuppressionRepository(url)
    repo.initialize()
    return SuppressionRegistryService(repo, clock, identifiers)
