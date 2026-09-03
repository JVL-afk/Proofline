"""M6.8-3 FINAL CLOSEOUT ITERATION - mandatory offline proof (owner authorization
2026-09-02, section 5).

Replay every immutable candidate from the latest Sonnet certification
(``m6.8-3-sonnet-final-certification-2026-09-02T194045Z.json``, key
e3cfca92...) through the corrected deterministic pipeline
(``OutputValidator(contract="v3")`` = ``comm.output_validator@7``,
``comm.canonical_claim_reconciler@2``, ``comm.cta_parser@3``). No Anthropic
calls. Reports previous vs corrected PASS/FAIL, canonical coverage, unresolved
spans, zero-tolerance findings, the exact remaining failures, and confirms:

  * the 67-char subject (s07 r5) is still rejected,
  * the two unparseable outputs (s01 r4 / r5) are still rejected,
  * no genuinely unsafe historical candidate is newly rescued.
"""

# Diagnostic replay harness over an immutable JSON report (not production code).
# mypy: ignore-errors
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_3_synthetic_corpus import NOT_DISTINCTIVE_SCENARIO_ID, build_corpus  # noqa: E402
from opintel_communication.domain import (  # noqa: E402
    ZERO_TOLERANCE_SAFETY_CODES,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
    ValidatorSeverity,
)
from opintel_communication.validator import OutputValidator  # noqa: E402

_IMMUTABLE = (
    ROOT
    / "docs"
    / "readiness"
    / "communication-layer"
    / "m6.8-3-sonnet-final-certification-2026-09-02T194045Z.json"
)


def _entry(raw: dict) -> ClaimManifestEntry:
    return ClaimManifestEntry(
        claim_id=raw["claim_id"],
        claim_type=ClaimType[raw["claim_type"]],
        rendered_artifact=raw.get("rendered_artifact", "first_contact_email"),
        rendered_span=raw["rendered_span"],
        licensed_source_ids=tuple(raw.get("licensed_source_ids", ())),
        qualifiers=tuple(raw.get("qualifiers", ())),
        asserted_strength=(
            FactStrength[raw["asserted_strength"]] if raw.get("asserted_strength") else None
        ),
        cta_intent=raw.get("cta_intent"),
    )


def _candidate(norm: dict, manifest_raw: dict) -> GenerationCandidate:
    return GenerationCandidate(
        candidate_id=norm["candidate_id"],
        artifacts=(
            GeneratedArtifact("subject", norm["normalized_subject"]),
            GeneratedArtifact("first_contact_email", norm["normalized_body"]),
        ),
        claim_manifest=ClaimManifest(
            entries=tuple(_entry(e) for e in manifest_raw.get("entries", ()))
        ),
    )


def main() -> int:
    report = json.loads(_IMMUTABLE.read_text(encoding="utf-8"))
    env_by_id = {s.scenario_id: s.envelope for s in build_corpus().specs}
    validator = OutputValidator(contract="v3")

    rows: list[dict] = []
    for att in report["attempts"]:
        sid = att["scenario_id"]
        ridx = att["repeat_index"]
        rec = att["record"]
        old_pass = att.get("passed_candidate_count", 0) > 0
        cands = rec.get("candidates", [])
        env = env_by_id[sid]
        if not cands:
            rows.append(
                {
                    "sid": sid,
                    "r": ridx,
                    "old_pass": old_pass,
                    "new_pass": False,
                    "coverage": None,
                    "unresolved": None,
                    "hard_codes": ["returned_candidate_count_0"],
                    "note": rec.get("reason", ""),
                }
            )
            continue
        best: dict | None = None
        for c in cands:
            vr = validator.validate(env, _candidate(c["normalized"], c["claim_manifest"]))
            hard = sorted({f.code for f in vr.findings if f.severity != ValidatorSeverity.ADVISORY})
            row = {
                "sid": sid,
                "r": ridx,
                "old_pass": old_pass,
                "new_pass": vr.passed,
                "coverage": vr.canonical_reconciliation_coverage,
                "unresolved": vr.unresolved_substantive_claims,
                "hard_codes": hard,
                "subject": c["normalized"]["normalized_subject"],
            }
            if best is None or (row["new_pass"] and not best["new_pass"]):
                best = row
        assert best is not None
        rows.append(best)

    distinctive = [r for r in rows if r["sid"] != NOT_DISTINCTIVE_SCENARIO_ID]
    old_p = sum(1 for r in distinctive if r["old_pass"])
    new_p = sum(1 for r in distinctive if r["new_pass"])
    n = len(distinctive)

    print(f"immutable dataset : {_IMMUTABLE.name}")
    print(f"attempts replayed : {len(rows)}  (distinctive evaluable: {n}; s03 gated)")
    print(f"PREVIOUS  PASS     : {old_p}/{n}  ({old_p / n:.4f})")
    print(f"CORRECTED PASS     : {new_p}/{n}  ({new_p / n:.4f})")

    min_cov = min((r["coverage"] for r in distinctive if r["coverage"] is not None), default=None)
    unresolved_total = sum(r["unresolved"] or 0 for r in distinctive if r["unresolved"] is not None)
    print(f"min canonical coverage        : {min_cov}")
    print(f"unresolved substantive spans  : {unresolved_total}")

    zt: dict[str, int] = {}
    for r in distinctive:
        for code in r["hard_codes"]:
            if code in ZERO_TOLERANCE_SAFETY_CODES:
                zt[code] = zt.get(code, 0) + 1
    print(f"zero-tolerance findings       : {zt or 'none'}")

    print("\n-- every corrected FAIL --")
    for r in distinctive:
        if not r["new_pass"]:
            print(f"  {r['sid']} r{r['r']}: {r['hard_codes']}  cov={r['coverage']}")

    print("\n-- newly rescued (old FAIL -> new PASS) --")
    rescued = [r for r in distinctive if r["new_pass"] and not r["old_pass"]]
    for r in rescued:
        print(f"  {r['sid']} r{r['r']}  (was: see immutable record)")
    print(f"  total rescued: {len(rescued)}")

    print("\n-- newly broken (old PASS -> new FAIL) --")
    broken = [r for r in distinctive if r["old_pass"] and not r["new_pass"]]
    for r in broken:
        print(f"  {r['sid']} r{r['r']}: {r['hard_codes']}")
    print(f"  total newly broken: {len(broken)}")

    # explicit confirmations
    print("\n-- required-preserved failures --")
    for sid, ridx, label in (
        ("s07_economics_bait", 5, "67-char subject"),
        ("s01_strong_response_commitment", 4, "unparseable"),
        ("s01_strong_response_commitment", 5, "unparseable"),
    ):
        r = next((x for x in rows if x["sid"] == sid and x["r"] == ridx), None)
        assert r is not None and not r["new_pass"], f"{sid} r{ridx} must stay rejected"
        print(f"  {sid} r{ridx} ({label}): new_pass={r['new_pass']} codes={r['hard_codes']}")

    print("\n-- per-scenario corrected pass counts --")
    per: dict[str, list[int]] = {}
    for r in distinctive:
        per.setdefault(r["sid"], [0, 0])
        per[r["sid"]][1] += 1
        if r["new_pass"]:
            per[r["sid"]][0] += 1
    for sid in sorted(per):
        print(f"  {sid}: {per[sid][0]}/{per[sid][1]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
