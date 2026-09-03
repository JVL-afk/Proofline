"""``demo.builder_brief@2`` - the simplified three-screen builder EXPERIENCE.

Owner authorization 2026-09-03 "M4 HUMAN-EXPERIENCE SIMPLIFICATION / BUILDER-BRIEF
V2", section 18. Proves the presentation projection stays entirely inside the M4
authority bundle, hides the internal ontology, and never manufactures relevance.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from m68_fixtures import aplus_envelope, elite_envelope, em_envelope
from opintel_communication.builder_brief import compile_builder_brief
from opintel_communication.builder_experience import (
    BUILDER_EXPERIENCE_VERSION,
    BuilderExperienceAuthorityError,
    _assert_experience_within_authority,
    compile_builder_experience,
    render_builder_experience_markdown,
)
from opintel_demo import demo_scenario_skeleton
from opintel_demo.composition import DeterministicDemoComposer

_SK = demo_scenario_skeleton()


def _drop_categories(env, categories):
    keep = tuple(f for f in env.eligible_company_facts if f.category not in categories)
    return dataclasses.replace(env, eligible_company_facts=keep)


def _customer_text(exp) -> str:
    from opintel_communication.builder_experience import _customer_facing_strings

    return " \n ".join(_customer_facing_strings(exp))


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------


def test_version_and_deterministic() -> None:
    assert BUILDER_EXPERIENCE_VERSION == "demo.builder_brief@2"
    a = compile_builder_experience(envelope=aplus_envelope())
    b = compile_builder_experience(envelope=aplus_envelope())
    assert dataclasses.asdict(a) == dataclasses.asdict(b)
    assert render_builder_experience_markdown(a) == render_builder_experience_markdown(b)


def test_three_screen_shape() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    md = render_builder_experience_markdown(exp)
    assert "## Screen 1 — Opportunity" in md
    assert "## Screen 2 — Simulate a commercial request" in md
    assert "## Screen 3 — Result / human handoff" in md
    # the internal state machine is NOT the customer UI
    assert "state machine" not in md.lower()
    assert "simulation_notice" not in md
    assert "qualification_result" not in md


# --------------------------------------------------------------------------
# section-18 required regressions
# --------------------------------------------------------------------------


def test_1_internal_m4_state_and_safety_semantics_unchanged() -> None:
    # the fixed skeleton is re-derived from opintel_demo.composition and must be
    # byte-identical to the composer's own statics.
    states = tuple(n.id for n in DeterministicDemoComposer._states())
    assert tuple(s.id for s in _SK.states) == states
    assert _SK.safety_handoff_message == (
        "This simulation cannot evaluate safety-critical or emergency situations. A real "
        "deployment would route this case to an approved human emergency-handling process. No "
        "dispatch or emergency action has occurred."
    )
    assert {a for a, _ in _SK.mock_actions} == {
        "CREATE_INTAKE_RECORD",
        "CREATE_CRM_LEAD",
        "QUEUE_HUMAN_CALLBACK",
        "NOTIFY_DISPATCH",
        "REQUEST_SCHEDULING_REVIEW",
        "CREATE_ACKNOWLEDGMENT_PREVIEW",
    }


def test_2_experience_is_a_projection_not_an_authority_change() -> None:
    env = aplus_envelope()
    exp = compile_builder_experience(envelope=env)
    brief = compile_builder_brief(envelope=env)
    # the experience is built on, and hashes, the V1 brief that already passed
    # the full M4-authority check.
    from opintel_communication.builder_experience import _brief_sha

    assert exp.underlying_brief_sha256 == _brief_sha(brief)
    # option lists are exactly the M4 brief's
    by_id = {f.field_id: f.options for f in exp.simulation_input_fields}
    assert by_id["service_need"] == tuple(brief.service_need_options)
    assert by_id["service_location"] == tuple(brief.service_location_options)


def test_3_opportunity_summary_word_count() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        exp = compile_builder_experience(envelope=fn())
        assert 30 <= len(exp.opportunity_summary.split()) <= 50


def test_4_opportunity_summary_has_evidence_simulation_and_unknown() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    low = exp.opportunity_summary.lower()
    assert "public pages" in low  # what we noticed
    assert "simulation" in low  # what the simulation proposes
    assert "don't know" in low  # what is unknown
    bad = dataclasses.replace(exp, opportunity_summary="A short simulation.")
    with pytest.raises(BuilderExperienceAuthorityError):
        _assert_experience_within_authority(
            bad, compile_builder_brief(envelope=aplus_envelope()), aplus_envelope(), _SK
        )


def test_5_fictional_names_cannot_be_company_facts() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    fact_words = {
        w.lower()
        for f in aplus_envelope().eligible_company_facts
        for w in re.findall(r"[A-Za-z]+", f.sanitized_phrase)
    }
    for p in exp.fictional_placeholders:
        assert p.name.lower() not in fact_words
    assert exp.business_display_name.split()[0].lower() not in {
        p.name.lower() for p in exp.fictional_placeholders
    }


def test_6_fictional_placeholder_disclosure_always_emitted() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        exp = compile_builder_experience(envelope=fn())
        for p in exp.fictional_placeholders:
            assert "fictional" in p.disclosure.lower()
            assert "not a real person" in p.disclosure.lower()
    env = aplus_envelope()
    exp = compile_builder_experience(envelope=env)
    stripped = dataclasses.replace(
        exp,
        fictional_placeholders=(
            dataclasses.replace(exp.fictional_placeholders[0], disclosure="Meet the team."),
        ),
    )
    with pytest.raises(BuilderExperienceAuthorityError):
        _assert_experience_within_authority(stripped, compile_builder_brief(envelope=env), env, _SK)


def test_7_no_internal_template_token_leaks() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        exp = compile_builder_experience(envelope=fn())
        blob = _customer_text(exp) + render_builder_experience_markdown(exp).split("## Appendix")[0]
        assert "{{" not in blob and "}}" not in blob
        assert "functional_role_or_team" not in blob


def test_8_mock_action_ids_not_required_in_customer_ui() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    for a in exp.prepared_actions:
        assert a.customer_label.startswith(("Prepare", "Preview", "Simulate"))
        assert a.internal_id not in a.customer_label
    # the customer screens (before the appendix) do not need the raw ids
    md_body = render_builder_experience_markdown(exp).split("## Appendix")[0]
    assert "CREATE_INTAKE_RECORD" not in md_body


def test_9_customer_labels_semantically_equivalent_to_internal() -> None:
    from opintel_communication.builder_experience import _MOCK_ACTION_LABEL

    exp = compile_builder_experience(envelope=aplus_envelope())
    got = {a.internal_id: a.customer_label for a in exp.prepared_actions}
    assert got == _MOCK_ACTION_LABEL
    assert {a.internal_id for a in exp.prepared_actions} == {a for a, _ in _SK.mock_actions}


def test_10_result_never_implies_a_real_action() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    blob = " ".join(line.text for line in exp.simulation_result_model) + " " + exp.result_disclosure
    assert "nothing was sent" in exp.result_disclosure.lower()
    env = aplus_envelope()
    bad = dataclasses.replace(
        exp,
        simulation_result_model=(
            *exp.simulation_result_model,
            dataclasses.replace(
                exp.simulation_result_model[0], text="Your request was dispatched."
            ),
        ),
    )
    with pytest.raises(BuilderExperienceAuthorityError):
        _assert_experience_within_authority(bad, compile_builder_brief(envelope=env), env, _SK)
    _ = blob


def test_11_result_never_implies_the_fictional_person_exists_at_company() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    for p in exp.fictional_placeholders:
        d = p.disclosure.lower()
        assert "employee" not in d and "on staff" not in d
        assert f"{p.name.lower()} works" not in d
    # a "sent to <name>" result line is rejected
    env = aplus_envelope()
    bad = dataclasses.replace(
        exp,
        simulation_result_model=(
            dataclasses.replace(
                exp.simulation_result_model[0],
                text=f"Assigned to {exp.fictional_placeholders[0].name}.",
            ),
        ),
    )
    with pytest.raises(BuilderExperienceAuthorityError):
        _assert_experience_within_authority(bad, compile_builder_brief(envelope=env), env, _SK)


def test_12_safety_exception_routes_correctly() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    triggers = {s.trigger for s in exp.exception_states}
    assert triggers == {"safety_critical", "out_of_scope", "mock_error"}
    safety = next(s for s in exp.exception_states if s.trigger == "safety_critical")
    assert "dispatched" in safety.body.lower()
    assert "human" in safety.body.lower()
    assert not re.search(r"\b\d{3}[- ]?\d{3,4}\b", safety.body)
    # 'Safety concern' urgency option maps to the M4 safety_critical branch
    urgency = next(f for f in exp.simulation_input_fields if f.field_id == "urgency")
    assert "Safety concern" in urgency.options
    assert "safety_critical" in urgency.internal_note


def test_13_unknowns_remain_unknown() -> None:
    env = aplus_envelope()
    exp = compile_builder_experience(envelope=env)
    low = (exp.opportunity_summary + " " + exp.unknown_summary).lower()
    assert "don't know" in low
    # the underlying brief still carries every explicit UNKNOWN component
    brief = compile_builder_brief(envelope=env)
    assert {u.component for u in brief.unknowns} == {u.component for u in env.explicit_unknowns}
    # no speed/performance assertion in customer copy
    assert not re.search(
        r"\bresponds?\b.*\b(fast|quick|minutes|hours)\b", _customer_text(exp).lower()
    )


def test_14_availability_cannot_become_response_behavior() -> None:
    env = elite_envelope()
    exp = compile_builder_experience(envelope=env)
    for s in (exp.opportunity_summary, *exp.known_public_context):
        sl = s.lower()
        if "don't know" in sl or "unknown" in sl:
            continue
        assert not (
            "availab" in sl
            and any(w in sl for w in ("respond", "response", "acknowledg", "callback"))
        )
    bad = dataclasses.replace(
        exp,
        opportunity_summary=(
            "Your public availability message means the team responds around the clock. "
            "We built a short simulation. We don't know your internal process."
        ),
    )
    with pytest.raises(BuilderExperienceAuthorityError):
        _assert_experience_within_authority(bad, compile_builder_brief(envelope=env), env, _SK)


def test_15_no_fake_crm_integration_or_metrics() -> None:
    env = aplus_envelope()
    exp = compile_builder_experience(envelope=env)
    for claim in (
        "Connected to your ServiceTitan account.",
        "Average response time 11 minutes. We built a simulation. We don't know your process.",
    ):
        bad = dataclasses.replace(exp, opportunity_summary=claim + " " * 0)
        with pytest.raises(BuilderExperienceAuthorityError):
            _assert_experience_within_authority(bad, compile_builder_brief(envelope=env), env, _SK)


def test_16_thin_evidence_still_downgrades() -> None:
    em = compile_builder_experience(envelope=em_envelope())
    assert em.demo_mode.value == "GENERIC_CAPABILITY_DEMO"
    assert "generic" in em.opportunity_summary.lower()
    assert "not built around your" in em.opportunity_summary.lower()
    thin = _drop_categories(em_envelope(), {"commercial_context"})
    tb = compile_builder_experience(envelope=thin)
    assert tb.demo_mode.value == "DEMO_NOT_DISTINCTIVE_ENOUGH"
    assert "generic" in tb.opportunity_summary.lower()


def test_17_ontology_never_surfaces_in_customer_copy() -> None:
    for fn in (aplus_envelope, elite_envelope, em_envelope):
        exp = compile_builder_experience(envelope=fn())
        blob = _customer_text(exp).lower()
        for tok in (
            "mock_only",
            "not_connected",
            "response_commitment",
            "current_process",
            "published_self_claim",
            "observed_public_text",
            "human_handoff",
        ):
            assert tok not in blob


def test_18_persistent_and_result_disclosures_preserve_meaning() -> None:
    exp = compile_builder_experience(envelope=aplus_envelope())
    assert "not connected" in exp.persistent_disclosure.lower()
    assert "nothing was sent" in exp.result_disclosure.lower()
    assert exp.closing_thought.lower().startswith("imagine this fitted")
    # closing thought must not pitch
    low = exp.closing_thought.lower()
    for pitch in ("roi", "save", "lose", "miss", "book a call", "schedule", "now", "today"):
        assert pitch not in low
