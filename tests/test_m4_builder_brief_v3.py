"""``demo.builder_brief@3`` - the opportunity-story projection.

Owner authorization 2026-09-03 "M4 BUILDER-BRIEF V3: OPPORTUNITY -> EXPERIENCE ->
HANDOFF", section 19. Proves V3 stays a presentation projection: it never
strengthens the evidence anchor, never leaks internal taxonomy or the demo mode,
never converts an evidence phrase into a selectable value, keeps the six mock
actions intact while grouping them into three understandable outcomes, keeps the
fictional human fictional, and never turns the closing bridge into a claim about
the real business.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from m68_fixtures import aplus_envelope, elite_envelope, em_envelope
from opintel_communication.builder_brief import compile_builder_brief
from opintel_communication.builder_experience import compile_builder_experience
from opintel_communication.builder_story import (
    BUILDER_STORY_VERSION,
    SEM_SYNTHETIC_DEMO_INPUT,
    BuilderStoryAuthorityError,
    _assert_story_within_authority,
    _story_customer_strings,
    compile_builder_story,
    render_builder_story_markdown,
)
from opintel_demo import demo_scenario_skeleton
from opintel_demo.composition import DeterministicDemoComposer

_SK = demo_scenario_skeleton()


def _ctx(env):
    return (
        compile_builder_experience(envelope=env),
        compile_builder_brief(envelope=env),
        env,
        _SK,
    )


def _customer_text(story) -> str:
    return " \n ".join(_story_customer_strings(story)).lower()


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------


def test_version_and_deterministic() -> None:
    assert BUILDER_STORY_VERSION == "demo.builder_brief@3.1"
    a = compile_builder_story(envelope=aplus_envelope())
    b = compile_builder_story(envelope=aplus_envelope())
    assert dataclasses.asdict(a) == dataclasses.asdict(b)
    assert render_builder_story_markdown(a) == render_builder_story_markdown(b)


def test_three_screen_shape_headline_is_the_title() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    md = render_builder_story_markdown(story)
    assert f"## Screen 1 — {story.opportunity_headline}" in md
    assert "## Screen 2 — " in md
    assert "## Screen 3 — " in md
    # the opportunity, not our artifact, is the hero: no "Opportunity"/"demo mode" label
    assert "## Screen 1 — Opportunity" not in md
    assert "Demo mode" not in md.split("## Appendix")[0]


# --------------------------------------------------------------------------
# section-19 required regressions
# --------------------------------------------------------------------------


def test_1_authoritative_m4_semantics_unchanged() -> None:
    states = tuple(n.id for n in DeterministicDemoComposer._states())
    assert tuple(s.id for s in _SK.states) == states
    story = compile_builder_story(envelope=aplus_envelope())
    exp = compile_builder_experience(envelope=aplus_envelope())
    # V3 is a projection of the V2 experience, which hashes the V1 brief.
    assert story.underlying_brief_sha256 == exp.underlying_brief_sha256
    # all six mock actions preserved verbatim
    assert story.internal_mock_actions == _SK.mock_actions
    assert _SK.safety_handoff_message.startswith("This simulation cannot evaluate safety-critical")


def test_2_opportunity_headline_cannot_strengthen_the_anchor() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        story = compile_builder_story(envelope=fn())
        h = story.opportunity_headline.lower()
        assert "could" in h
        for strong in (
            "fast",
            "fastest",
            "quick",
            "immediate",
            "guarantee",
            "best",
            "24/7",
            "24-hour",
            "same-day",
            "always",
        ):
            assert strong not in h
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    bad = dataclasses.replace(
        compile_builder_story(envelope=env),
        opportunity_headline="We respond faster than any other contractor in town",
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)


def test_3_internal_taxonomy_and_demo_mode_do_not_leak() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        story = compile_builder_story(envelope=fn())
        blob = _customer_text(story)
        body = render_builder_story_markdown(story).split("## Appendix")[0].lower()
        for tok in (
            "bespoke_demo",
            "evidence_bound_demo",
            "generic_capability_demo",
            "demo.builder_brief",
            "mock_only",
            "not_connected",
            "response_commitment",
            "published_self_claim",
            "safety_critical",
            "qualification_result",
        ):
            assert tok not in blob
            assert tok not in body


def test_4_evidence_phrases_are_not_selectable_inputs() -> None:
    env = aplus_envelope()
    story = compile_builder_story(envelope=env)
    fact_phrases = {
        p.strip().lower()
        for f in env.eligible_company_facts
        for p in (f.sanitized_phrase, f.verbatim_source_phrase)
    }
    all_values = {v.lower() for f in story.simulation_input_schema for v in f.values}
    assert not (all_values & fact_phrases)
    assert "service area" not in all_values
    assert "when to schedule ac replacement" not in all_values
    # but the field still exists, and records what M4 *would* derive, for audit
    loc = next(f for f in story.simulation_input_schema if f.field_id == "service_location")
    assert loc.exists_because
    assert loc.m4_option_labels  # the evidence-derived labels are retained in the audit layer


def test_5_synthetic_input_values_are_explicitly_synthetic() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    assert story.synthetic_input_values
    for f in story.simulation_input_schema:
        assert f.value_semantics == SEM_SYNTHETIC_DEMO_INPUT
    # the markdown tells the reader the values are illustrative
    md = render_builder_story_markdown(story)
    assert "illustrative simulation choice" in md.lower()


def test_6_fictional_human_remains_fictional() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        story = compile_builder_story(envelope=fn())
        p = story.human_handoff_preview
        d = p.disclosure.lower()
        assert "fictional" in d and "not a real person" in d
        # the result story leads with the ROLE, never the fictional name
        joined = " ".join(s.line for s in story.result_story)
        assert p.name not in joined
        assert p.role.lower() in joined.lower()
        assert not re.search(
            rf"\b(sent|assigned|routed)\s+to\s+{re.escape(p.name)}\b", _customer_text(story)
        )


def test_7_outcome_groups_preserve_every_mock_action() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    assert len(story.customer_facing_outcomes) == 3
    covered: list[str] = []
    for g in story.customer_facing_outcomes:
        covered.extend(g.internal_action_ids)
    registered = {a for a, _ in _SK.mock_actions}
    assert set(covered) == registered
    assert len(covered) == len(registered)  # disjoint - each action mapped exactly once


def test_8_grouping_cannot_imply_the_action_occurred() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    for g in story.customer_facing_outcomes:
        gt = f"{g.name} {g.description}".lower()
        assert not re.search(r"\b(was|were|has been|have been|sent|dispatched|created)\b", gt)
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    base = compile_builder_story(envelope=env)
    bad = dataclasses.replace(
        base,
        customer_facing_outcomes=(
            dataclasses.replace(
                base.customer_facing_outcomes[0],
                description="The lead record was sent to your CRM.",
            ),
            *base.customer_facing_outcomes[1:],
        ),
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)


def test_9_no_crm_or_vendor_is_invented() -> None:
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    base = compile_builder_story(envelope=env)
    # V3-authored copy never names a CRM vendor
    for s in (
        base.opportunity_headline,
        base.result_title,
        *(g.description for g in base.customer_facing_outcomes),
        *(f.exists_because for f in base.simulation_input_schema),
    ):
        assert not re.search(r"servicetitan|housecall|jobber|salesforce|hubspot", s.lower())
    bad = dataclasses.replace(
        base,
        customer_facing_outcomes=(
            dataclasses.replace(
                base.customer_facing_outcomes[0],
                description="Ready for your ServiceTitan account.",
            ),
            *base.customer_facing_outcomes[1:],
        ),
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)


def test_10_no_location_is_inferred() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    blob = _customer_text(story)
    for city in ("austin", "dallas", "houston"):
        assert city not in blob


def test_11_no_response_performance_is_inferred_from_positioning() -> None:
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    story = compile_builder_story(envelope=env)
    assert not re.search(
        r"\bresponds?\b[^.]*\b(fast|quick|minutes|hours|seconds)\b", _customer_text(story)
    )
    bad = dataclasses.replace(
        story,
        opportunity_headline="One way structured intake could show you respond in minutes",
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)


def test_12_closing_bridge_cannot_become_a_current_process_assertion() -> None:
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    story = compile_builder_story(envelope=env)
    cb = story.closing_bridge.lower()
    assert "imagine" in cb and "hypothetical" in cb
    for bad_close in (
        "Your current intake process is losing you leads",
        "Book a call today to fix your process",
    ):
        bad = dataclasses.replace(story, closing_bridge=bad_close)
        with pytest.raises(BuilderStoryAuthorityError):
            _assert_story_within_authority(bad, exp, brief, env, sk)


def test_13_safety_and_unknown_semantics_remain_intact() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    triggers = {s.trigger for s in story.exception_states}
    assert triggers == {"safety_critical", "out_of_scope", "mock_error"}
    safety = next(s for s in story.exception_states if s.trigger == "safety_critical")
    assert "dispatched" in safety.body.lower() and "human" in safety.body.lower()
    assert not re.search(r"\b\d{3}[- ]?\d{3,4}\b", safety.body)
    assert "don't know" in story.unknown_summary.lower()
    urgency = next(f for f in story.simulation_input_schema if f.field_id == "urgency")
    assert "Safety concern" in urgency.values
    assert "safety_critical" in urgency.internal_note
    # the underlying brief still carries every explicit UNKNOWN component
    brief = compile_builder_brief(envelope=aplus_envelope())
    assert {u.component for u in brief.unknowns} == {
        u.component for u in aplus_envelope().explicit_unknowns
    }


def test_14_result_story_is_a_four_stage_workflow() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    assert tuple(s.order for s in story.result_story) == (1, 2, 3, 4)
    labels = [s.label for s in story.result_story]
    assert labels == [
        "Request",
        "Structured context",
        "Example human review",
        "Next workflow preparation",
    ]
    for s in story.result_story:
        assert not re.search(r"\b(was|were)\s+(sent|dispatched|booked|created)\b", s.line.lower())


def test_15_semantics_legend_is_plain_language_only() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    labels = {k for k, _ in story.semantics_legend}
    assert labels == {
        "Public evidence",
        "Unknown",
        "Synthetic demo input",
        "Fictional demo placeholder",
        "Simulated output",
    }
    for _, v in story.semantics_legend:
        assert "_" not in v
        assert not re.search(r"\b[A-Z]{4,}\b", v)


def test_16_evidence_detail_is_collapsed_licensed_context_only() -> None:
    env = aplus_envelope()
    story = compile_builder_story(envelope=env)
    exp = compile_builder_experience(envelope=env)
    assert tuple(i.text for i in story.evidence_detail) == tuple(exp.known_public_context)
    md = render_builder_story_markdown(story)
    assert "<details><summary>Why we built this</summary>" in md


# --------------------------------------------------------------------------
# V3.1 cleanup regressions (owner authorization 2026-09-04, section 11)
# --------------------------------------------------------------------------


def _body(story) -> str:
    return render_builder_story_markdown(story).split("## Appendix")[0]


def test_v31_ontology_legend_not_in_default_customer_view() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        story = compile_builder_story(envelope=fn())
        body = _body(story).lower()
        # the legend is no longer a section in the customer-facing body
        assert "reading the labels" not in body
        assert "## semantic legend" not in body
        assert "- **public evidence** —" not in body
        # but the five distinctions are still preserved on the artifact + appendix
        assert len(story.semantics_legend) == 5
        appendix = render_builder_story_markdown(story).split("## Appendix")[1].lower()
        assert "semantic legend (audit" in appendix
        assert "- **public evidence** —" in appendix


def test_v31_no_debug_or_special_state_controls_in_normal_experience() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    # the screens themselves (Screen 1 onward) carry no state selector / debug control
    screens = render_builder_story_markdown(story).split("## Screen 1")[1].split("## Appendix")[0]
    screens_low = screens.lower()
    for probe in (
        "preview a special state",
        "test-state",
        "state selector",
        "scenario picker",
        "## debug",
        "developer controls",
    ):
        assert probe not in screens_low
    # exception screens are a builder note, never a user-facing selector
    assert "never a user-facing selector" in screens_low
    rules = " ".join(story.builder_hard_rules).lower()
    assert "state selector" in rules and "qa / debug" in rules


def test_v31_builder_cannot_invent_unlisted_functionality() -> None:
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    story = compile_builder_story(envelope=env)
    assert story.allowed_primary_actions == ("See how it could work", "Run simulation")
    rules = " ".join(story.builder_hard_rules).lower()
    for probe in ("download", "export", "pdf", "share or save", "analytics", "dashboard"):
        assert probe in rules
    # the rendered brief enumerates the allowed actions
    assert "Allowed interactive actions:" in render_builder_story_markdown(story)
    bad = dataclasses.replace(story, allowed_primary_actions=("See how it could work",))
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)


def test_v31_internal_evidence_and_semantic_metadata_preserved() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    # evidence rationale preserved in the audit layer even though it is not
    # customer-facing copy any more
    for f in story.simulation_input_schema:
        assert f.exists_because
        assert f.value_semantics == "SYNTHETIC_DEMO_INPUT"
    assert story.internal_mock_actions == _SK.mock_actions
    loc = next(f for f in story.simulation_input_schema if f.field_id == "service_location")
    assert loc.m4_option_labels
    assert any(k == "demo_mode" for k, _ in story.audit_appendix)
    assert any(k == "story_compiler_version" for k, _ in story.audit_appendix)


def test_v31_stronger_headline_cannot_exceed_evidence_strength() -> None:
    env = aplus_envelope()
    exp, brief, _, sk = _ctx(env)
    story = compile_builder_story(envelope=env)
    h = story.opportunity_headline.lower()
    assert "response" in h  # tied to the A-Plus anchor
    assert not re.search(r"\b(verified|proven|actual|measured|fast|quick|guarantee)\b", h)
    # a headline that claims verified performance is rejected
    bad = dataclasses.replace(
        story,
        opportunity_headline="One way structured intake reflects your verified response speed",
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad, exp, brief, env, sk)
    # a headline that drops the anchor keyword is rejected
    bad2 = dataclasses.replace(
        story,
        opportunity_headline="One way structured intake could support what your pages describe",
    )
    with pytest.raises(BuilderStoryAuthorityError):
        _assert_story_within_authority(bad2, exp, brief, env, sk)


def test_v31_screen2_customer_hints_are_concise() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    for f in story.simulation_input_schema:
        assert 1 <= len(f.customer_hint.split()) <= 6
        assert "evidence" not in f.customer_hint.lower()
        assert "public page" not in f.customer_hint.lower()
    # the long rationale is no longer rendered under every field
    body = _body(story)
    assert "without making any coverage promise" not in body
    assert "so the simulation asks which need applies" not in body


def test_v31_result_still_preserves_grouped_mock_action_meaning() -> None:
    story = compile_builder_story(envelope=aplus_envelope())
    covered = [aid for g in story.customer_facing_outcomes for aid in g.internal_action_ids]
    assert set(covered) == {a for a, _ in _SK.mock_actions}
    assert len(covered) == 6
    assert story.result_recap_line
    assert len(story.result_recap_line.split()) <= 22


# --------------------------------------------------------------------------
# PART II — Elite personalization proof (section 12-14)
# --------------------------------------------------------------------------


def test_elite_story_is_materially_different_from_aplus() -> None:
    a = compile_builder_story(envelope=aplus_envelope())
    e = compile_builder_story(envelope=elite_envelope())
    # different primary anchor
    assert a.primary_demo_anchor != e.primary_demo_anchor
    assert a.primary_demo_anchor == "response commitment"
    assert e.primary_demo_anchor == "service availability"
    # different opportunity headline, summary, framing, evidence detail
    assert a.opportunity_headline != e.opportunity_headline
    assert "response" in a.opportunity_headline.lower()
    assert "availab" in e.opportunity_headline.lower()
    assert a.opportunity_summary != e.opportunity_summary
    assert a.scenario_framing != e.scenario_framing
    assert {i.text for i in a.evidence_detail} != {i.text for i in e.evidence_detail}
    # shared mechanics are legitimately shared (section 14)
    assert a.internal_mock_actions == e.internal_mock_actions
    assert [f.field_id for f in a.simulation_input_schema] == [
        f.field_id for f in e.simulation_input_schema
    ]


def test_elite_availability_never_becomes_response_behaviour() -> None:
    e = compile_builder_story(envelope=elite_envelope())
    blob = " ".join(
        [e.opportunity_headline, e.opportunity_summary, e.scenario_framing]
        + [i.text for i in e.evidence_detail]
        + [s.line for s in e.result_story]
    ).lower()
    for sent in re.split(r"(?<=[.!?])\s+", blob):
        if any(g in sent for g in ("don't know", "unknown", "not public")):
            continue
        if "availab" in sent:
            assert not any(
                w in sent
                for w in ("respond", "response", "acknowledg", "callback", "24/7", "24-hour")
            )
    # 24-hour / 24/7 availability is never upgraded into a response claim
    assert "24/7" not in blob
    assert not re.search(r"responds?\b[^.]*24", blob)
