"""``demo.builder_brief@3`` - the opportunity-story builder projection.

Owner authorization 2026-09-03 "M4 BUILDER-BRIEF V3: OPPORTUNITY -> EXPERIENCE ->
HANDOFF". V2 (``demo.builder_brief@2``) already collapsed the internal state
machine into a three-screen human experience. V3 is a further *presentation*
projection - it changes nothing about M4 authority, the V1 brief, or the V2
experience semantics - and reframes the same three screens as a short opportunity
story:

    1. We noticed this        (Screen 1 - opportunity is the hero)
    2. Here is how it could work   (Screen 2 - one calm intake page)
    3. Here is what your team could receive   (Screen 3 - a workflow story)
    4. Imagine it fitted to your real process   (the closing bridge)

Externally V3 optimises for comprehension + relevance + desire while M4 keeps
optimising internally for truth + safety + provenance.

V3 is a pure deterministic function of the same frozen inputs. It builds on the
V2 ``BuilderExperience`` (so it inherits V1's *and* V2's fail-closed checks) and
adds a story-level authority check on top. Three things V3 does that V2 did not:

* the customer never sees an internal demo-mode badge or taxonomy word;
* public evidence justifies that a form *field* exists, but the selectable
  *values* are explicitly synthetic demo inputs - an evidence phrase is never
  offered as a pick (this retires the V2 "known tension");
* the six internal mock actions are grouped into three understandable
  customer-facing outcomes (all six are still preserved verbatim underneath).
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import datetime

from opintel_demo import DemoScenarioSkeleton, demo_scenario_skeleton

from opintel_communication.builder_brief import (
    _INTAKE_SURFACE,
    _RESPONSE_COMMITMENT,
    _SERVICE_AVAILABILITY,
    BuilderBrief,
    DemoMode,
    _licensed_phrase_text,
    compile_builder_brief,
)
from opintel_communication.builder_experience import (
    _ACTION_VERB_BAD,
    _ENUMISH,
    _FACILITY_OPTIONS,
    _FIELD_META,
    _FOLLOW_UP_OPTIONS,
    _HEXISH,
    _ONTOLOGY_BLOCKLIST,
    _URGENCY_OPTIONS,
    _VERSIONISH,
    BuilderExperience,
    ExceptionScreen,
    FictionalPlaceholder,
    _assert_experience_within_authority,
    compile_builder_experience,
)
from opintel_communication.domain import SemanticEnvelope
from opintel_communication.hashing import sha256_text

BUILDER_STORY_VERSION = "demo.builder_brief@3"

# --------------------------------------------------------------------------
# artifact semantics (section 15) - machine distinctions, never enum names in UI
# --------------------------------------------------------------------------

SEM_PUBLIC_EVIDENCE = "PUBLIC_EVIDENCE"
SEM_UNKNOWN = "UNKNOWN"
SEM_SYNTHETIC_DEMO_INPUT = "SYNTHETIC_DEMO_INPUT"
SEM_FICTIONAL_DEMO_PLACEHOLDER = "FICTIONAL_DEMO_PLACEHOLDER"
SEM_SIMULATED_OUTPUT = "SIMULATED_OUTPUT"

_SEMANTICS_LEGEND: tuple[tuple[str, str], ...] = (
    (
        "Public evidence",
        "Something we actually saw on the public website. Shown as an observation and never "
        "strengthened into a promise.",
    ),
    (
        "Unknown",
        "Something we cannot know from public pages - your process, tools, staffing or response "
        "times. Never stated or implied.",
    ),
    (
        "Synthetic demo input",
        "An illustrative choice inside the simulation. Not a fact about your business and not "
        "something you told us.",
    ),
    (
        "Fictional demo placeholder",
        "An example person or role, invented to make the workflow concrete. Not real and not "
        "your staff.",
    ),
    (
        "Simulated output",
        "Something the simulation prepared as a preview. Nothing was sent, booked, dispatched, "
        "or updated.",
    ),
)

# --------------------------------------------------------------------------
# synthetic simulation values (section 6) - clearly illustrative, never evidence
# --------------------------------------------------------------------------

_SYNTHETIC_NEED: tuple[str, ...] = (
    "Repair request",
    "Maintenance visit",
    "Replacement or quote",
    "Other",
    "Not sure",
)
_SYNTHETIC_LOCATION: tuple[str, ...] = ("Example service location", "Other", "Not sure")

# --------------------------------------------------------------------------
# grouped customer-facing outcomes (section 9) - all six mock actions preserved
# --------------------------------------------------------------------------

_OUTCOME_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Lead record",
        "Request details ready for the system your team uses.",
        ("CREATE_INTAKE_RECORD", "CREATE_CRM_LEAD"),
    ),
    (
        "Human follow-up",
        "A review or callback task ready for the appropriate person.",
        ("QUEUE_HUMAN_CALLBACK", "NOTIFY_DISPATCH", "CREATE_ACKNOWLEDGMENT_PREVIEW"),
    ),
    (
        "Scheduling context",
        "Relevant information ready if scheduling is appropriate.",
        ("REQUEST_SCHEDULING_REVIEW",),
    ),
)

# --------------------------------------------------------------------------
# visual guidance (section 13/14) - qualities, not one builder's implementation
# --------------------------------------------------------------------------

_VISUAL_GUIDANCE: tuple[str, ...] = (
    "Strong product presence: deliberate typography, clearly visible selected states, a "
    "coherent visual result story, an overall polished software feel.",
    "Opportunity framing first: lead with the opportunity, keep a calm hierarchy, keep "
    "cognitive load low.",
    "Radical simplicity: obvious navigation and one obvious primary action per screen, easy "
    "scanning, nothing on screen that does not earn its place.",
    "Synthesis target: premium polish, opportunity-first framing and radical simplicity "
    "together - not one at the expense of the others.",
)

_COMPANY_VISUAL_CHARACTER = (
    "No brand assets are authorized for this task. Use a premium, neutral, commercial-software "
    "presentation - restrained palette, professional typography, generous spacing. No logos, "
    "no reproduced branding, nothing implying the demo is official or affiliated."
)

# --------------------------------------------------------------------------
# detectors
# --------------------------------------------------------------------------

_STRENGTHEN = re.compile(
    r"\b(fast(?:er|est)?|quick(?:er|est|ly)?|rapid(?:ly)?|immediate(?:ly)?|instant(?:ly)?|"
    r"prompt(?:ly)?|best|leading|guarantee[ds]?|guaranteed|always|unbeatable|top|fastest|"
    r"same[- ]day|24/7|24-hour|round[- ]the[- ]clock)\b",
    re.IGNORECASE,
)
_SPEED = re.compile(
    r"\b(fast(?:er)?|quick(?:ly)?|slow(?:ly)?|prompt(?:ly)?|immediate(?:ly)?|minutes?|hours?|"
    r"seconds?|same[- ]day|on[- ]time|within \d)\b",
    re.IGNORECASE,
)
_RESP = re.compile(
    r"\b(responds?|responded|answers?|answered|acknowledges?|acknowledged|call(?:s|ed)? back|"
    r"callbacks?|repl(?:y|ies|ied))\b",
    re.IGNORECASE,
)
_V3_VENDORS: tuple[str, ...] = (
    "servicetitan",
    "housecall",
    "housecallpro",
    "jobber",
    "salesforce",
    "hubspot",
    "zoho",
    "connectwise",
    "fieldedge",
    "servicefusion",
)
_V3_FORBIDDEN: frozenset[str] = frozenset(
    {
        "roi",
        "revenue",
        "profit",
        "conversion",
        "savings",
        "dollars",
        "percent",
        "percentage",
        "slow",
        "slowly",
        "fast",
        "faster",
        "quick",
        "quickly",
        "delay",
        "delayed",
        "missed",
        "missing",
        "losing",
        "unanswered",
        "understaffed",
        "overwhelmed",
        "backlog",
        "manual",
        "automate",
        "automated",
        "automation",
        "testimonial",
        "rating",
        "endorsement",
        "deployed",
        "dashboard",
        "analytics",
        "kpi",
        "crm",
    }
)
_GEO_BLOCKLIST: tuple[str, ...] = ("austin", "dallas", "houston")
_WORDISH = re.compile(r"[a-z][a-z'/-]+")


# --------------------------------------------------------------------------
# dataclasses
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StoryEvidenceItem:
    text: str
    semantics: str  # PUBLIC_EVIDENCE


@dataclass(frozen=True, slots=True)
class StoryInputField:
    field_id: str  # internal M4 question id (audit only)
    label: str
    control: str  # select | choice
    values: tuple[str, ...]  # SYNTHETIC_DEMO_INPUT values
    value_semantics: str  # SYNTHETIC_DEMO_INPUT
    optional: bool
    exists_because: str  # the EVIDENCE_CONTEXT that justifies the field existing
    m4_option_labels: tuple[str, ...]  # audit: labels M4 composition would derive
    internal_note: str  # audit only


@dataclass(frozen=True, slots=True)
class ResultStoryStage:
    order: int  # 1..4
    label: str
    line: str
    semantics: str


@dataclass(frozen=True, slots=True)
class CustomerOutcomeGroup:
    name: str
    description: str
    internal_action_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuilderStory:
    story_version: str
    compiled_at: datetime
    business_display_name: str
    short_name: str
    permitted_hostname: str
    identity_rule: str
    primary_demo_anchor: str  # plain-language category label
    # --- Screen 1: opportunity is the hero ---
    opportunity_headline: str
    opportunity_summary: str  # 40-50 words, inherited from V2, already validated
    opportunity_primary_action: str
    evidence_detail_label: str
    evidence_detail: tuple[StoryEvidenceItem, ...]  # collapsed by default
    unknown_summary: str
    persistent_disclosure: str
    # --- Screen 2: one calm intake page ---
    simulation_intake_title: str
    simulation_input_schema: tuple[StoryInputField, ...]
    synthetic_input_values: tuple[str, ...]
    simulation_run_action: str
    # --- Screen 3: the workflow story ---
    result_title: str
    result_story: tuple[ResultStoryStage, ...]
    human_handoff_preview: FictionalPlaceholder
    customer_facing_outcomes: tuple[CustomerOutcomeGroup, ...]
    internal_mock_actions: tuple[tuple[str, str], ...]  # audit: all six preserved
    result_disclosure: str
    closing_bridge: str
    # --- exceptions + builder constraints ---
    exception_states: tuple[ExceptionScreen, ...]
    builder_forbidden_additions: tuple[str, ...]
    builder_visual_guidance: tuple[str, ...]
    company_visual_character: str
    semantics_legend: tuple[tuple[str, str], ...]
    ux_targets: tuple[str, ...]
    builder_freedom: str
    # --- audit ---
    underlying_experience_sha256: str
    underlying_brief_sha256: str
    audit_appendix: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# deterministic text generation
# --------------------------------------------------------------------------


def _opportunity_headline(anchor_category: str | None, mode: DemoMode) -> str:
    """Screen-1 hero line. Frames a *possibility* (always "could"), makes the
    primary evidence anchor visible, and never strengthens the public claim."""

    if mode in (DemoMode.GENERIC_CAPABILITY_DEMO, DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH):
        return (
            "One way a generic structured intake flow could organize incoming commercial "
            "HVAC requests"
        )
    if anchor_category == _RESPONSE_COMMITMENT:
        return (
            "One way structured intake could support the response experience your public "
            "pages already describe"
        )
    if anchor_category == _SERVICE_AVAILABILITY:
        return (
            "One way structured intake could complement the service availability your public "
            "pages already describe"
        )
    if anchor_category == _INTAKE_SURFACE:
        return (
            "One way a structured intake flow could sit behind the request path your public "
            "pages already offer"
        )
    return (
        "One way structured intake could organize the commercial requests your public pages invite"
    )


def _synthetic_input_schema(
    brief_need: tuple[str, ...],
    brief_location: tuple[str, ...],
    sk: DemoScenarioSkeleton,
    has_commercial: bool,
    has_area: bool,
) -> tuple[StoryInputField, ...]:
    fields: list[StoryInputField] = []
    for qid, _prompt, purpose in sk.base_questions:
        label, control, optional = _FIELD_META[qid]
        m4_labels: tuple[str, ...] = ()
        if qid == "service_need":
            values = _SYNTHETIC_NEED
            m4_labels = brief_need
            exists = (
                "Your public pages describe commercial HVAC work, so the simulation asks which "
                "need applies."
                if has_commercial
                else "Generic commercial HVAC scenario - the simulation asks which need applies."
            )
            note = (
                f"M4 question '{qid}': {purpose} Values are synthetic demo inputs; M4 would "
                "instead derive option labels from the public evidence (recorded in "
                "m4_option_labels for audit)."
            )
        elif qid == "service_location":
            values = _SYNTHETIC_LOCATION
            m4_labels = brief_location
            exists = (
                "Your public pages reference a service area, so the simulation asks about "
                "location - without making any coverage promise."
                if has_area
                else "Location is routed to human validation; the simulation makes no "
                "service-area promise."
            )
            note = (
                f"M4 question '{qid}': {purpose} Values are synthetic demo inputs; the real "
                "location is unknown, so a clearly-illustrative placeholder is used."
            )
        elif qid == "facility_type":
            values = _FACILITY_OPTIONS
            exists = "Bounded commercial facility context for the scenario."
            note = f"M4 question '{qid}': {purpose}"
        elif qid == "urgency":
            values = _URGENCY_OPTIONS
            exists = "The simulation demonstrates a fixed safety handoff."
            note = (
                f"M4 question '{qid}': {purpose} 'Safety concern' == M4 'safety_critical' and "
                "routes to the safety exception."
            )
        elif qid == "equipment_context":
            values = ("Rooftop unit", "Split system", "Chiller", "Other", "Not sure")
            exists = "Keeps equipment detail optional and never assumed."
            note = f"M4 question '{qid}': {purpose} 'Not sure' is always acceptable."
        else:  # contact_preference
            values = _FOLLOW_UP_OPTIONS
            exists = (
                "Chooses which preview channel the result shows; no real destination is collected."
            )
            note = (
                f"M4 question '{qid}': {purpose} No real contact destination is collected - this "
                "only selects which preview channel the result shows."
            )
        fields.append(
            StoryInputField(
                field_id=qid,
                label=label,
                control=control,
                values=tuple(values),
                value_semantics=SEM_SYNTHETIC_DEMO_INPUT,
                optional=optional,
                exists_because=exists,
                m4_option_labels=m4_labels,
                internal_note=note,
            )
        )
    return tuple(fields)


def _customer_facing_outcomes() -> tuple[CustomerOutcomeGroup, ...]:
    return tuple(
        CustomerOutcomeGroup(name=n, description=d, internal_action_ids=ids)
        for n, d, ids in _OUTCOME_GROUPS
    )


def _result_story(role: str) -> tuple[ResultStoryStage, ...]:
    return (
        ResultStoryStage(
            1,
            "Request",
            "A commercial request comes in through the simulated intake form.",
            SEM_SIMULATED_OUTPUT,
        ),
        ResultStoryStage(
            2,
            "Structured context",
            "The simulation organizes it into clear, consistent fields.",
            SEM_SIMULATED_OUTPUT,
        ),
        ResultStoryStage(
            3,
            "Example human review",
            f"An example {role.lower()} reviews the structured request before anything happens.",
            SEM_FICTIONAL_DEMO_PLACEHOLDER,
        ),
        ResultStoryStage(
            4,
            "Next workflow preparation",
            "The simulation prepares what the next step could hand to your team.",
            SEM_SIMULATED_OUTPUT,
        ),
    )


def _experience_sha(exp: BuilderExperience) -> str:
    return sha256_text(repr(sorted(dataclasses.asdict(exp).items(), key=lambda kv: kv[0])))


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------


def compile_builder_story(
    *,
    envelope: SemanticEnvelope,
    skeleton: DemoScenarioSkeleton | None = None,
    now: datetime | None = None,
) -> BuilderStory:
    sk = skeleton or demo_scenario_skeleton()
    brief = compile_builder_brief(envelope=envelope, skeleton=sk, now=now)
    exp = compile_builder_experience(envelope=envelope, skeleton=sk, now=now)

    anchor_category = brief.primary_demo_anchor.category if brief.primary_demo_anchor else None
    env_categories = {f.category for f in envelope.eligible_company_facts}
    has_commercial = "commercial_context" in env_categories
    has_area = "service_area_context" in env_categories

    fields = _synthetic_input_schema(
        tuple(brief.service_need_options),
        tuple(brief.service_location_options),
        sk,
        has_commercial,
        has_area,
    )
    synthetic_values = tuple(dict.fromkeys(v for f in fields for v in f.values))
    placeholder = exp.fictional_placeholders[0]

    story = BuilderStory(
        story_version=BUILDER_STORY_VERSION,
        compiled_at=exp.compiled_at,
        business_display_name=exp.business_display_name,
        short_name=exp.short_name,
        permitted_hostname=exp.permitted_hostname,
        identity_rule=exp.identity_rule,
        primary_demo_anchor=exp.primary_demo_anchor,
        opportunity_headline=_opportunity_headline(anchor_category, brief.demo_mode),
        opportunity_summary=exp.opportunity_summary,
        opportunity_primary_action="See how it could work",
        evidence_detail_label="Why we built this",
        evidence_detail=tuple(
            StoryEvidenceItem(text=c, semantics=SEM_PUBLIC_EVIDENCE)
            for c in exp.known_public_context
        ),
        unknown_summary=exp.unknown_summary,
        persistent_disclosure=exp.persistent_disclosure,
        simulation_intake_title=exp.simulation_intake_title,
        simulation_input_schema=fields,
        synthetic_input_values=synthetic_values,
        simulation_run_action=exp.simulation_run_action,
        result_title="A commercial request is ready for human review",
        result_story=_result_story(placeholder.role),
        human_handoff_preview=placeholder,
        customer_facing_outcomes=_customer_facing_outcomes(),
        internal_mock_actions=tuple(sk.mock_actions),
        result_disclosure=exp.result_disclosure,
        closing_bridge=exp.closing_thought,
        exception_states=exp.exception_states,
        builder_forbidden_additions=exp.builder_forbidden_additions,
        builder_visual_guidance=_VISUAL_GUIDANCE,
        company_visual_character=_COMPANY_VISUAL_CHARACTER,
        semantics_legend=_SEMANTICS_LEGEND,
        ux_targets=exp.ux_targets,
        builder_freedom=exp.builder_freedom,
        underlying_experience_sha256=_experience_sha(exp),
        underlying_brief_sha256=exp.underlying_brief_sha256,
        audit_appendix=(
            *exp.audit_appendix,
            ("story_compiler_version", BUILDER_STORY_VERSION),
            ("demo_mode", brief.demo_mode.value),
        ),
    )
    _assert_story_within_authority(story, exp, brief, envelope, sk)
    return story


# --------------------------------------------------------------------------
# fail-closed story-level authority check
# --------------------------------------------------------------------------


class BuilderStoryAuthorityError(Exception):
    """The compiled opportunity story strengthens the evidence anchor, leaks
    internal taxonomy, converts an evidence phrase into a selectable value, lets a
    grouped outcome imply it occurred, or turns the closing bridge into a claim
    about the real business."""


def _story_customer_strings(story: BuilderStory) -> list[str]:
    out = [
        story.opportunity_headline,
        story.opportunity_summary,
        story.opportunity_primary_action,
        story.evidence_detail_label,
        story.unknown_summary,
        story.persistent_disclosure,
        story.simulation_intake_title,
        story.simulation_run_action,
        story.result_title,
        story.result_disclosure,
        story.closing_bridge,
        story.company_visual_character,
        story.primary_demo_anchor,
        *(i.text for i in story.evidence_detail),
        *(f.label for f in story.simulation_input_schema),
        *(f.exists_because for f in story.simulation_input_schema),
        *(v for f in story.simulation_input_schema for v in f.values),
        *(s.label for s in story.result_story),
        *(s.line for s in story.result_story),
        *(g.name for g in story.customer_facing_outcomes),
        *(g.description for g in story.customer_facing_outcomes),
        story.human_handoff_preview.name,
        story.human_handoff_preview.role,
        story.human_handoff_preview.disclosure,
        *(t for pair in story.semantics_legend for t in pair),
        *(s.title for s in story.exception_states),
        *(s.body for s in story.exception_states),
        *story.builder_visual_guidance,
    ]
    return [s for s in out if s]


def _story_authored_strings(story: BuilderStory) -> list[str]:
    """Strings V3 writes itself (V2/V1 strings are validated by their own checks)."""

    return [
        story.opportunity_headline,
        story.opportunity_primary_action,
        story.evidence_detail_label,
        story.result_title,
        story.company_visual_character,
        *(f.label for f in story.simulation_input_schema),
        *(f.exists_because for f in story.simulation_input_schema),
        *(v for f in story.simulation_input_schema for v in f.values),
        *(s.label for s in story.result_story),
        *(s.line for s in story.result_story),
        *(g.name for g in story.customer_facing_outcomes),
        *(g.description for g in story.customer_facing_outcomes),
        *(t for pair in story.semantics_legend for t in pair),
        *story.builder_visual_guidance,
    ]


def _assert_story_within_authority(
    story: BuilderStory,
    exp: BuilderExperience,
    brief: BuilderBrief,
    envelope: SemanticEnvelope,
    sk: DemoScenarioSkeleton,
) -> None:
    def fail(msg: str) -> None:
        raise BuilderStoryAuthorityError(msg)

    # 0. inherit the full V1 + V2 authority checks.
    _assert_experience_within_authority(exp, brief, envelope, sk)

    strings = _story_customer_strings(story)
    low = " \n ".join(strings).lower()

    # 1. opportunity headline: hypothetical framing, concise, never strengthened.
    h = story.opportunity_headline
    if "could" not in h.lower():
        fail("opportunity headline is not framed as a possibility ('could')")
    if len(h.split()) > 20:
        fail(f"opportunity headline is too long ({len(h.split())} words)")
    if _STRENGTHEN.search(h):
        fail(f"opportunity headline strengthens the public claim: {h!r}")
    for f in envelope.eligible_company_facts:
        if not f.quotable and f.sanitized_phrase.strip().lower() in h.lower():
            fail("opportunity headline quotes a non-quotable evidence phrase")

    # 2. no internal ontology / demo-mode / id / version / enum in customer copy.
    for s in strings:
        sl = s.lower()
        for tok in _ONTOLOGY_BLOCKLIST:
            if tok in sl:
                fail(f"customer-facing string exposes internal ontology {tok!r}: {s!r}")
        if _HEXISH.search(s) or _VERSIONISH.search(s) or _ENUMISH.search(s):
            fail(f"customer-facing string exposes an id/version/enum: {s!r}")
    for m in DemoMode:
        if m.value.lower() in low:
            fail(f"customer-facing copy leaks the internal demo mode {m.value!r}")

    # 2b. V3-authored copy introduces no vendor / economics / performance term.
    licensed = _licensed_phrase_text(envelope)
    for s in _story_authored_strings(story):
        toks = set(_WORDISH.findall(s.lower()))
        for bad in _V3_FORBIDDEN & toks:
            if bad not in licensed:
                fail(f"V3 copy introduces unlicensed term {bad!r}: {s!r}")
        for v in _V3_VENDORS:
            if v in s.lower() and v not in licensed:
                fail(f"V3 copy names a CRM / vendor: {v!r}")

    # 3. evidence phrases are never selectable simulation values.
    fact_phrases = {
        p.strip().lower()
        for f in envelope.eligible_company_facts
        for p in (f.sanitized_phrase, f.verbatim_source_phrase)
    }
    for fld in story.simulation_input_schema:
        if fld.value_semantics != SEM_SYNTHETIC_DEMO_INPUT:
            fail(f"input field {fld.field_id!r} values are not marked synthetic")
        for v in fld.values:
            if v.strip().lower() in fact_phrases:
                fail(f"an evidence phrase is offered as a selectable value: {v!r}")
            if v not in story.synthetic_input_values:
                fail(f"synthetic value {v!r} missing from synthetic_input_values")
    urgency = next((f for f in story.simulation_input_schema if f.field_id == "urgency"), None)
    if (
        urgency is None
        or "Safety concern" not in urgency.values
        or "safety_critical" not in urgency.internal_note
    ):
        fail("urgency field lost the M4 safety_critical mapping")

    # 4. synthetic values look illustrative, not like real data.
    if not story.synthetic_input_values:
        fail("no synthetic input values were recorded")
    for v in story.synthetic_input_values:
        if len(v.split()) > 6 or re.search(r"\d", v):
            fail(f"synthetic value looks like a real datum: {v!r}")
        if v.strip().lower() in fact_phrases:
            fail(f"synthetic value duplicates an evidence phrase: {v!r}")

    # 5. outcome groups: three of them, every mock action mapped once, none implied done.
    if len(story.customer_facing_outcomes) != 3:
        fail("customer-facing outcomes must group into exactly three")
    registered = {a for a, _ in sk.mock_actions}
    seen: set[str] = set()
    for g in story.customer_facing_outcomes:
        for aid in g.internal_action_ids:
            if aid not in registered:
                fail(f"outcome group references an unregistered mock action: {aid}")
            if aid in seen:
                fail(f"mock action {aid} appears in more than one outcome group")
            seen.add(aid)
        gt = f"{g.name} {g.description}".lower()
        if _ACTION_VERB_BAD.search(gt) and not any(
            x in gt for x in ("ready", "could", "would", "prepared")
        ):
            fail(f"outcome group implies the action occurred: {g.name!r}")
        if re.search(r"\b(was|were|has been|have been)\b", gt):
            fail(f"outcome group uses completed-action phrasing: {g.name!r}")
    if seen != registered:
        fail("outcome groups do not cover every registered mock action")

    # 6. all six internal mock actions preserved verbatim.
    if story.internal_mock_actions != tuple(sk.mock_actions):
        fail("internal mock actions drifted from the fixed skeleton")

    # 7. result story: 4 ordered stages, no real-action claim, role (not name) leads.
    if tuple(s.order for s in story.result_story) != (1, 2, 3, 4):
        fail("result story is not a 4-stage ordered workflow")
    name = story.human_handoff_preview.name
    for stage in story.result_story:
        sl = stage.line.lower()
        if _ACTION_VERB_BAD.search(sl) and not any(
            g in sl
            for g in (
                "nothing",
                "no ",
                "not ",
                "simulat",
                "prepares",
                "prepared",
                "before anything",
            )
        ):
            fail(f"result story stage implies a real action: {stage.line!r}")
    human_stage = next(
        (s for s in story.result_story if s.semantics == SEM_FICTIONAL_DEMO_PLACEHOLDER), None
    )
    if (
        human_stage is None
        or story.human_handoff_preview.role.lower() not in human_stage.line.lower()
    ):
        fail("result story human stage does not lead with the role")
    if re.search(rf"\b{re.escape(name)}\b", " ".join(s.line for s in story.result_story)):
        fail("result story exposes the fictional name instead of the role")

    # 8. fictional placeholder stays fictional; the story never 'sends to <name>'.
    d = story.human_handoff_preview.disclosure.lower()
    if "fictional" not in d or "not a real person" not in d:
        fail("human handoff preview is not disclosed as fictional")
    if re.search(rf"\b(sent|assigned|routed|forwarded|delivered)\s+to\s+{re.escape(name)}\b", low):
        fail("story implies a real action to the fictional person")
    if re.search(rf"\b{re.escape(name.lower())}\b\s+(works|is on staff|received|will call)", low):
        fail("story implies the fictional person is real")

    # 9. closing bridge: possibility, not a claim about the real current process.
    cb = story.closing_bridge.lower()
    if cb != exp.closing_thought.lower():
        fail("closing bridge diverged from the approved closing thought")
    if "imagine" not in cb or "hypothetical" not in cb:
        fail("closing bridge lost its 'imagine ... hypothetical' framing")
    if re.search(
        r"\byou(?:r)?\s+(?:current|currently|team|process|intake|staff)\b[^.]*"
        r"\b(?:is|are|lack|lacks|need|needs|miss|misses|lose|loses)\b",
        cb,
    ):
        fail("closing bridge asserts something about the real current process")
    for pitch in (
        "roi",
        "save",
        "lose",
        "loss",
        "miss",
        "book a call",
        "schedule a",
        "sign up",
        "buy",
        "purchase",
        "today",
        "right now",
    ):
        if pitch in cb:
            fail(f"closing bridge became a sales pitch: {pitch!r}")

    # 10. persistent + result disclosures intact.
    if "not connected" not in story.persistent_disclosure.lower():
        fail("persistent disclosure lost 'not connected'")
    if "nothing was sent" not in story.result_disclosure.lower():
        fail("result disclosure lost 'nothing was sent'")

    # 11. evidence detail is exactly the V2 licensed public context, marked PUBLIC_EVIDENCE.
    if tuple(i.text for i in story.evidence_detail) != tuple(exp.known_public_context):
        fail("evidence detail diverged from the licensed public context")
    for i in story.evidence_detail:
        if i.semantics != SEM_PUBLIC_EVIDENCE:
            fail("evidence detail item is not marked PUBLIC_EVIDENCE")

    # 12. semantics legend: the five plain distinctions, no enum names exposed.
    legend_labels = {k for k, _ in story.semantics_legend}
    if legend_labels != {
        "Public evidence",
        "Unknown",
        "Synthetic demo input",
        "Fictional demo placeholder",
        "Simulated output",
    }:
        fail("semantics legend does not cover the five distinctions")
    for _, v in story.semantics_legend:
        if _ENUMISH.search(v) or "_" in v:
            fail("semantics legend exposes an enum name")

    # 13. availability is never rendered as response behaviour in an affirmative sentence.
    if _SERVICE_AVAILABILITY in {f.category for f in envelope.eligible_company_facts}:
        blob = " ".join(
            [
                story.opportunity_headline,
                story.opportunity_summary,
                *(i.text for i in story.evidence_detail),
            ]
        )
        for sent in re.split(r"(?<=[.!?])\s+", blob):
            s2 = sent.lower()
            if any(g in s2 for g in ("don't know", "do not know", "unknown", "not public")):
                continue
            if "availab" in s2 and any(
                w in s2 for w in ("respond", "response", "acknowledg", "callback", "reply")
            ):
                fail("availability rendered with response wording in customer copy")

    # 14. RESPONSE_PERFORMANCE is UNKNOWN -> no response-speed pairing anywhere.
    if any(u.component == "RESPONSE_PERFORMANCE" for u in envelope.explicit_unknowns):
        for s in strings:
            s2 = s.lower()
            if any(g in s2 for g in ("message", "unknown", "don't know", "not public")):
                continue
            if _RESP.search(s2) and _SPEED.search(s2):
                fail(f"customer copy asserts response speed (UNKNOWN): {s!r}")

    # 15. no inferred geography.
    for tok in _GEO_BLOCKLIST:
        if re.search(rf"\b{tok}\b", low) and tok not in licensed:
            fail(f"customer copy infers a location: {tok!r}")


# --------------------------------------------------------------------------
# human-readable renderer: BuilderStory -> paste-into-builder prompt
# --------------------------------------------------------------------------

_SEM_PLAIN: dict[str, str] = {
    SEM_PUBLIC_EVIDENCE: "Public evidence",
    SEM_UNKNOWN: "Unknown",
    SEM_SYNTHETIC_DEMO_INPUT: "Synthetic demo input",
    SEM_FICTIONAL_DEMO_PLACEHOLDER: "Fictional demo placeholder",
    SEM_SIMULATED_OUTPUT: "Simulated output",
}


def render_builder_story_markdown(story: BuilderStory) -> str:
    """A short opportunity-first product brief a non-technical person can paste
    into a website/app builder. Three screens, ~60 seconds, the opportunity is the
    hero, internal taxonomy hidden. Provenance is a trailing appendix only."""

    s = story
    lines: list[str] = []
    add = lines.append

    add(f"# {s.business_display_name} — an intake opportunity")
    add("")
    add(f"_Show on every screen:_ **{s.persistent_disclosure}**")
    add("")
    add(
        "> Builder brief. You have full freedom over visual design and **zero** freedom over "
        "the wording of any claim, label, disclosure, workflow step or result - use only the "
        f"copy in this brief for those. {s.builder_freedom}"
    )
    add("")

    add(f"## Screen 1 — {s.opportunity_headline}")
    add("")
    add(f"> {s.opportunity_summary}")
    add("")
    add(f"**Primary action:** `{s.opportunity_primary_action}`")
    add("")
    if s.evidence_detail:
        add(f"<details><summary>{s.evidence_detail_label}</summary>")
        add("")
        for i in s.evidence_detail:
            add(f"- {i.text}")
        add("")
        add("</details>")
        add("")
    add(f"_What we don't know:_ {s.unknown_summary}")
    add("")

    add(f"## Screen 2 — {s.simulation_intake_title}")
    add("")
    add(
        "One calm page - no wizard. Every value below is an **illustrative simulation choice**, "
        f"not a fact about {s.short_name} and not something they told us."
    )
    add("")
    add("| field | control | illustrative values | required | why the field exists |")
    add("|---|---|---|---|---|")
    for f in s.simulation_input_schema:
        vals = " / ".join(f.values)
        req = "no" if f.optional else "yes"
        add(f"| {f.label} | {f.control} | {vals} | {req} | {f.exists_because} |")
    add("")
    add(f"**Submit action:** `{s.simulation_run_action}`")
    add("")
    add(
        "_Never_ collect a real phone number, email, address, customer name or staff name. "
        "'Preferred follow-up' only picks which preview channel the result shows."
    )
    add("")

    add(f"## Screen 3 — {s.result_title}")
    add("")
    add("Show this as movement through a workflow, not a data dump:")
    add("")
    add("`" + "  →  ".join(stage.label for stage in s.result_story) + "`")
    add("")
    for stage in s.result_story:
        add(f"{stage.order}. **{stage.label}** — {stage.line}")
    add("")
    add("**Example human handoff** (fictional, illustrative):")
    add("")
    p = s.human_handoff_preview
    add(f"> **{p.name}**  ")
    add(f"> {p.role}\\*")
    add(">")
    add(f"> \\* {p.disclosure}")
    add("")
    add("**What could be prepared next** (grouped; nothing runs):")
    add("")
    for g in s.customer_facing_outcomes:
        add(f"- **{g.name}** — {g.description}")
    add("")
    add(f"_Result footer:_ {s.result_disclosure}")
    add("")

    add(f"## {s.closing_bridge}")
    add("")
    add("_Make this the visual conclusion of the story - calm, prominent, not a call to action._")
    add("")

    add("## If something needs a person (only when triggered)")
    add("")
    for ex in s.exception_states:
        add(f"### {ex.title}")
        add(ex.body)
        add("")

    add("## Visual direction")
    add("")
    for vg in s.builder_visual_guidance:
        add(f"- {vg}")
    add(f"- **Company visual character:** {s.company_visual_character}")
    add("")

    add("## Reading the labels")
    add("")
    for k, v in s.semantics_legend:
        add(f"- **{k}** — {v}")
    add("")

    add("## DO NOT ADD")
    add("")
    for item in s.builder_forbidden_additions:
        add(f"- {item}")
    add("")

    add("## Timing target")
    add("")
    for t in s.ux_targets:
        add(f"- {t}")
    add("")

    add("---")
    add("")
    add("## Appendix — provenance & audit (not for the rendered UI)")
    add("")
    add("| key | value |")
    add("|---|---|")
    for k, v in s.audit_appendix:
        add(f"| {k} | `{v}` |")
    add(f"| underlying_experience_sha256 | `{s.underlying_experience_sha256}` |")
    add(f"| underlying_brief_sha256 | `{s.underlying_brief_sha256}` |")
    add(f"| compiled_at | {s.compiled_at.isoformat()} |")
    add("")
    add("**Internal mock actions (all six preserved; audit only):**")
    add("")
    group_of = {aid: g.name for g in s.customer_facing_outcomes for aid in g.internal_action_ids}
    for aid, label in s.internal_mock_actions:
        add(f'- `{aid}` — "{label}" — grouped under **{group_of.get(aid, "?")}**')
    add("")
    add("**Simulation input fields — M4 evidence-derived option labels (audit only):**")
    add("")
    for f in s.simulation_input_schema:
        if f.m4_option_labels:
            add(f"- `{f.field_id}`: {list(f.m4_option_labels)}")
    add("")
    return "\n".join(lines)
