"""M6.10 first real acceptance case: A-Plus Air Conditioning & Home Solutions.

Owner authorization "M6.10 RECIPIENT & CHANNEL RESOLUTION ENGINE", section
26. Runs the deterministic M6.10 pipeline against A-Plus using ONLY evidence
already gathered and already authorized in prior M6.9 tasks - no new network
call is made by this script. No third-party contact-enrichment provider is
queried (THIRD_PARTY_CONTACT_SOURCE_AUTHORITY stays NOT_AUTHORIZED
throughout). Reality wins: this reports the true resolution state, it does
not force a successful endpoint.
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
    SourceAuthorityMatrix,
    SourceCategory,
    VerificationMethod,
    build_endpoint_evidence,
    evaluate_linkedin_eligibility,
    evaluate_phone_eligibility,
    rank_person_candidates,
)
from opintel_contact_resolution.ranking import rank_channels  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_COMPANY_ID = uuid5(NAMESPACE_URL, "https://www.aplusac.com/")
_OBSERVED_AT = datetime(2026, 9, 5, 9, 45, tzinfo=UTC)

# Every fact below is real, first-party, and was already gathered (with
# curl/WebFetch/WebSearch, real HTTP 200s) in the prior M6.9 pilot-package
# and recipient-resolution tasks. Nothing here is fetched again.
_TEAM_PAGE = "https://www.aplusac.com/about-us/our-team/"


def main() -> int:
    matrix = SourceAuthorityMatrix()  # every AuthorityDomain NOT_AUTHORIZED - unchanged this run

    person = PersonCandidate(
        id=uuid5(_COMPANY_ID, "greg-yamin"),
        company_id=_COMPANY_ID,
        full_name="Greg Yamin",
        role_title_as_stated="President",
        role_tier=RoleTier.OWNER_PRESIDENT,
        role_evidence=(
            f'{_TEAM_PAGE}: "Greg Yamin - President" (co-founder with Sharon Yamin, 1977)'
        ),
        source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE,
        source_url=_TEAM_PAGE,
        source_content_sha256=None,
        observed_at=_OBSERVED_AT,
        first_party=True,
        identity_confidence=IdentityConfidence.HIGH,
    )
    ranked = rank_person_candidates((person,))
    assert ranked[0].id == person.id

    # EMAIL: no email of any kind is published anywhere on the first-party
    # site (home, about-us, our-team, contact-us, commercial-hvac, intake,
    # service-area - all checked in the prior recipient-resolution task).
    # No pattern-derived candidate is constructed - section 7/E: a pattern
    # guess is not "discovery," it is fabrication, and this script does not
    # do that even to demonstrate the block. With no endpoint candidate at
    # all, ``evaluate_email_eligibility`` (which reasons about a specific
    # candidate) does not apply - the correct pipeline-level disposition for
    # "verified person, no discovered endpoint" is
    # IDENTITY_VERIFIED_CONTACT_UNRESOLVED directly (see Case B).
    email_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "email"),
        person=person,
        channel=Channel.EMAIL,
        endpoint="UNRESOLVED - no email published on aplusac.com",
        endpoint_kind=str(EmailKind.FIRST_PARTY_PUBLISHED_EMAIL),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party) - no email found",
        source_url="https://www.aplusac.com/contact-us/",
        observed_at=_OBSERVED_AT,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.NONE,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=EligibilityDisposition.IDENTITY_VERIFIED_CONTACT_UNRESOLVED,
        suppressed=False,
    )

    # LINKEDIN: a profile URL surfaced via web search (title mentions
    # A-Plus, matching this company) but LinkedIn blocked direct profile
    # fetch (HTTP 999) in the prior task - the profile page itself was never
    # read, so this is PROBABLE, not VERIFIED. LinkedIn discovery authority
    # was never granted, so this stays discovery-only regardless.
    linkedin_disposition, linkedin_mode = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        suppressed=False,
    )
    linkedin_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "linkedin"),
        person=person,
        channel=Channel.LINKEDIN,
        endpoint="https://www.linkedin.com/in/greg-yamin-a226a113/",
        endpoint_kind=str(LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE),
        source_category=SourceCategory.APPROVED_PROFESSIONAL_PROFILE,
        provider="web search snippet (profile page itself not fetched - HTTP 999)",
        source_url=None,
        observed_at=_OBSERVED_AT,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.MULTI_SOURCE_CORROBORATION,
        verification_result=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        eligibility_disposition=linkedin_disposition,
        suppressed=False,
    )

    # PHONE: the published number is the company's main line, not Greg's
    # personal/direct number - represented honestly per section 11.
    phone_disposition = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=matrix,
        suppressed=False,
    )
    phone_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "phone"),
        person=person,
        channel=Channel.PHONE,
        endpoint="512-450-1980",
        endpoint_kind=str(PhoneKind.MAIN_BUSINESS_PHONE),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com (first party)",
        source_url=_TEAM_PAGE,
        observed_at=_OBSERVED_AT,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=phone_disposition,
        suppressed=False,
    )

    ranking = rank_channels((email_evidence, linkedin_evidence, phone_evidence))

    result = {
        "task": "M6.10 first real acceptance case",
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
        "third_party_contact_source_authority": "NOT_AUTHORIZED",
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
        "final": "IDENTITY_VERIFIED_CONTACT_RESOLUTION_PARTIALLY_BLOCKED_BY_SOURCE_AUTHORITY",
    }

    path = _OUT / "m6.10-aplus-acceptance-2026-09-06.json"
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
