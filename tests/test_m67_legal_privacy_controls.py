from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opintel_shadow.compliance_application import (
    _EMAIL as _RE_EMAIL,
)
from opintel_shadow.compliance_application import (
    _PHONE as _RE_PHONE,
)
from opintel_shadow.compliance_application import (
    Chapter521IncidentService,
    PhaseOneMinimizer,
    approved_phase_one_retention_policy,
    evaluate_per_host_review,
)
from opintel_shadow.compliance_domain import (
    AuthorityVerification,
    CaptureDisposition,
    HostReviewState,
    IncidentAssessment,
    IncidentWorkflowState,
    PhaseOneDataClass,
    StatutoryAuthority,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 21, 12, tzinfo=UTC)


def _authorities() -> tuple[StatutoryAuthority, ...]:
    payload = json.loads(
        (
            ROOT / "docs/readiness/m6.7-authorization/texas-statutory-provenance-2026-08-21.json"
        ).read_text(encoding="utf-8")
    )
    retrieved_at = datetime.fromisoformat(payload["retrieved_at"])
    return tuple(
        StatutoryAuthority(
            authority_id=item["authority_id"],
            official_url=item["official_url"],
            section=item["section"],
            subsection=item["subsection"],
            retrieved_at=retrieved_at,
            proposition=item["proposition"],
            verification=AuthorityVerification(item["verification"]),
        )
        for item in payload["authorities"]
    )


def test_ephemeral_raw_body_is_minimized_without_durable_raw_retention() -> None:
    raw = b"""<html><head><title>Lone Star Commercial HVAC</title></head><body>
      <h1>Commercial HVAC service across Texas</h1>
      <p>Businesses may request a service estimate online.</p>
      <p>Email dispatch@example.com or call (512) 555-0199.</p>
      <p>Unrelated biography and favorite lunch details.</p>
    </body></html>"""
    result = PhaseOneMinimizer().minimize(
        source_uri="https://synthetic.invalid/",
        captured_at=NOW,
        raw_body=raw,
        required_evidence_markers=("Commercial HVAC", "Texas", "request"),
    )
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    assert not result.raw_body_retained
    assert result.raw_content_sha256
    assert raw.decode() not in result.model_dump_json()
    assert "dispatch@example.com" not in (result.minimized_text or "")
    assert "512" not in (result.minimized_text or "")
    assert result.removed_email_count == 1
    assert result.removed_phone_count == 1
    assert "Commercial HVAC" in (result.minimized_text or "")
    assert "favorite lunch" not in (result.minimized_text or "")


def test_structured_contact_and_person_blocks_cannot_enter_durable_capture() -> None:
    raw = b"""<html><body><h1>Texas Commercial HVAC</h1>
      <p>Request an estimate for your facility.</p>
      <section class='staff contact-card'><h2>Jane Technician</h2><p>jane@example.com</p></section>
      <script type='application/ld+json'>{"@type":"ContactPoint","telephone":"5125550100"}</script>
    </body></html>"""
    result = PhaseOneMinimizer().minimize(
        source_uri="https://synthetic.invalid/services",
        captured_at=NOW,
        raw_body=raw,
        required_evidence_markers=("Texas", "Commercial HVAC", "Request"),
    )
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    assert result.removed_structured_contact_blocks >= 2
    serialized = result.model_dump_json()
    assert "Jane Technician" not in serialized
    assert "jane@example.com" not in serialized
    assert "5125550100" not in serialized
    assert not result.person_contact_projection_allowed


def test_review_artifact_can_bind_only_a_redacted_minimized_excerpt() -> None:
    minimizer = PhaseOneMinimizer()
    capture = minimizer.minimize(
        source_uri="https://synthetic.invalid/request",
        captured_at=NOW,
        raw_body=(
            b"<h1>Texas Commercial HVAC</h1><p>Businesses can request an estimate.</p>"
            b"<p>dispatch@example.com</p>"
        ),
        required_evidence_markers=("Texas", "Commercial HVAC", "request"),
    )
    review = minimizer.build_review_artifact(
        review_id="synthetic-review-001",
        capture=capture,
        evidence_locator="minimized:text-line:2",
        excerpt="Businesses can request an estimate.",
    )
    assert review.minimized_capture_sha256 == capture.minimized_content_sha256
    assert review.evidence_locator == "minimized:text-line:2"
    assert not review.raw_source_body_retained
    assert not review.person_contact_fields_present
    assert "dispatch@example.com" not in review.model_dump_json()


