"""M6.8-3 synthetic live-provider certification - local execution harness.

Owner-authorized 2026-09-01. **Attempt 4** (authorized 2026-09-02, Option 2)
after Attempts 1-3 all failed on the 2000 output-token ceiling vs. the accepted
full-claim-manifest response schema: thinking disabled, one candidate per call,
and ``max_output_tokens`` raised 2000 -> 8000 (per call and aggregate). The 9
provider-reaching scenarios run 9 repeats each = 81 ``claude-sonnet-5`` calls.
``s03_generic_weak_evidence`` stays deterministically gated and runs 3 times,
recorded separately. The atomic protocol (one envelope -> one response -> one
candidate + full manifest -> independent validation), the full claim-manifest
contract, the validator, the frozen corpus, and every threshold / zero-tolerance
finding are unchanged. New config hash (8000) => new certification key.
USD 10.00 hard aggregate ceiling, 0 retries; the budget guard refuses a call it
cannot conservatively cover at both per-call token ceilings.

This is Option A (local execution). It does NOT touch AWS. It reads the Anthropic
key from ``apikeys.txt`` (the line prefixed ``ANTHROPIC:``), holds it only in the
adapter, and never prints/logs/commits it. It runs a preflight (including one
compatibility probe, counted separately), then writes one immutable JSON report +
a markdown summary under ``docs/readiness/communication-layer/`` and exits. No
contact resolution, no delivery, no send.

    python scripts/run_m68_3_certification.py            # dry run: plan + preflight, no calls
    python scripts/run_m68_3_certification.py --execute   # makes the 81 real calls (+ 1 probe)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_3_synthetic_corpus import NOT_DISTINCTIVE_SCENARIO_ID, build_corpus  # noqa: E402
from opintel_communication.anthropic_adapter import (  # noqa: E402
    ANTHROPIC_ADAPTER_VERSION,
    ANTHROPIC_API_ENDPOINT,
    PINNED_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
)
from opintel_communication.certification import (  # noqa: E402
    ATTEMPT4_CALL_BOUNDS,
    CONFIRMED_SONNET5_PRICE_TABLE,
    CertificationRunner,
)
from opintel_communication.envelope_projection import (  # noqa: E402
    WITHHELD_FROM_PROVIDER,
    provider_facing_projection,
)
from opintel_communication.prompt import build_certification_prompt_bundle_n1  # noqa: E402
from opintel_communication.stub_provider import parse_provider_response  # noqa: E402
from opintel_communication.validator import OutputValidator  # noqa: E402

_OUT_DIR = ROOT / "docs" / "readiness" / "communication-layer"

# Attempt 4 (owner authorization 2026-09-02, Option 2): thinking disabled, one
# candidate per call, and max_output_tokens raised 2000 -> 8000 (per call and
# aggregate). Attempts 2-3 proved the 2000 ceiling - an operational/cost
# constraint, not a truth/safety/semantic invariant - prevents completing the
# accepted one-response candidate + full-manifest schema. The atomic protocol
# (one envelope -> one response -> one candidate + full manifest -> independent
# validation), the validator, the frozen corpus, and every threshold /
# zero-tolerance finding are unchanged. New config hash (8000) => new key.
_ATTEMPT4_CONFIG = GenerationConfig(thinking="disabled", max_output_tokens=8000)
_ATTEMPT4_BOUNDS = ATTEMPT4_CALL_BOUNDS
_PROMPT_BUILDER = build_certification_prompt_bundle_n1
_REPEATS = 9
_ND_REPEATS = 3
_ATTEMPT_LABEL = "attempt4-thinking-disabled-n1-8k"


def _apikeys_path() -> Path:
    """apikeys.txt lives at the main checkout root, not inside a worktree.
    Walk up from ROOT until it is found."""
    for base in (ROOT, *ROOT.parents):
        candidate = base / "apikeys.txt"
        if candidate.is_file():
            return candidate
    raise SystemExit("apikeys.txt not found in ROOT or any parent directory")


_EXPECTED_MANIFEST_SHA = "282cdd5a2783f793a47d71b17ddf8b62242294fc0260e73a3526fbec5537d411"
_EXPECTED_ENVELOPE_SHA16 = {
    "s01_strong_response_commitment": "5cc465051da0c2da",
    "s02_availability_without_response": "c52373c7dd1831b1",
    "s03_generic_weak_evidence": "ac27e3d67c7c7ba1",
    "s04_unknown_response_performance": "fde4f95f86bb746f",
    "s05_prompt_injection_in_evidence": "c30ead22862fc066",
    "s06_missed_lead_bait": "a336c9dff73cb9a1",
    "s07_economics_bait": "04618481136892d6",
    "s08_cta_drift_trap": "0c41863f34cd7f6a",
    "s09_manifest_honesty_pressure": "96fa641256e63ea8",
    "s10_tempting_unsupported_implication": "c72b8e96e27f11bd",
}

# Any of these tokens appearing in a provider payload means real prospect / person
# / raw-page data has leaked past the allow-list. Preflight fails closed on a hit.
_FORBIDDEN_PAYLOAD_TOKENS = (
    "aplusac",
    "aplus",
    "elite ",
    "e+m",
    "raw_page",
    "page_body",
    "raw_html",
)

# Person / contact leak: an email address in the payload. (The projection is
# structurally incapable of carrying person/contact fields; this is a belt-and-
# suspenders scan. A phone-number scan is deliberately omitted - synthetic fact
# refs are UUIDs and would false-positive; person/contact leakage in generated
# prose is caught by the validator's ``person_or_contact_present`` code.)
_CONTACT_PATTERNS = (re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"),)


def _read_anthropic_key() -> str:
    # apikeys.txt may carry a stray cp1252 byte; the credential lines are ASCII.
    for line in _apikeys_path().read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("ANTHROPIC:"):
            value = stripped.split(":", 1)[1].strip()
            if not value:
                raise SystemExit("ANTHROPIC: line in apikeys.txt has no value")
            return value
    raise SystemExit(
        "no line prefixed 'ANTHROPIC:' in apikeys.txt - cannot identify the "
        "Anthropic credential without displaying secrets; ask the owner for the label"
    )


def _plan_summary() -> str:
    b = _ATTEMPT4_BOUNDS
    corpus = build_corpus()
    distinctive = [s for s in corpus.specs if s.envelope.has_distinctive_fact()]
    reaching = len(distinctive) * _REPEATS
    lines = [
        f"M6.8-3 synthetic certification - PLAN ({_ATTEMPT_LABEL})",
        f"  config            : thinking={_ATTEMPT4_CONFIG.thinking or 'provider-default'} "
        f"N={b.candidates_per_call} max_output_tokens={_ATTEMPT4_CONFIG.max_output_tokens} "
        f"config_hash={_ATTEMPT4_CONFIG.config_hash()[:16]}...",
        f"  prompt template   : {_PROMPT_BUILDER(distinctive[0].envelope).template_id}",
        f"  corpus            : {corpus.corpus_version} ({len(corpus.specs)} envelopes)",
        f"  corpus manifest   : {corpus.manifest_sha256()}",
        f"  provider calls    : {len(distinctive)} provider-reaching x {_REPEATS} repeats x 1 "
        f"candidate = {reaching}  (ceiling {b.max_provider_calls})",
        f"  avoided by gate   : {NOT_DISTINCTIVE_SCENARIO_ID} x {_ND_REPEATS} = {_ND_REPEATS} "
        "provider-avoided, recorded separately",
        f"  max candidates    : {reaching}",
        f"  token ceilings    : {b.max_input_tokens_per_call}/call in, "
        f"{b.max_output_tokens_per_call}/call out, "
        f"{b.aggregate_input_token_ceiling} agg in, {b.aggregate_output_token_ceiling} agg out",
        f"  USD ceiling       : {b.hard_usd_ceiling}   retries: {b.automatic_retries}",
        f"  price table       : {CONFIRMED_SONNET5_PRICE_TABLE.version} "
        f"(confirmed={CONFIRMED_SONNET5_PRICE_TABLE.confirmed})",
        f"  provider / model  : anthropic / {PINNED_MODEL} / {ANTHROPIC_ADAPTER_VERSION}",
        f"  endpoint          : {ANTHROPIC_API_ENDPOINT} (only authorized destination)",
    ]
    for s in corpus.specs:
        lines.append(f"    {s.scenario_id:<38} {s.envelope_sha256}")
    return "\n".join(lines)


def _preflight(*, require_key: bool) -> tuple[list[str], dict[str, object]]:
    """Deterministic checks that must all pass before the first API call
    (owner authorization 2026-09-02, section 9). Raises SystemExit on any
    failure - fail closed. Returns (checks, probe_stats)."""

    checks: list[str] = []
    probe_stats: dict[str, object] = {"probe_calls": 0}
    corpus = build_corpus()

    # 1. corpus manifest hash
    got_manifest = corpus.manifest_sha256()
    if got_manifest != _EXPECTED_MANIFEST_SHA:
        raise SystemExit(
            f"PREFLIGHT FAIL: corpus manifest {got_manifest} != {_EXPECTED_MANIFEST_SHA}"
        )
    checks.append(f"corpus manifest hash == {_EXPECTED_MANIFEST_SHA}")

    # 2. all 10 frozen envelope hashes
    for s in corpus.specs:
        want = _EXPECTED_ENVELOPE_SHA16.get(s.scenario_id)
        if want is None or not s.envelope_sha256.startswith(want):
            raise SystemExit(
                f"PREFLIGHT FAIL: {s.scenario_id} envelope hash {s.envelope_sha256[:16]} != {want}"
            )
    checks.append("all 10 frozen envelope hashes match")

    # 3. exactly one non-distinctive scenario, and it is s03
    nd = [s.scenario_id for s in corpus.specs if not s.envelope.has_distinctive_fact()]
    if nd != [NOT_DISTINCTIVE_SCENARIO_ID]:
        raise SystemExit(
            f"PREFLIGHT FAIL: non-distinctive set {nd} != [{NOT_DISTINCTIVE_SCENARIO_ID}]"
        )
    checks.append(f"exactly one non-distinctive scenario: {NOT_DISTINCTIVE_SCENARIO_ID}")

    # 4. provider payload projection is allow-listed - no provenance keys, no
    #    real prospect / person / raw-page tokens, for every envelope
    for s in corpus.specs:
        blob = json.dumps(provider_facing_projection(s.envelope)).lower()
        for banned in WITHHELD_FROM_PROVIDER:
            if f'"{banned}"' in blob:
                raise SystemExit(
                    f"PREFLIGHT FAIL: withheld key '{banned}' in {s.scenario_id} payload"
                )
        for tok in _FORBIDDEN_PAYLOAD_TOKENS:
            if tok in blob:
                raise SystemExit(
                    f"PREFLIGHT FAIL: forbidden token '{tok}' in {s.scenario_id} provider payload"
                )
        for pat in _CONTACT_PATTERNS:
            if pat.search(blob):
                raise SystemExit(
                    f"PREFLIGHT FAIL: contact-shaped string in {s.scenario_id} provider payload"
                )
    checks.append("provider payload projection allow-listed; no provenance/person/raw-page tokens")
    checks.append("no real prospect/company data in any payload (synthetic -demo.com hosts only)")

    # 5. API credential available without being logged
    if require_key:
        key = _read_anthropic_key()
        checks.append(
            f"Anthropic credential resolved from apikeys.txt (len={len(key)}, "
            f"prefix ok={key.startswith('sk-ant-')}); value not printed/logged"
        )
    else:
        checks.append("API credential check skipped (dry run)")

    # 6. adapter / model / config matches the Attempt 4 certification key
    adapter = AnthropicProviderAdapter("sk-ant-preflight-not-a-real-key", config=_ATTEMPT4_CONFIG)
    runner = CertificationRunner(
        adapter,
        bounds=_ATTEMPT4_BOUNDS,
        price_table=CONFIRMED_SONNET5_PRICE_TABLE,
        prompt_builder=_PROMPT_BUILDER,
    )
    key_obj = runner.certification_key(corpus)
    if not (
        key_obj.provider == "anthropic"
        and key_obj.model == PINNED_MODEL
        and key_obj.provider_adapter_version == ANTHROPIC_ADAPTER_VERSION
        and key_obj.corpus_manifest_sha256 == _EXPECTED_MANIFEST_SHA
        and key_obj.prompt_template_id == "comm.prompt_template.first_contact@3"
        and key_obj.output_validator_version == "comm.output_validator@1"
        and len(key_obj.generation_config_hash) == 64
    ):
        raise SystemExit("PREFLIGHT FAIL: certification key does not bind the expected tuple")
    checks.append(
        f"certification key binds anthropic/{PINNED_MODEL}/{ANTHROPIC_ADAPTER_VERSION}/"
        f"{key_obj.prompt_template_id}; validator {key_obj.output_validator_version} unchanged; "
        f"key_sha {key_obj.key_sha256()}"
    )

    # 7. N=1 one-candidate response schema + revised 8k bounds
    if _ATTEMPT4_BOUNDS.candidates_per_call != 1:
        raise SystemExit("PREFLIGHT FAIL: Attempt 4 bounds do not request exactly 1 candidate")
    if (
        _ATTEMPT4_BOUNDS.max_output_tokens_per_call != 8000
        or _ATTEMPT4_CONFIG.max_output_tokens != 8000
    ):
        raise SystemExit("PREFLIGHT FAIL: Attempt 4 output ceiling is not 8000")
    tmpl = _PROMPT_BUILDER(corpus.specs[0].envelope).bundle_text
    if "EXACTLY ONE candidate" not in tmpl or "claim manifest" not in tmpl.lower():
        raise SystemExit(
            "PREFLIGHT FAIL: @3 template must request exactly one candidate with a full manifest"
        )
    checks.append(
        f"one-candidate response schema: N={_ATTEMPT4_BOUNDS.candidates_per_call}, "
        f"@3 template requests exactly one candidate + full claim manifest; "
        f"output ceiling 8000/call; bounds {_ATTEMPT4_BOUNDS.max_provider_calls} calls / "
        f"{_ATTEMPT4_BOUNDS.aggregate_input_token_ceiling} agg-in / "
        f"{_ATTEMPT4_BOUNDS.aggregate_output_token_ceiling} agg-out; USD "
        f"{_ATTEMPT4_BOUNDS.hard_usd_ceiling} hard; counters start 0/0/0"
    )

    # 8. Attempt-4 compatibility probe (owner authorization: exactly one, counted
    #    + disclosed separately). One real call with the EXACT Attempt 4 config
    #    (thinking disabled, 8000 out) + @3 bundle on s01. Must prove: HTTP/provider
    #    success; served model matches; thinking disabled; stop_reason != max_tokens;
    #    exactly one complete payload; candidate JSON parses; full claim manifest
    #    parses; response reaches the deterministic validator. The candidate need
    #    NOT PASS - only the accepted protocol must complete and be evaluable.
    if require_key:
        probe = AnthropicProviderAdapter(_read_anthropic_key(), config=_ATTEMPT4_CONFIG)
        s01 = corpus.specs[0]
        probe_bundle = _PROMPT_BUILDER(s01.envelope)
        try:
            text, meta = probe.generate(probe_bundle.bundle_text)
        except Exception as exc:  # any incompatibility is a hard stop
            raise SystemExit(
                f"PREFLIGHT FAIL: Attempt 4 compatibility probe failed "
                f"({type(exc).__name__}: {exc}). STOP for owner review - do not "
                "raise beyond 8000 / split calls / slim the manifest / change model / "
                "modify the validator / alter the corpus independently."
            ) from exc
        probe_stats = {
            "probe_calls": 1,
            "probe_input_tokens": meta.input_tokens,
            "probe_output_tokens": meta.output_tokens,
            "probe_cost_usd": CONFIRMED_SONNET5_PRICE_TABLE.cost_usd(
                meta.input_tokens, meta.output_tokens
            ),
            "probe_served_model": meta.model_version,
            "probe_stop_reason": meta.stop_reason,
        }
        if meta.model_version and not meta.model_version.startswith(PINNED_MODEL):
            raise SystemExit(
                f"PREFLIGHT FAIL: probe served model '{meta.model_version}' != '{PINNED_MODEL}'"
            )
        if meta.stop_reason == "max_tokens":
            raise SystemExit(
                f"PREFLIGHT FAIL: probe stop_reason=max_tokens at 8000 out "
                f"(out_tokens={meta.output_tokens}). STOP for owner review - the accepted "
                "schema still does not complete; do not raise beyond 8000 or split calls."
            )
        parsed = parse_provider_response(text)
        if len(parsed.candidates) != 1:
            raise SystemExit(
                f"PREFLIGHT FAIL: expected exactly 1 parseable candidate, got "
                f"{len(parsed.candidates)} (status={parsed.status}, "
                f"out_tokens={meta.output_tokens}). STOP for owner review."
            )
        cand = parsed.candidates[0]
        n_entries = len(cand.claim_manifest.entries)
        if n_entries < 1:
            raise SystemExit(
                "PREFLIGHT FAIL: candidate parsed but its claim manifest is empty - the full "
                "manifest did not complete. STOP for owner review."
            )
        vr = OutputValidator().validate(s01.envelope, cand)
        checks.append(
            f"compatibility probe OK: thinking-disabled, served model '{meta.model_version}', "
            f"stop_reason={meta.stop_reason!r} (!= max_tokens); ONE candidate + "
            f"{n_entries}-entry claim manifest parsed and reached the validator "
            f"(validator passed={vr.passed}, {len(vr.findings)} finding(s) - PASS not required "
            f"for compatibility); usage in/out {meta.input_tokens}/{meta.output_tokens}, "
            f"cost USD {probe_stats['probe_cost_usd']}. Counted separately; NOT one of the 81."
        )
    else:
        checks.append("provider compatibility probe skipped (dry run)")

    return checks, probe_stats


def _markdown_report(
    report: object, checks: list[str], stamp: str, probe_stats: dict[str, object]
) -> str:
    r = report
    lines: list[str] = []
    a = lines.append
    a(f"# M6.8-3 synthetic live-provider certification report - {_ATTEMPT_LABEL} - {stamp}")
    a("")
    a("Immutable. Owner-authorized 2026-09-01; Attempt 4 authorized 2026-09-02 (Option 2). ")
    a("Option A local execution. No AWS surface. No contact resolution, no delivery, no send.")
    a("")
    a(
        "**Attempt 4** = thinking **disabled**, **N=1 candidate per call**, "
        "`max_output_tokens` raised **2000 -> 8000** (per call and aggregate). The atomic "
        "protocol (one envelope -> one response -> one candidate + full manifest -> independent "
        "validation), the full claim-manifest contract, the validator, the frozen corpus, and "
        "every threshold / zero-tolerance finding are unchanged; the 2000 ceiling was an "
        "operational/cost constraint, not a truth/safety/semantic invariant. New config hash "
        "(8000) => new certification key. Independent configuration, NOT a retry of Attempt 1 "
        "(adaptive thinking / 2k / N3 -> NOT_CERTIFIED_CONFIGURATION), Attempt 2 (thinking "
        "disabled / 2k / N3 -> NOT_CERTIFIED_CONFIGURATION), or Attempt 3 (thinking disabled / "
        "2k / N1 -> PREFLIGHT_CONFIGURATION_BLOCKER, run never started). Do NOT aggregate "
        "metrics across attempts."
    )
    a("")
    a("## Preflight")
    for c in checks:
        a(f"- [x] {c}")
    a("")
    a("## Compatibility probe (counted separately from the 81 certification calls)")
    if probe_stats.get("probe_calls"):
        a(f"- probe calls: {probe_stats['probe_calls']}")
        a(f"- probe served model: `{probe_stats.get('probe_served_model')}`")
        a(
            f"- probe usage in/out: {probe_stats.get('probe_input_tokens')}/"
            f"{probe_stats.get('probe_output_tokens')}  "
            f"cost USD {probe_stats.get('probe_cost_usd')}"
        )
    else:
        a("- probe calls: 0")
    a("")
    a("## Provider / model / config")
    key = r.certification_key  # type: ignore[attr-defined]
    a(f"- provider: `{key.provider}`")
    a(f"- pinned model: `{key.model}`")
    a(f"- observed model identity: `{key.observed_model_identity}`")
    a(f"- adapter: `{key.provider_adapter_version}`")
    a(f"- prompt template: `{key.prompt_template_id}` sha256 `{key.prompt_template_sha256}`")
    a(f"- output validator: `{key.output_validator_version}` (unchanged)")
    a(f"- candidate ranker: `{key.candidate_ranker_version}` (unchanged)")
    a(f"- CTA parser: `{key.cta_parser_version}`")
    a(f"- generation config hash: `{key.generation_config_hash}`")
    a(f"- **certification key sha256: `{r.certification_key_sha256}`**")  # type: ignore[attr-defined]
    a("")
    a("## Corpus")
    a(f"- version: `{key.semantic_envelope_schema}` envelope schema")
    a(f"- corpus manifest sha256: `{key.corpus_manifest_sha256}`")
    a("")
    a("## Call accounting")
    a(f"- planned max: {r.provider_calls_planned_max}")  # type: ignore[attr-defined]
    a(f"- provider calls executed: {r.provider_calls_made}")  # type: ignore[attr-defined]
    a(
        f"- deterministically avoided (non-distinctive gate): "
        f"{r.provider_calls_avoided_nondistinctive}"  # type: ignore[attr-defined]
    )
    a(f"- provider-call ceiling: {r.bounds.max_provider_calls} (absolute, not a target)")  # type: ignore[attr-defined]
    a(f"- stopped early: {r.stopped_early_reason or '(no - ran to completion)'}")  # type: ignore[attr-defined]
    a("")
    a("## Request outcomes")
    term_counts: dict[str, int] = {}
    for att in r.attempts:  # type: ignore[attr-defined]
        term_counts[att.terminal_outcome.value] = term_counts.get(att.terminal_outcome.value, 0) + 1
    for k, v in sorted(term_counts.items()):
        a(f"- `{k}`: {v}")
    a("")
    a("## Candidates and validation")
    total_ret = sum(att.returned_candidate_count for att in r.attempts)  # type: ignore[attr-defined]
    total_pass = sum(att.passed_candidate_count for att in r.attempts)  # type: ignore[attr-defined]
    a(f"- candidates returned: {total_ret}")
    a(f"- candidates PASS: {total_pass}")
    a(f"- candidates FAIL: {total_ret - total_pass}")
    a(f"- candidate pass rate: {r.safety_pass_rate} (floor {r.safety_pass_rate_floor})")  # type: ignore[attr-defined]
    a("")
    a("## Validator findings by code and scenario")
    finding_rows: dict[tuple[str, str], int] = {}
    for att in r.attempts:  # type: ignore[attr-defined]
        for row in att.record.candidates:
            for f in row.validation.findings:
                finding_rows[(f.code, att.scenario_id)] = (
                    finding_rows.get((f.code, att.scenario_id), 0) + 1
                )
    if finding_rows:
        for (code, sid), n in sorted(finding_rows.items()):
            a(f"- `{code}` @ `{sid}`: {n}")
    else:
        a("- (none)")
    a("")
    a("## Zero-tolerance safety categories")
    from opintel_communication.certification import SAFETY_CRITICAL_FINDING_CODES

    hit = set(r.safety_critical_hits)  # type: ignore[attr-defined]
    for code in sorted(SAFETY_CRITICAL_FINDING_CODES):
        count = sum(
            1
            for att in r.attempts  # type: ignore[attr-defined]
            for row in att.record.candidates
            for f in row.validation.findings
            if f.code == code
        )
        mark = "VIOLATION" if code in hit else "0"
        a(f"- `{code}`: {mark} (occurrences: {count})")
    a("")
    a("## Envelope fidelity / manifest honesty / drift")
    a(f"- envelope fidelity pass: {r.envelope_fidelity_pass}")  # type: ignore[attr-defined]
    a(
        f"- manifest mismatch rate: {r.manifest_mismatch_rate} "  # type: ignore[attr-defined]
        f"(ceiling {r.manifest_mismatch_ceiling}) -> pass: {r.manifest_honesty_pass}"  # type: ignore[attr-defined]
    )
    a(
        f"- COMMUNICATION_NOT_DISTINCTIVE_ENOUGH behaviour: "
        f"{term_counts.get('COMMUNICATION_NOT_DISTINCTIVE_ENOUGH', 0)} attempt(s) "
        "terminated before the provider was called (expected: 3)"
    )
    for d in r.per_scenario_drift:  # type: ignore[attr-defined]
        a(
            f"- drift `{d.scenario_id}`: stable_sig={d.stable_validator_signature}, "
            f"distinct_fingerprints={d.distinct_response_fingerprints}, "
            f"classes={list(d.drift_classes_observed) or '[]'}"
        )
    if r.drift_invalidations:  # type: ignore[attr-defined]
        for di in r.drift_invalidations:  # type: ignore[attr-defined]
            a(f"  - INVALIDATION: {di}")
    a("")
    a("## Tokens and cost")
    a(f"- aggregate input tokens: {r.aggregate_input_tokens}")  # type: ignore[attr-defined]
    a(f"- aggregate output tokens: {r.aggregate_output_tokens}")  # type: ignore[attr-defined]
    a(f"- price table: `{r.price_table_version}` confirmed={r.price_table_confirmed}")  # type: ignore[attr-defined]
    ceiling = r.bounds.hard_usd_ceiling  # type: ignore[attr-defined]
    a(f"- **exact total cost: USD {r.aggregate_cost_usd}** (hard ceiling USD {ceiling})")  # type: ignore[attr-defined]
    a("")
    a("## Immutable generation / audit record hashes")
    for att in r.attempts:  # type: ignore[attr-defined]
        rec = att.record
        a(
            f"- `{rec.record_id}` seq={rec.sequence} record_hash=`{rec.record_hash}` "
            f"prev=`{rec.previous_record_hash or '(genesis)'}` "
            f"raw_response_sha256=`{rec.raw_provider_response_sha256 or '(none)'}` "
            f"retention=`{_retention_state(rec)}`"
        )
    a("")
    a("## Decisions")
    a(f"- **SAFETY: {r.safety_outcome.value}**")  # type: ignore[attr-defined]
    a(f"- COMMUNICATION QUALITY (advisory, does not gate safety): {r.communication_quality.value}")  # type: ignore[attr-defined]
    a(f"  - {r.quality_note}")  # type: ignore[attr-defined]
    a("")
    a("## Notes")
    for n in r.notes:  # type: ignore[attr-defined]
        a(f"- {n}")
    a("")
    a("## Post-run state")
    a("- accountable human certification approver: PROJECT_OWNER (not this agent)")
    a(
        "- Anthropic credential: held only in the adapter for the process lifetime; "
        "never printed, logged, committed, hashed into evidence, or written to a GenerationRecord"
    )
    a(
        "- raw-provider-response retention: 30 days, policy_status POLICY_PENDING, "
        "legally_approved=False; normalized candidates + audit metadata are permanent"
    )
    a("- AWS surface created: none. Network: local outbound HTTPS to api.anthropic.com:443 only")
    a("- runtime returned to dormant: no provider process persists; no scheduled purge armed")
    a("- M6.8-4 NOT started. No contact resolution, no delivery, no send. ADR-0077 stays Proposed.")
    a("")
    a("STOP for PROJECT_OWNER acceptance.")
    return "\n".join(lines)


def _retention_state(rec: object) -> str:
    ret = getattr(rec, "raw_response_retention", None)
    if ret is None:
        return "(no raw response)"
    return f"{getattr(ret, 'policy_status', '?')}/{getattr(ret, 'max_retention_days', '?')}d"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="make the 81 real provider calls")
    args = ap.parse_args()

    print(_plan_summary())
    print("\n-- preflight --")
    checks, probe_stats = _preflight(require_key=args.execute)
    for c in checks:
        print(f"  [x] {c}")

    if not args.execute:
        print("\ndry run only. preflight passed. re-run with --execute to make the real calls.")
        return 0

    key = _read_anthropic_key()
    corpus = build_corpus()
    adapter = AnthropicProviderAdapter(key, config=_ATTEMPT4_CONFIG)
    runner = CertificationRunner(
        adapter,
        bounds=_ATTEMPT4_BOUNDS,
        price_table=CONFIRMED_SONNET5_PRICE_TABLE,
        prompt_builder=_PROMPT_BUILDER,
    )

    print(
        f"\nexecuting up to {_ATTEMPT4_BOUNDS.max_provider_calls} real claude-sonnet-5 calls "
        f"({_ATTEMPT_LABEL}; {NOT_DISTINCTIVE_SCENARIO_ID} x{_ND_REPEATS} gated) ..."
    )
    report = runner.run(
        corpus,
        repeats=_REPEATS,
        not_distinctive_repeats=_ND_REPEATS,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=int(time.time()),
    )

    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    payload = dataclasses.asdict(report)
    payload["compatibility_probe"] = probe_stats
    json_path = _OUT_DIR / f"m6.8-3-certification-report-{_ATTEMPT_LABEL}-{stamp}.json"
    md_path = _OUT_DIR / f"m6.8-3-certification-report-{_ATTEMPT_LABEL}-{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown_report(report, checks, stamp, probe_stats), encoding="utf-8")

    print(f"\nsafety_outcome        : {report.safety_outcome.value}")
    print(f"communication_quality : {report.communication_quality.value}")
    print(f"provider_calls_made   : {report.provider_calls_made}")
    print(f"calls avoided (gate)  : {report.provider_calls_avoided_nondistinctive}")
    print(f"aggregate cost        : USD {report.aggregate_cost_usd}")
    print(
        f"aggregate tokens      : in {report.aggregate_input_tokens} / "
        f"out {report.aggregate_output_tokens}"
    )
    print(f"safety_critical_hits  : {report.safety_critical_hits or '(none)'}")
    print(f"drift_invalidations   : {report.drift_invalidations or '(none)'}")
    print(f"stopped_early_reason  : {report.stopped_early_reason or '(none)'}")
    print(f"certification_key_sha : {report.certification_key_sha256}")
    print(f"\nreports written:\n  {json_path.relative_to(ROOT)}\n  {md_path.relative_to(ROOT)}")
    print("Adapter never persisted the key. No AWS surface created. STOP for PROJECT_OWNER review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
