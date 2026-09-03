"""``demo.builder_brief@1`` - deterministic M4 -> builder-brief compiler.

Owner authorization 2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM", section 10. Proves
the compiler cannot hand a website/app builder anything the M4 authority bundle
does not license, and that thin evidence downgrades rather than forcing a
bespoke-looking demo.
"""

from __future__ import annotations

import dataclasses

import pytest
from m68_fixtures import aplus_envelope, elite_envelope, em_envelope
from opintel_communication.builder_brief import (
    BUILDER_BRIEF_VERSION,
    BuilderBriefAuthorityError,
    DemoMode,
    _assert_within_authority,
    compile_builder_brief,
    render_builder_brief_markdown,
)
from opintel_demo import demo_scenario_skeleton

_SK = demo_scenario_skeleton()


def _drop_categories(env, categories):
    keep = tuple(f for f in env.eligible_company_facts if f.category not in categories)
    return dataclasses.replace(env, eligible_company_facts=keep)


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------


def test_version_and_deterministic() -> None:
    assert BUILDER_BRIEF_VERSION == "demo.builder_brief@1"
    a = compile_builder_brief(envelope=aplus_envelope())
    b = compile_builder_brief(envelope=aplus_envelope())
    assert dataclasses.asdict(a) == dataclasses.asdict(b)
    assert render_builder_brief_markdown(a) == render_builder_brief_markdown(b)


def test_aplus_is_bespoke_and_renders() -> None:
    brief = compile_builder_brief(envelope=aplus_envelope())
    assert brief.demo_mode is DemoMode.BESPOKE_DEMO
    md = render_builder_brief_markdown(brief)
    assert "A-Plus Air Conditioning & Home Solutions" in md
    assert "## 9. DO NOT ADD" in md
    assert "SIMULATED / MOCK_ONLY / NOT_CONNECTED" in md


# --------------------------------------------------------------------------
# section-10 required regressions (11 named invariants)
# --------------------------------------------------------------------------


def test_1_cannot_introduce_a_fact_absent_from_m4_authority() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    tampered = dataclasses.replace(
        brief,
        central_demo_story=brief.central_demo_story
        + " The business also uses ServiceTitan and books 40 jobs a week.",
    )
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(tampered, env, _SK)


def test_2_unknowns_stay_unknown() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    env_components = {u.component for u in env.explicit_unknowns}
    assert {u.component for u in brief.unknowns} == env_components
    # RESPONSE_PERFORMANCE + CURRENT_PROCESS carry their hard prohibitions
    hard = {u.component for u in brief.unknowns if u.hard_prohibition}
    assert {"RESPONSE_PERFORMANCE", "CURRENT_PROCESS"} <= hard
    dropped = dataclasses.replace(brief, unknowns=brief.unknowns[:-1])
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(dropped, env, _SK)


def test_3_service_availability_cannot_become_response_commitment() -> None:
    env = elite_envelope()
    brief = compile_builder_brief(envelope=env)
    avail = next(e for e in brief.licensed_public_evidence if e.category == "service_availability")
    assert avail.is_selectable_demo_option is False
    assert brief.demo_mode is not DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH
    # story references it only as an availability signal
    assert "service-availability signal" in brief.central_demo_story
    assert "respond" not in brief.central_demo_story.lower()
    tampered = dataclasses.replace(
        brief,
        central_demo_story="About Our 24-Hour Service means the team responds around the clock.",
    )
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(tampered, env, _SK)


def test_4_no_crm_or_vendor_name_unless_supplied() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    for tok in ("ServiceTitan", "Housecall", "Salesforce", "HubSpot"):
        tampered = dataclasses.replace(
            brief, demo_objective=brief.demo_objective + f" Integrates with {tok}."
        )
        with pytest.raises(BuilderBriefAuthorityError):
            _assert_within_authority(tampered, env, _SK)


def test_5_no_fake_metric() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    for claim in (
        "Responds in 12 minutes.",
        "Converts 30% of leads.",
        "Saves $5000 per month.",
    ):
        tampered = dataclasses.replace(
            brief, central_demo_story=brief.central_demo_story + " " + claim
        )
        with pytest.raises(BuilderBriefAuthorityError):
            _assert_within_authority(tampered, env, _SK)


def test_6_mock_actions_remain_mock() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    registered = {a for a, _ in _SK.mock_actions}
    for a in brief.mock_actions:
        assert a.action_type in registered
        assert a.marking == "SIMULATED / MOCK_ONLY / NOT_CONNECTED"
    from opintel_communication.builder_brief import MockActionSpec

    tampered = dataclasses.replace(
        brief, mock_actions=(*brief.mock_actions, MockActionSpec("SEND_REAL_EMAIL", "x"))
    )
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(tampered, env, _SK)


