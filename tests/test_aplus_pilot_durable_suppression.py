"""A-Plus pilot durable-suppression wiring.

Owner authorization "ADDRESS PRIMARY_A PRE-APPROVAL FINDINGS AND PRODUCE
REVISED EXACT PACKAGE", section 1. PRIMARY_A flagged that the recipient-bound
pilot suppression check used a fresh in-memory registry. These tests prove the
pilot now binds the *persistent* suppression subsystem (no second
implementation): it survives a process restart, the send gate queries the same
durable authority, address/domain/person/company all fail closed, a suppression
written after package approval invalidates the package, and an in-memory URL is
refused outright for a real send.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_suppression import (
    DeliveryBlockedSuppressed,
    SuppressionRegistryService,
    enforce_pre_send_suppression_gate,
)
from opintel_suppression_local import (
    APLUS_PILOT_SUPPRESSION_DB_RELPATH,
    APLUS_PILOT_WORKSPACE_ID,
    InMemorySuppressionForRealSendError,
    aplus_pilot_database_url,
    build_durable_suppression_service,
    require_persistent_database_url,
)

ROOT = Path(__file__).resolve().parents[1]
_WS = APLUS_PILOT_WORKSPACE_ID


class _FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


_CLOCK = _FakeClock(datetime(2026, 9, 6, tzinfo=UTC))


def _fresh_db_url() -> str:
    # Repo-local scratch dir: the suite also runs in sandboxes where the system
    # temp directory is not writable.
    scratch = ROOT / "local-data" / "test-aplus-durable-suppression"
    scratch.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(scratch / f'db-{uuid4()}.sqlite3').as_posix()}"


def _service(url: str) -> SuppressionRegistryService:
    return build_durable_suppression_service(
        database_url=url, clock=_CLOCK, identifiers=UuidFactory()
    )


def test_require_persistent_database_url_refuses_in_memory() -> None:
    for bad in ("sqlite:///:memory:", "sqlite:///", "redis://x", "mysql://x"):
        with pytest.raises(InMemorySuppressionForRealSendError):
            require_persistent_database_url(bad)
    ok = f"sqlite:///{(ROOT / 'local-data' / 'x.db').as_posix()}"
    assert require_persistent_database_url(ok) == ok
    assert (
        require_persistent_database_url("postgresql+psycopg://u@h/db")
        == "postgresql+psycopg://u@h/db"
    )


def test_build_durable_suppression_service_refuses_in_memory() -> None:
    with pytest.raises(InMemorySuppressionForRealSendError):
        build_durable_suppression_service(
            database_url="sqlite:///:memory:", clock=_CLOCK, identifiers=UuidFactory()
        )


def test_aplus_pilot_database_url_is_a_persistent_file() -> None:
    url = aplus_pilot_database_url(ROOT)
    assert url.startswith("sqlite:///")
    assert url.endswith("suppression.db")
    assert APLUS_PILOT_SUPPRESSION_DB_RELPATH.replace("/", "") in url.replace("/", "")
    # never rejected as in-memory
    assert require_persistent_database_url(url) == url


def test_durable_service_persists_all_kinds_across_restart() -> None:
    url = _fresh_db_url()
    writer = _service(url)
    writer.record_address_opt_out(
        workspace_id=_WS,
        raw_email="victim@somehvac.example",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-1",
    )
    writer.suppress_domain(
        workspace_id=_WS, raw_domain="blockeddomain.example", reason="x", evidence_ref="e"
    )
    writer.suppress_person(workspace_id=_WS, person_key="person-xyz", reason="x", evidence_ref="e")
    writer.suppress_company(
        workspace_id=_WS, company_key="company-xyz", reason="x", evidence_ref="e"
    )

    # A brand-new service instance against the same file == a process restart.
    reader = _service(url)
    assert reader.check_eligibility(
        workspace_id=_WS, candidate_email="victim@somehvac.example"
    ).blocked
    assert reader.check_eligibility(
        workspace_id=_WS, candidate_email="anyone@blockeddomain.example"
    ).blocked
    assert reader.check_channel_blocked(
        workspace_id=_WS, person_key="person-xyz", company_key="c", channel="email"
    )
    assert reader.check_channel_blocked(
        workspace_id=_WS, person_key="p", company_key="company-xyz", channel="email"
    )
    # an unrelated recipient is still eligible
    assert not reader.check_eligibility(
        workspace_id=_WS, candidate_email="greg@aplusac.com"
    ).blocked


def test_pilot_send_gate_uses_same_durable_authority_and_fails_closed() -> None:
    url = _fresh_db_url()
    _service(url).record_address_opt_out(
        workspace_id=_WS,
        raw_email="greg@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-99",
    )
    gate_service = _service(url)  # fresh instance, same durable file
    with pytest.raises(DeliveryBlockedSuppressed):
        enforce_pre_send_suppression_gate(
            gate_service, workspace_id=_WS, candidate_email="greg@aplusac.com"
        )


def test_suppression_written_after_approval_invalidates_package() -> None:
    url = _fresh_db_url()
    service = _service(url)
    # "package approved" - the pre-send gate currently says eligible
    assert not enforce_pre_send_suppression_gate(
        service, workspace_id=_WS, candidate_email="greg@aplusac.com"
    ).blocked
    # an opt-out arrives afterwards
    service.record_address_opt_out(
        workspace_id=_WS,
        raw_email="greg@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-later",
    )
    # the very next gate call re-checks and blocks - approval is never cached
    with pytest.raises(DeliveryBlockedSuppressed):
        enforce_pre_send_suppression_gate(
            service, workspace_id=_WS, candidate_email="greg@aplusac.com"
        )


def test_package_script_binds_the_durable_store_not_in_memory() -> None:
    src = (ROOT / "scripts" / "run_m610_aplus_primary_a_package.py").read_text(encoding="utf-8")
    assert "build_durable_suppression_service" in src
    assert "aplus_pilot_database_url" in src
    assert "APLUS_PILOT_WORKSPACE_ID" in src
    assert "sqlite:///:memory:" not in src
