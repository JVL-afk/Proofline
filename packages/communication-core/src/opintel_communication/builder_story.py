"""``demo.builder_brief@3.2`` - the opportunity-story builder projection (FROZEN).

Owner authorization 2026-09-03 "M4 BUILDER-BRIEF V3: OPPORTUNITY -> EXPERIENCE ->
HANDOFF" (V3) then 2026-09-04 "M4 BUILDER-BRIEF V3.1 CLEANUP + ELITE
PERSONALIZATION PROOF" (V3.1). V2 (``demo.builder_brief@2``) collapsed the
internal state machine into a three-screen human experience. V3 reframed the same
three screens as a short opportunity story:

    1. We noticed this        (Screen 1 - opportunity is the hero)
    2. Here is how it could work   (Screen 2 - one calm intake page)
    3. Here is what your team could receive   (Screen 3 - a workflow story)
    4. Imagine it fitted to your real process   (the closing bridge)

Externally V3 optimises for comprehension + relevance + desire while M4 keeps
optimising internally for truth + safety + provenance.

V3.1 is presentation cleanup only (no M4 / V1 / V2 semantic change):

* the ontology legend is no longer part of the default customer view - it moves
  to an audit / optional developer note;
* Screen 2 field copy is a short customer hint; the evidence/safety rationale
  stays in the machine artifact + audit layer;
* a hard builder rule set forbids invented functionality (exports, downloads,
  share/save, analytics, dashboards, state selectors, demo badges, ...) - the
  only interactive actions are the enumerated Screen 1 + Screen 2 actions;
* the opportunity headline is guaranteed to carry an anchor-specific keyword,
  and a per-anchor ``scenario_framing`` string makes different evidence produce
  a different opportunity story (the Elite personalization proof).

V3.2 (owner authorization 2026-09-04 "FREEZE M4 -> RUN M6.8-4 ...", Part A)
formalizes two manual UX discoveries and **freezes** the M4 presentation layer:

* ``example_scenarios`` - a small set of Screen-2 presets that fill the existing
  synthetic form fields with ``SYNTHETIC_DEMO_INPUT`` values only. Selecting a
  preset is exactly equivalent to selecting those fields by hand; no new
  workflow authority, never a fact about the target company;
* ``start_over`` - a customer-facing state-reset control after a result /
  exception. It clears local synthetic state and returns to the opportunity
  screen. It never saves, transmits, tracks, persists, or implies a real action.

After V3.2 the presentation compiler is FROZEN: no further M4 aesthetic tuning.
Authoritative M4 demo semantics are unchanged; A-Plus and Elite are generated
through this same compiler; builder rendering stays manual; no external builder
is part of the authority chain.

V3(.x) is a pure deterministic function of the same frozen inputs. It builds on
the V2 ``BuilderExperience`` (inheriting V1's *and* V2's fail-closed checks) and
adds a story-level authority check on top.
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

BUILDER_STORY_VERSION = "demo.builder_brief@3.2"
# The M4 presentation compiler is frozen at this version (owner authorization
# 2026-09-04). No further aesthetic tuning; only bug/authority fixes.
M4_PRESENTATION_FROZEN = True

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
# V3.1 hard builder rules (section 6, 4, 5) - functionality lock-down. The
# builder invents visual treatment; it does not invent product functionality.
# --------------------------------------------------------------------------

_STORY_HARD_BUILDER_RULES: tuple[str, ...] = (
    "Do NOT add any functional control, export, download, PDF or print generation, share or "
    "save action, link-out, email capture, analytics, dashboard, KPI tile, integration, sign-in, "
    "or any capability that is not explicitly listed as a primary or submit action in this "
    "brief. You may invent visual treatment; you may not invent product functionality.",
    "The only interactive actions are the enumerated Screen 1 primary action, the Screen 2 "
    "submit action, and the standard form inputs. Nothing else is clickable.",
    "Do NOT add a state selector, test-state switcher, scenario picker, 'preview a special "
    "state' control, or any QA / debug affordance to the customer experience. The exception "
    "screens render only when the simulation itself routes to them.",
    "Do NOT add a product or demo badge, a mode tag, a 'DEMO' chip, a category label, or any "
    "technical or semantic badge. The only persistent chrome is the disclosure line.",
    "Do NOT surface the semantic legend, evidence/unknown labels, or any internal taxonomy in "
    "the normal customer view. Explain meaning in plain language in context if needed.",
)

# V3.2 (freeze): the complete, closed list of customer-facing controls. A builder
# renders exactly these and nothing else.
_CUSTOMER_FACING_CONTROLS: tuple[str, ...] = (
    "Progress from the opportunity screen to the simulation (Screen 1 primary action).",
    "Select or edit the synthetic simulation inputs (Screen 2 form).",
    "Optionally load one example scenario preset that fills those same synthetic inputs.",
    "Run the simulation (Screen 2 submit action).",
    "Expand the permitted explanatory detail ('Why we built this').",
    "Start over after a result or exception screen (clears local synthetic state only).",
)

# V3.2 example-scenario presets (Part A.1.A). Every value is a SYNTHETIC_DEMO_INPUT
# value already present on the corresponding field. A preset is exactly equivalent
# to selecting those fields by hand - no new workflow authority, never a fact
# about the target company.
_EXAMPLE_SCENARIOS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Office repair",
        (
            ("service_need", "Repair request"),
            ("facility_type", "Office"),
            ("service_location", "Example service location"),
            ("urgency", "Routine"),
            ("equipment_context", "Split system"),
            ("contact_preference", "Phone"),
        ),
    ),
    (
        "Retail maintenance",
        (
            ("service_need", "Maintenance visit"),
            ("facility_type", "Retail"),
            ("service_location", "Example service location"),
            ("urgency", "Routine"),
            ("equipment_context", "Rooftop unit"),
            ("contact_preference", "Email"),
        ),
    ),
    (
        "Hospitality quote",
        (
            ("service_need", "Replacement or quote"),
            ("facility_type", "Hospitality"),
            ("service_location", "Example service location"),
            ("urgency", "Routine"),
            ("equipment_context", "Chiller"),
            ("contact_preference", "Phone"),
        ),
    ),
    (
        "Warehouse safety concern",
        (
            ("service_need", "Repair request"),
            ("facility_type", "Warehouse"),
            ("service_location", "Example service location"),
            ("urgency", "Safety concern"),
            ("equipment_context", "Rooftop unit"),
            ("contact_preference", "Phone"),
        ),
    ),
)

_START_OVER_LABEL = "Start over"
_START_OVER_SEMANTICS = (
    "Clears the local synthetic form state and returns to the opportunity screen so another "
    "simulation can be run. It saves nothing, sends nothing, records no history, creates no "
    "analytics, contacts no one, persists no customer data, and does not imply any real action "
    "occurred - it is a local reset only."
)

# internal M4 question id -> short customer-facing hint (section 7). The
# evidence / safety rationale stays in ``exists_because`` (audit layer only).
_CUSTOMER_HINTS: dict[str, str] = {
    "service_need": "Which need applies",
    "facility_type": "Facility type",
    "service_location": "Example simulation location",
    "urgency": "How urgent",
    "equipment_context": "Equipment (optional)",
    "contact_preference": "Preview follow-up as",
}

# per-anchor scenario framing (Part II, section 12/14). Different evidence ->
# different opportunity story, without a different internal workflow. Never
# pairs availability / response positioning with a speed or response claim.
_SCENARIO_FRAMING: dict[str, str] = {
    _RESPONSE_COMMITMENT: (
        "a commercial request, organized and summarized so a person can pick it up"
    ),
    _SERVICE_AVAILABILITY: (
        "a service request that could come in at any time, organized so a person can pick it up"
    ),
    _INTAKE_SURFACE: ("a scheduling or service-call request, organized so a person can pick it up"),
}
_SCENARIO_FRAMING_DEFAULT = "a commercial request, organized so a person can pick it up"

# per-anchor keyword the headline MUST carry so it stays tied to the anchor
# (section 2) and can never collapse into a generic "your public pages describe".
_ANCHOR_HEADLINE_KEYWORD: dict[str, str] = {
    _RESPONSE_COMMITMENT: "response",
    _SERVICE_AVAILABILITY: "availab",
    _INTAKE_SURFACE: "request path",
}

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
    customer_hint: str  # V3.1: short customer-facing hint (few words)
    control: str  # select | choice
    values: tuple[str, ...]  # SYNTHETIC_DEMO_INPUT values
    value_semantics: str  # SYNTHETIC_DEMO_INPUT
    optional: bool
    exists_because: str  # EVIDENCE_CONTEXT rationale - audit layer only, not customer copy
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
class ExampleScenario:
    """A Screen-2 preset that fills the synthetic form fields. Equivalent to
    selecting those same fields by hand; no new workflow authority."""

    name: str
    field_values: tuple[tuple[str, str], ...]  # (field_id, SYNTHETIC_DEMO_INPUT value)


@dataclass(frozen=True, slots=True)
class BuilderStory:
    story_version: str
    compiled_at: datetime
    business_display_name: str
    short_name: str
    permitted_hostname: str
    identity_rule: str
    primary_demo_anchor: str  # plain-language category label
    scenario_framing: str  # V3.1: per-anchor story framing (different evidence -> different story)
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
    example_scenarios: tuple[ExampleScenario, ...]  # V3.2: optional Screen-2 presets
    simulation_run_action: str
    # --- Screen 3: the workflow story ---
    result_title: str
    result_recap_line: str  # V3.1: concise recap; outcomes are the hero, not the recap
    result_story: tuple[ResultStoryStage, ...]
    human_handoff_preview: FictionalPlaceholder
    customer_facing_outcomes: tuple[CustomerOutcomeGroup, ...]
    internal_mock_actions: tuple[tuple[str, str], ...]  # audit: all six preserved
    result_disclosure: str
    closing_bridge: str
    start_over_label: str  # V3.2: post-result / post-exception state-reset control
    start_over_semantics: str  # V3.2: what "start over" may and may not do
    # --- exceptions + builder constraints ---
    exception_states: tuple[ExceptionScreen, ...]
    allowed_primary_actions: tuple[str, ...]  # V3.1: the ONLY primary click actions
    customer_facing_controls: tuple[str, ...]  # V3.2: the closed list of all controls
    builder_hard_rules: tuple[str, ...]  # V3.1: functionality lock-down
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
                customer_hint=_CUSTOMER_HINTS[qid],
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


def _example_scenarios(fields: tuple[StoryInputField, ...]) -> tuple[ExampleScenario, ...]:
    """Screen-2 presets. Every value must already be a synthetic option on its
    field, so selecting a preset is exactly equivalent to selecting by hand."""

    by_field = {f.field_id: set(f.values) for f in fields}
    out: list[ExampleScenario] = []
    for name, pairs in _EXAMPLE_SCENARIOS:
        kept = tuple((fid, val) for fid, val in pairs if val in by_field.get(fid, set()))
        if len(kept) == len(pairs):  # only offer a preset that fully lands on real options
            out.append(ExampleScenario(name=name, field_values=kept))
    return tuple(out)


def _result_story(role: str, framing: str) -> tuple[ResultStoryStage, ...]:
    return (
        ResultStoryStage(
            1,
            "Request",
            "A request arrives through the simulated intake form.",
            SEM_SIMULATED_OUTPUT,
        ),
        ResultStoryStage(
            2,
            "Structured context",
            f"The simulation turns the form answers into {framing}.",
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

    scenario_framing = _SCENARIO_FRAMING.get(anchor_category or "", _SCENARIO_FRAMING_DEFAULT)
    result_recap_line = (
        "A one-line recap of the simulated request - need, facility, and urgency - then the "
        "workflow story below."
    )

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
        scenario_framing=scenario_framing,
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
        example_scenarios=_example_scenarios(fields),
        simulation_run_action=exp.simulation_run_action,
        result_title="A commercial request is ready for human review",
        result_recap_line=result_recap_line,
        result_story=_result_story(placeholder.role, scenario_framing),
        human_handoff_preview=placeholder,
        customer_facing_outcomes=_customer_facing_outcomes(),
        internal_mock_actions=tuple(sk.mock_actions),
        result_disclosure=exp.result_disclosure,
        closing_bridge=exp.closing_thought,
        start_over_label=_START_OVER_LABEL,
        start_over_semantics=_START_OVER_SEMANTICS,
        exception_states=exp.exception_states,
        allowed_primary_actions=("See how it could work", "Run simulation"),
        customer_facing_controls=_CUSTOMER_FACING_CONTROLS,
        builder_hard_rules=_STORY_HARD_BUILDER_RULES,
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
            ("m4_presentation_frozen", str(M4_PRESENTATION_FROZEN).lower()),
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
        story.result_recap_line,
        story.result_disclosure,
        story.closing_bridge,
        story.company_visual_character,
        story.primary_demo_anchor,
        story.scenario_framing,
        *(i.text for i in story.evidence_detail),
        *(f.label for f in story.simulation_input_schema),
        *(f.customer_hint for f in story.simulation_input_schema),
        *(v for f in story.simulation_input_schema for v in f.values),
        *(s.label for s in story.result_story),
        *(s.line for s in story.result_story),
        *(g.name for g in story.customer_facing_outcomes),
        *(g.description for g in story.customer_facing_outcomes),
        story.human_handoff_preview.name,
        story.human_handoff_preview.role,
        story.human_handoff_preview.disclosure,
        story.start_over_label,
        story.start_over_semantics,
        *(p.name for p in story.example_scenarios),
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
        story.result_recap_line,
        story.scenario_framing,
        story.company_visual_character,
        *(f.label for f in story.simulation_input_schema),
        *(f.customer_hint for f in story.simulation_input_schema),
        *(f.exists_because for f in story.simulation_input_schema),
        *(v for f in story.simulation_input_schema for v in f.values),
        *(s.label for s in story.result_story),
        *(s.line for s in story.result_story),
        *(g.name for g in story.customer_facing_outcomes),
        *(g.description for g in story.customer_facing_outcomes),
        *(p.name for p in story.example_scenarios),
        story.start_over_label,
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

    # 1b. V3.1: the headline must carry the anchor-specific keyword - it can never
    #     collapse into a generic "your public pages describe" line.
    anchor_cat = brief.primary_demo_anchor.category if brief.primary_demo_anchor else None
    kw = _ANCHOR_HEADLINE_KEYWORD.get(anchor_cat or "")
    if kw and kw not in h.lower():
        fail(f"opportunity headline is not tied to the {anchor_cat!r} anchor (missing {kw!r})")
    if re.search(r"\b(verified|proven|actual|measured|confirmed)\b", h.lower()):
        fail(f"opportunity headline implies verified performance: {h!r}")

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

    # 16. V3.1: the semantic legend / ontology is preserved on the artifact (5
    #     distinctions) but is no longer one of the default customer strings - it
    #     is rendered only in the audit / developer note (asserted by the render
    #     tests). Every legend label stays plain language.
    if len(story.semantics_legend) != 5:
        fail("semantic legend must keep all five distinctions on the artifact")

    # 17. V3.1: the ONLY interactive actions are the two enumerated ones.
    if story.allowed_primary_actions != (
        story.opportunity_primary_action,
        story.simulation_run_action,
    ):
        fail("allowed_primary_actions must be exactly the Screen 1 + Screen 2 actions")
    if len(story.allowed_primary_actions) != 2:
        fail("there must be exactly two allowed primary actions")

    # 18. V3.1: the hard builder rules forbid invented functionality / debug / badges.
    rules_blob = " ".join(story.builder_hard_rules).lower()
    if not story.builder_hard_rules:
        fail("V3.1 hard builder rules are missing")
    for needle in ("download", "export", "state selector", "badge", "clickable"):
        if needle not in rules_blob:
            fail(f"hard builder rules do not cover {needle!r}")

    # 19. V3.1: the result recap stays concise and never claims a real action.
    if len(story.result_recap_line.split()) > 22:
        fail("result recap line is not concise")
    if _ACTION_VERB_BAD.search(story.result_recap_line.lower()) and not any(
        g in story.result_recap_line.lower() for g in ("recap", "simulat", "nothing")
    ):
        fail("result recap line implies a real action")

    # 20. V3.1: scenario framing - present, never a speed / response claim, never strengthened.
    sf = story.scenario_framing.lower()
    if not sf:
        fail("scenario framing is empty")
    if _STRENGTHEN.search(story.scenario_framing):
        fail(f"scenario framing strengthens the claim: {story.scenario_framing!r}")
    if _RESP.search(sf) and _SPEED.search(sf):
        fail("scenario framing pairs a response verb with a speed word")
    if "availab" in sf and any(
        w in sf for w in ("respond", "response", "acknowledg", "callback", "reply")
    ):
        fail("scenario framing turns availability into response behaviour")

    # 21. V3.1: Screen-2 customer hints are short and free of architecture wording.
    for fld in story.simulation_input_schema:
        if len(fld.customer_hint.split()) > 6:
            fail(f"customer hint for {fld.field_id!r} is not concise: {fld.customer_hint!r}")
        hl = fld.customer_hint.lower()
        if any(
            w in hl
            for w in (
                "evidence",
                "public page",
                "safety handoff",
                "coverage promise",
                "m4",
                "unknown",
            )
        ):
            fail(f"customer hint for {fld.field_id!r} leaks the authority rationale")

    # 22. V3.2: example-scenario presets only fill existing synthetic options -
    #     selecting a preset is exactly equivalent to selecting by hand.
    field_opts = {f.field_id: set(f.values) for f in story.simulation_input_schema}
    field_ids = set(field_opts)
    for preset in story.example_scenarios:
        pl = preset.name.lower()
        if any(pl == p.strip().lower() or p.strip().lower() in pl for p in fact_phrases):
            fail(f"example scenario name echoes an evidence phrase: {preset.name!r}")
        if len(preset.name.split()) > 4:
            fail(f"example scenario name is not a short label: {preset.name!r}")
        for fid, val in preset.field_values:
            if fid not in field_ids:
                fail(f"example scenario {preset.name!r} sets an unknown field {fid!r}")
            if val not in field_opts[fid]:
                fail(
                    f"example scenario {preset.name!r} sets {fid!r}={val!r}, not a synthetic option"
                )
            if val.strip().lower() in fact_phrases:
                fail(f"example scenario {preset.name!r} uses an evidence phrase as a value")

    # 23. V3.2: 'start over' is a local state reset - it never persists, transmits,
    #     tracks, or implies a real action.
    so = story.start_over_semantics.lower()
    if story.start_over_label.lower() not in ("start over", "start again", "reset"):
        fail(f"unexpected start-over label: {story.start_over_label!r}")
    if not all(k in so for k in ("clears", "local", "another simulation")) or not all(
        k in so for k in ("saves nothing", "sends nothing")
    ):
        fail("start-over semantics do not describe a pure local reset")
    for forbidden in ("tracks", "analytics", "history", "persists", "contacts"):
        # the sentence must DENY these, never permit them
        if re.search(rf"\b{forbidden}\b", so) and "no" not in so and "not" not in so:
            fail(f"start-over semantics do not deny {forbidden!r}")

    # 24. V3.2 freeze: the customer-facing control list is the closed six-item set.
    if len(story.customer_facing_controls) != 6:
        fail("customer_facing_controls must be the closed six-item list")
    controls_blob = " ".join(story.customer_facing_controls).lower()
    for needle in (
        "opportunity screen",
        "synthetic simulation inputs",
        "example scenario",
        "run the simulation",
        "explanatory detail",
        "start over",
    ):
        if needle not in controls_blob:
            fail(f"customer_facing_controls missing {needle!r}")


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

    add("## Builder rules (hard limits — read first)")
    add("")
    for rule in s.builder_hard_rules:
        add(f"- {rule}")
    add("")
    add("**The complete set of customer-facing controls (render exactly these, nothing else):**")
    add("")
    for c in s.customer_facing_controls:
        add(f"- {c}")
    add(
        "- **Primary click actions:** "
        + ", ".join(f"`{a}`" for a in s.allowed_primary_actions)
        + "."
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
    add("| field | hint | control | illustrative values | required |")
    add("|---|---|---|---|---|")
    for f in s.simulation_input_schema:
        vals = " / ".join(f.values)
        req = "no" if f.optional else "yes"
        add(f"| {f.label} | {f.customer_hint} | {f.control} | {vals} | {req} |")
    add("")
    if s.example_scenarios:
        add("### Example scenarios (optional presets)")
        add("")
        add(
            "A small set of one-tap presets that fill the fields above with the same "
            "illustrative values. Selecting a preset is exactly the same as choosing those "
            "options by hand — it adds no new behaviour and describes nothing about the business."
        )
        add("")
        for es in s.example_scenarios:
            picks = ", ".join(f"{fid.replace('_', ' ')} = {val}" for fid, val in es.field_values)
            add(f"- **{es.name}** — {picks}")
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
    add(f"_{s.result_recap_line}_")
    add("")
    add("Show this as movement through a workflow, not a data dump — the **outcome** is the hero:")
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

    add("## Exception screens")
    add("")
    add(
        "_Builder note: render one of these **only** when the simulation itself routes there. "
        "Never a user-facing selector or a way to preview them._"
    )
    add("")
    for ex in s.exception_states:
        add(f"### {ex.title}")
        add(ex.body)
        add("")

    add(f"## {s.start_over_label}")
    add("")
    add(
        f"After any result or exception screen, offer a **{s.start_over_label}** control. "
        f"{s.start_over_semantics}"
    )
    add("")

    add("## Visual direction")
    add("")
    for vg in s.builder_visual_guidance:
        add(f"- {vg}")
    add(f"- **Company visual character:** {s.company_visual_character}")
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
    add("**Simulation input fields — customer hint, M4 rationale, M4 option labels (audit only):**")
    add("")
    for f in s.simulation_input_schema:
        add(f'- `{f.field_id}` — hint "{f.customer_hint}" — {f.exists_because}')
        if f.m4_option_labels:
            add(f"  - M4 evidence-derived option labels: {list(f.m4_option_labels)}")
    add("")
    add(f"**Scenario framing (per-anchor story):** {s.scenario_framing}")
    add("")
    add(f"**Result recap line:** {s.result_recap_line}")
    add("")
    add("**Semantic legend (audit / optional developer note — not the customer view):**")
    add("")
    for k, v in s.semantics_legend:
        add(f"- **{k}** — {v}")
    add("")
    return "\n".join(lines)