def test_7_required_disclosure_survives() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    env_slots = {d.slot_kind for d in env.required_disclosures}
    assert env_slots <= {d.slot_kind for d in brief.required_disclosures}
    md = render_builder_brief_markdown(brief)
    assert "not a system deployed, connected, official, or operated" in md
    dropped = dataclasses.replace(brief, required_disclosures=brief.required_disclosures[1:])
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(dropped, env, _SK)


def test_8_weak_evidence_downgrades_not_personalizes() -> None:
    # E+M: only generic labels -> GENERIC_CAPABILITY_DEMO, never BESPOKE.
    em = compile_builder_brief(envelope=em_envelope())
    assert em.demo_mode is DemoMode.GENERIC_CAPABILITY_DEMO
    assert "GENERIC" in em.central_demo_story
    assert "not built around" in em.central_demo_story.lower()
    # even thinner: drop the commercial fact -> NOT_DISTINCTIVE_ENOUGH
    thin = _drop_categories(em_envelope(), {"commercial_context"})
    tb = compile_builder_brief(envelope=thin)
    assert tb.demo_mode is DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH


def test_9_strongest_eligible_anchor_retained() -> None:
    brief = compile_builder_brief(envelope=aplus_envelope())
    assert brief.primary_demo_anchor is not None
    assert brief.primary_demo_anchor.category == "response_commitment"
    assert brief.primary_demo_anchor.anchor_rank == 0
    # elite: strongest is the availability signal
    eb = compile_builder_brief(envelope=elite_envelope())
    assert eb.primary_demo_anchor is not None
    assert eb.primary_demo_anchor.category == "service_availability"


def test_10_aplus_response_commitment_not_silently_dropped() -> None:
    env = aplus_envelope()
    assert any(f.category == "response_commitment" for f in env.eligible_company_facts)
    brief = compile_builder_brief(envelope=env)
    rc = [e for e in brief.licensed_public_evidence if e.category == "response_commitment"]
    assert len(rc) == 1
    assert rc[0].is_selectable_demo_option is False
    assert rc[0].strength == "PUBLISHED_SELF_CLAIM"
    assert "must not" in rc[0].usage_note.lower()
    assert brief.retained_context_not_selectable
    assert "published response-time claim" in brief.central_demo_story
    # dropping the category from the compiled brief fails closed
    kept = tuple(e for e in brief.licensed_public_evidence if e.category != "response_commitment")
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(
            dataclasses.replace(brief, licensed_public_evidence=kept), env, _SK
        )


def test_11_thin_evidence_cannot_produce_bespoke_claims() -> None:
    # every E+M-shaped thin envelope stays generic/thin, never bespoke, and its
    # prose never claims the demo is built around the business.
    for env in (em_envelope(), _drop_categories(em_envelope(), {"service_area_context"})):
        brief = compile_builder_brief(envelope=env)
        assert brief.demo_mode in (
            DemoMode.GENERIC_CAPABILITY_DEMO,
            DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH,
        )
        low = brief.central_demo_story.lower()
        assert "built around" not in low or "not built around" in low
        _assert_within_authority(brief, env, _SK)


# --------------------------------------------------------------------------
# option-label authority
# --------------------------------------------------------------------------


def test_option_labels_are_exact_fact_phrases_or_base_set() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    fact_labels = {f.sanitized_phrase for f in env.eligible_company_facts}
    base = {
        "repair",
        "maintenance",
        "replacement_quote",
        "unknown",
        "other",
        "north_texas",
        "central_texas",
        "gulf_coast",
    }
    for opt in (*brief.service_need_options, *brief.service_location_options):
        assert opt in fact_labels or opt in base
    # the response-commitment phrase is never an option
    rc_phrase = next(
        f.sanitized_phrase
        for f in env.eligible_company_facts
        if f.category == "response_commitment"
    )
    assert rc_phrase not in brief.service_need_options
    assert rc_phrase not in brief.service_location_options


def test_scaffolding_is_pinned() -> None:
    env = aplus_envelope()
    brief = compile_builder_brief(envelope=env)
    drift = dataclasses.replace(
        brief,
        ux_presentation_brief=brief.ux_presentation_brief + " Add fake metrics!",
    )
    with pytest.raises(BuilderBriefAuthorityError):
        _assert_within_authority(drift, env, _SK)
