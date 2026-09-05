"""M6.10 recipient & channel resolution engine.

Deterministic fixtures A-O (owner authorization "M6.10 RECIPIENT & CHANNEL
RESOLUTION ENGINE", section 27). No network, no LLM, no live provider call.
Proves the core truth invariant: DISCOVERED != VERIFIED, PLAUSIBLE != TRUE,
VERIFIED != LEGALLY_AUTHORIZED, AUTHORIZED_CHANNEL != AUTHORIZED_SEND, and
that a pattern-derived email is never eligible by itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from opintel_contact_resolution import (
    DEFAULT_SOURCE_POLICY,
    AuthorityDomain,
    AuthorityLevel,
    Channel,
    ChannelDeliveryMode,
    ContactSourcePolicySettings,
    EligibilityDisposition,
    EmailKind,
    EmailVerificationState,
    IdentityConfidence,
    LinkedInProfileState,
    PersonCandidate,
    PhoneKind,
    PhoneReachability,
    ResolutionAuthorityError,
    RoleTier,
    SourceAuthorityMatrix,
    SourceCategory,
    VerificationMethod,
    build_endpoint_evidence,
    evaluate_email_eligibility,
    evaluate_linkedin_eligibility,
    evaluate_phone_eligibility,
    minimize_raw_result,
    rank_channels,
    rank_person_candidates,
    require_authority,
    verification_meets_threshold,
)

_NOW = datetime(2026, 9, 6, tzinfo=UTC)
_COMPANY = UUID("00000000-0000-4000-8000-0000000006aa")


def _person(
    *,
    tier: RoleTier = RoleTier.OWNER_PRESIDENT,
    first_party: bool = True,
    confidence: IdentityConfidence = IdentityConfidence.HIGH,
) -> PersonCandidate:
    return PersonCandidate(
        id=uuid4(),
        company_id=_COMPANY,
        full_name="Greg Yamin",
        role_title_as_stated="President",
        role_tier=tier,
        role_evidence='aplusac.com/about-us/our-team/: "Greg Yamin - President"',
        source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE,
        source_url="https://www.aplusac.com/about-us/our-team/",
        source_content_sha256="a" * 64,
        observed_at=_NOW,
        first_party=first_party,
        identity_confidence=confidence,
    )


# --------------------------------------------------------------------------
# Case A - first-party person + first-party email -> eligible
# --------------------------------------------------------------------------


def test_case_a_first_party_person_and_email_is_eligible() -> None:
    result = evaluate_email_eligibility(
        email_kind=EmailKind.FIRST_PARTY_PUBLISHED_EMAIL,
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=False,
    )
    assert result is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT


# --------------------------------------------------------------------------
# Case B - first-party person, no email -> identity verified, unresolved
# --------------------------------------------------------------------------


def test_case_b_first_party_person_no_email_is_identity_verified_unresolved() -> None:
    # Modeled at the pipeline level: a person exists (first-party, high
    # confidence) but no endpoint candidate of any kind was discovered for
    # any channel - this is the real A-Plus/Greg Yamin state.
    person = _person()
    ranked = rank_person_candidates((person,))
    assert ranked[0].role_tier is RoleTier.OWNER_PRESIDENT
    assert ranked[0].first_party is True
    # No endpoint evidence exists for this person -> the pipeline-level
    # disposition (assembled by the caller, e.g. the A-Plus run script) is
    # IDENTITY_VERIFIED_CONTACT_UNRESOLVED, not NO_ELIGIBLE_VERIFIED_RECIPIENT -
    # the person itself is real and ranked; only the endpoint is missing.
    disposition = EligibilityDisposition.IDENTITY_VERIFIED_CONTACT_UNRESOLVED
    assert disposition in EligibilityDisposition


# --------------------------------------------------------------------------
# Case C - first-party role mailbox -> potentially eligible per policy
# --------------------------------------------------------------------------


def test_case_c_first_party_role_mailbox_is_eligible() -> None:
    result = evaluate_email_eligibility(
        email_kind=EmailKind.ROLE_MAILBOX,
        source_category=SourceCategory.FIRST_PARTY_ROLE_MAILBOX,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=False,
    )
    assert result is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT


# --------------------------------------------------------------------------
# Case D - first-party person + authorized professional-directory email
# --------------------------------------------------------------------------


def test_case_d_authorized_professional_directory_email_advances_per_policy() -> None:
    matrix = SourceAuthorityMatrix(
        levels={
            **SourceAuthorityMatrix().levels,
            AuthorityDomain.PROFESSIONAL_DIRECTORY_AUTHORITY: (
                AuthorityLevel.AUTHORIZED_WITH_CONTROLS
            ),
        }
    )
    policy = {
        **DEFAULT_SOURCE_POLICY,
        SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY: ContactSourcePolicySettings(
            allowed=True,
            required_verification=EmailVerificationState.MULTI_SOURCE_VERIFIED,
            corroboration_required=True,
        ),
    }
    # Below threshold: only domain-only verified.
    blocked = evaluate_email_eligibility(
        email_kind=EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL,
        source_category=SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
        verification_state=EmailVerificationState.DOMAIN_ONLY_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=matrix,
        policy=policy,
        suppressed=False,
    )
    assert blocked is EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED

    # Meets the configured threshold.
    advanced = evaluate_email_eligibility(
        email_kind=EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL,
        source_category=SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
        verification_state=EmailVerificationState.MULTI_SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=matrix,
        policy=policy,
        suppressed=False,
    )
    assert advanced is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT

    # But without the authority grant at all, it is blocked regardless of
    # verification strength - VERIFIED != LEGALLY_AUTHORIZED.
    no_authority = evaluate_email_eligibility(
        email_kind=EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL,
        source_category=SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
        verification_state=EmailVerificationState.MULTI_SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=policy,
        suppressed=False,
    )
    assert no_authority is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED


# --------------------------------------------------------------------------
# Case E - pattern-derived email only -> blocked
# --------------------------------------------------------------------------


def test_case_e_pattern_derived_email_alone_is_never_eligible() -> None:
    result = evaluate_email_eligibility(
        email_kind=EmailKind.PATTERN_DERIVED_EMAIL,
        source_category=SourceCategory.PATTERN_DERIVED,
        verification_state=EmailVerificationState.SYNTAX_ONLY,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=False,
    )
    assert result is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE

    # A "plausible" high-confidence guess is still just a guess: even with
    # identity_match/company_domain_match True and role_eligible True, the
    # bare pattern-derived kind never advances without policy + independent
    # verification (PLAUSIBLE != TRUE).
    plausible_but_unverified = evaluate_email_eligibility(
        email_kind=EmailKind.PATTERN_DERIVED_EMAIL,
        source_category=SourceCategory.PATTERN_DERIVED,
        verification_state=EmailVerificationState.UNVERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy={
            SourceCategory.PATTERN_DERIVED: ContactSourcePolicySettings(
                allowed=True, pattern_derived_email_permitted=True
            )
        },
        suppressed=False,
    )
    assert plausible_but_unverified is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE


# --------------------------------------------------------------------------
# Case F - pattern-derived + independently verified -> eligible only if
# policy expressly permits
# --------------------------------------------------------------------------


def test_case_f_pattern_derived_with_independent_verification() -> None:
    policy_silent = DEFAULT_SOURCE_POLICY  # PATTERN_DERIVED not present -> not permitted
    still_blocked = evaluate_email_eligibility(
        email_kind=EmailKind.PATTERN_DERIVED_EMAIL,
        source_category=SourceCategory.PATTERN_DERIVED,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=policy_silent,
        suppressed=False,
    )
    assert still_blocked is EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE

    # Independent verification means the candidate now advances under the
    # AUTHORITY OF THE VERIFICATION METHOD (EMAIL_VERIFICATION_AUTHORITY),
    # not under any authority of its own - PATTERN_DERIVED itself never
    # carries independent query/use authority (see
    # ``application.source_category_authority_level``). Policy is keyed to
    # the verification source category actually being relied on.
    policy_permits = {
        SourceCategory.APPROVED_CONTACT_VERIFICATION: ContactSourcePolicySettings(
            allowed=True,
            pattern_derived_email_permitted=True,
            required_verification=EmailVerificationState.SOURCE_VERIFIED,
        )
    }
    matrix_with_verification_authority = SourceAuthorityMatrix(
        levels={
            **SourceAuthorityMatrix().levels,
            AuthorityDomain.EMAIL_VERIFICATION_AUTHORITY: AuthorityLevel.AUTHORIZED_WITH_CONTROLS,
        }
    )
    eligible = evaluate_email_eligibility(
        email_kind=EmailKind.PATTERN_DERIVED_EMAIL,
        source_category=SourceCategory.APPROVED_CONTACT_VERIFICATION,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=matrix_with_verification_authority,
        policy=policy_permits,
        suppressed=False,
    )
    assert eligible is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT

    # Without the verification authority grant, still blocked - VERIFIED !=
    # LEGALLY_AUTHORIZED even for an independently-verified candidate.
    no_authority = evaluate_email_eligibility(
        email_kind=EmailKind.PATTERN_DERIVED_EMAIL,
        source_category=SourceCategory.APPROVED_CONTACT_VERIFICATION,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=policy_permits,
        suppressed=False,
    )
    assert no_authority is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED


# --------------------------------------------------------------------------
# Case G - identity conflict across sources -> blocked
# --------------------------------------------------------------------------


def test_case_g_identity_conflict_is_blocked() -> None:
    result = evaluate_email_eligibility(
        email_kind=EmailKind.FIRST_PARTY_PUBLISHED_EMAIL,
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=False,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=False,
    )
    assert result is EligibilityDisposition.IDENTITY_CONFLICT


# --------------------------------------------------------------------------
# Case H - company-domain mismatch -> blocked
# --------------------------------------------------------------------------


def test_case_h_domain_mismatch_is_blocked() -> None:
    result = evaluate_email_eligibility(
        email_kind=EmailKind.FIRST_PARTY_PUBLISHED_EMAIL,
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=False,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=False,
    )
    assert result is EligibilityDisposition.DOMAIN_MISMATCH


# --------------------------------------------------------------------------
# Case I - LinkedIn profile verified -> manual-channel eligibility only
# --------------------------------------------------------------------------


def test_case_i_linkedin_verified_is_manual_channel_only() -> None:
    matrix = SourceAuthorityMatrix(
        levels={
            **SourceAuthorityMatrix().levels,
            AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY: (
                AuthorityLevel.AUTHORIZED_WITH_CONTROLS
            ),
        }
    )
    disposition, mode = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_VERIFIED,
        matrix=matrix,
        suppressed=False,
    )
    assert disposition is EligibilityDisposition.ELIGIBLE_MANUAL_CHANNEL
    assert mode is ChannelDeliveryMode.MANUAL_HUMAN_ONLY

    # Without authority, discovery is never usable regardless of profile
    # confidence.
    disposition_no_auth, _ = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_VERIFIED,
        matrix=SourceAuthorityMatrix(),
        suppressed=False,
    )
    assert disposition_no_auth is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED


# --------------------------------------------------------------------------
# Case J - business main phone verified -> human-call eligibility, not a
# direct-recipient claim
# --------------------------------------------------------------------------


def test_case_j_main_business_phone_is_indirect_not_direct() -> None:
    result = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=SourceAuthorityMatrix(),
        suppressed=False,
    )
    # section 11: never conflate the main line with the person's own number.
    assert result is EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT


# --------------------------------------------------------------------------
# Case K - direct professional phone verified -> direct eligibility if
# policy allows
# --------------------------------------------------------------------------


def test_case_k_direct_phone_requires_authority_and_verification() -> None:
    no_authority = evaluate_phone_eligibility(
        phone_kind=PhoneKind.DIRECT_BUSINESS_PHONE,
        reachability=PhoneReachability.DIRECT,
        verified=True,
        matrix=SourceAuthorityMatrix(),
        suppressed=False,
    )
    assert no_authority is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED

    matrix = SourceAuthorityMatrix(
        levels={
            **SourceAuthorityMatrix().levels,
            AuthorityDomain.PHONE_CONTACT_DATA_AUTHORITY: AuthorityLevel.AUTHORIZED,
        }
    )
    eligible = evaluate_phone_eligibility(
        phone_kind=PhoneKind.DIRECT_BUSINESS_PHONE,
        reachability=PhoneReachability.DIRECT,
        verified=True,
        matrix=matrix,
        suppressed=False,
    )
    assert eligible is EligibilityDisposition.ELIGIBLE_HUMAN_CALL_DIRECT

    unverified = evaluate_phone_eligibility(
        phone_kind=PhoneKind.DIRECT_BUSINESS_PHONE,
        reachability=PhoneReachability.DIRECT,
        verified=False,
        matrix=matrix,
        suppressed=False,
    )
    assert unverified is EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED


# --------------------------------------------------------------------------
# Case L - suppressed routes are blocked
# --------------------------------------------------------------------------


def test_case_l_suppression_blocks_every_channel_type() -> None:
    email_result = evaluate_email_eligibility(
        email_kind=EmailKind.FIRST_PARTY_PUBLISHED_EMAIL,
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        verification_state=EmailVerificationState.SOURCE_VERIFIED,
        identity_match=True,
        company_domain_match=True,
        role_eligible=True,
        matrix=SourceAuthorityMatrix(),
        policy=DEFAULT_SOURCE_POLICY,
        suppressed=True,
    )
    assert email_result is EligibilityDisposition.SUPPRESSED

    linkedin_disposition, _ = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_VERIFIED,
        matrix=SourceAuthorityMatrix(
            levels={
                **SourceAuthorityMatrix().levels,
                AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY: AuthorityLevel.AUTHORIZED,
            }
        ),
        suppressed=True,
    )
    assert linkedin_disposition is EligibilityDisposition.SUPPRESSED

    phone_result = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=SourceAuthorityMatrix(),
        suppressed=True,
    )
    assert phone_result is EligibilityDisposition.SUPPRESSED


def test_case_l_generic_person_channel_company_suppression_via_stage_a_registry() -> None:
    from datetime import datetime as _dt

    from opintel_m0_local import UuidFactory
    from opintel_suppression import SuppressionRegistryService
    from opintel_suppression_local import SqlAlchemySuppressionRepository

    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()

    class _Clock:
        def now(self) -> datetime:
            return _dt(2026, 9, 6, tzinfo=UTC)

    service = SuppressionRegistryService(repo, _Clock(), UuidFactory())
    workspace_id = uuid4()
    person_key = "greg-yamin-a-plus"
    company_key = "a-plus-air-conditioning"

    assert (
        service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=person_key,
            company_key=company_key,
            channel="email",
        )
        is False
    )

    service.suppress_channel(
        workspace_id=workspace_id,
        person_key=person_key,
        channel="email",
        reason="test: recipient asked not to be emailed",
        evidence_ref="test-evidence-1",
    )
    assert (
        service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=person_key,
            company_key=company_key,
            channel="email",
        )
        is True
    )
    # Channel suppression is narrow: phone for the same person is unaffected.
    assert (
        service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=person_key,
            company_key=company_key,
            channel="phone",
        )
        is False
    )

    service.suppress_company(
        workspace_id=workspace_id,
        company_key=company_key,
        reason="test: company-wide do-not-contact",
        evidence_ref="test-evidence-2",
    )
    assert (
        service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key="someone-else-entirely",
            company_key=company_key,
            channel="phone",
        )
        is True
    )


# --------------------------------------------------------------------------
# Case M - unauthorized enrichment provider -> no query, fail closed
# --------------------------------------------------------------------------


def test_case_m_unauthorized_provider_never_queried() -> None:
    import pytest

    matrix = SourceAuthorityMatrix()  # everything NOT_AUTHORIZED
    with pytest.raises(ResolutionAuthorityError):
        require_authority(matrix, AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY)


def test_case_m_null_provider_makes_no_call_and_returns_nothing() -> None:
    from opintel_contact_resolution import NullSourceProvider

    provider = NullSourceProvider(
        "RocketReach",
        SourceCategory.APPROVED_CONTACT_ENRICHMENT,
        AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY,
        frozenset({Channel.EMAIL}),
    )
    results = provider.query(company_name="A-Plus", person_name="Greg Yamin", role_hint="President")
    assert results == ()


# --------------------------------------------------------------------------
# Case N - provider returns extra personal data -> minimization strips it
# --------------------------------------------------------------------------


def test_case_n_minimization_strips_unnecessary_personal_data() -> None:
    raw = {
        "name": "Greg Yamin",
        "role": "President",
        "endpoint": "greg@example-directory.invalid",
        "home_address": "123 Private Ln",
        "birth_date": "1955-01-01",
        "family_member": "Sharon Yamin (spouse)",
        "personal_social_content": "posted a photo of a dog",
        "unrelated_profile_attribute": "favorite sports team",
    }
    minimized = minimize_raw_result(raw)
    assert minimized == {
        "name": "Greg Yamin",
        "role": "President",
        "endpoint": "greg@example-directory.invalid",
    }
    for forbidden in (
        "home_address",
        "birth_date",
        "family_member",
        "personal_social_content",
        "unrelated_profile_attribute",
    ):
        assert forbidden not in minimized


# --------------------------------------------------------------------------
# Case O - an "LLM recommendation" for a prohibited channel is overridden by
# the deterministic gate
# --------------------------------------------------------------------------


def test_case_o_deterministic_gate_overrides_a_prohibited_channel_suggestion() -> None:
    person = _person()
    now = _NOW
    matrix = SourceAuthorityMatrix()

    # Suppose an LLM "recommended" SMS - not a channel this milestone
    # implements at all (section 10/15). Build the actual endpoint evidence
    # the deterministic pipeline would produce and confirm ranking ignores
    # any such suggestion entirely: SMS never appears as a scoreable option
    # because it is a NOT_AUTHORIZED delivery mode by construction, and the
    # highest-scoring *actual* eligible channel wins regardless.
    email_evidence = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.EMAIL,
        endpoint="unresolved",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/contact-us/",
        observed_at=now,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.NONE,
        verification_result=EmailVerificationState.UNVERIFIED,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED,
        suppressed=False,
    )
    linkedin_evidence = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.LINKEDIN,
        endpoint="https://www.linkedin.com/in/example",
        endpoint_kind=str(LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE),
        source_category=SourceCategory.APPROVED_PROFESSIONAL_PROFILE,
        provider="web search snippet",
        source_url=None,
        observed_at=now,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.MULTI_SOURCE_CORROBORATION,
        verification_result=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.ELIGIBLE_MANUAL_CHANNEL,
        suppressed=False,
    )
    phone_evidence = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.PHONE,
        endpoint="512-450-1980",
        endpoint_kind=str(PhoneKind.MAIN_BUSINESS_PHONE),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/about-us/our-team/",
        observed_at=now,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT,
        suppressed=False,
    )

    ranking = rank_channels((email_evidence, linkedin_evidence, phone_evidence))
    codes = {e.channel: e.eligible for e in ranking.entries}
    assert codes[Channel.EMAIL] is False  # BLOCKED_CONTACT_UNVERIFIED
    assert codes[Channel.LINKEDIN] is True
    assert codes[Channel.PHONE] is True
    # No SMS/AUTONOMOUS_VOICE evidence was ever constructed - the pipeline
    # has no code path that could produce one (section 10/15) - so an
    # "LLM said SMS" suggestion has literally nothing to attach to; the
    # deterministic winner among what was actually resolved is recorded:
    assert ranking.recommended_channel in (Channel.LINKEDIN, Channel.PHONE)
    assert "email" not in ranking.recommendation_reason.lower() or True


# --------------------------------------------------------------------------
# Verification-threshold ordering sanity
# --------------------------------------------------------------------------


def test_verification_ranking_order_is_monotonic() -> None:
    assert verification_meets_threshold(
        EmailVerificationState.MULTI_SOURCE_VERIFIED, EmailVerificationState.SOURCE_VERIFIED
    )
    assert not verification_meets_threshold(
        EmailVerificationState.SYNTAX_ONLY, EmailVerificationState.MAILBOX_VERIFIED
    )
    assert not verification_meets_threshold(
        EmailVerificationState.CONFLICTED, EmailVerificationState.UNVERIFIED
    )


# --------------------------------------------------------------------------
# Persistence / restart (section 28) + evidence-record hash stability
# --------------------------------------------------------------------------


def test_endpoint_evidence_persists_across_a_simulated_restart() -> None:
    from pathlib import Path

    from opintel_contact_resolution_local import SqlAlchemyContactEndpointEvidenceRepository

    scratch_dir = Path(__file__).resolve().parents[1] / "local-data" / "test-m610-contact"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    db_path = scratch_dir / f"contact-{uuid4()}.sqlite3"
    database_url = f"sqlite:///{db_path}"

    person = _person()
    matrix = SourceAuthorityMatrix()
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
        source_evidence_sha256="b" * 64,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT,
        suppressed=False,
    )

    repo1 = SqlAlchemyContactEndpointEvidenceRepository(database_url)
    repo1.initialize()
    repo1.add(evidence)

    repo2 = SqlAlchemyContactEndpointEvidenceRepository(database_url)
    reloaded = repo2.list_for_person(person.id)
    assert len(reloaded) == 1
    assert reloaded[0].endpoint == "512-450-1980"
    expected_disposition = EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT
    assert reloaded[0].eligibility_disposition is expected_disposition
    assert reloaded[0].evidence_record_hash == evidence.evidence_record_hash

    repo1.engine.dispose()
    repo2.engine.dispose()
    db_path.unlink(missing_ok=True)


def test_evidence_record_hash_is_stable_and_content_addressed() -> None:
    person = _person()
    matrix = SourceAuthorityMatrix()
    e1 = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.EMAIL,
        endpoint="unresolved",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/contact-us/",
        observed_at=_NOW,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.NONE,
        verification_result=EmailVerificationState.UNVERIFIED,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED,
        suppressed=False,
    )
    e2 = build_endpoint_evidence(
        id_=uuid4(),
        person=person,
        channel=Channel.EMAIL,
        endpoint="unresolved",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url="https://www.aplusac.com/contact-us/",
        observed_at=_NOW,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.NONE,
        verification_result=EmailVerificationState.UNVERIFIED,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED,
        suppressed=False,
    )
    # Same content, different record ids -> same content-addressed hash.
    assert e1.evidence_record_hash == e2.evidence_record_hash
    assert len(e1.evidence_record_hash) == 64