def test_unsafe_minimization_quarantines_without_page_content() -> None:
    raw = b"<section class='staff'><p>Texas Commercial HVAC</p></section>"
    result = PhaseOneMinimizer().minimize(
        source_uri="https://synthetic.invalid/team",
        captured_at=NOW,
        raw_body=raw,
        required_evidence_markers=("Commercial HVAC",),
    )
    assert result.disposition is CaptureDisposition.QUARANTINE_AND_REVIEW
    assert result.minimized_text is None
    assert result.minimized_content_sha256 is None
    assert result.quarantine_reasons == ("REQUIRED_EVIDENCE_NOT_SAFELY_PRESERVED:Commercial HVAC",)
    assert raw.decode() not in result.model_dump_json()


# --- Repair #5: deterministic block-level minimization -------------------------

def _contains_contact(text: str) -> bool:
    return bool(_RE_EMAIL.search(text) or _RE_PHONE.search(text))


def _minimize(raw: bytes, markers: tuple[str, ...], path: str = "p"):
    return PhaseOneMinimizer().minimize(
        source_uri=f"https://synthetic.invalid/{path}",
        captured_at=NOW,
        raw_body=raw,
        required_evidence_markers=markers,
    )


def test_void_elements_do_not_strand_the_parser_and_discard_evidence() -> None:
    # A skip subtree with unbalanced void tags (the real Slot 01 defect shape):
    # the parser must recover and still see the business content after it.
    raw = (
        b"<html><head><style>.x{}</style><link rel=x><meta charset=utf-8></head><body>"
        b"<svg><path><rect><use></svg>"
        b"<div><img src=a><br><img src=b><br><input type=text></div>"
        b"<h1>Commercial heating and cooling service in the region</h1>"
        b"<p>Air conditioning repair and furnace maintenance for the facility.</p>"
        b"</body></html>"
    )
    result = _minimize(raw, ("heating", "cooling", "air conditioning", "service", "commercial"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    text = result.minimized_text or ""
    for marker in ("heating", "cooling", "air conditioning", "service", "commercial"):
        assert marker in text.casefold()


def test_service_text_with_phone_keeps_the_text_and_removes_the_phone() -> None:
    raw = b"<p>Call (512) 555-0142 for same-day air conditioning service.</p>"
    result = _minimize(raw, ("air conditioning", "service"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    text = result.minimized_text or ""
    assert "air conditioning service" in text.casefold()
    assert "512" not in text and "555" not in text
    assert result.removed_phone_count == 1
    assert not _contains_contact(text)


def test_hvac_statement_with_email_keeps_evidence_and_removes_the_email() -> None:
    raw = b"<p>Our HVAC company installs commercial heating systems. sales@vendor.example</p>"
    result = _minimize(raw, ("hvac", "commercial", "heating", "company"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    text = result.minimized_text or ""
    assert "hvac company installs commercial heating" in text.casefold()
    assert "sales@vendor.example" not in text
    assert result.removed_email_count == 1


def test_request_an_estimate_mechanism_survives_but_not_the_contact_value() -> None:
    raw = (
        b"<form id='small-contact-form'><label>Name</label><label>Phone</label>"
        b"<button>Request an Estimate</button></form>"
        b"<p>Reach dispatch at hello@vendor.example for a quote.</p>"
    )
    result = _minimize(raw, ("request", "estimate", "quote"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    text = (result.minimized_text or "").casefold()
    assert "request an estimate" in text
    assert "hello@vendor.example" not in text
    assert "quote" in text  # the "for a quote" line survives without the email


def test_person_card_is_dropped_without_contaminating_unrelated_business_evidence() -> None:
    raw = (
        b"<h1>Commercial HVAC service for the facility</h1>"
        b"<div class='team-member vcard'><h3>Alex Roe</h3><p>Owner</p>"
        b"<p>alex.roe@vendor.example</p><p>(512) 555-0170</p></div>"
        b"<p>Financing available for heating and cooling installations.</p>"
    )
    result = _minimize(raw, ("commercial", "service", "heating", "cooling"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    serialized = result.model_dump_json()
    assert "Alex Roe" not in serialized
    assert "alex.roe@vendor.example" not in serialized
    assert "555-0170" not in serialized and "512" not in serialized
    text = (result.minimized_text or "").casefold()
    assert "commercial hvac service" in text
    assert "heating and cooling installations" in text
    assert result.removed_structured_contact_blocks >= 1


def test_mixed_contact_fragment_without_business_meaning_is_dropped_not_reconstructed() -> None:
    # A fragment that is only a contact stub after redaction must not be kept.
    raw = (
        b"<h1>Commercial heating service</h1>"
        b"<p>Owner Sam Poe, sam@vendor.example, (512) 555-0180</p>"
    )
    result = _minimize(raw, ("commercial", "heating", "service"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    text = result.minimized_text or ""
    assert "Sam Poe" not in text
    assert "sam@vendor.example" not in text and "512" not in text
    assert "commercial heating service" in text.casefold()


def test_inseparable_page_where_all_evidence_lives_in_contact_blocks_stays_quarantined() -> None:
    raw = (
        b"<div class='vcard'><p>Commercial heating and cooling</p>"
        b"<p>info@vendor.example</p></div>"
    )
    result = _minimize(raw, ("commercial", "heating", "cooling"))
    assert result.disposition is CaptureDisposition.QUARANTINE_AND_REVIEW
    assert result.minimized_text is None
    assert all(
        r.startswith("REQUIRED_EVIDENCE_NOT_SAFELY_PRESERVED:")
        for r in result.quarantine_reasons
    )


def test_residual_contact_value_in_minimized_text_fails_closed() -> None:
    # An exotic phone shape the redaction misses but a required-marker line keeps.
    raw = b"<p>Commercial HVAC service, dial 5 1 2 5 5 5 0 1 9 0 today.</p>"
    result = PhaseOneMinimizer().minimize(
        source_uri="https://synthetic.invalid/x", captured_at=NOW, raw_body=raw,
        required_evidence_markers=("commercial", "service"),
    )
    if result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE:
        assert not _contains_contact(result.minimized_text or "")
    else:
        assert result.disposition is CaptureDisposition.QUARANTINE_AND_REVIEW


def test_empty_safe_evidence_fails_closed() -> None:
    raw = b"<div class='contact-info'><span class='phone'>(512) 555-0100</span></div>"
    result = _minimize(raw, ())
    assert result.disposition is CaptureDisposition.QUARANTINE_AND_REVIEW
    assert "SAFE_EVIDENCE_EMPTY" in result.quarantine_reasons


def test_minimization_is_byte_identical_for_identical_input() -> None:
    raw = (
        b"<h1>Commercial HVAC service</h1><p>Heating and cooling for the facility.</p>"
        b"<p>Call (512) 555-0133.</p>"
    )
    markers = ("commercial", "hvac", "service", "heating", "cooling")
    a = _minimize(raw, markers)
    b = _minimize(raw, markers)
    assert a.minimized_text == b.minimized_text
    assert a.minimized_content_sha256 == b.minimized_content_sha256
    assert a.raw_content_sha256 == b.raw_content_sha256


def test_provenance_survives_minimization() -> None:
    raw = b"<h1>Commercial HVAC heating service</h1>"
    result = _minimize(raw, ("commercial", "hvac", "heating", "service"))
    assert result.disposition is CaptureDisposition.DURABLE_MINIMIZED_CAPTURE
    import hashlib as _h

    assert result.raw_content_sha256 == _h.sha256(raw).hexdigest()
    minimized_bytes = (result.minimized_text or "").encode()
    assert result.minimized_content_sha256 == _h.sha256(minimized_bytes).hexdigest()
    assert result.minimizer_version == "phase1-minimizer@2"
    assert result.source_uri == "https://synthetic.invalid/p"


def test_retention_policy_has_exact_periods_effective_maxima_and_destruction() -> None:
    policy = approved_phase_one_retention_policy()
    by_class = {item.data_class: item for item in policy.rules}
    assert by_class[PhaseOneDataClass.EVIDENCE_EXCERPT_LOCATOR].retention_days == 90
    assert (
        by_class[PhaseOneDataClass.EVIDENCE_EXCERPT_LOCATOR].maximum_effective_retention_days == 120
    )
    assert (
        by_class[PhaseOneDataClass.SUCCESSFUL_MINIMIZED_SNAPSHOT].maximum_effective_retention_days
        == 120
    )
    assert by_class[PhaseOneDataClass.FAILED_ABORTED_CAPTURE].maximum_effective_retention_days == 60
    assert by_class[PhaseOneDataClass.HUMAN_REVIEW_RECORD].redacted_excerpts_only
    assert all(item.destruction_methods for item in policy.rules)
    assert all(
        item.applies_to_stores
        == (
            "primary",
            "replicas",
            "object_versions",
            "backups",
            "derived_stores",
        )
        for item in policy.rules
    )


def test_tombstone_contract_excludes_url_and_content() -> None:
    policy = approved_phase_one_retention_policy()
    assert not policy.tombstone_source_uri_allowed
    assert "source_uri" not in policy.tombstone_allowed_fields
    assert "content" not in policy.tombstone_allowed_fields
    assert set(policy.tombstone_allowed_fields) == {
        "artifact_hash",
        "internal_artifact_id",
        "data_class",
        "deletion_reason_code",
        "deleted_at",
        "policy_revision",
    }


def test_verified_chapter_521_deadlines_bind_exact_authority() -> None:
    assessment = IncidentAssessment(
        incident_id="synthetic-incident-001",
        detected_at=NOW,
        detection_summary="synthetic unauthorized acquisition fixture",
        sensitive_information_maintained=True,
        breach_determined=True,
        breach_determined_at=NOW,
        affected_texas_residents=250,
        affected_subjects_determined=True,
        notification_required=True,
    )
    result = Chapter521IncidentService().evaluate(assessment, _authorities())
    assert result.state is IncidentWorkflowState.NOTIFICATION_DECISION_READY
    by_recipient = {item.recipient_class: item for item in result.deadlines}
    assert by_recipient["AFFECTED_INDIVIDUAL"].deadline_at == NOW + timedelta(days=60)
    assert by_recipient["AFFECTED_INDIVIDUAL"].authority_id == "TX-BC-521.053-B"
    assert by_recipient["TEXAS_ATTORNEY_GENERAL"].deadline_at == NOW + timedelta(days=30)
    assert by_recipient["TEXAS_ATTORNEY_GENERAL"].authority_id == "TX-BC-521.053-I"
    assert not result.external_notification_sent
    assert result.immutable_record_hash


def test_ag_rule_does_not_activate_below_statutory_threshold() -> None:
    assessment = IncidentAssessment(
        incident_id="synthetic-incident-002",
        detected_at=NOW,
        detection_summary="synthetic threshold fixture",
        sensitive_information_maintained=True,
        breach_determined=True,
        breach_determined_at=NOW,
        affected_texas_residents=249,
        affected_subjects_determined=True,
        notification_required=True,
    )
    result = Chapter521IncidentService().evaluate(assessment, _authorities())
    assert [item.recipient_class for item in result.deadlines] == ["AFFECTED_INDIVIDUAL"]


def test_unverified_or_missing_statutory_rule_fails_closed() -> None:
    assessment = IncidentAssessment(
        incident_id="synthetic-incident-003",
        detected_at=NOW,
        detection_summary="synthetic unresolved-authority fixture",
        sensitive_information_maintained=True,
        breach_determined=True,
        breach_determined_at=NOW,
        affected_texas_residents=250,
        affected_subjects_determined=True,
        notification_required=True,
    )
    authorities = tuple(item for item in _authorities() if item.authority_id != "TX-BC-521.053-I")
    result = Chapter521IncidentService().evaluate(assessment, authorities)
    assert result.state is IncidentWorkflowState.LEGAL_REVIEW_REQUIRED
    assert result.unresolved_rules == ("TEXAS_AG_NOTIFICATION_AUTHORITY_UNVERIFIED",)
    assert not result.external_notification_sent


def test_incomplete_incident_facts_fail_closed() -> None:
    assessment = IncidentAssessment(
        incident_id="synthetic-incident-004",
        detected_at=NOW,
        detection_summary="synthetic incomplete fixture",
        sensitive_information_maintained=None,
        breach_determined=None,
        breach_determined_at=None,
        affected_texas_residents=None,
        affected_subjects_determined=False,
        notification_required=None,
    )
    result = Chapter521IncidentService().evaluate(assessment, _authorities())
    assert result.state is IncidentWorkflowState.LEGAL_REVIEW_REQUIRED
    assert result.unresolved_rules == ("INCIDENT_FACTS_INCOMPLETE",)


def test_per_host_gate_blocks_unreviewed_and_materially_risky_hosts() -> None:
    pending = evaluate_per_host_review(
        source_id="FIRST_PARTY_RESEARCH::synthetic.invalid",
        exact_host="synthetic.invalid",
        reviewed_at=NOW,
        reviewer_actor_binding="OWNER_SUBJECT_PENDING_IDP_BINDING",
        terms_reviewed=False,
        robots_reviewed=True,
        access_restrictions_reviewed=True,
        automated_access_restrictions_reviewed=True,
        capture_storage_reuse_reviewed=True,
        unresolved_copyright_or_contract_issue=False,
        material_prohibition=False,
    )
    assert pending.state is HostReviewState.PENDING_PER_HOST_REVIEW
    blocked = evaluate_per_host_review(
        source_id="FIRST_PARTY_RESEARCH::blocked.invalid",
        exact_host="blocked.invalid",
        reviewed_at=NOW,
        reviewer_actor_binding="OWNER_SUBJECT_PENDING_IDP_BINDING",
        terms_reviewed=True,
        robots_reviewed=True,
        access_restrictions_reviewed=True,
        automated_access_restrictions_reviewed=True,
        capture_storage_reuse_reviewed=True,
        unresolved_copyright_or_contract_issue=True,
        material_prohibition=False,
    )
    assert blocked.state is HostReviewState.SOURCE_BLOCKED
    assert blocked.robots_is_technical_not_legal_authority


def test_per_host_gate_approves_only_complete_exact_host_review() -> None:
    approved = evaluate_per_host_review(
        source_id="FIRST_PARTY_RESEARCH::synthetic.invalid",
        exact_host="synthetic.invalid",
        reviewed_at=NOW,
        reviewer_actor_binding="OWNER_SUBJECT_PENDING_IDP_BINDING",
        terms_reviewed=True,
        robots_reviewed=True,
        access_restrictions_reviewed=True,
        automated_access_restrictions_reviewed=True,
        capture_storage_reuse_reviewed=True,
        unresolved_copyright_or_contract_issue=False,
        material_prohibition=False,
    )
    assert approved.state is HostReviewState.APPROVED


def test_role_decisions_preserve_human_separation_without_inventing_subjects() -> None:
    value = json.loads(
        (ROOT / "docs/readiness/m6.7-authorization/role-assignments.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["state"] == "APPROVED_PENDING_IDENTITY_BINDING"
    assert all(item["subject_ref"] is None for item in value["assignments"])
    by_role = {item["role"]: item["approved_actor_binding"] for item in value["assignments"]}
    assert by_role["OPPORTUNITY_REVIEWER"] == "OWNER_SUBJECT"
    assert by_role["INDEPENDENT_SECOND_REVIEWER"] == "PRIMARY_A_SUBJECT"
    assert by_role["QUALIFIED_LEGAL_REVIEWER"] == "EXTERNAL_ATTORNEY_A17_SUBJECT"
    assert by_role["PROJECT_OWNER"] != by_role["QUALIFIED_LEGAL_REVIEWER"]


def test_terraform_contains_no_forbidden_live_capability_or_secret_inputs() -> None:
    root = ROOT / "infra/terraform/phase1"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.tf"))
    prohibited = (
        "openai",
        "anthropic",
        "gemini",
        "playwright",
        "sendgrid",
        "twilio",
        "ses_email_identity",
        "calendar",
        "crm",
        "sender_credential",
        "delivery_credential",
    )
    assert not any(item in text.casefold() for item in prohibited)
    assert "default     = 0" in text
