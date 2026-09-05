"""M6.10 counsel-directed controls (owner authorization "M6.10 LEGAL SOURCE
ACTIVATION + LIVE A-PLUS RECIPIENT RESOLUTION", section 23).

No live vendor call anywhere in this file. Proves the encoded controls
match counsel's exact restrictions, not a generic AUTHORIZED collapse.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from opintel_contact_resolution import (
    AuthorityDomain,
    AuthorityLevel,
    CatchAllDetectionResult,
    Channel,
    ContactSourcePolicySettings,
    DataBrokerRegistryResult,
    DirectorySourceKind,
    DomainBounceMonitor,
    EligibilityDisposition,
    EmailKind,
    EmailVerificationState,
    IdentityConfidence,
    PatternCandidateSet,
    PersonCandidate,
    PhoneKind,
    PhoneReachability,
    RolePreVerification,
    RoleTier,
    SourceCategory,
    SourceConflict,
    TexasDataBrokerRegistryCheck,
    VendorComplianceChecklist,
    VerificationMethodClass,
    build_deletion_provenance_report,
    build_endpoint_evidence,
    classify_verification_method,
    counsel_controlled_authority_matrix,
    directory_source_permitted,
    enrichment_permitted_for_person,
    evaluate_email_eligibility,
    evaluate_phone_eligibility,
    is_corporate_domain,
    is_generic_role_mailbox,
    minimize_directory_result,
    pattern_email_eligibility_disposition,
    phone_execution_disposition,
    phone_kind_from_provenance,
    resolve_first_party_vs_linkedin_conflict,
    verification_is_expired,
)
from opintel_contact_resolution.domain import VerificationMethod
from opintel_contact_resolution.ranking import rank_channels

_NOW = datetime(2026, 9, 6, tzinfo=UTC)
_COMPANY = uuid4()


def _person() -> PersonCandidate:
    return PersonCandidate(
        id=uuid4(),
        company_id=_COMPANY,
        full_name="Greg Yamin",
        role_title_as_stated="President",
        role_tier=RoleTier.OWNER_PRESIDENT,
        role_evidence='aplusac.com/about-us/our-team/: "Greg Yamin - President"',
        source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE,
        source_url="https://www.aplusac.com/about-us/our-team/",
        source_content_sha256=None,
        observed_at=_NOW,
        first_party=True,
        identity_confidence=IdentityConfidence.HIGH,
    )


# --------------------------------------------------------------------------
# Counsel controls are recorded exactly - not a generic AUTHORIZED
# --------------------------------------------------------------------------


def test_counsel_controls_encoded_as_authorized_with_controls_not_generic_authorized() -> None:
    matrix = counsel_controlled_authority_matrix()
    for domain in (
        AuthorityDomain.PROFESSIONAL_DIRECTORY_AUTHORITY,
        AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY,
        AuthorityDomain.EMAIL_VERIFICATION_AUTHORITY,
        AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY,
        AuthorityDomain.PHONE_CONTACT_DATA_AUTHORITY,
    ):
        assert matrix.level(domain) is AuthorityLevel.AUTHORIZED_WITH_CONTROLS
        assert matrix.level(domain) is not AuthorityLevel.AUTHORIZED

    # Phone RESOLUTION is authorized-with-controls, but EXECUTION stays
    # blocked (section 11) - the two are structurally separate domains.
    assert matrix.level(AuthorityDomain.PHONE_CONTACT_DATA_AUTHORITY) is (
        AuthorityLevel.AUTHORIZED_WITH_CONTROLS
    )
    assert matrix.level(AuthorityDomain.PHONE_OUTBOUND_EXECUTION_AUTHORITY) is (
        AuthorityLevel.NOT_AUTHORIZED
    )


# --------------------------------------------------------------------------
# Role must pre-exist before enrichment (section 3)
# --------------------------------------------------------------------------


def test_role_must_pre_exist_before_enrichment_is_permitted() -> None:
    verified = RolePreVerification(
        role_confirmed=True, role_source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE
    )
    assert enrichment_permitted_for_person(verified) is True

    unverified = RolePreVerification(
        role_confirmed=False, role_source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE
    )
    assert enrichment_permitted_for_person(unverified) is False

    # A role sourced from enrichment itself must never originate targeting.
    from_enrichment = RolePreVerification(
        role_confirmed=True, role_source_category=SourceCategory.APPROVED_CONTACT_ENRICHMENT
    )
    assert enrichment_permitted_for_person(from_enrichment) is False


# --------------------------------------------------------------------------
# Consumer people-search / unauthorized vendor blocked (sections 2, 3)
# --------------------------------------------------------------------------


def test_consumer_people_search_source_is_blocked() -> None:
    assert directory_source_permitted(DirectorySourceKind.BUSINESS_PROFESSIONAL_DIRECTORY) is True
    for prohibited in (
        DirectorySourceKind.CONSUMER_PEOPLE_SEARCH,
        DirectorySourceKind.CONSUMER_PROFILE_DATABASE,
        DirectorySourceKind.AD_TECH,
        DirectorySourceKind.LOCATION_TRACKING,
    ):
        assert directory_source_permitted(prohibited) is False


def test_unauthorized_vendor_checklist_blocks_activation() -> None:
    incomplete = VendorComplianceChecklist(
        lawful_sourcing_warranty=True,
        per_record_provenance=True,
        # everything else missing
    )
    assert incomplete.satisfied is False
    assert "no_sensitive_categories" in incomplete.missing
    assert "texas_data_broker_registry_screened" in incomplete.missing

    complete = VendorComplianceChecklist(
        lawful_sourcing_warranty=True,
        per_record_provenance=True,
        no_sensitive_categories=True,
        no_minors=True,
        no_scraped_credentials=True,
        deletion_on_request=True,
        vendor_contractual_controls_or_indemnity=True,
        texas_data_broker_registry_screened=True,
    )
    assert complete.satisfied is True
    assert complete.missing == ()


def test_texas_data_broker_registration_is_not_proof_of_lawful_sourcing() -> None:
    check = TexasDataBrokerRegistryCheck(
        provider="ExampleVendor",
        registry_result=DataBrokerRegistryResult.REGISTERED,
        check_date=_NOW,
        source="Texas SOS Data Broker Registry",
        disposition="REGISTERED_BUT_VENDOR_TERMS_NOT_YET_ESTABLISHED_NOT_ACTIVATED",
    )
    # Registration alone is recorded as a fact, not a disposition - the
    # checklist above is the actual gate.
    assert check.registry_result is DataBrokerRegistryResult.REGISTERED
    assert "NOT_ACTIVATED" in check.disposition


# --------------------------------------------------------------------------
# Excess enrichment fields discarded before persistence (section 5)
# --------------------------------------------------------------------------


def test_excess_directory_fields_discarded_before_persistence() -> None:
    raw = {
        "name": "Greg Yamin",
        "title": "President",
        "employer": "A-Plus Air Conditioning & Home Solutions",
        "work_email": "greg@example-directory.invalid",
        "business_phone": "512-450-1980",
        "source": "Example Directory",
        "retrieval_date": "2026-09-06",
        "home_address": "123 Private Ln",
        "personal_mobile": "512-555-0100",
        "family_member": "Sharon Yamin (spouse)",
        "consumer_profile_id": "cp-12345",
    }
    minimized = minimize_directory_result(raw)
    assert "home_address" not in minimized
    assert "personal_mobile" not in minimized
    assert "family_member" not in minimized
    assert "consumer_profile_id" not in minimized
    assert minimized["work_email"] == "greg@example-directory.invalid"


# --------------------------------------------------------------------------
# Passive verification allowed, deceptive verification blocked (section 6)
# --------------------------------------------------------------------------


def test_passive_verification_methods_allowed_deceptive_blocked() -> None:
    assert classify_verification_method("syntax_validation") is (
        VerificationMethodClass.PASSIVE_ALLOWED
    )
    assert classify_verification_method("dns_mx") is VerificationMethodClass.PASSIVE_ALLOWED
    assert classify_verification_method("catch_all_detection") is (
        VerificationMethodClass.PASSIVE_ALLOWED
    )
    assert classify_verification_method("pretexting") is (
        VerificationMethodClass.DECEPTIVE_PROHIBITED
    )
    assert classify_verification_method("impersonation") is (
        VerificationMethodClass.DECEPTIVE_PROHIBITED
    )
    # Fail closed: unrecognized methods are never assumed passive.
    assert classify_verification_method("some_new_untested_method") is (
        VerificationMethodClass.DECEPTIVE_PROHIBITED
    )


# --------------------------------------------------------------------------
# 90-day verification expiry (section 6)
# --------------------------------------------------------------------------


def test_email_verification_expires_after_90_days() -> None:
    verified_at = _NOW
    still_fresh = verified_at + timedelta(days=89)
    assert verification_is_expired(verified_at, still_fresh) is False
    expired = verified_at + timedelta(days=91)
    assert verification_is_expired(verified_at, expired) is True


# --------------------------------------------------------------------------
# Pattern-only blocked / catch-all blocked / one-candidate enforcement
# (section 7)
# --------------------------------------------------------------------------


def test_pattern_only_still_blocked_without_verification() -> None:
    candidate_set = PatternCandidateSet(
        person_key="greg-yamin",
        all_generated=("greg@aplusac.com", "g.yamin@aplusac.com", "gyamin@aplusac.com"),
        chosen="greg@aplusac.com",
    )
    disposition = pattern_email_eligibility_disposition(
        candidate_set=candidate_set,
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=False, inconclusive=False),
        bounce_monitor=None,
        verification_method="pretexting",  # deceptive -> blocked regardless
    )
    assert disposition is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE


def test_catch_all_domain_or_inconclusive_verification_drops_candidate() -> None:
    candidate_set = PatternCandidateSet(
        person_key="greg-yamin", all_generated=("greg@aplusac.com",), chosen="greg@aplusac.com"
    )
    catch_all = pattern_email_eligibility_disposition(
        candidate_set=candidate_set,
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=True, inconclusive=False),
        bounce_monitor=None,
        verification_method="dns_mx",
    )
    assert catch_all is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE

    inconclusive = pattern_email_eligibility_disposition(
        candidate_set=candidate_set,
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=False, inconclusive=True),
        bounce_monitor=None,
        verification_method="dns_mx",
    )
    assert inconclusive is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE


def test_only_one_candidate_may_ever_advance_no_permutation_spraying() -> None:
    with pytest.raises(ValueError, match="chosen candidate"):
        PatternCandidateSet(
            person_key="greg-yamin",
            all_generated=("greg@aplusac.com",),
            chosen="not-in-the-generated-list@aplusac.com",
        )

    no_chosen = PatternCandidateSet(
        person_key="greg-yamin",
        all_generated=("greg@aplusac.com", "g.yamin@aplusac.com"),
        chosen=None,
    )
    assert no_chosen.is_single_candidate_selection is False
    result = pattern_email_eligibility_disposition(
        candidate_set=no_chosen,
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=False, inconclusive=False),
        bounce_monitor=None,
        verification_method="dns_mx",
    )
    assert result is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE


def test_personal_provider_and_generic_role_mailbox_domains_rejected() -> None:
    assert is_corporate_domain("aplusac.com", "aplusac.com") is True
    assert is_corporate_domain("gmail.com", "aplusac.com") is False
    assert is_generic_role_mailbox("info") is True
    assert is_generic_role_mailbox("sales") is True
    assert is_generic_role_mailbox("greg") is False

    generic_local_part = pattern_email_eligibility_disposition(
        candidate_set=PatternCandidateSet(
            person_key="greg-yamin", all_generated=("info@aplusac.com",), chosen="info@aplusac.com"
        ),
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=False, inconclusive=False),
        bounce_monitor=None,
        verification_method="dns_mx",
    )
    assert generic_local_part is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE


def test_bounce_rate_suspends_domain_pattern_use() -> None:
    healthy = DomainBounceMonitor(domain="aplusac.com", bounce_count=1, send_count=100)
    assert healthy.suspended is False
    over_threshold = DomainBounceMonitor(domain="aplusac.com", bounce_count=10, send_count=100)
    assert over_threshold.suspended is True

    disposition = pattern_email_eligibility_disposition(
        candidate_set=PatternCandidateSet(
            person_key="greg-yamin",
            all_generated=("greg@aplusac.com",),
            chosen="greg@aplusac.com",
        ),
        company_domain="aplusac.com",
        catch_all=CatchAllDetectionResult(is_catch_all_domain=False, inconclusive=False),
        bounce_monitor=over_threshold,
        verification_method="dns_mx",
    )
    assert disposition is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED


# --------------------------------------------------------------------------
# Professional-profile first-party conflict resolution (section 8)
# --------------------------------------------------------------------------


def test_first_party_company_source_wins_conflict_with_linkedin() -> None:
    conflicts = (
        SourceConflict(field_name="title", first_party_value="President", linkedin_value="CEO"),
        SourceConflict(
            field_name="employer",
            first_party_value="A-Plus Air Conditioning & Home Solutions",
            linkedin_value="A-Plus Energy Management",
        ),
    )
    resolved = resolve_first_party_vs_linkedin_conflict(conflicts)
    assert resolved["title"] == "President"
    assert resolved["employer"] == "A-Plus Air Conditioning & Home Solutions"


# --------------------------------------------------------------------------
# Main phone remains indirect / ambiguous mobile excluded (sections 9, 10)
# --------------------------------------------------------------------------


def test_main_phone_remains_indirect_never_claimed_as_direct() -> None:
    kind = phone_kind_from_provenance(company_assigned_proven=False, ambiguous=False)
    assert kind is PhoneKind.MAIN_BUSINESS_PHONE


def test_ambiguous_mobile_vs_direct_line_is_excluded() -> None:
    kind = phone_kind_from_provenance(company_assigned_proven=True, ambiguous=True)
    assert kind is None


def test_proven_company_assigned_direct_line_is_retained() -> None:
    kind = phone_kind_from_provenance(company_assigned_proven=True, ambiguous=False)
    assert kind is PhoneKind.DIRECT_BUSINESS_PHONE


# --------------------------------------------------------------------------
# Phone resolution never grants execution (section 11)
# --------------------------------------------------------------------------


def test_phone_resolution_does_not_grant_execution_authority() -> None:
    matrix = counsel_controlled_authority_matrix()
    resolved = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=matrix,
        suppressed=False,
    )
    assert resolved is EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT

    execution_gated = phone_execution_disposition(resolved, matrix)
    assert execution_gated is EligibilityDisposition.RESOLVED_BUT_EXECUTION_NOT_AUTHORIZED

    # Ranking treats this as a hard blocker - phone is never the
    # auto-recommended channel while execution authority is withheld.
    person = _person()
    evidence = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.PHONE,
        endpoint="512-450-1980",
        endpoint_kind=str(PhoneKind.MAIN_BUSINESS_PHONE),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/about-us/our-team/",
        observed_at=_NOW,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=execution_gated,
        suppressed=False,
    )
    ranking = rank_channels((evidence,))
    assert ranking.entries[0].eligible is False
    assert ranking.recommended_channel is None


# --------------------------------------------------------------------------
# Person suppression propagates cross-channel (section 12)
# --------------------------------------------------------------------------


def test_person_suppression_propagates_across_channels_channel_suppression_does_not() -> None:
    from opintel_m0_local import UuidFactory
    from opintel_suppression import SuppressionRegistryService
    from opintel_suppression_local import SqlAlchemySuppressionRepository

    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()

    class _Clock:
        def now(self) -> datetime:
            return _NOW

    service = SuppressionRegistryService(repo, _Clock(), UuidFactory())
    workspace_id = uuid4()
    person_key = "greg-yamin-a-plus"
    company_key = "a-plus-air-conditioning"

    # Greg opts out via email -> person-wide suppression (not just
    # channel-scoped) per counsel's cross-channel requirement.
    service.suppress_person(
        workspace_id=workspace_id,
        person_key=person_key,
        reason="opted out via email reply, person-wide per configured scope",
        evidence_ref="reply-msg-greg-1",
    )
    for channel in ("email", "phone", "linkedin"):
        assert (
            service.check_channel_blocked(
                workspace_id=workspace_id,
                person_key=person_key,
                company_key=company_key,
                channel=channel,
            )
            is True
        ), channel

    # A different, narrowly-scoped channel opt-out for someone else does NOT
    # propagate to their other channels.
    other_person_key = "someone-else"
    service.suppress_channel(
        workspace_id=workspace_id,
        person_key=other_person_key,
        channel="email",
        reason="test: channel-only opt-out",
        evidence_ref="reply-msg-other-1",
    )
    assert (
        service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=other_person_key,
            company_key=company_key,
            channel="phone",
        )
        is False
    )


# --------------------------------------------------------------------------
# Retention / purge + suppression hash retained after purge (section 13)
# --------------------------------------------------------------------------


def test_retention_policy_enforces_counsel_permitted_range() -> None:
    from opintel_contact_resolution import RetentionPolicy

    RetentionPolicy(purge_after_days=30)
    RetentionPolicy(purge_after_days=60)
    RetentionPolicy(purge_after_days=90)
    with pytest.raises(ValueError, match="30-90"):
        RetentionPolicy(purge_after_days=10)
    with pytest.raises(ValueError, match="30-90"):
        RetentionPolicy(purge_after_days=200)


def test_default_retention_is_60_days() -> None:
    from opintel_contact_resolution import DEFAULT_RETENTION_POLICY

    assert DEFAULT_RETENTION_POLICY.purge_after_days == 60


def test_purge_removes_contact_evidence_but_suppression_hash_survives() -> None:
    from pathlib import Path

    from opintel_contact_resolution_local import SqlAlchemyContactEndpointEvidenceRepository
    from opintel_m0_local import UuidFactory
    from opintel_suppression import SuppressionRegistryService
    from opintel_suppression_local import SqlAlchemySuppressionRepository

    scratch_dir = Path(__file__).resolve().parents[1] / "local-data" / "test-m610-purge"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    db_path = scratch_dir / f"contact-{uuid4()}.sqlite3"
    contact_repo = SqlAlchemyContactEndpointEvidenceRepository(f"sqlite:///{db_path}")
    contact_repo.initialize()

    suppression_repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    suppression_repo.initialize()

    class _Clock:
        def now(self) -> datetime:
            return _NOW

    suppression_service = SuppressionRegistryService(suppression_repo, _Clock(), UuidFactory())

    person = _person()
    matrix = counsel_controlled_authority_matrix()
    old_observed_at = _NOW - timedelta(days=100)  # older than any counsel-permitted retention
    evidence = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.EMAIL,
        endpoint="greg@aplusac.com",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/contact-us/",
        observed_at=old_observed_at,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=EmailVerificationState.SOURCE_VERIFIED,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT,
        suppressed=False,
    )
    contact_repo.add(evidence)
    workspace_id = uuid4()
    suppression_service.suppress_person(
        workspace_id=workspace_id,
        person_key=str(person.id),
        reason="test: opted out",
        evidence_ref="reply-msg-purge-test",
    )

    deleted = contact_repo.purge_expired(retention_days=60, now=_NOW)
    assert deleted == 1
    assert contact_repo.list_for_person(person.id) == ()

    # The suppression entry (an irreversible hash-keyed record in a
    # different, never-purged store) is untouched by the contact-evidence
    # purge above - it is the "minimum irreversible/hash-based suppression
    # representation" section 13 requires to survive indefinitely.
    assert (
        suppression_service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=str(person.id),
            company_key=str(person.company_id),
            channel="email",
        )
        is True
    )

    contact_repo.engine.dispose()
    db_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Deletion / provenance request workflow (section 14)
# --------------------------------------------------------------------------


def test_deletion_and_provenance_request_workflow() -> None:
    report = build_deletion_provenance_report(
        person_name="Greg Yamin",
        source="https://www.aplusac.com/about-us/our-team/",
        retrieval_date=_NOW,
        retained_fields=("name", "title", "employer", "source"),
        deletion_requested=False,
    )
    assert report.source == "https://www.aplusac.com/about-us/our-team/"
    assert report.action_taken == "PROVENANCE_DISCLOSED_NO_DELETION"
    assert "personal_email" not in report.retained_fields

    deletion = build_deletion_provenance_report(
        person_name="Greg Yamin",
        source="https://www.aplusac.com/about-us/our-team/",
        retrieval_date=_NOW,
        retained_fields=("name", "title", "employer", "source"),
        deletion_requested=True,
    )
    assert deletion.action_taken == "DELETED_AND_SUPPRESSED"


# --------------------------------------------------------------------------
# Sanity: the general email-eligibility gate still requires everything it
# always required, even with counsel's controls encoded.
# --------------------------------------------------------------------------


def test_directory_sourced_email_still_requires_verification_threshold() -> None:
    matrix = counsel_controlled_authority_matrix()
    policy = {
        SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY: ContactSourcePolicySettings(
            allowed=True, required_verification=EmailVerificationState.MULTI_SOURCE_VERIFIED
        )
    }
    unverified = evaluate_email_eligibility(
        email_kind=EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL,
        source_category=SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
        verification_state=EmailVerificationState.SYNTAX_ONLY,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=matrix,
        policy=policy,
        suppressed=False,
    )
    assert unverified is EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED
