"""M6.10 - one bounded readability revision of the real A-Plus first-contact email.

Owner authorization 2026-09-06 "ADDRESS PRIMARY_A PRE-APPROVAL FINDINGS AND
PRODUCE REVISED EXACT PACKAGE", section 2. PRIMARY_A found the M6.9 Stage B
body truthful but unnecessarily dense.

EXACTLY ONE bounded revision cycle:
  - same authoritative semantic envelope (frozen ``real_aplus_envelope``) -
    unchanged;
  - the existing accepted transformer (claude-sonnet-5 + deterministic
    validator + compactor), new prompt template
    ``comm.prompt_template.first_contact@10`` (wording-only: shorter target,
    compare-CTA, salutation placement, spread the disclosure meanings);
  - MAXIMUM 1 provider generation. No candidate tournament. No retry to
    gate-fit. If the single revision fails substantive validation, the
    previous package is retained and the failure is reported.

No send, no recipient resolution here, no demo deployment.
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from opintel_communication.anthropic_adapter import (  # noqa: E402
    ANTHROPIC_API_ENDPOINT,
    PINNED_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
    _model_family,
)
from opintel_communication.certification import CONFIRMED_SONNET5_PRICE_TABLE  # noqa: E402
from opintel_communication.compactor import compact_candidate  # noqa: E402
from opintel_communication.domain import ValidatorSeverity  # noqa: E402
from opintel_communication.envelope_projection import provider_facing_projection  # noqa: E402
from opintel_communication.hashing import sha256_text  # noqa: E402
from opintel_communication.prompt import (  # noqa: E402
    PROMPT_TEMPLATE_ID_CERT_V10,
    build_certification_prompt_bundle_v10,
)
from opintel_communication.quality import assess_quality  # noqa: E402
from opintel_communication.stub_provider import parse_provider_response  # noqa: E402
from opintel_communication.validator import OutputValidator  # noqa: E402
from opintel_suppression import (  # noqa: E402
    PROOFLINE_SENDER_IDENTITY,
    resolve_known_disclosure_slots,
)
from run_m69_real_bounded_aplus import real_aplus_envelope  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_CONFIG = GenerationConfig(model=PINNED_MODEL, thinking="disabled", max_output_tokens=8000)
_CONTRACT = "v3"
_PREV = _OUT / "m6.9-real-run-aplus-2026-09-05.json"


def _read_key() -> str:
    for base in (ROOT, *ROOT.parents):
        p = base / "apikeys.txt"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s.upper().startswith("ANTHROPIC:"):
                    v = s.split(":", 1)[1].strip()
                    if not v:
                        raise SystemExit("ANTHROPIC: line has no value")
                    return v
    raise SystemExit("no ANTHROPIC: line in apikeys.txt")


def _visible_word_count(body: str) -> int:
    words = 0
    for line in body.splitlines():
        st = line.strip()
        if not st or (st.startswith("{{") and st.endswith("}}")):
            continue
        words += len(st.split())
    return words


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="make the one real provider call")
    args = ap.parse_args()

    env = real_aplus_envelope(candidate_count=1)
    prev = json.loads(_PREV.read_text(encoding="utf-8"))
    bundle = build_certification_prompt_bundle_v10(env)

    # The authoritative envelope is UNCHANGED at the substantive level. Its
    # internal record UUIDs (and therefore envelope_sha256 / projection ref ids)
    # are freshly minted on every construction - pre-existing behaviour of
    # real_aplus_envelope, relied on by the M6.9 Stage B run itself. What must
    # not drift is the licensed content: the fact phrases and the disclosure
    # canonical texts. This run changes only the prompt wording (@9 -> @10).
    _proj = provider_facing_projection(env)
    substantive_invariants = {
        "licensed_fact_phrases": sorted(f["sanitized_phrase"] for f in _proj["licensed_facts"]),
        "licensed_finding_texts": sorted(f["licensed_text"] for f in _proj["licensed_findings"]),
        "disclosure_canonical_texts": sorted(
            d.canonical_text for d in env.required_disclosures if d.canonical_text
        ),
        "cta_intent": env.structured_cta.cta_intent,
        "prohibited_claims": sorted(env.prohibited_claims),
    }

    print("M6.10 readability revision - one bounded cycle")
    print(f"  endpoint {ANTHROPIC_API_ENDPOINT}")
    print(f"  template {PROMPT_TEMPLATE_ID_CERT_V10}  bundle_sha256 {bundle.bundle_sha256}")
    print(f"  envelope {env.envelope_sha256}  (unchanged)")
    print(f"  previous body words: {_visible_word_count(prev['body_frozen'])}")

    if not args.execute:
        print("\ndry run only - no provider call made.")
        return 0

    if _model_family(_CONFIG.model) != "claude-sonnet-5":
        raise SystemExit("PREFLIGHT FAIL: model is not the claude-sonnet-5 family")

    adapter = AnthropicProviderAdapter(_read_key(), config=_CONFIG)
    t0 = time.time()
    text, meta = adapter.generate(bundle.bundle_text)
    latency = round(time.time() - t0, 1)
    call_cost = Decimal(
        CONFIRMED_SONNET5_PRICE_TABLE.cost_usd(meta.input_tokens, meta.output_tokens)
    )
    if _model_family(meta.model_version) != "claude-sonnet-5":
        raise SystemExit(f"served '{meta.model_version}' not sonnet-5 - aborting")

    result: dict[str, object] = {
        "task": "M6.10 one bounded readability revision of the real A-Plus first-contact email",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
        "authoritative_envelope_substantive_invariants": substantive_invariants,
        "prompt_template": PROMPT_TEMPLATE_ID_CERT_V10,
        "prompt_bundle_sha256": bundle.bundle_sha256,
        "provider": {
            "served_model": meta.model_version,
            "stop_reason": meta.stop_reason,
            "input_tokens": meta.input_tokens,
            "output_tokens": meta.output_tokens,
            "latency_s": latency,
        },
        "provider_generations": 1,
        "cost_usd": str(call_cost),
        "previous_body_sha256": prev["body_frozen_sha256"],
        "previous_body_word_count": _visible_word_count(prev["body_frozen"]),
    }

    parsed = parse_provider_response(text)
    if not parsed.candidates:
        result["outcome"] = "NO_CANDIDATE_PARSED"
        result["parse_status"] = str(parsed.status)
        result["parse_reason"] = parsed.reason
        result["decision"] = "RETAIN_PREVIOUS_PACKAGE"
        _write(result)
        print(f"\nNO CANDIDATE PARSED: {parsed.status} {parsed.reason}")
        return 1

    cand = parsed.candidates[0]
    compacted, audit = compact_candidate(cand, env)
    vr = OutputValidator(contract=_CONTRACT).validate(env, compacted)
    qa = assess_quality(compacted, env)
    arts = {a.kind: a.text for a in compacted.artifacts}
    subject = arts.get("subject", "")
    body = arts.get("first_contact_email", "") or arts.get("body", "")
    resolved_body = resolve_known_disclosure_slots(body, PROOFLINE_SENDER_IDENTITY)

    non_advisory = [f.code for f in vr.findings if f.severity != ValidatorSeverity.ADVISORY]
    result.update(
        {
            "revised_subject": subject,
            "revised_subject_has_adv_prefix": subject.upper().startswith("ADV"),
            "revised_body_frozen": body,
            "revised_body_frozen_sha256": sha256_text(body),
            "revised_body_with_known_slots_resolved": resolved_body,
            "revised_body_word_count": _visible_word_count(body),
            "compacted": bool(audit.removed_sentences),
            "unresolved_tokens_after_known_slots": [
                t
                for t in ("{{exact_demo_url}}", "{{functional_role_or_team}}")
                if t in resolved_body
            ],
            "validator": {
                "passed": vr.passed,
                "findings": [f.code for f in vr.findings],
                "non_advisory_findings": non_advisory,
                "canonical_coverage": vr.canonical_reconciliation_coverage,
                "unresolved_substantive_claims": vr.unresolved_substantive_claims,
            },
            "quality": {
                "classification": qa.classification,
                "score": qa.score,
                "uses_company_specific_evidence": qa.uses_company_specific_evidence,
                "uses_strongest_hook": qa.uses_strongest_hook,
                "body_word_count": qa.body_word_count,
            },
        }
    )

    if vr.passed:
        result["outcome"] = "REVISION_PASSED_SUBSTANTIVE_VALIDATION"
        result["decision"] = "ADOPT_REVISED_BODY"
    else:
        result["outcome"] = "REVISION_FAILED_SUBSTANTIVE_VALIDATION"
        result["decision"] = "RETAIN_PREVIOUS_PACKAGE"

    _write(result)
    print(f"\nsubject: {subject!r}")
    print(f"revised body words (visible): {result['revised_body_word_count']}")
    print(f"validator passed={vr.passed} non_advisory={non_advisory}")
    print(f"quality {qa.classification} ({qa.score})  cost USD {call_cost}")
    print(f"decision: {result['decision']}")
    return 0 if vr.passed else 1


def _write(result: dict[str, object]) -> None:
    path = _OUT / "m6.10-aplus-readability-revision-2026-09-06.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"report: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
