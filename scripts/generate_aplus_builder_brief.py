"""Generate the A-Plus builder artifacts.

* ``demo.builder_brief@1`` - the detailed audit-grade brief (owner authorization
  2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM").
* ``demo.builder_brief@2`` - the simplified three-screen human experience (owner
  authorization 2026-09-03 "M4 HUMAN-EXPERIENCE SIMPLIFICATION / BUILDER-BRIEF
  V2", section 16).

First and only target: A-Plus. Uses ONLY the frozen, corrected M2-M5 evidence in
``tests/m68_fixtures.aplus_envelope`` + the fixed M4 scenario skeleton. No
re-research, no web, no new evidence. Manual workflow only - this writes files;
a human pastes a ``.md`` into Lovable / Base44.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m68_fixtures import aplus_envelope, elite_envelope  # noqa: E402
from opintel_communication.builder_brief import (  # noqa: E402
    compile_builder_brief,
    render_builder_brief_markdown,
)
from opintel_communication.builder_experience import (  # noqa: E402
    compile_builder_experience,
    render_builder_experience_markdown,
)
from opintel_communication.builder_story import (  # noqa: E402
    compile_builder_story,
    render_builder_story_markdown,
)

_OUT = ROOT / "docs" / "readiness" / "demo-builder-brief"


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    env = aplus_envelope()
    source = {
        "target": "A-Plus",
        "frozen_envelope_sha256": env.envelope_sha256,
        "m2_m5_bundle_sha256": env.source_lineage.m2_m5_bundle_sha256,
        "fixture": "tests/m68_fixtures.aplus_envelope()",
        "note": "Frozen corrected M2-M5 evidence; no re-research, no web, no new evidence.",
    }

    # --- V1: detailed audit-grade brief ---
    brief = compile_builder_brief(envelope=env)
    v1_payload = dataclasses.asdict(brief)
    v1_payload["_source"] = source
    (_OUT / "m4-aplus-builder-brief-2026-09-03.json").write_text(
        json.dumps(v1_payload, indent=2, default=str), encoding="utf-8"
    )
    (_OUT / "m4-aplus-builder-brief-2026-09-03.md").write_text(
        render_builder_brief_markdown(brief), encoding="utf-8"
    )

    # --- V2: simplified three-screen experience ---
    exp = compile_builder_experience(envelope=env)
    v2_payload = dataclasses.asdict(exp)
    v2_payload["_source"] = source
    v2_json = _OUT / "m4-aplus-builder-brief-v2-2026-09-03.json"
    v2_md = _OUT / "m4-aplus-builder-brief-v2-2026-09-03.md"
    v2_json.write_text(json.dumps(v2_payload, indent=2, default=str), encoding="utf-8")
    v2_md.write_text(render_builder_experience_markdown(exp), encoding="utf-8")

    # --- V3 / V3.1: opportunity-story projection ---
    story = compile_builder_story(envelope=env)
    v3_payload = dataclasses.asdict(story)
    v3_payload["_source"] = source
    v3_json = _OUT / "m4-aplus-builder-brief-v3-2026-09-03.json"
    v3_md = _OUT / "m4-aplus-builder-brief-v3-2026-09-03.md"
    v3_json.write_text(json.dumps(v3_payload, indent=2, default=str), encoding="utf-8")
    v3_md.write_text(render_builder_story_markdown(story), encoding="utf-8")

    # --- Elite V3.1 (same generalized compiler, Elite's frozen evidence only) ---
    elite_env = elite_envelope()
    elite_source = {
        "target": "Elite",
        "frozen_envelope_sha256": elite_env.envelope_sha256,
        "m2_m5_bundle_sha256": elite_env.source_lineage.m2_m5_bundle_sha256,
        "fixture": "tests/m68_fixtures.elite_envelope()",
        "note": "Frozen Elite evidence; no re-research, no web, no new evidence.",
    }
    elite_story = compile_builder_story(envelope=elite_env)
    elite_payload = dataclasses.asdict(elite_story)
    elite_payload["_source"] = elite_source
    elite_json = _OUT / "m4-elite-builder-brief-v3.1-2026-09-04.json"
    elite_md = _OUT / "m4-elite-builder-brief-v3.1-2026-09-04.md"
    elite_json.write_text(json.dumps(elite_payload, indent=2, default=str), encoding="utf-8")
    elite_md.write_text(render_builder_story_markdown(elite_story), encoding="utf-8")

    print("== V1 (audit-grade brief) ==")
    print(f"  demo_mode {brief.demo_mode.value}  anchor {exp.primary_demo_anchor}")
    print("== V2 (three-screen experience) ==")
    print(f"  demo_mode              : {exp.demo_mode.value}")
    print(f"  opportunity words      : {len(exp.opportunity_summary.split())}")
    print(f"  opportunity summary    : {exp.opportunity_summary}")
    print(f"  primary anchor         : {exp.primary_demo_anchor}")
    print(f"  simulation fields      : {[f.label for f in exp.simulation_input_fields]}")
    print(
        "  fictional placeholder  : "
        f"{exp.fictional_placeholders[0].name} / {exp.fictional_placeholders[0].role}"
    )
    print(f"  prepared previews      : {[a.customer_label for a in exp.prepared_actions]}")
    print(f"  exception screens      : {[s.trigger for s in exp.exception_states]}")
    print(f"  persistent disclosure  : {exp.persistent_disclosure}")
    print(f"  result disclosure      : {exp.result_disclosure}")
    print(f"  closing thought        : {exp.closing_thought}")
    print("== V3 (opportunity story) ==")
    print(f"  opportunity headline   : {story.opportunity_headline}")
    print(f"  opportunity words      : {len(story.opportunity_summary.split())}")
    print(f"  primary anchor         : {story.primary_demo_anchor}")
    print(f"  synthetic input values : {list(story.synthetic_input_values)}")
    print(
        "  outcome groups         : "
        f"{[(g.name, g.internal_action_ids) for g in story.customer_facing_outcomes]}"
    )
    print(f"  result story stages    : {[s.label for s in story.result_story]}")
    print(
        f"  human handoff          : {story.human_handoff_preview.name} / "
        f"{story.human_handoff_preview.role}"
    )
    print(f"  closing bridge         : {story.closing_bridge}")
    print("== Elite V3.1 (same compiler, Elite evidence) ==")
    print(f"  primary anchor         : {elite_story.primary_demo_anchor}")
    print(f"  opportunity headline   : {elite_story.opportunity_headline}")
    print(f"  scenario framing       : {elite_story.scenario_framing}")
    print(f"  opportunity summary    : {elite_story.opportunity_summary}")
    print(f"  evidence detail        : {[i.text for i in elite_story.evidence_detail]}")
    print(f"\n  V2 machine-readable : {v2_json.relative_to(ROOT)}")
    print(f"  V2 paste-ready md   : {v2_md.relative_to(ROOT)}")
    print(f"  V3.1 A-Plus md      : {v3_md.relative_to(ROOT)}")
    print(f"  V3.1 Elite md       : {elite_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
