"""M6.9 Stage B - REAL BOUNDED A-PLUS ENGINE RUN.

Owner authorization 2026-09-05 "IMPLEMENT SUPPRESSION / OPT-OUT CONTROLS, THEN
EXECUTE REAL BOUNDED A-PLUS ENGINE RUN", Stage B. Runs only after Stage A
(suppression/opt-out controls) is committed and green.

Scope, honestly stated (do not overclaim): this script performs a genuine
passive public-data fetch of A-Plus Air Conditioning & Home Solutions' public
pages (already captured separately via curl/WebFetch, real HTTP 200s, real
sha256 content hashes - not the ``tests/m68_fixtures.py`` fixture's synthetic
placeholder provenance), and assembles a REAL ``SemanticEnvelope`` from that
freshly-captured evidence using the same production ``assemble_envelope``
call the fixture uses. It does NOT stand up a full DB-backed workspace
running the M1 crawl worker / M2 opportunity engine / M3 audit engine end to
end - that would require production crawler/worker infrastructure this
bounded task does not provision. Generic, non-company-specific defaults
(economics-insufficient state, the standard explicit-unknowns list, the
standard CTA, the standard demo-safety facts) are reused verbatim from
``tests/m68_fixtures.py`` because they are genuinely generic policy text, not
convenient shortcuts around company-specific evidence.

Makes exactly ONE real anthropic claude-sonnet-5 call (the single bounded
pilot candidate - not the N=3 shadow-evaluation pattern), then resolves the
disclosure slots this pilot's real supplied configuration can resolve
(Proofline/Andrew sender identity, postal disclosure, opt-out notice),
leaving the demo URL unresolved. Compiles the real M4 builder brief from the
same real envelope. No contact resolution, no send, no demo deployment.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_fixtures import (  # noqa: E402
    _COVERAGE_FINDING,
    _ECONOMICS,
    _INFERENCE,
    _RECOMMENDATION,
    _UNKNOWN_FINDING,
    _observed_finding,
)
from opintel_communication.anthropic_adapter import (  # noqa: E402
    ANTHROPIC_API_ENDPOINT,
    PINNED_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
    _model_family,
)
from opintel_communication.builder_story import (  # noqa: E402
    compile_builder_story,
    render_builder_story_markdown,
)
from opintel_communication.certification import CONFIRMED_SONNET5_PRICE_TABLE  # noqa: E402
from opintel_communication.compactor import compact_candidate  # noqa: E402
from opintel_communication.domain import (  # noqa: E402
    BusinessIdentity,
    ReferenceArtifacts,
    SemanticEnvelope,
    SourceLineage,
)
from opintel_communication.envelope import assemble_envelope  # noqa: E402
from opintel_communication.envelope_projection import (  # noqa: E402
    WITHHELD_FROM_PROVIDER,
    provider_facing_projection,
)
from opintel_communication.hashing import sha256_text  # noqa: E402
from opintel_communication.prompt import build_certification_prompt_bundle_v9  # noqa: E402
from opintel_communication.quality import assess_quality  # noqa: E402
from opintel_communication.stub_provider import parse_provider_response  # noqa: E402
from opintel_communication.validator import OutputValidator  # noqa: E402
from opintel_opportunity.domain import CompanyFact, FactCategory  # noqa: E402
from opintel_suppression import (  # noqa: E402
    PROOFLINE_SENDER_IDENTITY,
    resolve_known_disclosure_slots,
)

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_M4_OUT = ROOT / "docs" / "readiness" / "demo-builder-brief"
_CONFIG = GenerationConfig(model=PINNED_MODEL, thinking="disabled", max_output_tokens=8000)
_CONTRACT = "v3"
_HOSTNAME = "www.aplusac.com"
_CAPTURED_AT = datetime(2026, 9, 5, 9, 45, tzinfo=UTC)

# Real, freshly captured 2026-09-05 via `curl` (HTTP 200 each) then verified
# with `grep`/regex against the raw HTML - not the fixture's placeholder
# ``https://example.com/...`` + ``"a" * 64`` provenance.
_REAL_PAGES = {
    "intake": (
        "https://www.aplusac.com/press-releases/when-to-schedule-ac-replacement/",
        "7a9934dcc38ffeae61a656a0533e1d24ec402f2661470610eb13964f048e6ad3",
    ),
    "commercial": (
        "https://www.aplusac.com/commercial-hvac/",
        "38abd278346387e88c9e89e609c9f679d25c59d2eb48f90cdaf155b19604eef3",
    ),
    "area": (
        "https://www.aplusac.com/service-area/",
        "d6ecb8709c821986b7da76f5893f6830a88ae71a3f765b01debb5abcfe85f8f3",
    ),
}

_REAL_INTAKE = "When to Schedule AC Replacement"
_REAL_COMMERCIAL = "The Austin Commercial AC Repair Company"
_REAL_RESPONSE = (
    "we will do everything in our power to fix your problem fast, sometimes even on the same day"
)
_REAL_AREA = "Service Area"


def _uid() -> UUID:
    return uuid4()


def _cf(
    tag: str, category: FactCategory, phrase: str, fact_class: str, page_purpose: str, uri_key: str
) -> CompanyFact:
    uri, sha = _REAL_PAGES[uri_key]
    return CompanyFact(
        id=_uid(),
        hypothesis_id=_uid(),
        category=category,
        phrase=phrase,
        evidence_id=_uid(),
        fact_class=fact_class,
        page_purpose=page_purpose,
        source_uri=uri,
        content_sha256=sha,
        selector_version="commercial_hvac.company_fact_selector@3",
        created_at=_CAPTURED_AT,
        verbatim_phrase=phrase,
    )


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def real_aplus_envelope(candidate_count: int = 1) -> SemanticEnvelope:
    facts = (
        _cf(
            "f-intake",
            FactCategory.INTAKE_SURFACE,
            _REAL_INTAKE,
            "public_inbound_path",
            "press_release_article",
            "intake",
        ),
        _cf(
            "f-commercial",
            FactCategory.COMMERCIAL_CONTEXT,
            _REAL_COMMERCIAL,
            "public_service_description",
            "commercial_hvac_service_page",
            "commercial",
        ),
        _cf(
            "f-response",
            FactCategory.RESPONSE_COMMITMENT,
            _REAL_RESPONSE,
            "public_inbound_path",
            "commercial_hvac_service_page",
            "commercial",
        ),
        _cf(
            "f-area",
            FactCategory.SERVICE_AREA_CONTEXT,
            _REAL_AREA,
            "public_service_area",
            "service_area_page",
            "area",
        ),
    )
    rendered = frozenset({str(facts[0].id), str(facts[1].id)})
    omission = {
        str(facts[2].id): (
            "outreach.projection@4: the fixed first-contact frame renders only the first two "
            "ordered facts; recorded as an intentional omission, not dropped."
        ),
        str(facts[3].id): "outreach.projection@4: thin fact, not rendered in the first contact.",
    }
    findings = (
        _observed_finding(
            "f-intake",
            "observed_intake_surface",
            "finding.intake_surface",
            _REAL_INTAKE,
            f"Observed intake surface: the captured public pages present a request path "
            f'("{_REAL_INTAKE}").',
        ),
        _observed_finding(
            "f-commercial",
            "observed_commercial_context",
            "finding.commercial_context",
            _REAL_COMMERCIAL,
            f"Observed commercial-service context: the captured public pages describe "
            f'commercial HVAC work ("{_REAL_COMMERCIAL}").',
        ),
        _observed_finding(
            "f-response",
            "observed_response_commitment",
            "finding.response_commitment",
            _REAL_RESPONSE,
            f"Observed response commitment: the business's own commercial HVAC page states "
            f"{_REAL_RESPONSE!r}.",
        ),
        _observed_finding(
            "f-area",
            "observed_service_area",
            "finding.service_area_context",
            _REAL_AREA,
            f"Observed service-area context: the captured public pages list a service area "
            f'("{_REAL_AREA}").',
        ),
        _UNKNOWN_FINDING,
        _COVERAGE_FINDING,
    )
    lineage = SourceLineage(
        workspace_id=_uid(),
        business_id=_uid(),
        research_run_id=_uid(),
        opportunity_hypothesis_revision_id=_uid(),
        audit_revision_id=_uid(),
        audit_revision_hash=_canonical_hash([f.rendered_text for f in findings]),
        demo_revision_id=_uid(),
        demo_specification_hash=_canonical_hash(
            {"hostname": _HOSTNAME, "facts": [f.phrase for f in facts]}
        ),
        outreach_revision_id=_uid(),
        outreach_content_hash=_canonical_hash(
            {"subject": "A quick question about A-Plus AC's intake process"}
        ),
        m2_m5_bundle_sha256="a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7",
        policy_versions=(
            ("company_fact_selector", "commercial_hvac.company_fact_selector@3"),
            ("phrase_sanitation", "commercial_hvac.phrase_sanitation@1"),
            ("demo_composition", "demo.commercial_hvac.lead_response@3"),
            ("outreach_projection", "outreach.projection@4"),
            ("outreach_qc", "outreach.qc@3"),
        ),
    )
    reference = ReferenceArtifacts(
        subject="A quick question about A-Plus AC's intake process",
        first_contact_email=(
            "Hello {{functional_role_or_team}},\n\n"
            f'your website has a public request path — "{_REAL_INTAKE}".\n\n'
            f'your site describes commercial HVAC work — "{_REAL_COMMERCIAL}".\n\n'
            "a step that acknowledges and sorts new service requests could be evaluated.\n\n"
            "This is not a claim about how your team works today — we have no visibility "
            "into that.\n\n"
            "We prepared a short deterministic simulation based only on approved public "
            "information.\n\n"
            "It is a simulation—not a system deployed, connected, official, or operated by "
            "the business.\n\n"
            f'I noticed your site offers "{_REAL_INTAKE}". I\'m curious — roughly how many '
            "commercial inquiries arrive in a typical month, and how after-hours ones are "
            "handled today?\n\n"
            "{{verified_sender_signature}}\n\n{{required_postal_disclosure}}\n\n"
            "{{approved_opt_out_instruction}}"
        ),
        follow_up_draft=f'I noticed your site offers "{_REAL_INTAKE}". ...',
        call_opening_script="{{truthful_verified_sender_introduction}} ...",
        note="Semantic floor and fallback; Claude is not asked to rewrite these.",
    )
    return assemble_envelope(
        generated_at=_CAPTURED_AT,
        source_lineage=lineage,
        business_identity=BusinessIdentity(
            display_name="A-Plus Air Conditioning & Home Solutions",
            name_tokens=("A-Plus", "Air", "Conditioning", "Home", "Solutions"),
            exact_public_hostname=_HOSTNAME,
            identity_note=(
                "Display name and hostname are the only identity assertions permitted. No "
                "inferred location, size, ownership, tenure, or affiliation."
            ),
        ),
        company_facts=facts,
        rendered_fact_ids=rendered,
        deterministic_omission_by_fact_id=omission,
        m3_findings=findings,
        conditional_inferences=(_INFERENCE,),
        recommendations=(_RECOMMENDATION,),
        economics=_ECONOMICS,
        available_validation_questions=(
            "Approximately how many new commercial service or quote inquiries arrive in a "
            "typical month, and through which channels?",
            "How are new inquiries acknowledged today, including after hours, and what "
            "response times are typical?",
        ),
        reference_artifacts=reference,
        candidate_count=candidate_count,
    )


def _apikeys_path() -> Path:
    for base in (ROOT, *ROOT.parents):
        p = base / "apikeys.txt"
        if p.is_file():
            return p
    raise SystemExit("apikeys.txt not found")


def _read_key() -> str:
    for line in _apikeys_path().read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s.upper().startswith("ANTHROPIC:"):
            v = s.split(":", 1)[1].strip()
            if not v:
                raise SystemExit("ANTHROPIC: line has no value")
            return v
    raise SystemExit("no ANTHROPIC: line in apikeys.txt")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="make the real provider call")
    args = ap.parse_args()

    print("M6.9 Stage B - real bounded A-Plus engine run")
    print(f"  endpoint {ANTHROPIC_API_ENDPOINT}")
    env = real_aplus_envelope(candidate_count=1)

    print("\n-- preflight --")
    if _model_family(_CONFIG.model) != "claude-sonnet-5":
        raise SystemExit("PREFLIGHT FAIL: model is not the claude-sonnet-5 family")
    proj = provider_facing_projection(env)
    blob = json.dumps(proj).lower()
    for w in WITHHELD_FROM_PROVIDER:
        if f'"{w}"' in blob:
            raise SystemExit(f"PREFLIGHT FAIL: withheld key {w} in projection")
    ident = proj.get("business_identity", {})
    if set(ident) - {"display_name", "public_hostname", "identity_rule"}:
        raise SystemExit(f"PREFLIGHT FAIL: identity carries more than allowed: {sorted(ident)}")
    print(f"  envelope {env.envelope_sha256}")
    print(f"  distinctive={env.has_distinctive_fact()}")
    print("  identity projection allow-listed (display_name + hostname only)")

    m4 = compile_builder_story(envelope=env)
    m4_md = render_builder_story_markdown(m4)
    m4_hash = sha256_text(m4_md)
    _M4_OUT.mkdir(parents=True, exist_ok=True)
    (_M4_OUT / "m6.9-real-run-aplus-builder-brief-2026-09-05.md").write_text(
        m4_md, encoding="utf-8"
    )

    result: dict[str, object] = {
        "task": "M6.9 Stage B real bounded A-Plus engine run",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
        "envelope_sha256": env.envelope_sha256,
        "m2_m5_bundle_sha256": env.source_lineage.m2_m5_bundle_sha256,
        "m4_builder_brief_version": m4.version
        if hasattr(m4, "version")
        else "demo.builder_brief@3.2",
        "m4_builder_brief_sha256": m4_hash,
        "distinctive": env.has_distinctive_fact(),
        "real_pages_captured": {
            k: {"url": u, "content_sha256": s, "captured_at_utc": _CAPTURED_AT.isoformat()}
            for k, (u, s) in _REAL_PAGES.items()
        },
    }

    if not args.execute:
        print("\ndry run only. preflight + M4 compile passed. no provider call made.")
        (_OUT / "m6.9-real-run-aplus-2026-09-05-dryrun.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        return 0

    key = _read_key()
    adapter = AnthropicProviderAdapter(key, config=_CONFIG)
    bundle = build_certification_prompt_bundle_v9(env).bundle_text
    t0 = time.time()
    text, meta = adapter.generate(bundle)
    latency = round(time.time() - t0, 1)
    call_cost = Decimal(
        CONFIRMED_SONNET5_PRICE_TABLE.cost_usd(meta.input_tokens, meta.output_tokens)
    )
    if _model_family(meta.model_version) != "claude-sonnet-5":
        raise SystemExit(f"served '{meta.model_version}' not sonnet-5 - aborting")

    parsed = parse_provider_response(text)
    if not parsed.candidates:
        result["provider_result"] = {
            "parse_status": str(parsed.status),
            "parse_reason": parsed.reason,
        }
        result["cost_usd"] = str(call_cost)
        path = _OUT / "m6.9-real-run-aplus-2026-09-05.json"
        path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"\nNO CANDIDATE PARSED: {parsed.status} {parsed.reason}")
        print(f"report: {path.relative_to(ROOT)}")
        return 1

    cand = parsed.candidates[0]
    compacted, audit = compact_candidate(cand, env)
    vr = OutputValidator(contract=_CONTRACT).validate(env, compacted)
    qa = assess_quality(compacted, env)
    arts = {a.kind: a.text for a in compacted.artifacts}
    subject = arts.get("subject", "")
    body = arts.get("first_contact_email", "") or arts.get("body", "")

    resolved_body = resolve_known_disclosure_slots(body, PROOFLINE_SENDER_IDENTITY)

    result["provider"] = {
        "served_model": meta.model_version,
        "stop_reason": meta.stop_reason,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_s": latency,
    }
    result["cost_usd"] = str(call_cost)
    result["subject"] = subject
    result["subject_has_adv_prefix"] = subject.upper().startswith("ADV")
    result["body_frozen_sha256"] = sha256_text(body)
    result["body_frozen"] = body
    result["body_with_known_slots_resolved"] = resolved_body
    result["unresolved_tokens_remaining"] = [
        tok for tok in ("{{exact_demo_url}}", "{{functional_role_or_team}}") if tok in resolved_body
    ]
    result["compacted"] = bool(audit.removed_sentences)
    result["validator"] = {
        "passed": vr.passed,
        "findings": [f.code for f in vr.findings],
        "canonical_coverage": vr.canonical_reconciliation_coverage,
        "unresolved_substantive_claims": vr.unresolved_substantive_claims,
    }
    result["quality"] = {
        "classification": qa.classification,
        "score": qa.score,
        "uses_company_specific_evidence": qa.uses_company_specific_evidence,
        "uses_strongest_hook": qa.uses_strongest_hook,
        "body_word_count": qa.body_word_count,
    }

    path = _OUT / "m6.9-real-run-aplus-2026-09-05.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nsubject: {subject!r}")
    print(f"validator passed={vr.passed} findings={[f.code for f in vr.findings]}")
    print(f"quality: {qa.classification} ({qa.score})")
    print(f"cost USD {call_cost}")
    print(f"report: {path.relative_to(ROOT)}")
    m4_path = _M4_OUT / "m6.9-real-run-aplus-builder-brief-2026-09-05.md"
    print(f"M4 brief: {m4_path.relative_to(ROOT)}")
    print("No send. No recipient resolution. No demo deployment. STOP for PROJECT_OWNER review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
