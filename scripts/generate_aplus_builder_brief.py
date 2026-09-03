"""Generate the A-Plus ``demo.builder_brief@1`` artifacts (owner authorization
2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM", sections 8/11).

First and only target: A-Plus. Uses ONLY the frozen, corrected M2-M5 evidence in
``tests/m68_fixtures.aplus_envelope`` + the fixed M4 scenario skeleton. No
re-research, no web, no new evidence. Manual workflow only - this writes files;
a human pastes the ``.md`` into Lovable.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_fixtures import aplus_envelope  # noqa: E402
from opintel_communication.builder_brief import (  # noqa: E402
    compile_builder_brief,
    render_builder_brief_markdown,
)

_OUT = ROOT / "docs" / "readiness" / "demo-builder-brief"


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)

    payload = dataclasses.asdict(brief)
    payload["_source"] = {
        "target": "A-Plus",
        "frozen_envelope_sha256": env.envelope_sha256,
        "m2_m5_bundle_sha256": env.source_lineage.m2_m5_bundle_sha256,
        "fixture": "tests/m68_fixtures.aplus_envelope()",
        "note": "Frozen corrected M2-M5 evidence; no re-research, no web, no new evidence.",
    }
    json_path = _OUT / "m4-aplus-builder-brief-2026-09-03.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    md_path = _OUT / "m4-aplus-builder-brief-2026-09-03.md"
    md_path.write_text(render_builder_brief_markdown(brief), encoding="utf-8")

    anchor = brief.primary_demo_anchor.category if brief.primary_demo_anchor else None
    print(f"demo_mode                 : {brief.demo_mode.value}")
    print(f"primary anchor            : {anchor}")
    print(f"licensed evidence items   : {len(brief.licensed_public_evidence)}")
    print(f"UNKNOWNs carried          : {len(brief.unknowns)}")
    print(f"required disclosures       : {len(brief.required_disclosures)}")
    print(f"forbidden additions        : {len(brief.forbidden_additions)}")
    print(f"service_need options       : {list(brief.service_need_options)}")
    print(f"service_location options   : {list(brief.service_location_options)}")
    print(f"\nmachine-readable : {json_path.relative_to(ROOT)}")
    print(f"paste-ready md   : {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
