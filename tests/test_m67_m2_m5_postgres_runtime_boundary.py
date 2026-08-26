from __future__ import annotations

import pytest
from opintel_audit_local import SqlAlchemyAuditRepository
from opintel_demo_local import SqlAlchemyDemoRepository
from opintel_opportunity_local import SqlAlchemyOpportunityRepository
from opintel_outreach_local import SqlAlchemyOutreachRepository


@pytest.mark.parametrize(
    "repository_type",
    [
        SqlAlchemyOpportunityRepository,
        SqlAlchemyAuditRepository,
        SqlAlchemyDemoRepository,
        SqlAlchemyOutreachRepository,
    ],
)
def test_phase1_m2_m5_repository_accepts_locked_postgresql_driver_without_connecting(
    repository_type: type,
) -> None:
    repository = repository_type(
        "postgresql+psycopg://phase1:test@database.invalid:5432/opintel_phase1?sslmode=require"
    )
    try:
        assert repository.engine.url.drivername == "postgresql+psycopg"
    finally:
        repository.engine.dispose()


@pytest.mark.parametrize(
    "repository_type",
    [
        SqlAlchemyOpportunityRepository,
        SqlAlchemyAuditRepository,
        SqlAlchemyDemoRepository,
        SqlAlchemyOutreachRepository,
    ],
)
def test_m2_m5_repository_rejects_unapproved_database_scheme(repository_type: type) -> None:
    with pytest.raises(ValueError):
        repository_type("mysql://unapproved.invalid/database")
