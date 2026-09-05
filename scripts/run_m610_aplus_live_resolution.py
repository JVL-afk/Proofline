"""M6.10 live A-Plus recipient resolution, post counsel-source-activation.

Owner authorization "M6.10 LEGAL SOURCE ACTIVATION + LIVE A-PLUS RECIPIENT
RESOLUTION" (2026-09-06), sections 17-19. Resumes the paused A-Plus
acceptance case now that Texas counsel has returned all eight source
decisions as APPROVED_WITH_CONTROLS.

Bounded order actually followed this run: FIRST_PARTY (already had) ->
APPROVED_PROFESSIONAL_DIRECTORY (BBB business profile, checked live this
run) -> STOP. APPROVED_CONTACT_ENRICHMENT and APPROVED_EMAIL_VERIFICATION
were never queried: this project holds no vendor credentials or contract
for any contact-enrichment or email-verification provider (checked
apikeys.txt - only ANTHROPIC/OPENAI/GEMINI keys exist), and per the owner
authorization's own section 15, missing credentials are reported, not
invented. No pattern-derived candidate was generated for the same reason -
independent verification (the only thing that could make one eligible) has
no available provider.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opintel_contact_resolution import (  # noqa: E402
    Channel,
    EligibilityDisposition,
    EmailKind,
    IdentityConfidence,
    LinkedInProfileState,
    PersonCandidate,
    PhoneKind,
    PhoneReachability,
    RoleTier,
    SourceCategory,
    VerificationMethod,
    build_endpoint_evidence,
    counsel_controlled_authority_matrix,
    evaluate_linkedin_eligibility,
    evaluate_phone_eligibility,
    phone_execution_disposition,
    rank_person_candidates,
)
from opintel_contact_resolution.ranking import rank_channels  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_COMPANY_ID = uuid5(NAMESPACE_URL, "https://www.aplusac.com/")
_OBSERVED_AT_2026_09_05 = datetime(2026, 9, 5, 9, 45, tzinfo=UTC)
_OBSERVED_AT_2026_09_06 = datetime(2026, 9, 6, tzinfo=UTC)
_TEAM_PAGE = "https://www.aplusac.com/about-us/our-team/"
_BBB_PROFILE = (
    "https://www.bbb.org/us/tx/austin/profile/air-conditioning-contractor/"
    "a-plus-air-conditioning-home-solutions-0825-39557"
)


def main() -> int:
    matrix = counsel_controlled_authority_matrix()

    person = PersonCandidate(
        id=uuid5(_COMPANY_ID, "greg-yamin"),
        company_id=_COMPANY_ID,
        full_name="Greg Yamin",
        role_title_as_stated="President",
        role_tier=RoleTier.OWNER_PRESIDENT,
        role_evidence=(
            f'{_TEAM_PAGE}: "Greg Yamin - President" (co-founder with Sharon Yamin, 1977); '
            f'corroborated at {_BBB_PROFILE}: "Mr. Gregory K. Yamin (President)"'
        ),
        source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE,
        source_url=_TEAM_PAGE,
        source_content_sha256=None,
        observed_at=_OBSERVED_AT_2026_09_05,
        first_party=True,
        identity_confidence=IdentityConfidence.HIGH,
    )
    ranked = rank_person_candidates((person,))
    assert ranked[0].id == person.id

    # EMAIL: FIRST_PARTY (re-confirmed, unchanged) then
    # APPROVED_PROFESSIONAL_DIRECTORY (BBB business profile - a legitimate
    # business/professional directory, not a consumer people-search source)
    # attempted live this run. Real fetch, 2026-09-06: business info,
    # accreditation, and named personnel (Sharon Yamin VP, Gregory K. Yamin
    # President, Josh Yamin - Company Contact) confirmed, but "the only
    # email reference provided is a sales contact link" - no email address
    # itself. CONTACT_ENRICHMENT / EMAIL_VERIFICATION not attempted: no
    # vendor credentials exist in this project. No pattern candidate
    # generated (nothing to independently verify it with).
    email_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "email-2026-09-06"),
        person=person,
        channel=Channel.EMAIL,
        endpoint="UNRESOLVED - no email published on aplusac.com or its BBB profile",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
        provider=f"BBB business profile ({_BBB_PROFILE}) - no email found",
        source_url=_BBB_PROFILE,
        observed_at=_OBSERVED_AT_2026_09_06,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.NONE,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.IDENTITY_VERIFIED_CONTACT_UNRESOLVED,
        suppressed=False,
    )

    # LINKEDIN: same profile URL as before (search snippet only - the
    # profile page itself still was not fetched, respecting LinkedIn's
    # platform terms rather than attempting to bypass the earlier HTTP 999
    # block). What changed: LINKEDIN_PROFILE_DISCOVERY_AUTHORITY is now
    # AUTHORIZED_WITH_CONTROLS (counsel), so this is no longer
    # CONTACT_SOURCE_NOT_AUTHORIZED - it is genuinely eligible for a later,
    # separately-reviewed MANUAL human message.
    linkedin_disposition, linkedin_mode = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        suppressed=False,
    )
    linkedin_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "linkedin-2026-09-06"),
        person=person,
        channel=Channel.LINKEDIN,
        endpoint="https://www.linkedin.com/in/greg-yamin-a226a113/",
        endpoint_kind=str(LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE),
        source_category=SourceCategory.APPROVED_PROFESSIONAL_PROFILE,
        provider="web search snippet (profile page itself not fetched - respects platform terms)",
        source_url=None,
        observed_at=_OBSERVED_AT_2026_09_05,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.MULTI_SOURCE_CORROBORATION,
        verification_result=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        eligibility_disposition=linkedin_disposition,
        suppressed=False,
    )

    # PHONE: resolution unchanged and still verified (main line, indirect).
    # What changed: PHONE_CONTACT_DATA_AUTHORITY is now
    # AUTHORIZED_WITH_CONTROLS, but PHONE_OUTBOUND_EXECUTION_AUTHORITY stays
    # NOT_AUTHORIZED (section 11 - Texas telemarketing review still
    # pending) - resolution succeeding never implies execution permission.
    phone_resolution_disposition = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=matrix,
        suppressed=False,
    )
    phone_final_disposition = phone_execution_disposition(phone_resolution_disposition, matrix)
    phone_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "phone-2026-09-06"),
        person=person,
        channel=Channel.PHONE,
        endpoint="512-450-1980",
        endpoint_kind=str(PhoneKind.MAIN_BUSINESS_PHONE),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com + BBB business profile (first party / directory, corroborating)",
        source_url=_TEAM_PAGE,
        observed_at=_OBSERVED_AT_2026_09_05,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=phone_final_disposition,
        suppressed=False,
    )

    ranking = rank_channels((email_evidence, linkedin_evidence, phone_evidence))

    result = {
        "task": "M6.10 live A-Plus recipient resolution (post counsel source activation)",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
        "company": "A-Plus Air Conditioning & Home Solutions",
        "company_id": str(_COMPANY_ID),
        "recipient": {
            "name": person.full_name,
            "role": person.role_title_as_stated,
            "role_tier": str(person.role_tier),
            "role_confidence": str(person.identity_confidence),
            "role_evidence": person.role_evidence,
            "first_party": person.first_party,
        },
        "sources_attempted_this_run": [
            "FIRST_PARTY (aplusac.com - re-confirmed, unchanged)",
            f"APPROVED_PROFESSIONAL_DIRECTORY (BBB business profile, {_BBB_PROFILE})",
        ],
        "sources_not_attempted": {
            "APPROVED_CONTACT_ENRICHMENT": "no vendor credentials/contract exist in this project",
            "APPROVED_EMAIL_VERIFICATION": "no verification-provider credentials exist",
            "PATTERN_DERIVED": "no independent verification method available to check one",
        },
        "channels": {
            str(e.channel): {
                "endpoint": e.endpoint,
                "endpoint_kind": e.endpoint_kind,
                "source_category": str(e.source_category),
                "provider": e.provider,
                "verification_method": str(e.verification_method),
                "verification_result": str(e.verification_result)
                if e.verification_result
                else None,
                "legal_source_authority": str(e.legal_source_authority),
                "channel_authority": str(e.channel_authority),
                "eligibility_disposition": str(e.eligibility_disposition),
                "evidence_record_hash": e.evidence_record_hash,
            }
            for e in (email_evidence, linkedin_evidence, phone_evidence)
        },
        "channel_ranking": {
            str(entry.channel): {
                "eligible": entry.eligible,
                "disposition": str(entry.disposition),
                "score": entry.score,
                "reasons": list(entry.reasons),
            }
            for entry in ranking.entries
        },
        "recommended_channel": str(ranking.recommended_channel)
        if ranking.recommended_channel
        else None,
        "recommendation_reason": ranking.recommendation_reason,
        "phone_outbound_execution_authority": "NOT_AUTHORIZED_PENDING_TELEMARKETING_REVIEW",
        "final": "M6.10_LIVE_RESOLUTION_COMPLETE",
    }

    path = _OUT / "m6.10-aplus-live-resolution-2026-09-06.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"recipient: {person.full_name}, {person.role_title_as_stated}")
    print(f"email: {email_evidence.eligibility_disposition}")
    print(f"linkedin: {linkedin_evidence.eligibility_disposition} ({linkedin_mode})")
    print(f"phone: {phone_evidence.eligibility_disposition}")
    print(f"recommended channel: {ranking.recommended_channel}")
    print(f"final: {result['final']}")
    print(f"report: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
