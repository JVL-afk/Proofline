"""M6.8-3 synthetic live-provider certification — local execution harness.

Owner-authorized (2026-09-01). Runs EXACTLY the bounded certification described
in ``docs/readiness/communication-layer/m6.8-3-execution-plan-2026-09-01.md``:
10 frozen synthetic envelopes x 3 repeats = 30 real ``claude-sonnet-5`` calls,
N=3 candidates/call, USD ceiling 10.00, 0 retries.

This is Option A (local execution). It does NOT touch AWS. It reads the Anthropic
key from ``apikeys.txt`` (the line prefixed ``ANTHROPIC:``), holds it only in the
adapter, and never prints/logs/commits it. It writes one immutable JSON report +
a markdown summary under ``docs/readiness/communication-layer/`` and exits. It
performs no contact resolution, no delivery, no send.

Do not run without the owner's go on the execution-environment decision.

    python scripts/run_m68_3_certification.py            # dry run: prints plan, no calls
    python scripts/run_m68_3_certification.py --execute   # makes the 30 real calls
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_3_synthetic_corpus import NOT_DISTINCTIVE_SCENARIO_ID, build_corpus  # noqa: E402
from opintel_communication.anthropic_adapter import (  # noqa: E402
    AnthropicProviderAdapter,
    GenerationConfig,
)
from opintel_communication.certification import (  # noqa: E402
    DEFAULT_CALL_BOUNDS,
    CertificationRunner,
    PriceTable,
)

_APIKEYS = ROOT / "apikeys.txt"
_OUT_DIR = ROOT / "docs" / "readiness" / "communication-layer"


def _read_anthropic_key() -> str:
    for line in _APIKEYS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("ANTHROPIC:"):
            return stripped.split(":", 1)[1].strip()
    raise SystemExit("no line prefixed 'ANTHROPIC:' in apikeys.txt")


def _plan_summary() -> str:
    b = DEFAULT_CALL_BOUNDS
    corpus = build_corpus()
    lines = [
        "M6.8-3 synthetic certification - PLAN",
        f"  corpus            : {corpus.corpus_version} ({len(corpus.specs)} envelopes)",
        f"  corpus manifest   : {corpus.manifest_sha256()}",
        f"  provider calls    : {len(corpus.specs) - 1} distinctive x 3 repeats = "
        f"{(len(corpus.specs) - 1) * 3} (<= {b.max_provider_calls})",
        f"  candidates / call : {b.candidates_per_call}",
        f"  token ceilings    : {b.max_input_tokens_per_call}/call in, "
        f"{b.aggregate_input_token_ceiling} agg in, {b.aggregate_output_token_ceiling} agg out",
        f"  USD ceiling       : {b.hard_usd_ceiling}   retries: {b.automatic_retries}",
        f"  not-distinctive   : {NOT_DISTINCTIVE_SCENARIO_ID} (provider not called)",
    ]
    for s in corpus.specs:
        lines.append(f"    {s.scenario_id:<38} {s.envelope_sha256}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="make the 30 real provider calls")
    args = ap.parse_args()

    print(_plan_summary())
    if not args.execute:
        print("\ndry run only. re-run with --execute to make the real calls.")
        return 0

    key = _read_anthropic_key()
    corpus = build_corpus()
    adapter = AnthropicProviderAdapter(key, config=GenerationConfig())
    runner = CertificationRunner(adapter, price_table=PriceTable())

    print("\nexecuting 30 real claude-sonnet-5 calls ...")
    report = runner.run(
        corpus,
        repeats=3,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=int(time.time()),
    )

    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    payload = dataclasses.asdict(report)
    json_path = _OUT_DIR / f"m6.8-3-certification-report-{stamp}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"\nsafety_outcome        : {report.safety_outcome.value}")
    print(f"communication_quality : {report.communication_quality.value}")
    print(f"provider_calls_made   : {report.provider_calls_made}")
    print(f"aggregate cost (est)  : USD {report.aggregate_cost_usd}")
    print(f"safety_critical_hits  : {report.safety_critical_hits or '(none)'}")
    print(f"stopped_early_reason  : {report.stopped_early_reason or '(none)'}")
    print(f"certification_key_sha : {report.certification_key_sha256}")
    print(f"\nreport written: {json_path.relative_to(ROOT)}")
    print("Adapter never persisted the key. No AWS surface created. STOP for owner review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
