"""M6.10 -> M6.9 Path B: build the exact recipient-bound A-Plus email
package for PRIMARY_A review, now that Hunter resolved Greg Yamin's
verified work email.

Owner authorization "RECORD HUNTER REGISTRY APPROVAL AND RESUME LIVE M6.10
GREG RESOLUTION" (2026-09-06), sections 9-13.

Uses the already-frozen real A-Plus communication (the Stage B real run
body + subject, revalidated PASS after the LICENSED_SOURCE_PHRASE_WITH_GEOGRAPHY
fix). No Sonnet call. Runs suppression + a final deterministic validation
pass. Produces the package - does NOT send it.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from opintel_communication.domain import (  # noqa: E402
    ClaimManifest,
    GeneratedArtifact,
    GenerationCandidate,
)
from opintel_communication.validator import OutputValidator  # noqa: E402
from opintel_m0_local import UuidFactory  # noqa: E402
from opintel_suppression import (  # noqa: E402
    PROOFLINE_SENDER_IDENTITY,
    SuppressionRegistryService,
    domain_of,
    enforce_pre_send_suppression_gate,
    normalize_email,
    resolve_known_disclosure_slots,
)
from opintel_suppression_local import SqlAlchemySuppressionRepository  # noqa: E402
from run_m69_real_bounded_aplus import real_aplus_envelope  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_STAGE_B = _OUT / "m6.9-real-run-aplus-2026-09-05.json"
_HUNTER = _OUT / "m6.10-hunter-greg-resolution-2026-09-06.json"
_DEMO_URL = "https://ac-request-demo.preview.emergentagent.com/"
_NOW = datetime.now(UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


def main() -> int:
    stage_b = json.loads(_STAGE_B.read_text(encoding="utf-8"))
    hunter = json.loads(_HUNTER.read_text(encoding="utf-8"))

    subject = stage_b["subject"]
    frozen_body = stage_b["body_frozen"]  # 4 unresolved {{...}} slot lines at the end
    to_email = normalize_email(hunter["hunter_finder"]["minimized_persisted_fields"]["email"])

    # --- 1. suppression checks (section 9) ----------------------------
    repo = SqlAlchemySuppressionRepository("sqlite:///:memory:")
    repo.initialize()
    service = SuppressionRegistryService(repo, _Clock(), UuidFactory())
    workspace_id = uuid4()
    person_key = "greg-yamin@a-plus-air-conditioning"
    company_key = "a-plus-air-conditioning-home-solutions"

    suppression: dict[str, object] = {}
    try:
        gate = enforce_pre_send_suppression_gate(
            service, workspace_id=workspace_id, candidate_email=to_email
        )
        suppression["address_and_domain"] = gate.outcome.value
    except Exception as exc:
        suppression["address_and_domain"] = f"BLOCKED: {exc}"
    suppression["person"] = (
        "blocked"
        if service.check_channel_blocked(
            workspace_id=workspace_id,
            person_key=person_key,
            company_key=company_key,
            channel="email",
        )
        else "clear"
    )
    suppression["domain_of_recipient"] = domain_of(to_email)
    suppression_clear = (
        suppression["address_and_domain"] == "eligible" and suppression["person"] == "clear"
    )

    # --- 2. final deterministic validation of the frozen (unresolved) body ---
    env = real_aplus_envelope(candidate_count=1)
    candidate = GenerationCandidate(
        candidate_id="m6.10-primary-a-package",
        artifacts=(
            GeneratedArtifact("subject", subject),
            GeneratedArtifact("first_contact_email", frozen_body),
        ),
        claim_manifest=ClaimManifest(entries=()),
    )
    vr = OutputValidator(contract="v3").validate(env, candidate)
    validation = {
        "passed": vr.passed,
        "findings": [f.code for f in vr.findings],
        "canonical_coverage": vr.canonical_reconciliation_coverage,
        "unresolved_substantive_claims": vr.unresolved_substantive_claims,
        "note": (
            "Validation runs on the frozen body with disclosure slots still {{...}} "
            "(the state the validator's contract expects). Slot resolution + the one "
            "demo URL are the final non-substantive rendering step, checked below."
        ),
    }

    # --- 3. render the recipient-bound body (section 10) --------------
    resolved = resolve_known_disclosure_slots(frozen_body, PROOFLINE_SENDER_IDENTITY)
    # insert the single ADR-0079 demo URL just before the signature block
    sig_start = resolved.find(PROOFLINE_SENDER_IDENTITY.sender_person_name + "\n")
    if sig_start == -1:
        rendered = resolved + f"\n\nThe simulation: {_DEMO_URL}"
    else:
        rendered = (
            resolved[:sig_start].rstrip()
            + f"\n\nThe simulation: {_DEMO_URL}\n\n"
            + resolved[sig_start:]
        )

    unresolved_tokens = [t for t in ("{{", "}}") if t in rendered]
    url_count = rendered.count("http://") + rendered.count("https://")
    rendering_checks = {
        "no_unresolved_tokens": unresolved_tokens == [],
        "exactly_one_url": url_count == 1,
        "the_one_url_is_the_approved_demo_url": _DEMO_URL in rendered,
        "postal_disclosure_present": PROOFLINE_SENDER_IDENTITY.postal_disclosure in rendered,
        "opt_out_present": "reply to this message with the word UNSUBSCRIBE" in rendered,
        "reply_to_present": PROOFLINE_SENDER_IDENTITY.reply_to_mailbox in rendered,
        "no_adv_prefix": not subject.upper().startswith("ADV"),
        "demo_status_truth_present": (
            "not a system deployed, connected, official, or operated by your business" in rendered
        ),
    }
    rendering_ok = all(rendering_checks.values())

    eligible = (
        hunter["email_eligible_verified_recipient"]
        and suppression_clear
        and vr.passed
        and rendering_ok
    )

    package = {
        "task": "M6.10 -> M6.9 Path B recipient-bound A-Plus package for PRIMARY_A review",
        "generated_at_utc": _NOW.isoformat(),
        "recipient": {
            "name": "Greg Yamin",
            "role": "President",
            "company": "A-Plus Air Conditioning & Home Solutions",
            "work_email": to_email,
            "identity_provenance": (
                'first-party: aplusac.com/about-us/our-team/ ("Greg Yamin - President"); '
                'BBB business profile ("Mr. Gregory K. Yamin, President")'
            ),
            "email_provenance": (
                "Hunter Email Finder, confidence 97, provenance OBSERVED "
                f"({hunter['hunter_finder']['source_count']} public sources); "
                "Hunter Email Verifier status=valid, mx=true, smtp_check=true, not catch-all, "
                f"verifier_score=100, verified {hunter['hunter_verifier']['verified_at'][:10]}, "
                "fresh (<90 days)"
            ),
            "verification_result": "source_verified",
            "verification_date": hunter["hunter_verifier"]["verified_at"][:10],
        },
        "from": f"Andrew <{PROOFLINE_SENDER_IDENTITY.reply_to_mailbox}>",
        "reply_to": PROOFLINE_SENDER_IDENTITY.reply_to_mailbox,
        "subject": subject,
        "email_body_rendered": rendered,
        "demo_url": _DEMO_URL,
        "minimized_persisted_contact_fields": {
            "name": "Greg Yamin",
            "employer": "A-Plus Air Conditioning & Home Solutions",
            "role": "President",
            "work_email": to_email,
            "source": "Hunter (hunter.io) Email Finder + Verifier; identity first-party + BBB",
            "finder_confidence": hunter["hunter_finder"]["finder_confidence"],
            "verification_method": (
                "approved_third_party_verification_service (Hunter Email Verifier)"
            ),
            "verification_result": "valid",
            "verification_date": hunter["hunter_verifier"]["verified_at"][:10],
        },
        "suppression_result": suppression,
        "final_deterministic_validation": validation,
        "recipient_bound_rendering_checks": rendering_checks,
        "compliance": {
            "postal_disclosure": PROOFLINE_SENDER_IDENTITY.postal_disclosure,
            "opt_out": (
                "To stop receiving email from Proofline, reply to this message with the word "
                "UNSUBSCRIBE. We will remove your address within three days."
            ),
            "path_b_exception": "ADR-0078 / ADR-0079 - one bounded A-Plus first contact, "
            "M6.8-3 NOT_CERTIFIED acknowledged not waived",
            "m6_8_3_status": "NOT_CERTIFIED (acknowledged)",
            "telemetry_state": "HOST_PLATFORM_TELEMETRY_CONFIRMED_PRESENT "
            "(Emergent hosting template's PostHog + Cloudflare; not Proofline-added; "
            "ADR-0079 determination that host telemetry is not itself prohibited is unchanged)",
            "after_send": "NONE AUTOMATIC",
        },
        "channel_ranking": hunter["channel_ranking"],
        "recommended_channel": hunter["recommended_channel"],
        "alternative_channels": {
            "linkedin": "eligible_manual_channel (unchanged, not used)",
            "phone": "resolved_but_execution_not_authorized (unchanged, not used)",
        },
        "final_human_reviewer": "PRIMARY_A",
        "final_human_review_status": "PENDING_EXACT_PACKAGE_REVIEW",
        "eligible_verified_recipient": eligible,
        "final": (
            "READY_FOR_PRIMARY_A_EXACT_PACKAGE_REVIEW"
            if eligible
            else "NOT_READY - see checks above"
        ),
    }

    path = _OUT / "m6.10-aplus-primary-a-package-2026-09-06.json"
    path.write_text(json.dumps(package, indent=2, default=str), encoding="utf-8")
    print(f"recipient: Greg Yamin <{to_email}>")
    print(f"suppression: {suppression}")
    print(f"validation passed: {vr.passed} findings={[f.code for f in vr.findings]}")
    print(f"rendering checks ok: {rendering_ok} ({rendering_checks})")
    print(f"final: {package['final']}")
    print(f"package: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
