"""``demo.builder_brief@2`` - the simplified three-screen builder experience.

Owner authorization 2026-09-03 "M4 HUMAN-EXPERIENCE SIMPLIFICATION / BUILDER-BRIEF
V2". The first builder brief (``demo.builder_brief@1``, still available and still
the audit-grade artifact) was accurate but commercially overcomplicated - it
exposed the internal state machine to the customer.

V2 keeps every M4 truth, evidence, UNKNOWN, safety, provenance, mock-action and
deterministic-workflow semantic UNDERNEATH (nothing in ``opintel_demo`` or the
authoritative envelope changes) and compiles a *presentation projection*: three
primary screens - Opportunity / Simulation input / Result-handoff - that a busy
HVAC owner can understand and experience in ~60 seconds without learning our
internal ontology.

    complex truthful M4  ->  simple human experience   (NOT a simplified truth model)

This module is a pure deterministic function of the same frozen inputs
(``SemanticEnvelope`` + the fixed M4 scenario skeleton). It builds on the V1
``BuilderBrief`` (so it inherits V1's fail-closed M4-authority check) and adds a
customer-experience authority check on top.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from opintel_demo import DemoScenarioSkeleton, demo_scenario_skeleton

from opintel_communication.builder_brief import (
    _RESPONSE_COMMITMENT,
    _SERVICE_AVAILABILITY,
    BuilderBrief,
    DemoMode,
    _assert_within_authority,
    _short_name,
    compile_builder_brief,
)
from opintel_communication.domain import SemanticEnvelope
from opintel_communication.hashing import sha256_text

BUILDER_EXPERIENCE_VERSION = "demo.builder_brief@2"

# --------------------------------------------------------------------------
# customer-facing translation tables (deterministic, semantics-preserving)
# --------------------------------------------------------------------------

# internal mock-action id -> customer-facing "prepare ..." label. Semantics are
# identical (a preview, never a real side effect); only the wording changes.
_MOCK_ACTION_LABEL: dict[str, str] = {
    "CREATE_INTAKE_RECORD": "Prepare intake record",
    "CREATE_CRM_LEAD": "Prepare lead for CRM",
    "QUEUE_HUMAN_CALLBACK": "Prepare callback task",
    "NOTIFY_DISPATCH": "Prepare dispatch notification",
    "REQUEST_SCHEDULING_REVIEW": "Prepare scheduling review",
    "CREATE_ACKNOWLEDGMENT_PREVIEW": "Prepare acknowledgment preview",
}

# internal M4 question id -> (customer label, control, is_optional)
_FIELD_META: dict[str, tuple[str, str, bool]] = {
    "service_need": ("Service need", "select", False),
    "facility_type": ("Facility", "select", False),
    "service_location": ("Service location", "select", False),
    "urgency": ("Urgency", "choice", False),
    "equipment_context": ("Equipment", "select", True),
    "contact_preference": ("Preferred follow-up", "choice", False),
}
_FACILITY_OPTIONS = ("Office", "Retail", "Warehouse", "Hospitality", "Other", "Unknown")
_URGENCY_OPTIONS = ("Routine", "Urgent", "Safety concern")
_EQUIPMENT_OPTIONS = ("Rooftop unit", "Split system", "Chiller", "Other", "Unknown")
_FOLLOW_UP_OPTIONS = ("Phone", "Email")

# roles compatible with the hypothetical M4 human-handoff / callback / dispatch
# steps. A fictional NAME only exists to make the handoff concrete; the ROLE is
# what matters, and every named placeholder is disclosed as fictional.
_HANDOFF_ROLE = "Intake coordinator"
_FICTIONAL_NAMES = ("Jordan", "Morgan", "Riley", "Avery", "Casey", "Quinn", "Sam", "Alex")

# tokens that must NEVER appear in any customer-facing string - the internal
# ontology the owner (section 9) wants hidden from normal users.
_ONTOLOGY_BLOCKLIST: tuple[str, ...] = (
    "mock_only",
    "not_connected",
    "qualification_result",
    "human_handoff",
    "simulation_notice",
    "scenario_start",
    "response_commitment",
    "service_availability",
    "current_process",
    "intake_surface",
    "commercial_context",
    "observed_public_text",
    "observed_availability_signal",
    "published_self_claim",
    "licensed_inference",
    "licensed_recommendation",
    "verified_fact",
    "faststrength",
    "factcategory",
    "demo.commercial_hvac",
    "demo.lead_response",
    "demo.scenario_skeleton",
    "demo.builder_brief",
    "create_intake_record",
    "create_crm_lead",
    "queue_human_callback",
    "notify_dispatch",
    "request_scheduling_review",
    "create_acknowledgment_preview",
    "{{",
    "}}",
)
_HEXISH = re.compile(r"\b[0-9a-f]{16,}\b")
_VERSIONISH = re.compile(r"\b[a-z_]+@\d+\b")
_ENUMISH = re.compile(r"\b[A-Z][A-Z_]{4,}\b")

_ACTION_VERB_BAD = re.compile(
    r"\b(sent|send|created|creates|dispatched|dispatch(?:es)?|booked|books|"
    r"updated|updates|submitted|submits|delivered|emailed|called)\b"
)


@dataclass(frozen=True, slots=True)
class FictionalPlaceholder:
    kind: str  # FICTIONAL_DEMO_PLACEHOLDER
    name: str
    role: str
    disclosure: str


@dataclass(frozen=True, slots=True)
class SimulationInputField:
    field_id: str  # internal M4 question id (audit only)
    label: str
    control: str  # select | choice
    options: tuple[str, ...]
    optional: bool
    internal_note: str  # semantic equivalence note (audit only)


@dataclass(frozen=True, slots=True)
class ResultLine:
    kind: str  # summary | checkmark | prepared_action
    text: str


@dataclass(frozen=True, slots=True)
class PreparedAction:
    internal_id: str  # audit only
    customer_label: str


@dataclass(frozen=True, slots=True)
class ExceptionScreen:
    trigger: str  # safety_critical | out_of_scope | mock_error
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class BuilderExperience:
    experience_version: str
    compiled_at: datetime
    demo_mode: DemoMode
    business_display_name: str
    short_name: str
    permitted_hostname: str
    identity_rule: str
    primary_demo_anchor: str  # category label, plain
    # --- Screen 1: Opportunity ---
    opportunity_summary: str  # 40-50 words, deterministic
    opportunity_primary_action: str
    known_public_context: tuple[str, ...]
    unknown_summary: str
    persistent_disclosure: str
    # --- Screen 2: Simulation input ---
    simulation_intake_title: str
    simulation_input_fields: tuple[SimulationInputField, ...]
    simulation_run_action: str
    # --- Screen 3: Result / handoff ---
    result_title: str
    simulation_result_model: tuple[ResultLine, ...]
    prepared_actions: tuple[PreparedAction, ...]
    fictional_placeholders: tuple[FictionalPlaceholder, ...]
    result_disclosure: str
    closing_thought: str
    # --- exceptions ---
    exception_states: tuple[ExceptionScreen, ...]
    # --- constraints for the builder ---
    builder_forbidden_additions: tuple[str, ...]
    ux_targets: tuple[str, ...]
    builder_freedom: str
    # --- audit ---
    underlying_brief_sha256: str
    audit_appendix: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# deterministic text generation
# --------------------------------------------------------------------------


def _plain_anchor_observation(brief: BuilderBrief) -> str:
    """Screen-1 sentence 1: 'what we noticed publicly' - short plain language, no
    ontology, no upgrade. Built from the primary anchor."""

    cats = {e.category for e in brief.licensed_public_evidence}
    core = "commercial HVAC repair" if "commercial_context" in cats else "commercial HVAC work"
    anchor = brief.primary_demo_anchor.category if brief.primary_demo_anchor else None

    if anchor == _RESPONSE_COMMITMENT:
        return f"Your public pages emphasize {core} and feature a published response-time message."
    if anchor == _SERVICE_AVAILABILITY:
        return f"Your public pages emphasize {core} and feature a published availability message."
    if "intake_surface" in cats:
        return f"Your public pages emphasize {core} and a public request path for service."
    return f"Your public pages emphasize {core}."


def _opportunity_summary(brief: BuilderBrief) -> str:
    if brief.demo_mode in (DemoMode.GENERIC_CAPABILITY_DEMO, DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH):
        s1 = "Your public pages show broad commercial-HVAC service labels only."
        s2 = (
            "We built a short simulation of a generic structured intake flow that prepares a "
            "commercial request for human follow-up - not built around your business."
        )
    else:
        s1 = _plain_anchor_observation(brief)
        s2 = (
            "We built a short simulation showing how a structured intake flow could prepare a "
            "commercial request for human follow-up."
        )
    s3 = "We don't know your current internal process, systems, staffing, or response performance."
    return f"{s1} {s2} {s3}"


def _known_public_context(brief: BuilderBrief) -> tuple[str, ...]:
    out: list[str] = []
    for e in brief.licensed_public_evidence:
        if e.generic_label and e.category not in (_RESPONSE_COMMITMENT, _SERVICE_AVAILABILITY):
            continue
        if e.category == "intake_surface":
            out.append(f'a public request path ("{e.phrase}")')
        elif e.category == "commercial_context":
            out.append(f'commercial air-conditioning repair work ("{e.phrase}")')
        elif e.category == _RESPONSE_COMMITMENT:
            out.append("a published response-time message on the public site")
        elif e.category == _SERVICE_AVAILABILITY:
            out.append("a published service-availability message on the public site")
        elif e.category == "service_area_context" and not e.generic_label:
            out.append(f'a service-area reference ("{e.phrase}")')
    return tuple(out)


def _unknown_summary() -> str:
    return (
        "We don't know how your team currently handles requests, what tools, CRM or "
        "scheduling systems you use, how you're staffed, or your actual response times - none "
        "of that is public, and this simulation does not assume any of it."
    )


def _fictional_placeholder(display_name: str) -> FictionalPlaceholder:
    idx = int(sha256_text(display_name)[:8], 16) % len(_FICTIONAL_NAMES)
    name = _FICTIONAL_NAMES[idx]
    return FictionalPlaceholder(
        kind="FICTIONAL_DEMO_PLACEHOLDER",
        name=name,
        role=_HANDOFF_ROLE,
        disclosure=(
            f"{name} is a fictional demo placeholder, not a real person. We don't know how "
            f"{_short_name(display_name)} assigns or handles requests internally - the role is "
            "illustrative only."
        ),
    )


def _simulation_input_fields(
    brief: BuilderBrief, sk: DemoScenarioSkeleton
) -> tuple[SimulationInputField, ...]:
    fields: list[SimulationInputField] = []
    for qid, _prompt, purpose in sk.base_questions:
        label, control, optional = _FIELD_META[qid]
        if qid == "service_need":
            options = brief.service_need_options
            note = f"M4 question '{qid}': {purpose} Options are the M4 evidence-derived labels."
        elif qid == "service_location":
            options = brief.service_location_options
            note = f"M4 question '{qid}': {purpose} Options are the M4 evidence-derived labels."
        elif qid == "facility_type":
            options = _FACILITY_OPTIONS
            note = f"M4 question '{qid}': {purpose}"
        elif qid == "urgency":
            options = _URGENCY_OPTIONS  # 'Safety concern' maps to M4 'safety_critical'
            note = (
                f"M4 question '{qid}': {purpose} 'Safety concern' == M4 'safety_critical' and "
                "routes to the safety exception."
            )
        elif qid == "equipment_context":
            options = _EQUIPMENT_OPTIONS
            note = f"M4 question '{qid}': {purpose} 'Unknown' is always acceptable."
        else:  # contact_preference
            options = _FOLLOW_UP_OPTIONS
            note = (
                f"M4 question '{qid}': {purpose} No real contact destination is collected - "
                "this only selects which preview channel the result shows."
            )
        fields.append(SimulationInputField(qid, label, control, tuple(options), optional, note))
    return tuple(fields)


def _result_model(brief: BuilderBrief) -> tuple[ResultLine, ...]:
    return (
        ResultLine(
            "summary",
            "A one-line recap of the simulated request: service need, facility, equipment, "
            "urgency, and preferred follow-up channel - filled from the form the owner just "
            "completed.",
        ),
        ResultLine("checkmark", "Request details organized"),
        ResultLine("checkmark", "Urgency captured"),
        ResultLine("checkmark", "Preferred follow-up captured"),
        ResultLine("checkmark", "Human review required before anything happens"),
    )


def _prepared_actions(sk: DemoScenarioSkeleton) -> tuple[PreparedAction, ...]:
    return tuple(
        PreparedAction(internal_id, _MOCK_ACTION_LABEL[internal_id])
        for internal_id, _ in sk.mock_actions
    )


def _exception_screens(sk: DemoScenarioSkeleton) -> tuple[ExceptionScreen, ...]:
    return (
        ExceptionScreen(
            "safety_critical",
            "Safety review required",
            "This simulation can't evaluate safety-critical situations. A real implementation "
            "would hand this straight to an approved human process. Nothing has been "
            "dispatched, and this screen gives no emergency advice.",
        ),
        ExceptionScreen(
            "out_of_scope",
            "Outside this simulation",
            "This simulation doesn't cover that kind of request. In a real setup a person "
            "would take it from here. Nothing was sent or scheduled.",
        ),
        ExceptionScreen(
            "mock_error",
            "Simulation hiccup",
            "The simulation couldn't finish this step. Nothing real happened - you can start over.",
        ),
    )


def _persistent_disclosure(short: str) -> str:
    return f"Simulation · not connected to {short}"


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------


def compile_builder_experience(
    *,
    envelope: SemanticEnvelope,
    skeleton: DemoScenarioSkeleton | None = None,
    now: datetime | None = None,
) -> BuilderExperience:
    sk = skeleton or demo_scenario_skeleton()
    brief = compile_builder_brief(envelope=envelope, skeleton=sk, now=now)
    short = _short_name(brief.business_display_name)
    anchor = (
        brief.primary_demo_anchor.category.replace("_", " ")
        if brief.primary_demo_anchor
        else "commercial intake context"
    )

    placeholder = _fictional_placeholder(brief.business_display_name)

    exp = BuilderExperience(
        experience_version=BUILDER_EXPERIENCE_VERSION,
        compiled_at=brief.compiled_at,
        demo_mode=brief.demo_mode,
        business_display_name=brief.business_display_name,
        short_name=short,
        permitted_hostname=brief.permitted_hostname,
        identity_rule=brief.identity_rule,
        primary_demo_anchor=anchor,
        opportunity_summary=_opportunity_summary(brief),
        opportunity_primary_action="See the simulation",
        known_public_context=_known_public_context(brief),
        unknown_summary=_unknown_summary(),
        persistent_disclosure=_persistent_disclosure(short),
        simulation_intake_title="Simulate a commercial request",
        simulation_input_fields=_simulation_input_fields(brief, sk),
        simulation_run_action="Run simulation",
        result_title="Request prepared for human review",
        simulation_result_model=_result_model(brief),
        prepared_actions=_prepared_actions(sk),
        fictional_placeholders=(placeholder,),
        result_disclosure=(
            "Nothing was sent, booked, dispatched, or updated. This was a hypothetical simulation."
        ),
        closing_thought=(
            "Imagine this fitted to your actual intake process rather than this hypothetical one."
        ),
        exception_states=_exception_screens(sk),
        builder_forbidden_additions=brief.forbidden_additions,
        ux_targets=(
            "Whole flow under ~60 seconds with no instructions.",
            "Opportunity ~10s, simulation input ~20-30s, result ~10-20s.",
            "Progressive disclosure: simple first; internal detail only on request.",
        ),
        builder_freedom=(
            "Free: visual hierarchy, typography, colour, spacing, animation, transitions, "
            "icons, cards, responsive design, polish. Constrained: factual copy, business "
            "claims, workflow meaning, result semantics, placeholder semantics, integration "
            "state, metrics/data - use only the wording this brief supplies."
        ),
        underlying_brief_sha256=_brief_sha(brief),
        audit_appendix=(
            *brief.audit_appendix,
            ("experience_compiler_version", BUILDER_EXPERIENCE_VERSION),
        ),
    )
    _assert_experience_within_authority(exp, brief, envelope, sk)
    return exp


def _brief_sha(brief: BuilderBrief) -> str:
    import dataclasses

    return sha256_text(repr(sorted(dataclasses.asdict(brief).items(), key=lambda kv: kv[0])))


# --------------------------------------------------------------------------
# fail-closed customer-experience authority check
# --------------------------------------------------------------------------


class BuilderExperienceAuthorityError(Exception):
    """The compiled experience exposes internal ontology, an unresolved token, an
    undisclosed fictional name, or a claim outside the M4 authority bundle."""


def _customer_facing_strings(exp: BuilderExperience) -> list[str]:
    out = [
        exp.opportunity_summary,
        exp.opportunity_primary_action,
        exp.unknown_summary,
        exp.persistent_disclosure,
        exp.simulation_intake_title,
        exp.simulation_run_action,
        exp.result_title,
        exp.result_disclosure,
        exp.closing_thought,
        exp.primary_demo_anchor,
        *exp.known_public_context,
        *(f.label for f in exp.simulation_input_fields),
        *(o for f in exp.simulation_input_fields for o in f.options),
        *(line.text for line in exp.simulation_result_model),
        *(a.customer_label for a in exp.prepared_actions),
        *(p.name for p in exp.fictional_placeholders),
        *(p.role for p in exp.fictional_placeholders),
        *(p.disclosure for p in exp.fictional_placeholders),
        *(s.title for s in exp.exception_states),
        *(s.body for s in exp.exception_states),
    ]
    return [s for s in out if s]


def _assert_experience_within_authority(
    exp: BuilderExperience,
    brief: BuilderBrief,
    envelope: SemanticEnvelope,
    sk: DemoScenarioSkeleton,
) -> None:
    def fail(msg: str) -> None:
        raise BuilderExperienceAuthorityError(msg)

    # 0. the underlying V1 brief must still pass the full M4-authority check.
    _assert_within_authority(brief, envelope, sk)

    strings = _customer_facing_strings(exp)
    joined = " \n ".join(strings).lower()

    # 1. opportunity summary: 30-50 words, and carries the three required ideas.
    words = exp.opportunity_summary.split()
    if not 30 <= len(words) <= 50:
        fail(f"opportunity summary is {len(words)} words (must be 30-50)")
    low = exp.opportunity_summary.lower()
    if not any(t in low for t in ("public pages", "public site", "your site", "public")):
        fail("opportunity summary does not state what was noticed publicly")
    if "simulation" not in low:
        fail("opportunity summary does not state what the simulation proposes")
    if not any(t in low for t in ("don't know", "do not know", "not public", "unknown")):
        fail("opportunity summary does not state what is unknown")

    # 2. no unresolved template token or internal ontology anywhere customer-facing.
    for s in strings:
        sl = s.lower()
        for tok in _ONTOLOGY_BLOCKLIST:
            if tok in sl:
                fail(f"customer-facing string exposes internal ontology {tok!r}: {s!r}")
        if _HEXISH.search(s) or _VERSIONISH.search(s) or _ENUMISH.search(s):
            fail(f"customer-facing string exposes an id/version/enum: {s!r}")

    # 3. fictional placeholders: always named + roled + disclosed as fictional,
    #    never asserting employment at the business.
    for p in exp.fictional_placeholders:
        if not p.name or not p.role:
            fail("fictional placeholder missing name or role")
        d = p.disclosure.lower()
        if "fictional" not in d or "not a real person" not in d:
            fail("fictional placeholder disclosure does not mark it fictional")
        bad = (
            f"{p.name.lower()} works",
            f"{p.name.lower()} is a {exp.short_name.lower()}",
            f"{p.name.lower()} at {exp.short_name.lower()}",
            "employee",
            "on staff",
        )
        if any(b in d for b in bad):
            fail("fictional placeholder disclosure implies real employment")
    # result copy must not read "sent to <name>" style
    for line in exp.simulation_result_model:
        for p in exp.fictional_placeholders:
            if re.search(
                rf"\b(sent|assigned|routed|forwarded)\s+to\s+{re.escape(p.name)}\b", line.text, re.I
            ):
                fail("result implies a real action to the fictional person")

    # 4. prepared actions: registered id, deterministic label, safe verb.
    registered = {a for a, _ in sk.mock_actions}
    for a in exp.prepared_actions:
        if a.internal_id not in registered:
            fail(f"prepared action references an unregistered mock action: {a.internal_id}")
        if a.customer_label != _MOCK_ACTION_LABEL[a.internal_id]:
            fail(f"prepared action label diverged from the fixed mapping: {a.internal_id}")
        cl = a.customer_label.lower()
        if not any(cl.startswith(v) for v in ("prepare", "preview", "simulate")):
            fail(f"prepared action label uses a non-simulated verb: {a.customer_label!r}")
    if {a.internal_id for a in exp.prepared_actions} != registered:
        fail("prepared actions are not the exact registered mock-action set")

    # 5. result / exception copy: never claims a real action occurred. A bad
    #    verb is only allowed inside an explicitly-negated / simulated sentence.
    result_sentences = re.split(
        r"(?<=[.!?])\s+",
        " ".join(
            [line.text for line in exp.simulation_result_model]
            + [exp.result_disclosure, exp.closing_thought]
            + [s.body for s in exp.exception_states]
        ),
    )
    for sent in result_sentences:
        sl = sent.lower()
        if _ACTION_VERB_BAD.search(sl) and not any(
            g in sl
            for g in (
                "nothing was",
                "nothing has",
                "no ",
                "not ",
                "simulat",
                "prepared",
                "hypothetical",
            )
        ):
            fail(f"result/exception copy implies a real action: {sent!r}")

    # 6. form options never include a response-commitment / availability phrase.
    non_selectable = {
        f.sanitized_phrase.strip().lower()
        for f in envelope.eligible_company_facts
        if f.category in (_RESPONSE_COMMITMENT, _SERVICE_AVAILABILITY)
    }
    for fld in exp.simulation_input_fields:
        for o in fld.options:
            if o.strip().lower() in non_selectable:
                fail(f"a non-selectable evidence phrase is a form option: {o!r}")

    # 7. service-need / service-location options match the V1 brief exactly.
    by_id = {f.field_id: f.options for f in exp.simulation_input_fields}
    if by_id.get("service_need") != tuple(brief.service_need_options):
        fail("service_need options diverged from the M4 brief")
    if by_id.get("service_location") != tuple(brief.service_location_options):
        fail("service_location options diverged from the M4 brief")

    # 8. availability never rendered as response behaviour in an AFFIRMATIVE
    #    customer sentence (the UNKNOWN disclaimer legitimately says "response").
    if _SERVICE_AVAILABILITY in {f.category for f in envelope.eligible_company_facts}:
        blob = " ".join((exp.opportunity_summary, *exp.known_public_context))
        for sent in re.split(r"(?<=[.!?])\s+", blob):
            sl = sent.lower()
            if any(g in sl for g in ("don't know", "do not know", "unknown", "not public")):
                continue
            if "availab" in sl and any(
                w in sl for w in ("respond", "response", "acknowledg", "callback", "reply")
            ):
                fail("availability rendered with response wording in customer copy")

    # 9. RESPONSE_PERFORMANCE is UNKNOWN -> no speed/performance assertion.
    if any(u.component == "RESPONSE_PERFORMANCE" for u in envelope.explicit_unknowns):
        speed = re.compile(
            r"\b(fast(?:er)?|quick(?:ly)?|slow(?:ly)?|prompt(?:ly)?|immediate(?:ly)?|minutes?|"
            r"hours?|same[- ]day|on[- ]time|within \d)\b"
        )
        resp = re.compile(
            r"\b(responds?|answers?|acknowledges?|call(?:s|ed)? back|repl(?:y|ies))\b"
        )
        for s in strings:
            sl = s.lower()
            if "message" in sl or "unknown" in sl or "don't know" in sl or "not public" in sl:
                continue
            if resp.search(sl) and speed.search(sl):
                fail(f"customer copy asserts response speed (UNKNOWN): {s!r}")

    # 10. exception screens present for all three branches.
    if {s.trigger for s in exp.exception_states} != {
        "safety_critical",
        "out_of_scope",
        "mock_error",
    }:
        fail("exception screens do not cover safety / out-of-scope / mock-error")
    safety = next(s for s in exp.exception_states if s.trigger == "safety_critical")
    if "dispatched" not in safety.body.lower() or "human" not in safety.body.lower():
        fail("safety exception lost its non-dispatch / human-process meaning")
    if re.search(r"\b\d{3}[- ]?\d{3,4}\b|call \d", safety.body):
        fail("safety exception fabricates a phone number")

    # 11. thin / generic evidence must not manufacture bespoke relevance.
    if exp.demo_mode in (DemoMode.GENERIC_CAPABILITY_DEMO, DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH):
        osl = exp.opportunity_summary.lower()
        if "generic" not in osl:
            fail("generic/thin evidence did not say so in the opportunity summary")
        if "built around your" in osl and "not built around your" not in osl:
            fail("generic/thin evidence manufactured a bespoke claim")

    # 12. persistent + result disclosures preserve the substantive meaning.
    if "not connected" not in exp.persistent_disclosure.lower():
        fail("persistent disclosure lost 'not connected'")
    if "nothing was sent" not in exp.result_disclosure.lower():
        fail("result disclosure lost 'nothing was sent'")

    _ = joined


# --------------------------------------------------------------------------
# human-readable renderer: BuilderExperience -> paste-into-Lovable/Base44 prompt
# --------------------------------------------------------------------------


def render_builder_experience_markdown(exp: BuilderExperience) -> str:
    """A short product brief a non-technical person can paste into Lovable,
    Base44, or another builder. Three screens, ~60-second experience, internal
    ontology hidden. Provenance is a trailing appendix only."""

    e = exp
    lines: list[str] = []
    add = lines.append

    add(f"# {e.business_display_name} — commercial intake demo")
    add("")
    add(f"_Persistent indicator (show on every screen):_ **{e.persistent_disclosure}**")
    add("")
    add(
        "> Build a **3-screen** interactive demo a busy HVAC owner can get through in about "
        "60 seconds with no instructions. You have full freedom over visual design; you have "
        "**no** freedom over the wording of any claim, label, disclosure, workflow step or "
        "result. Use only the copy in this brief for those. "
        f"{e.builder_freedom}"
    )
    add("")
    add(f"**Demo mode:** `{e.demo_mode.value}` · **story anchor:** {e.primary_demo_anchor}")
    add("")

    add("## Screen 1 — Opportunity")
    add("")
    add(f"> {e.opportunity_summary}")
    add("")
    if e.known_public_context:
        add("_What we actually saw on the public site (optional detail, progressive disclosure):_")
        for c in e.known_public_context:
            add(f"- {c}")
        add("")
    add(f"_What we don't know:_ {e.unknown_summary}")
    add("")
    add(f"**Primary action:** `{e.opportunity_primary_action}`")
    add("")

    add("## Screen 2 — Simulate a commercial request")
    add("")
    add(
        f"One page. Title: **{e.simulation_intake_title}**. Collapse everything below into a "
        "single coherent form — no multi-step wizard."
    )
    add("")
    add("| field | control | options | required |")
    add("|---|---|---|---|")
    for f in e.simulation_input_fields:
        opts = " / ".join(f.options)
        add(f"| {f.label} | {f.control} | {opts} | {'no' if f.optional else 'yes'} |")
    add("")
    add(f"**Submit action:** `{e.simulation_run_action}`")
    add("")
    add(
        "_Never_ collect a real phone number, email, address, customer name or staff name. "
        "'Preferred follow-up' only picks which preview channel the result shows."
    )
    add("")

    add("## Screen 3 — Result / human handoff")
    add("")
    add(f"Title: **{e.result_title}**")
    add("")
    for line in e.simulation_result_model:
        if line.kind == "summary":
            add(f"- _{line.text}_")
        elif line.kind == "checkmark":
            add(f"- ✓ {line.text}")
        else:
            add(f"- {line.text}")
    add("")
    add("**Example human handoff** (fictional, illustrative):")
    add("")
    for p in e.fictional_placeholders:
        add(f"> **{p.name}**  ")
        add(f"> {p.role}\\*")
        add(">")
        add(f"> \\* {p.disclosure}")
    add("")
    add("**Prepared previews** (all simulated — nothing runs):")
    for a in e.prepared_actions:
        add(f"- {a.customer_label}")
    add("")
    add(f"_Result footer:_ {e.result_disclosure}")
    add("")
    add(f"_Closing line:_ {e.closing_thought}")
    add("")

    add("## Exception screens (only when triggered)")
    add("")
    for s in e.exception_states:
        add(f"### {s.title}  `[{s.trigger}]`")
        add(s.body)
        add("")

    add("## DO NOT ADD")
    add("")
    for item in e.builder_forbidden_additions:
        add(f"- {item}")
    add("")

    add("## Timing target")
    for t in e.ux_targets:
        add(f"- {t}")
    add("")

    add("---")
    add("")
    add("## Appendix — provenance (not for the rendered UI)")
    add("")
    add("| key | value |")
    add("|---|---|")
    for k, v in e.audit_appendix:
        add(f"| {k} | `{v}` |")
    add(f"| underlying_brief_sha256 | `{e.underlying_brief_sha256}` |")
    add(f"| compiled_at | {e.compiled_at.isoformat()} |")
    add("")
    add(
        "Internal M4 identifiers (audit only — do not surface to users): "
        + ", ".join(f'`{a.internal_id}`→"{a.customer_label}"' for a in e.prepared_actions)
    )
    add("")
    return "\n".join(lines)
