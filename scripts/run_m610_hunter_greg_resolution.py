"""M6.10 — activate Hunter (registry gate closed by counsel) and resolve
Greg Yamin's professional work email. Bounded: 1 Email Finder + at most
1 Email Verifier. No key is printed, logged, persisted, or written to any
artifact by this script.

Owner authorization "RECORD HUNTER REGISTRY APPROVAL AND RESUME LIVE M6.10
GREG RESOLUTION" (2026-09-06).
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
    ContactSourcePolicySettings,
    EligibilityDisposition,
    EmailKind,
    EmailVerificationState,
    IdentityConfidence,
    PersonCandidate,
    PhoneKind,
    PhoneReachability,
    RoleTier,
    SourceCategory,
    VendorComplianceChecklist,
    VerificationMethod,
    build_endpoint_evidence,
    counsel_controlled_authority_matrix,
    evaluate_email_eligibility,
    evaluate_linkedin_eligibility,
    evaluate_phone_eligibility,
    is_corporate_domain,
    phone_execution_disposition,
    verification_is_expired,
)
from opintel_contact_resolution.domain import LinkedInProfileState  # noqa: E402
from opintel_contact_resolution.ranking import rank_channels  # noqa: E402
from opintel_contact_resolution_local import HunterAdapter  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_COMPANY_ID = uuid5(NAMESPACE_URL, "https://www.aplusac.com/")
_CORP_DOMAIN = "aplusac.com"
_NOW = datetime.now(UTC)

# 8/8 - the registry field is now closed by counsel's HUNTER_REGISTRY_APPROVED
# operational decision (see m6.10-hunter-vendor-record-2026-09-06.json).
_HUNTER_CHECKLIST = VendorComplianceChecklist(
    lawful_sourcing_warranty=True,
    per_record_provenance=True,
    no_sensitive_categories=True,
    no_minors=True,
    no_scraped_credentials=True,
    deletion_on_request=True,
    vendor_contractual_controls_or_indemnity=True,
    texas_data_broker_registry_screened=True,
)


def _verifier_outcome(status: str, is_catch_all: bool, mx: bool) -> str:
    """Counsel's fail-closed verification policy."""
    s = status.lower()
    if is_catch_all or s in ("accept_all", "catch_all"):
        return "FAIL_CLOSED_CATCH_ALL"
    if s == "valid":
        return "VALID" if mx else "DROP_NO_MX"
    if s == "invalid":
        return "DROP_INVALID"
    return "DROP_UNKNOWN_OR_INCONCLUSIVE"


