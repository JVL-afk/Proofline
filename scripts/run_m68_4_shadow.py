"""M6.8-4 - REAL-COMPANY INTERNAL SHADOW EVALUATION ONLY.

Owner authorization 2026-09-04 "FREEZE M4 -> RUN M6.8-4 REAL-COMPANY SHADOW ->
DRAFT M6.9 LAUNCH REVIEW", Part B.

This grants NO contact / send authority. M6.8-3 remains formally NOT_CERTIFIED;
its provider behaviour is accepted as sufficiently safe for this human-reviewed
shadow evaluation only. No delivery, no recipient, no contact resolution.

For each already-frozen real-company envelope (A-Plus / Elite / E+M) this:
  * verifies the exact frozen envelope hash;
  * verifies the provider-facing projection leaks no withheld provenance key and
    no contact-shaped string, and asserts identity == display name + hostname;
  * runs the deterministic distinctiveness gate (envelope.has_distinctive_fact);
  * for each company that passes the gate, generates N=3 candidates with the
    accepted claude-sonnet-5 transformer config (prompt @9, thinking disabled,
    8000 out, 30s, 0 retries) - MAX 9 real-company generations total;
  * compacts + validates (contract="v3") + quality-assesses every candidate;
  * stops before USD 1.00 total Anthropic spend.

Reads the Anthropic key from apikeys.txt (ANTHROPIC: line), holds it only in the
adapter, never prints / logs / commits / hashes it. Writes an immutable JSON
report. No AWS. No send. Does NOT resolve contacts or begin M6.9 execution.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_fixtures import aplus_envelope, elite_envelope, em_envelope  # noqa: E402
from opintel_communication.anthropic_adapter import (  # noqa: E402
    ANTHROPIC_API_ENDPOINT,
    PINNED_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
    _model_family,
)
from opintel_communication.certification import CONFIRMED_SONNET5_PRICE_TABLE  # noqa: E402
from opintel_communication.compactor import compact_candidate  # noqa: E402
from opintel_communication.envelope_projection import (  # noqa: E402
    WITHHELD_FROM_PROVIDER,
    provider_facing_projection,
)
from opintel_communication.hashing import sha256_text  # noqa: E402
from opintel_communication.prompt import build_certification_prompt_bundle_v9  # noqa: E402
from opintel_communication.quality import assess_quality  # noqa: E402
from opintel_communication.stub_provider import parse_provider_response  # noqa: E402
from opintel_communication.validator import OutputValidator  # noqa: E402

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_CONFIG = GenerationConfig(model=PINNED_MODEL, thinking="disabled", max_output_tokens=8000)
_CONTRACT = "v3"
_USD_CEILING = Decimal("1.00")
_N_PER_COMPANY = 3
_MAX_TOTAL_CALLS = 9
_CONTACT = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")

_COMPANIES: tuple[tuple[str, object, str], ...] = (
    ("A-Plus", aplus_envelope, "c5a6307f4427d450"),
    ("Elite", elite_envelope, "2eca7a18a88c657e"),
    ("E+M", em_envelope, "2c35afc05382f3f2"),
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


def _preflight() -> list[str]:
    checks: list[str] = []
    if _model_family(_CONFIG.model) != "claude-sonnet-5":
        raise SystemExit("PREFLIGHT FAIL: model is not the claude-sonnet-5 family")
    if _CONFIG.thinking != "disabled" or _CONFIG.max_output_tokens != 8000:
        raise SystemExit("PREFLIGHT FAIL: config drifted (thinking / output ceiling)")
    if _CONFIG.timeout_seconds != 30.0 or _CONFIG.automatic_retries != 0:
        raise SystemExit("PREFLIGHT FAIL: config drifted (timeout / retries)")
    checks.append(
        f"config: anthropic/{PINNED_MODEL}/prompt@9, thinking disabled, 8000 out, 30s, 0 retries"
    )

    for name, fn, sha16 in _COMPANIES:
        env = fn()  # type: ignore[operator]
        if not env.envelope_sha256.startswith(sha16):
            raise SystemExit(
                f"PREFLIGHT FAIL: {name} envelope hash changed ({env.envelope_sha256})"
            )
        proj = provider_facing_projection(env)
        blob = json.dumps(proj).lower()
        for w in WITHHELD_FROM_PROVIDER:
            if f'"{w}"' in blob:
                raise SystemExit(f"PREFLIGHT FAIL: withheld key {w} in {name} projection")
        if _CONTACT.search(blob):
            raise SystemExit(f"PREFLIGHT FAIL: contact-shaped string in {name} projection")
        ident = proj.get("business_identity", {})
        if set(ident) - {"display_name", "public_hostname", "identity_rule"}:
            raise SystemExit(
                f"PREFLIGHT FAIL: {name} identity carries more than name + hostname + rule: "
                f"{sorted(set(ident))}"
            )
        checks.append(
            f"{name}: envelope {env.envelope_sha256[:16]} frozen; projection allow-listed "
            f"(identity = display name + hostname only); distinctive={env.has_distinctive_fact()}"
        )
    return checks


def _evaluate_candidate(env: object, raw: str, meta: object) -> dict[str, object]:
    parsed = parse_provider_response(raw)
    if not parsed.candidates:
        return {
            "parse_status": parsed.status.value
            if hasattr(parsed.status, "value")
            else str(parsed.status),
            "parse_reason": parsed.reason,
            "candidate": None,
        }
    cand = parsed.candidates[0]
    compacted, audit = compact_candidate(cand, env)  # type: ignore[arg-type]
    vr = OutputValidator(contract=_CONTRACT).validate(env, compacted)  # type: ignore[arg-type]
    qa = assess_quality(compacted, env)  # type: ignore[arg-type]
    arts = {a.kind: a.text for a in compacted.artifacts}
    body = arts.get("first_contact_email", "") or arts.get("body", "")
    return {
        "subject": arts.get("subject", ""),
        "body": body,
        "body_sha256": sha256_text(body),
        "compacted": bool(audit.removed_sentences),
        "validator": {
            "passed": vr.passed,
            "findings": [f.code for f in vr.findings],
            "canonical_coverage": vr.canonical_reconciliation_coverage,
            "unresolved_substantive_claims": vr.unresolved_substantive_claims,
            "canonical_substantive": vr.canonical_substantive_claims,
            "canonical_licensed": vr.canonical_licensed_claims,
            "canonical_rejected": vr.canonical_rejected_claims,
        },
        "quality": {
            "classification": qa.classification,
            "score": qa.score,
            "uses_company_specific_evidence": qa.uses_company_specific_evidence,
            "uses_strongest_hook": qa.uses_strongest_hook,
            "boilerplate_hits": qa.boilerplate_hits,
            "generic_praise": qa.generic_praise,
            "fake_familiarity": qa.fake_familiarity,
            "body_word_count": qa.body_word_count,
            "observations": list(qa.observations),
        },
        "provider": {
            "served_model": meta.model_version,  # type: ignore[attr-defined]
            "stop_reason": meta.stop_reason,  # type: ignore[attr-defined]
            "input_tokens": meta.input_tokens,  # type: ignore[attr-defined]
            "output_tokens": meta.output_tokens,  # type: ignore[attr-defined]
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="make the real provider calls")
    ap.add_argument("--n", type=int, default=_N_PER_COMPANY, help="candidates per company")
    ap.add_argument(
        "--max-calls", type=int, default=_MAX_TOTAL_CALLS, help="hard cap on total generations"
    )
    args = ap.parse_args()
    n_per_company = args.n
    max_total_calls = args.max_calls

    print(
        f"M6.8-4 real-company shadow: {PINNED_MODEL} thinking=disabled N={_N_PER_COMPANY}/company "
        f"max {_MAX_TOTAL_CALLS} calls, USD ceiling {_USD_CEILING}"
    )
    print(f"  endpoint {ANTHROPIC_API_ENDPOINT}")
    print("\n-- preflight --")
    checks = _preflight()
    for c in checks:
        print(f"  [x] {c}")

    if not args.execute:
        print("\ndry run only. preflight passed. no provider calls made.")
        return 0

    key = _read_key()
    adapter = AnthropicProviderAdapter(key, config=_CONFIG)
    cost = Decimal("0")
    calls = 0
    results: list[dict[str, object]] = []

    for name, fn, _sha16 in _COMPANIES:
        env = fn()  # type: ignore[operator]
        entry: dict[str, object] = {
            "company": name,
            "envelope_sha256": env.envelope_sha256,
            "m2_m5_bundle_sha256": env.source_lineage.m2_m5_bundle_sha256,
            "primary_anchor": (
                sorted(
                    env.eligible_company_facts,
                    key=lambda f: {
                        "response_commitment": 0,
                        "service_availability": 1,
                        "commercial_context": 2,
                        "intake_surface": 3,
                        "service_area_context": 4,
                    }.get(f.category, 9),
                )[0].category
                if env.eligible_company_facts
                else None
            ),
            "distinctive": env.has_distinctive_fact(),
        }
        if not env.has_distinctive_fact():
            entry["disposition"] = "COMMUNICATION_NOT_DISTINCTIVE_ENOUGH"
            entry["candidates"] = []
            entry["note"] = (
                "deterministic distinctiveness gate failed; no generation (section 6/8)."
            )
            results.append(entry)
            print(f"\n{name}: NOT distinctive -> COMMUNICATION_NOT_DISTINCTIVE_ENOUGH (0 calls)")
            continue

        bundle = build_certification_prompt_bundle_v9(env).bundle_text
        cands: list[dict[str, object]] = []
        for i in range(n_per_company):
            if calls >= max_total_calls:
                entry["stopped_early"] = "max total calls reached"
                break
            # cost guard: stop if the *next* call could plausibly breach the ceiling
            if cost > _USD_CEILING - Decimal("0.15"):
                entry["stopped_early"] = f"USD ceiling guard at cost {cost}"
                break
            calls += 1
            t0 = time.time()
            try:
                text, meta = adapter.generate(bundle)
            except Exception as exc:
                cands.append({"index": i, "error": f"{type(exc).__name__}: {exc}"})
                print(f"  {name} #{i + 1}: ERROR {type(exc).__name__}")
                continue
            call_cost = Decimal(
                CONFIRMED_SONNET5_PRICE_TABLE.cost_usd(meta.input_tokens, meta.output_tokens)
            )
            cost += call_cost
            if _model_family(meta.model_version) != "claude-sonnet-5":
                raise SystemExit(f"served '{meta.model_version}' not sonnet-5 - aborting")
            ev = _evaluate_candidate(env, text, meta)
            ev["index"] = i
            ev["call_cost_usd"] = str(call_cost)
            ev["latency_s"] = round(time.time() - t0, 1)
            cands.append(ev)
            qcls = ev.get("quality")
            vfind = ev.get("validator")
            cls = qcls.get("classification") if isinstance(qcls, dict) else "?"
            fnd = vfind.get("findings") if isinstance(vfind, dict) else None
            print(f"  {name} #{i + 1}: {cls}, findings={fnd}, cost USD {call_cost}, total USD {cost}")
        entry["candidates"] = cands
        results.append(entry)

    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    payload = {
        "task": "M6.8-4 real-company internal shadow evaluation",
        "generated_at_utc": stamp,
        "config": {
            "provider": "anthropic",
            "model": PINNED_MODEL,
            "prompt_template": "build_certification_prompt_bundle_v9 (@9)",
            "validator_contract": _CONTRACT,
            "thinking": "disabled",
            "max_output_tokens": 8000,
            "timeout_seconds": 30.0,
            "automatic_retries": 0,
            "n_per_company": n_per_company,
        },
        "preflight_checks": checks,
        "total_provider_calls": calls,
        "total_cost_usd": str(cost),
        "usd_ceiling": str(_USD_CEILING),
        "m6_8_3_formal_status": "NOT_CERTIFIED (unchanged; provider behaviour accepted for shadow)",
        "companies": results,
    }
    path = _OUT / f"m6.8-4-real-shadow-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\ntotal calls {calls}, total cost USD {cost} (ceiling {_USD_CEILING})")
    print(f"report: {path.relative_to(ROOT)}")
    print("Adapter never persisted the key. No AWS. No send. STOP for PROJECT_OWNER review.")
    _ = dataclasses  # keep import for --help symmetry with sibling scripts
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
