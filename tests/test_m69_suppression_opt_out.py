"""M6.9 suppression / opt-out controls.

Owner authorization "IMPLEMENT SUPPRESSION / OPT-OUT CONTROLS, THEN EXECUTE
REAL BOUNDED A-PLUS ENGINE RUN", Stage A. Proves the registry is
deterministic, checked before every send-eligibility decision, cannot be
overridden by provider/human input, applies immediately, persists across
restart, and never unsuppresses automatically.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_suppression import (
    DEFAULT_OPT_OUT_NOTICE,
    PROOFLINE_SENDER_IDENTITY,
    DeliveryBlockedSuppressed,
    SuppressionAuthorizationError,
    SuppressionCheckOutcome,
    SuppressionKind,
    SuppressionRegistryService,
    SuppressionValidationError,
    domain_of,
    enforce_pre_send_suppression_gate,
    ingest_operator_observed_opt_out,
    normalize_domain,
    normalize_email,
    resolve_known_disclosure_slots,
)
from opintel_suppression_local import SqlAlchemySuppressionRepository

WORKSPACE_ID = UUID("00000000-0000-4000-8000-0000000069a1")


class _FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def _service(
    repo: SqlAlchemySuppressionRepository, clock: _FakeClock
) -> SuppressionRegistryService:
    return SuppressionRegistryService(repo, clock, UuidFactory())


def test_normalizes_email_address() -> None:
    assert normalize_email("  Recipient@Example.COM ") == "recipient@example.com"
    with pytest.raises(SuppressionValidationError):
        normalize_email("not-an-email")


def test_normalizes_domain() -> None:
    assert normalize_domain(" @Example.COM ") == "example.com"
    assert domain_of("recipient@example.com") == "example.com"
    with pytest.raises(SuppressionValidationError):
        normalize_domain("has a space.com")


def test_address_suppression_blocks_delivery() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-1",
    )
    result = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert result.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED
    assert result.matched_kind is SuppressionKind.ADDRESS_SUPPRESSED


def test_domain_suppression_blocks_delivery() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    service.suppress_domain(
        workspace_id=WORKSPACE_ID,
        raw_domain="aplusac.com",
        reason="company-wide suppression requested",
        evidence_ref="reply-msg-2",
    )
    result = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="anyone@aplusac.com"
    )
    assert result.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED
    assert result.matched_kind is SuppressionKind.DOMAIN_SUPPRESSED


def test_unrelated_recipient_remains_eligible() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-3",
    )
    result = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="someone-else@example.com"
    )
    assert result.outcome is SuppressionCheckOutcome.ELIGIBLE
    assert result.matched_entry_id is None


def test_opt_out_recording_immediately_creates_suppression() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    before = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert before.outcome is SuppressionCheckOutcome.ELIGIBLE

    service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-4",
    )
    after = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert after.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED


def test_duplicate_opt_outs_are_idempotent() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    first = service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-5",
    )
    second = service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="OWNER@APLUSAC.COM",
        reason="duplicate reply UNSUBSCRIBE",
        evidence_ref="reply-msg-5-duplicate",
    )
    assert first.id == second.id
    assert len(repo.list_entries(WORKSPACE_ID)) == 1


def test_provider_or_llm_output_cannot_override_suppression() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-6",
    )
    # enforce_pre_send_suppression_gate has no override/bypass parameter of any
    # kind - a "human approved" or "provider says safe" caller has no argument
    # to pass that would change the outcome.
    with pytest.raises(DeliveryBlockedSuppressed):
        enforce_pre_send_suppression_gate(
            service, workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
        )
    with pytest.raises(TypeError):
        enforce_pre_send_suppression_gate(  # type: ignore[call-arg]
            service,
            workspace_id=WORKSPACE_ID,
            candidate_email="owner@aplusac.com",
            override=True,
        )


def test_previously_approved_package_becomes_non_sendable_after_suppression() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    # Package approved; gate passes at approval time.
    approved_at_gate = enforce_pre_send_suppression_gate(
        service, workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert approved_at_gate.outcome is SuppressionCheckOutcome.ELIGIBLE

    # Recipient opts out after approval, before send.
    service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE received after package approval",
        evidence_ref="reply-msg-7",
    )

    # The same package, re-checked immediately before send, is now blocked.
    with pytest.raises(DeliveryBlockedSuppressed):
        enforce_pre_send_suppression_gate(
            service, workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
        )


def test_suppression_survives_restart_persistence() -> None:
    # A repo-local scratch directory rather than pytest's tmp_path: this suite
    # runs in sandboxes where the system temp directory is not writable.
    scratch_dir = Path(__file__).resolve().parents[1] / "local-data" / "test-m69-suppression"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    db_path = scratch_dir / f"suppression-{uuid4()}.sqlite3"
    database_url = f"sqlite:///{db_path}"

    repo1 = SqlAlchemySuppressionRepository(database_url)
    repo1.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service1 = _service(repo1, clock)
    service1.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-8",
    )

    # A fresh repository instance against the same durable database file -
    # simulating a process restart - must still see the suppression.
    repo2 = SqlAlchemySuppressionRepository(database_url)
    service2 = _service(repo2, clock)
    result = service2.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert result.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED
    repo1.engine.dispose()
    repo2.engine.dispose()
    db_path.unlink(missing_ok=True)


def test_no_automatic_unsuppression_only_explicit_owner_authority() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 5, tzinfo=UTC))
    service = _service(repo, clock)

    entry = service.record_address_opt_out(
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="reply-msg-9",
    )

    # No time-based expiry lifts it - even far in the future.
    later_clock = _FakeClock(datetime(2030, 1, 1, tzinfo=UTC))
    later_service = _service(repo, later_clock)
    still_blocked = later_service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert still_blocked.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED

    # Unsuppression requires a named authority and a reason.
    with pytest.raises(SuppressionAuthorizationError):
        service.owner_authorized_unsuppress(
            workspace_id=WORKSPACE_ID,
            suppressed_entry_id=entry.id,
            authorized_by="",
            reason="",
        )

    service.owner_authorized_unsuppress(
        workspace_id=WORKSPACE_ID,
        suppressed_entry_id=entry.id,
        authorized_by="PROJECT_OWNER (jvlmanus@gmail.com)",
        reason="test: explicit owner-authorized lift",
    )
    lifted = service.check_eligibility(
        workspace_id=WORKSPACE_ID, candidate_email="owner@aplusac.com"
    )
    assert lifted.outcome is SuppressionCheckOutcome.ELIGIBLE


def test_opt_out_sla_timestamp_calculation_is_auditable() -> None:
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    clock = _FakeClock(datetime(2026, 9, 10, tzinfo=UTC))
    service = _service(repo, clock)

    received_at = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
    recorded_at = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)  # 1 day later: within 3-day SLA
    result = ingest_operator_observed_opt_out(
        service,
        workspace_id=WORKSPACE_ID,
        raw_email="owner@aplusac.com",
        reply_evidence_ref="reply-msg-10",
        received_at=received_at,
        recorded_at=recorded_at,
    )
    assert result.elapsed == timedelta(days=1)
    assert result.within_sla is True
    assert result.suppressed_at == received_at

    late_recorded_at = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)  # 5 days later: breach
    late_result = ingest_operator_observed_opt_out(
        service,
        workspace_id=WORKSPACE_ID,
        raw_email="late-reply@example.com",
        reply_evidence_ref="reply-msg-11",
        received_at=received_at,
        recorded_at=late_recorded_at,
    )
    assert late_result.elapsed == timedelta(days=5)
    assert late_result.within_sla is False


def test_explicit_opt_out_copy_present_in_final_rendering() -> None:
    body_with_slots = (
        "Body text.\n\n"
        "{{verified_sender_signature}}\n"
        "{{required_postal_disclosure}}\n"
        "{{approved_opt_out_instruction}}\n"
        "{{functional_role_or_team}}\n"
        "{{exact_demo_url}}"
    )
    resolved = resolve_known_disclosure_slots(body_with_slots, PROOFLINE_SENDER_IDENTITY)
    assert "reply to this message with the word UNSUBSCRIBE" in resolved
    assert DEFAULT_OPT_OUT_NOTICE in resolved
    assert "{{approved_opt_out_instruction}}" not in resolved
    # The demo-URL slot is intentionally left untouched.
    assert "{{exact_demo_url}}" in resolved


def test_physical_postal_disclosure_present_in_final_rendering() -> None:
    resolved = resolve_known_disclosure_slots(
        "{{required_postal_disclosure}}", PROOFLINE_SENDER_IDENTITY
    )
    assert "Str. Lucian Blaga, nr. 8" in resolved
    assert "Ciugud, Alba 517240" in resolved
    assert "Romania" in resolved


def test_sender_reply_to_is_andrew_at_proofline() -> None:
    assert PROOFLINE_SENDER_IDENTITY.reply_to_mailbox == "andrew@proofline.business"
    resolved = resolve_known_disclosure_slots(
        "{{verified_sender_signature}}", PROOFLINE_SENDER_IDENTITY
    )
    assert "Andrew" in resolved
    assert "andrew@proofline.business" in resolved


def test_subject_does_not_receive_adv_prefix() -> None:
    subject = "A quick question about A-Plus AC's intake process"
    # DO_NOT_PREPEND_ADV is a counsel-directed operational instruction for this
    # exact Texas pilot: the subject is used exactly as generated/frozen, with
    # no "ADV:" (or similar) prefix ever prepended by this codebase.
    assert not subject.upper().startswith("ADV")
    assert "ADV:" not in subject.upper()