def main() -> int:
    matrix = counsel_controlled_authority_matrix()
    person = PersonCandidate(
        id=uuid5(_COMPANY_ID, "greg-yamin"),
        company_id=_COMPANY_ID,
        full_name="Greg Yamin",
        role_title_as_stated="President",
        role_tier=RoleTier.OWNER_PRESIDENT,
        role_evidence=(
            'aplusac.com/about-us/our-team/: "Greg Yamin - President"; '
            'BBB profile: "Mr. Gregory K. Yamin (President)"'
        ),
        source_category=SourceCategory.FIRST_PARTY_PERSON_ROLE,
        source_url="https://www.aplusac.com/about-us/our-team/",
        source_content_sha256=None,
        observed_at=datetime(2026, 9, 5, 9, 45, tzinfo=UTC),
        first_party=True,
        identity_confidence=IdentityConfidence.HIGH,
    )

    adapter = HunterAdapter(matrix=matrix, vendor_checklist=_HUNTER_CHECKLIST)

    report: dict[str, object] = {
        "task": "M6.10 Hunter activation + Greg Yamin email resolution",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
        "hunter_provider_activation": "AUTHORIZED_WITH_CONTROLS",
        "api_calls": {"email_finder": 0, "email_verifier": 0},
        "credits_or_cost_note": "Hunter counts 1 request per Finder call and 1 per Verifier call; "
        "cost depends on plan.",
    }

    # --- one Email Finder operation -------------------------------------
    try:
        finder = adapter.find_email(company_domain=_CORP_DOMAIN, full_name="Greg Yamin")
    except Exception as exc:
        report["api_calls"] = {"email_finder": 1, "email_verifier": 0}
        report["hunter_api_error"] = f"{type(exc).__name__}: {exc}"
        report["email_resolution"] = "HUNTER_API_ERROR"
        report["final"] = "HUNTER_DID_NOT_RESOLVE_ELIGIBLE_EMAIL"
        path = _OUT / "m6.10-hunter-greg-resolution-2026-09-06.json"
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"hunter API error: {type(exc).__name__}")
        print(f"report: {path.relative_to(ROOT)}")
        return 1
    report["api_calls"] = {"email_finder": 1, "email_verifier": 0}

    minimized_persisted: dict[str, str] = {
        k: v
        for k, v in finder.minimized_fields.items()
        if k in ("first_name", "last_name", "position", "email", "domain", "company", "score")
    }
    finder_public = {
        "email_present": finder.email is not None,
        "corporate_domain_returned": finder.corporate_domain,
        "finder_confidence": finder.score,
        "provenance_kind": finder.provenance_kind,
        "source_count": len(finder.sources),
        "sources": list(finder.sources)[:5],
        "retrieved_at": finder.retrieved_at.isoformat(),
        "minimized_persisted_fields": minimized_persisted,
    }
    report["hunter_finder"] = finder_public

    email_disposition: EligibilityDisposition = (
        EligibilityDisposition.IDENTITY_VERIFIED_CONTACT_UNRESOLVED
    )
    email_endpoint = "UNRESOLVED"
    verification_state = EmailVerificationState.UNVERIFIED
    verification_note = "no candidate to verify"

    if finder.email is None:
        report["email_resolution"] = "HUNTER_DID_NOT_RESOLVE_EMAIL"
    else:
        candidate = finder.email.strip().lower()
        local, _, domain = candidate.partition("@")
        corporate_ok = is_corporate_domain(domain, _CORP_DOMAIN)
        personal_domain = not corporate_ok  # is_corporate_domain already rejects personal providers
        syntax_ok = "@" in candidate and "." in domain and bool(local)

        if personal_domain or not corporate_ok:
            email_disposition = EligibilityDisposition.DOMAIN_MISMATCH
            verification_note = (
                "candidate domain is not the verified A-Plus corporate domain - DROP"
            )
        elif not syntax_ok:
            email_disposition = EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED
            verification_note = "candidate failed syntax check - DROP"
        else:
            # --- at most one Email Verifier operation ------------------
            try:
                verifier = adapter.verify_email(candidate)
            except Exception as exc:
                report["api_calls"] = {"email_finder": 1, "email_verifier": 1}
                report["hunter_verifier_error"] = f"{type(exc).__name__}: {exc}"
                report["email_resolution"] = "HUNTER_VERIFIER_ERROR"
                report["final"] = "HUNTER_DID_NOT_RESOLVE_ELIGIBLE_EMAIL"
                path = _OUT / "m6.10-hunter-greg-resolution-2026-09-06.json"
                path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
                print(f"hunter verifier error: {type(exc).__name__}")
                return 1
            report["api_calls"] = {"email_finder": 1, "email_verifier": 1}
            outcome = _verifier_outcome(verifier.status, verifier.is_catch_all, verifier.mx_records)
            report["hunter_verifier"] = {
                "status": verifier.status,
                "is_catch_all": verifier.is_catch_all,
                "mx_records": verifier.mx_records,
                "smtp_check": verifier.smtp_check,
                "verifier_score": verifier.score,
                "verified_at": verifier.verified_at.isoformat(),
                "policy_outcome": outcome,
            }
            fresh = not verification_is_expired(verifier.verified_at, _NOW)
            if outcome == "VALID" and fresh:
                email_endpoint = candidate
                # source-verified via an approved third-party verifier;
                # provenance INFERRED if Hunter generated it from a pattern.
                verification_state = EmailVerificationState.SOURCE_VERIFIED
                _prov = "INFERRED" if finder.provenance_kind != "observed" else "OBSERVED"
                verification_note = (
                    "Hunter Email Verifier status=valid, mx=true, not catch-all, "
                    f"verified {verifier.verified_at.date()}, fresh (<90d); provenance={_prov}"
                )
                # run the general eligibility gate
                policy = {
                    SourceCategory.APPROVED_CONTACT_VERIFICATION: ContactSourcePolicySettings(
                        allowed=True,
                        required_verification=EmailVerificationState.SOURCE_VERIFIED,
                        pattern_derived_email_permitted=True,
                    )
                }
                email_kind = (
                    EmailKind.PATTERN_DERIVED_EMAIL
                    if finder.provenance_kind != "observed"
                    else EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL
                )
                email_disposition = evaluate_email_eligibility(
                    email_kind=email_kind,
                    source_category=SourceCategory.APPROVED_CONTACT_VERIFICATION,
                    verification_state=verification_state,
                    identity_match=True,
                    company_domain_match=True,
                    role_eligible=True,
                    matrix=matrix,
                    policy=policy,
                    suppressed=False,
                )
            else:
                email_disposition = EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
                verification_note = f"verifier policy outcome {outcome} (fresh={fresh}) - DROP"
        report["email_resolution_note"] = verification_note

    # --- endpoint evidence + channel ranking ---------------------------
    email_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "email-hunter-2026-09-06"),
        person=person,
        channel=Channel.EMAIL,
        endpoint=email_endpoint,
        endpoint_kind="hunter_email_finder+verifier",
        source_category=SourceCategory.APPROVED_CONTACT_ENRICHMENT,
        provider="Hunter (hunter.io)",
        source_url=None,
        observed_at=finder.retrieved_at,
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=email_endpoint != "UNRESOLVED",
        verification_method=VerificationMethod.APPROVED_THIRD_PARTY_VERIFICATION_SERVICE,
        verification_result=verification_state,
        matrix=matrix,
        eligibility_disposition=email_disposition,
        suppressed=False,
    )

    linkedin_disposition, _mode = evaluate_linkedin_eligibility(
        profile_state=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        suppressed=False,
    )
    linkedin_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "linkedin-2026-09-06b"),
        person=person,
        channel=Channel.LINKEDIN,
        endpoint="https://www.linkedin.com/in/greg-yamin-a226a113/",
        endpoint_kind=str(LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE),
        source_category=SourceCategory.APPROVED_PROFESSIONAL_PROFILE,
        provider="web search snippet (profile page not fetched - platform terms)",
        source_url=None,
        observed_at=datetime(2026, 9, 5, 9, 45, tzinfo=UTC),
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.MULTI_SOURCE_CORROBORATION,
        verification_result=LinkedInProfileState.LINKEDIN_PROFILE_PROBABLE,
        matrix=matrix,
        eligibility_disposition=linkedin_disposition,
        suppressed=False,
    )

    phone_resolution = evaluate_phone_eligibility(
        phone_kind=PhoneKind.MAIN_BUSINESS_PHONE,
        reachability=PhoneReachability.INDIRECT,
        verified=True,
        matrix=matrix,
        suppressed=False,
    )
    phone_evidence = build_endpoint_evidence(
        id_=uuid5(person.id, "phone-2026-09-06b"),
        person=person,
        channel=Channel.PHONE,
        endpoint="512-450-1980",
        endpoint_kind=str(PhoneKind.MAIN_BUSINESS_PHONE),
        source_category=SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        provider="aplusac.com + BBB (first party / directory)",
        source_url="https://www.aplusac.com/about-us/our-team/",
        observed_at=datetime(2026, 9, 5, 9, 45, tzinfo=UTC),
        source_evidence_sha256=None,
        identity_match=True,
        company_domain_match=True,
        verification_method=VerificationMethod.FIRST_PARTY_PAGE_OBSERVATION,
        verification_result=None,
        matrix=matrix,
        eligibility_disposition=phone_execution_disposition(phone_resolution, matrix),
        suppressed=False,
    )

    ranking = rank_channels((email_evidence, linkedin_evidence, phone_evidence))
    report["channels"] = {
        str(e.channel): {
            "endpoint": e.endpoint
            if e.channel is not Channel.EMAIL
            else (
                "[redacted work email - in PRIMARY_A packet only]"
                if e.endpoint != "UNRESOLVED"
                else "UNRESOLVED"
            ),
            "eligibility_disposition": str(e.eligibility_disposition),
            "verification_result": str(e.verification_result) if e.verification_result else None,
        }
        for e in (email_evidence, linkedin_evidence, phone_evidence)
    }
    report["channel_ranking"] = {
        str(entry.channel): {
            "eligible": entry.eligible,
            "disposition": str(entry.disposition),
            "score": entry.score,
        }
        for entry in ranking.entries
    }
    report["recommended_channel"] = (
        str(ranking.recommended_channel) if ranking.recommended_channel else None
    )
    report["email_eligible_verified_recipient"] = (
        email_disposition is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT
    )
    report["final"] = (
        "READY_FOR_PRIMARY_A_EXACT_PACKAGE_REVIEW"
        if email_disposition is EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT
        else "HUNTER_DID_NOT_RESOLVE_ELIGIBLE_EMAIL"
    )

    path = _OUT / "m6.10-hunter-greg-resolution-2026-09-06.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("hunter activation: AUTHORIZED_WITH_CONTROLS")
    print(
        f"finder: email_present={finder.email is not None} score={finder.score} "
        f"provenance={finder.provenance_kind}"
    )
    print(f"email disposition: {email_disposition}")
    print(f"recommended channel: {ranking.recommended_channel}")
    print(f"final: {report['final']}")
    print(f"report: {path.relative_to(ROOT)}")
    # the resolved email endpoint (if any) is written to the JSON report for
    # the PRIMARY_A packet build step; not printed here.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
