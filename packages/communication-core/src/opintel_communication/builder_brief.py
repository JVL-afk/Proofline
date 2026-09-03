"""``demo.builder_brief@1`` - deterministic M4 -> builder-implementation-brief compiler.

Owner authorization 2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM". Compiles the
existing, unchanged, evidence-bound M4 demo authority (the frozen
``SemanticEnvelope`` + the fixed ``commercial_hvac.inbound_lead_response``
scenario skeleton) into an explicit brief a human can paste into a mature
website/app builder (Lovable etc.).

Core rule: **the builder is a presentation renderer, not a source of business
truth.** It may decide layout / typography / spacing / animation / responsive
behaviour / aesthetic composition. It may not decide what the business does,
what integrations exist, response times, staffing, economics, internal process,
or whether a public absence means an internal absence.

No LLM. No second provider. Pure deterministic function. Every substantive
sentence is built only from the envelope's licensed evidence / findings /
inferences / recommendations / UNKNOWNs / disclosures and the fixed scenario
skeleton; ``_assert_within_authority`` fails closed on any leak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from opintel_demo import DemoScenarioSkeleton, demo_scenario_skeleton

from opintel_communication.domain import (
    EnvelopeFact,
    SemanticEnvelope,
    _is_generic_label,
)

BUILDER_BRIEF_VERSION = "demo.builder_brief@1"

_RESPONSE_COMMITMENT = "response_commitment"
_SERVICE_AVAILABILITY = "service_availability"
_COMMERCIAL_CONTEXT = "commercial_context"
_INTAKE_SURFACE = "intake_surface"
_SERVICE_AREA_CONTEXT = "service_area_context"

# Categories a viewer must never be able to "select" inside the simulation
# (M4 demo.commercial_hvac.lead_response@3): a published response promise or a
# bare availability signal is retained semantic context, not an intake choice.
_NON_SELECTABLE_CATEGORIES = frozenset({_RESPONSE_COMMITMENT, _SERVICE_AVAILABILITY})

# Words the brief prose may never contain unless they appear verbatim in a
# licensed evidence phrase / finding / inference / recommendation. A leak here is
# the builder being handed business truth it was not authorized to state.
_FORBIDDEN_UNLESS_LICENSED: frozenset[str] = frozenset(
    {
        # integrations / vendors
        "crm",
        "servicetitan",
        "housecall",
        "housecallpro",
        "jobber",
        "salesforce",
        "hubspot",
        "zoho",
        "connectwise",
        "dispatch",
        "api",
        "integration",
        "integrated",
        "connected",
        "sync",
        "webhook",
        # economics / metrics
        "revenue",
        "roi",
        "profit",
        "conversion",
        "convert",
        "leads",
        "lead",
        "pipeline",
        "savings",
        "dollars",
        "percent",
        "percentage",
        # performance judgements
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
        "lose",
        "unanswered",
        "understaffed",
        "overwhelmed",
        "backlog",
        "manual",
        "automate",
        "automated",
        "automation",
        # social proof
        "testimonial",
        "review",
        "reviews",
        "rated",
        "rating",
        "endorsement",
        "case-study",
        # deployment status (positive)
        "deployed",
        "live",
        "production",
        "official",
        "operational",
        "operated",
        # dashboards
        "dashboard",
        "analytics",
        "metric",
        "metrics",
        "kpi",
    }
)

_DIGIT = re.compile(r"\d")
_WORD = re.compile(r"[a-z][a-z'/-]{1,}")

# The one thing the builder is genuinely free to shape. Fixed guidance, not a
# pixel spec (owner section 3 "UX/presentation brief").
_UX_BRIEF = (
    "Produce something polished, premium, modern and immediately understandable - "
    "credible to a commercial-HVAC operator who has seen good software. It must be "
    "fully responsive, visually clear, and interactive enough that the owner can "
    "picture using it. You choose layout, typography, spacing, colour, motion, "
    "component styling and overall composition. Do NOT invent product copy that "
    "asserts anything about the business; use only the wording this brief supplies "
    "for any claim, label, disclosure or workflow text. Keep the required "
    "simulation disclosure visible and unmissable at all times - it is not "
    "decorative chrome."
)


class DemoMode(StrEnum):
    BESPOKE_DEMO = "BESPOKE_DEMO"
    EVIDENCE_BOUND_DEMO = "EVIDENCE_BOUND_DEMO"
    GENERIC_CAPABILITY_DEMO = "GENERIC_CAPABILITY_DEMO"
    DEMO_NOT_DISTINCTIVE_ENOUGH = "DEMO_NOT_DISTINCTIVE_ENOUGH"


@dataclass(frozen=True, slots=True)
class BriefEvidenceItem:
    category: str
    strength: str
    phrase: str
    verbatim_phrase: str
    fact_class: str
    page_purpose: str
    quotable: bool
    generic_label: bool
    is_selectable_demo_option: bool
    anchor_rank: int
    usage_note: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BriefUnknown:
    component: str
    text: str
    hard_prohibition: str | None


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    ordinal: int
    state_id: str
    title: str
    description: str
    builder_hint: str


@dataclass(frozen=True, slots=True)
class MockActionSpec:
    action_type: str
    label: str
    marking: str = "SIMULATED / MOCK_ONLY / NOT_CONNECTED"


@dataclass(frozen=True, slots=True)
class DisclosureSpec:
    slot_kind: str
    meaning: str
    placement: str


@dataclass(frozen=True, slots=True)
class BuilderBrief:
    brief_version: str
    compiled_at: datetime
    demo_mode: DemoMode
    mode_rationale: str
    business_display_name: str
    permitted_hostname: str
    identity_rule: str
    demo_title: str
    target_use_case: str
    demo_objective: str
    central_demo_story: str
    licensed_public_evidence: tuple[BriefEvidenceItem, ...]
    primary_demo_anchor: BriefEvidenceItem | None
    service_need_options: tuple[str, ...]
    service_location_options: tuple[str, ...]
    retained_context_not_selectable: tuple[tuple[str, str], ...]
    unknowns: tuple[BriefUnknown, ...]
    scenario_description: str
    workflow_steps: tuple[WorkflowStep, ...]
    mock_actions: tuple[MockActionSpec, ...]
    required_disclosures: tuple[DisclosureSpec, ...]
    forbidden_additions: tuple[str, ...]
    ux_presentation_brief: str
    audit_appendix: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# deterministic anchor ranking
# --------------------------------------------------------------------------


def _anchor_score(category: str, generic: bool) -> int:
    if category == _RESPONSE_COMMITMENT:
        return 100
    if category == _SERVICE_AVAILABILITY:
        return 90
    if category == _COMMERCIAL_CONTEXT:
        return 70 if not generic else 35
    if category == _INTAKE_SURFACE:
        return 65 if not generic else 30
    if category == _SERVICE_AREA_CONTEXT:
        return 20 if not generic else 10
    return 10


def _option_label(phrase: str, limit: int = 48) -> str:
    """Identical to ``opintel_demo.composition._option_label`` - the exact label
    M4 would render for an evidence-derived synthetic option."""

    text = " ".join(phrase.split()).strip().rstrip(".;:,")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].strip()
    return text


def _short_name(display_name: str) -> str:
    first = display_name.split()[0] if display_name.split() else display_name
    return first if len(first) >= 3 else display_name


def _category_reference(category: str) -> str:
    """How to name a non-quotable fact without quoting or upgrading it."""

    return {
        _RESPONSE_COMMITMENT: "a published response-time claim",
        _SERVICE_AVAILABILITY: "a published service-availability signal",
        _COMMERCIAL_CONTEXT: "a commercial-service description",
        _INTAKE_SURFACE: "a public request path",
        _SERVICE_AREA_CONTEXT: "a service-area reference",
    }.get(category, "a public page reference")


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------


def compile_builder_brief(
    *,
    envelope: SemanticEnvelope,
    skeleton: DemoScenarioSkeleton | None = None,
    now: datetime | None = None,
) -> BuilderBrief:
    sk = skeleton or demo_scenario_skeleton()
    now = now or envelope.generated_at
    identity = envelope.business_identity
    facts = [f for f in envelope.eligible_company_facts if not f.injection_suspected]

    # --- evidence carry-through + anchor ranking -----------------------
    scored: list[tuple[int, int, EnvelopeFact]] = []
    for idx, f in enumerate(facts):
        generic = _is_generic_label(f.sanitized_phrase)
        scored.append((-_anchor_score(f.category, generic), idx, f))
    scored.sort(key=lambda t: (t[0], t[1]))

    evidence: list[BriefEvidenceItem] = []
    for rank, (_, _, f) in enumerate(scored):
        generic = _is_generic_label(f.sanitized_phrase)
        selectable = f.category not in _NON_SELECTABLE_CATEGORIES and f.category in (
            _COMMERCIAL_CONTEXT,
            _INTAKE_SURFACE,
            _SERVICE_AREA_CONTEXT,
        )
        evidence.append(
            BriefEvidenceItem(
                category=f.category,
                strength=f.strength.value,
                phrase=f.sanitized_phrase,
                verbatim_phrase=f.verbatim_source_phrase,
                fact_class=f.fact_class,
                page_purpose=f.page_purpose,
                quotable=bool(f.quotable),
                generic_label=generic,
                is_selectable_demo_option=selectable,
                anchor_rank=rank,
                usage_note=" ".join((f.usage_rule or "").split()),
                evidence_ids=tuple(str(e) for e in f.evidence_ids),
            )
        )
    primary = evidence[0] if evidence else None

    # --- demo mode ---------------------------------------------------
    non_generic = [e for e in evidence if not e.generic_label]
    has_intake = any(e.category == _INTAKE_SURFACE for e in evidence)
    has_commercial = any(e.category == _COMMERCIAL_CONTEXT for e in evidence)
    strong_anchor = any(
        e.category in (_RESPONSE_COMMITMENT, _SERVICE_AVAILABILITY)
        or (e.category in (_COMMERCIAL_CONTEXT, _INTAKE_SURFACE) and not e.generic_label)
        for e in evidence
    )
    distinctive = envelope.has_distinctive_fact()

    if not has_intake or len(evidence) < 2 or (not has_commercial and not strong_anchor):
        mode = DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH
        rationale = (
            "Fewer than two eligible facts, or no public request path, or no commercial "
            "context and no distinctive anchor - not enough to build a demo worth presenting."
        )
    elif strong_anchor and len(non_generic) >= 2 and distinctive:
        mode = DemoMode.BESPOKE_DEMO
        rationale = (
            "A distinctive anchor plus two or more company-specific (non-generic) public "
            "facts support a demo whose scenario is genuinely built around this business."
        )
    elif non_generic:
        mode = DemoMode.EVIDENCE_BOUND_DEMO
        rationale = (
            "At least one company-specific public fact contextualises the demo, but the "
            "mechanics stay substantially generic."
        )
    else:
        mode = DemoMode.GENERIC_CAPABILITY_DEMO
        rationale = (
            "Only broad category labels are available; the demo shows a generic intake "
            "capability, not a business-specific workflow."
        )

    # --- evidence-derived synthetic option labels (identical to M4) ---
    cat_labels: list[str] = []
    area_labels: list[str] = []
    seen_lbl: set[str] = set()
    for f in facts:
        if f.category in (_INTAKE_SURFACE, _COMMERCIAL_CONTEXT, _SERVICE_AREA_CONTEXT):
            lbl = _option_label(f.sanitized_phrase)
            if not lbl or lbl.lower() in seen_lbl:
                continue
            seen_lbl.add(lbl.lower())
            (area_labels if f.category == _SERVICE_AREA_CONTEXT else cat_labels).append(lbl)
    need_options = (
        (*cat_labels, "other", "unknown")
        if cat_labels
        else ("repair", "maintenance", "replacement_quote", "unknown")
    )
    location_options = (
        (*area_labels, "other", "unknown")
        if area_labels
        else ("north_texas", "central_texas", "gulf_coast", "other", "unknown")
    )

    # --- objective + story (evidence-bound, deterministic) -----------
    name = identity.display_name
    short = _short_name(name)

    def _ref(e: BriefEvidenceItem) -> str:
        if e.quotable:
            return f'"{e.phrase}"'
        return _category_reference(e.category)

    story_bits: list[str] = []
    if any(e.category == _INTAKE_SURFACE for e in evidence):
        intake = next(e for e in evidence if e.category == _INTAKE_SURFACE)
        story_bits.append(f"its public pages present a request path ({_ref(intake)})")
    if any(e.category == _COMMERCIAL_CONTEXT for e in evidence):
        comm = next(e for e in evidence if e.category == _COMMERCIAL_CONTEXT)
        story_bits.append(f"describe commercial HVAC work ({_ref(comm)})")
    if any(e.category == _RESPONSE_COMMITMENT for e in evidence):
        story_bits.append("and the public site carries a published response-time claim")
    if any(e.category == _SERVICE_AVAILABILITY for e in evidence):
        story_bits.append("and the public site carries a service-availability signal")

    observed = (
        "; ".join(story_bits) if story_bits else "its public pages describe commercial HVAC work"
    )

    if mode in (DemoMode.BESPOKE_DEMO, DemoMode.EVIDENCE_BOUND_DEMO):
        central_story = (
            f"{name} publishes a commercial-service intake surface: {observed}. This demo shows "
            f"ONE hypothetical structured intake workflow that could sit behind that public "
            f"request path. It is not a description of how the {short} team works today, and it "
            f"makes no claim about {short}'s actual response performance, staffing, tools, or "
            f"lead handling - those are explicit unknowns."
        )
        objective = (
            f"Demonstrate one possible structured commercial-HVAC intake workflow for {name}, "
            f"built only from the public evidence supplied, without representing it as the "
            f"company's actual internal process or performance."
        )
    else:
        central_story = (
            f"Only broad category labels are available for {name}. This demo shows a GENERIC "
            f"commercial-HVAC intake capability - it is not built around anything specific to "
            f"{short} and must not imply that it is."
        )
        objective = (
            "Demonstrate a generic structured commercial-HVAC intake capability using only "
            "public category evidence, explicitly not a business-specific workflow."
        )

    # --- UNKNOWNs --------------------------------------------------
    unknowns = tuple(
        BriefUnknown(u.component, u.text, u.hard_prohibition) for u in envelope.explicit_unknowns
    )

    # --- workflow (M4 states -> builder steps) --------------------
    workflow = _workflow_steps(sk)

    # --- mock actions --------------------------------------------
    mock_actions = tuple(MockActionSpec(a, label) for a, label in sk.mock_actions)

    # --- required disclosures ------------------------------------
    disclosures = _disclosures(envelope)

    # --- forbidden additions (prohibited_claims + must_not_say + owner list)
    forbidden = _forbidden_additions(envelope)

    # --- retained-but-not-selectable evidence (M4 non-option reasons) ---
    _non_option = {
        _RESPONSE_COMMITMENT: (
            "demo.commercial_hvac.lead_response@3: a published response promise is retained as "
            "context / the demo's story anchor, but is NEVER a selectable dropdown option - a "
            "viewer must not be able to 'select' the business's own published response promise "
            "inside the simulation, and it must never be shown as verified performance."
        ),
        _SERVICE_AVAILABILITY: (
            "demo.commercial_hvac.lead_response@3: a bare availability signal is retained as "
            "context, not a selectable service-need or service-location option; it is an "
            "availability statement, never inbound response / acknowledgement / callback "
            "behaviour."
        ),
    }
    retained_not_selectable: list[tuple[str, str]] = []
    for e in evidence:
        if e.category in _non_option:
            ref = f'"{e.phrase}"' if e.quotable else _category_reference(e.category)
            retained_not_selectable.append((ref, _non_option[e.category]))

    # --- audit appendix (provenance identity only) -------------
    lineage = envelope.source_lineage
    appendix: tuple[tuple[str, str], ...] = (
        ("envelope_sha256", envelope.envelope_sha256),
        ("m2_m5_bundle_sha256", lineage.m2_m5_bundle_sha256),
        ("audit_revision_hash", lineage.audit_revision_hash),
        ("demo_specification_hash", lineage.demo_specification_hash),
        ("scenario_id", sk.scenario_id),
        ("scenario_skeleton_version", sk.version),
        ("state_machine_version", sk.state_machine_version),
        ("question_set_version", sk.question_set_version),
        ("brief_compiler_version", BUILDER_BRIEF_VERSION),
        *((f"policy:{k}", v) for k, v in lineage.policy_versions),
    )

    brief = BuilderBrief(
        brief_version=BUILDER_BRIEF_VERSION,
        compiled_at=now,
        demo_mode=mode,
        mode_rationale=rationale,
        business_display_name=name,
        permitted_hostname=identity.exact_public_hostname,
        identity_rule=" ".join((identity.identity_note or "").split()),
        demo_title=f"{name} - commercial intake workflow (hypothetical simulation)",
        target_use_case="Commercial HVAC inbound service / quote request intake and qualification.",
        demo_objective=objective,
        central_demo_story=central_story,
        licensed_public_evidence=tuple(evidence),
        primary_demo_anchor=primary,
        service_need_options=need_options,
        service_location_options=location_options,
        retained_context_not_selectable=tuple(retained_not_selectable),
        unknowns=unknowns,
        scenario_description=_scenario_description(sk),
        workflow_steps=workflow,
        mock_actions=mock_actions,
        required_disclosures=disclosures,
        forbidden_additions=forbidden,
        ux_presentation_brief=_UX_BRIEF,
        audit_appendix=appendix,
    )
    _assert_within_authority(brief, envelope, sk)
    return brief


# --------------------------------------------------------------------------
# workflow + disclosures + forbidden list
# --------------------------------------------------------------------------

_STEP_META: dict[str, tuple[str, str, str]] = {
    "simulation_notice": (
        "Simulation notice",
        "Persistent, prominent statement that this is a hypothetical simulation, not "
        "operated by or connected to the business. Viewer acknowledges to continue.",
        "Full-bleed notice / modal; must stay visible (header banner) for the whole flow.",
    ),
    "scenario_start": (
        "Scenario introduction",
        "One-screen framing of the hypothetical: a commercial HVAC inbound request is "
        "coming in; the simulation will collect synthetic details and stop at a human handoff.",
        "Hero / intro card with a single primary action.",
    ),
    "service_need": (
        "Service need",
        "Single-choice: which simulated commercial HVAC need matches this scenario. "
        "Options are supplied by this brief; include 'other' and 'unknown'.",
        "Single-select list or segmented control.",
    ),
    "facility_type": (
        "Facility type",
        "Single-choice synthetic commercial facility type (office / retail / warehouse / "
        "hospitality / other / unknown).",
        "Single-select list.",
    ),
    "service_location": (
        "Service location",
        "Single-choice simulated service location. Options are supplied by this brief; "
        "include 'other' and 'unknown'. No service-area promise is made.",
        "Single-select list.",
    ),
    "urgency": (
        "Urgency",
        "Single-choice: routine / urgent / safety_critical / unknown. 'safety_critical' "
        "routes straight to the fixed safety handoff.",
        "Single-select; safety_critical visually distinct.",
    ),
    "equipment_context": (
        "Equipment context",
        "Optional single-choice synthetic equipment context (rooftop_unit / split_system / "
        "chiller / other / unknown). 'unknown' is always acceptable.",
        "Single-select list, skippable.",
    ),
    "contact_preference": (
        "Preview channel",
        "Single-choice simulated follow-up channel (simulated_phone / simulated_email). "
        "NO real contact destination is collected.",
        "Two-option toggle; never a free-text contact field.",
    ),
    "review": (
        "Review",
        "Read-only summary of the synthetic answers so far; viewer confirms or goes back.",
        "Summary list with edit affordances.",
    ),
    "qualification_result": (
        "Qualification summary",
        "Deterministic summary of the simulated qualification. Anything unknown or "
        "out-of-scope routes to human handoff or an out-of-scope close.",
        "Result card.",
    ),
    "human_handoff": (
        "Human handoff",
        "Explicit statement that a real deployment would hand this case to an approved "
        "human review process before any commitment or action. This is the end of the "
        "scripted flow.",
        "Prominent handoff panel; primary action = acknowledge.",
    ),
    "mock_actions": (
        "Simulated actions preview",
        "Show the mock operational actions as PREVIEWS ONLY, each clearly marked "
        "SIMULATED / MOCK_ONLY / NOT_CONNECTED. Nothing is sent, booked, dispatched or updated.",
        "Receipt-style list; each row badged 'MOCK_ONLY'.",
    ),
    "success": (
        "Completion",
        "Close by repeating that nothing was sent, booked, dispatched or updated and that "
        "this was a hypothetical simulation.",
        "Completion panel.",
    ),
    "not_qualified": (
        "Out of scope",
        "Close for cases the simulation does not cover; restate that nothing happened.",
        "Completion panel (neutral).",
    ),
    "safety_handoff": (
        "Safety handoff",
        "Fixed non-business safety message: the simulation cannot evaluate safety-critical "
        "situations; a real deployment would route to an approved human emergency process; "
        "no dispatch or emergency action has occurred. Use the exact supplied wording.",
        "Distinct safety panel; no emergency advice, no phone numbers.",
    ),
    "mock_error": (
        "Simulated error",
        "If a mock action 'fails', show a plain error notice and end; still nothing real happened.",
        "Error notice.",
    ),
    "ended": (
        "Ended",
        "Terminal close state.",
        "Completion panel.",
    ),
}


def _workflow_steps(sk: DemoScenarioSkeleton) -> tuple[WorkflowStep, ...]:
    steps: list[WorkflowStep] = []
    for ordinal, state in enumerate(sk.states, start=1):
        title, desc, hint = _STEP_META.get(
            state.id, (state.id.replace("_", " ").title(), "", state.component)
        )
        steps.append(WorkflowStep(ordinal, state.id, title, desc, hint))
    return tuple(steps)


def _scenario_description(sk: DemoScenarioSkeleton) -> str:
    return (
        f"Fixed M4 scenario '{sk.scenario_id}' ({sk.state_machine_version}). A synthetic "
        "commercial-HVAC inbound inquiry is collected through a bounded, deterministic "
        "state machine, summarised, and handed to a human review step. Handoff is forced "
        "on: " + " / ".join(sk.handoff_conditions) + " Every operational action is "
        "MOCK_ONLY and NOT_CONNECTED. Deployment status: " + sk.deployment_status + "."
    )


def _disclosures(envelope: SemanticEnvelope) -> tuple[DisclosureSpec, ...]:
    out: list[DisclosureSpec] = []
    for d in envelope.required_disclosures:
        meaning = d.canonical_text or (
            f"[unresolved slot] keep the placeholder token {d.placeholder!r} literally; "
            "the brief stays DRAFT_INCOMPLETE until a human resolves it."
        )
        placement = {
            "simulation_disclosure": "Persistent, prominent - visible on every screen.",
            "not_claiming_transition": "Wherever any observation about the business's public "
            "pages appears.",
        }.get(d.slot_kind, "Retain the literal placeholder token; do not render a value.")
        out.append(DisclosureSpec(d.slot_kind, " ".join(meaning.split()), placement))
    demo = envelope.mentionable_demo_facts
    out.append(
        DisclosureSpec(
            "deployment_status",
            demo.deployment_status,
            "State near the simulation notice; integrations are " + demo.integrations + ".",
        )
    )
    return tuple(out)


def _forbidden_additions(envelope: SemanticEnvelope) -> tuple[str, ...]:
    fixed = (
        "fake response-time / acknowledgement / callback metrics",
        "fake ROI / revenue / conversion / savings numbers",
        "fake customer testimonials, reviews, ratings, case studies or endorsements",
        "fake employee or customer names, photos or quotes",
        "fake CRM / integration / vendor logos or names (no ServiceTitan, Housecall, "
        "Jobber, Salesforce, HubSpot, etc. unless a supplied evidence phrase names it)",
        "fake 'connected' / 'live' / 'deployed' / 'production' states or badges",
        "fake dashboards, analytics, KPI tiles or live-data widgets",
        "labels implying this is the business's current or real process",
        "any claim that the business misses, loses or mishandles leads",
        "any claim that the business responds slowly or quickly, on time or late",
        "any claim that the business lacks or under-uses a CRM, automation, dispatcher or staff",
        "any conversion of a service-availability signal (24/7, 24-hour, same-day, emergency) "
        "into a claim about inbound response, acknowledgement or callback behaviour",
        "urgency, scarcity or countdown pressure",
        "any specific number for lead volume, response time, revenue, ROI, conversion or "
        "customer value",
        "any HIGH / LOW / priority / tier / confidence-band language",
        "any statement about the business's location, size, ownership, tenure, revenue or "
        "affiliations beyond the display name and hostname",
    )
    extra = tuple(f"(from M4 authority) {c}" for c in envelope.prohibited_claims)
    must_not = tuple(
        f"(simulation must-not-say) {c}" for c in envelope.mentionable_demo_facts.must_not_say
    )
    # de-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for item in (*fixed, *extra, *must_not):
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return tuple(out)


# --------------------------------------------------------------------------
# fail-closed authority check
# --------------------------------------------------------------------------


class BuilderBriefAuthorityError(Exception):
    """The compiled brief asserts something the M4 authority bundle does not license."""


def _licensed_phrase_text(envelope: SemanticEnvelope) -> str:
    parts: list[str] = []
    for f in envelope.eligible_company_facts:
        parts.append(f.sanitized_phrase)
        parts.append(f.verbatim_source_phrase)
        parts.append(f.usage_rule or "")
    for m in envelope.m3_findings:
        parts.append(m.rendered_text)
        parts.append(m.supporting_excerpt or "")
        parts.append(m.usage_rule or "")
    for i in envelope.allowed_conditional_inferences:
        parts.append(i.text)
        parts.append(i.usage_rule or "")
    for r in envelope.allowed_recommendations:
        parts.append(r.text)
        parts.append(r.usage_rule or "")
    for u in envelope.explicit_unknowns:
        parts.append(u.text)
        parts.append(u.hard_prohibition or "")
    parts.append(envelope.business_identity.display_name)
    parts.append(envelope.business_identity.exact_public_hostname)
    parts.append(envelope.mentionable_demo_facts.deployment_status)
    parts.extend(envelope.mentionable_demo_facts.may_say)
    parts.extend(envelope.mentionable_demo_facts.must_not_say)
    parts.extend(envelope.prohibited_claims)
    return " \n ".join(p.lower() for p in parts if p)


def _business_claim_prose(brief: BuilderBrief) -> str:
    """The compiler-AUTHORED sentences that could smuggle a claim ABOUT THE
    BUSINESS. Envelope-verbatim text (evidence usage notes, disclosure meanings,
    UNKNOWN text) and the fixed scenario scaffolding are pinned separately and
    are not scanned here - only what this module writes itself."""

    chunks = [
        brief.demo_title,
        brief.target_use_case,
        brief.demo_objective,
        brief.central_demo_story,
        brief.mode_rationale,
    ]
    return " \n ".join(c.lower() for c in chunks if c)


def _assert_scaffolding_is_fixed(
    brief: BuilderBrief, envelope: SemanticEnvelope, sk: DemoScenarioSkeleton
) -> None:
    def fail(msg: str) -> None:
        raise BuilderBriefAuthorityError(msg)

    if brief.workflow_steps != _workflow_steps(sk):
        fail("workflow steps drifted from the fixed M4 scenario skeleton")
    if brief.scenario_description != _scenario_description(sk):
        fail("scenario description drifted from the fixed skeleton")
    if brief.mock_actions != tuple(MockActionSpec(a, label) for a, label in sk.mock_actions):
        fail("mock actions drifted from the fixed skeleton")
    if brief.required_disclosures != _disclosures(envelope):
        fail("required disclosures drifted from the envelope")
    if brief.ux_presentation_brief != _UX_BRIEF:
        fail("UX brief drifted from the fixed template")
    if brief.forbidden_additions != _forbidden_additions(envelope):
        fail("forbidden-additions list drifted")


def _assert_within_authority(
    brief: BuilderBrief, envelope: SemanticEnvelope, sk: DemoScenarioSkeleton
) -> None:
    def fail(msg: str) -> None:
        raise BuilderBriefAuthorityError(msg)

    _assert_scaffolding_is_fixed(brief, envelope, sk)
    licensed = _licensed_phrase_text(envelope)
    prose = _business_claim_prose(brief)

    # 1. every evidence item is an exact eligible fact - phrase, verbatim,
    #    strength, category and the envelope's own usage_rule (verbatim).
    by_phrase = {f.sanitized_phrase.strip().lower(): f for f in envelope.eligible_company_facts}
    fact_phrases = {
        p.strip().lower()
        for f in envelope.eligible_company_facts
        for p in (f.sanitized_phrase, f.verbatim_source_phrase)
    }
    for e in brief.licensed_public_evidence:
        if e.phrase.strip().lower() not in fact_phrases:
            fail(f"evidence phrase not an eligible fact: {e.phrase!r}")
        if e.verbatim_phrase.strip().lower() not in fact_phrases:
            fail(f"verbatim phrase not an eligible fact: {e.verbatim_phrase!r}")
        src = by_phrase.get(e.phrase.strip().lower())
        if src is not None:
            if e.strength != src.strength.value or e.category != src.category:
                fail(f"evidence item strength/category diverged from the fact: {e.phrase!r}")
            if e.usage_note != " ".join((src.usage_rule or "").split()):
                fail(f"evidence usage note is not the envelope's own usage_rule: {e.phrase!r}")

    # 2. prose introduces no forbidden token that is not in a licensed phrase
    for tok in set(_WORD.findall(prose)):
        if tok in _FORBIDDEN_UNLESS_LICENSED and tok not in licensed:
            fail(f"brief prose introduces unlicensed term {tok!r}")

    # 3. no digit in prose unless the exact numeric sequence is in a licensed phrase
    for seq in re.findall(r"\d[\d:/.,-]*", prose):
        if seq not in licensed:
            fail(f"brief prose states a number not present in licensed evidence: {seq!r}")

    # 4. every explicit UNKNOWN is carried
    brief_components = {u.component for u in brief.unknowns}
    for u in envelope.explicit_unknowns:
        if u.component not in brief_components:
            fail(f"explicit UNKNOWN dropped: {u.component}")

    # 5. every required disclosure slot is represented
    brief_slots = {d.slot_kind for d in brief.required_disclosures}
    for d in envelope.required_disclosures:
        if d.slot_kind not in brief_slots:
            fail(f"required disclosure dropped: {d.slot_kind}")

    # 6. response-commitment / availability facts: retained, never selectable,
    #    never rendered as response/acknowledgement behaviour
    for e in brief.licensed_public_evidence:
        if e.category in _NON_SELECTABLE_CATEGORIES and e.is_selectable_demo_option:
            fail(f"{e.category} rendered as a selectable simulation option")
        if e.category == _RESPONSE_COMMITMENT and "must not" not in e.usage_note.lower():
            fail("response-commitment evidence lost its published-self-claim caveat")
        if e.category == _SERVICE_AVAILABILITY and "availability" not in e.usage_note.lower():
            fail("service-availability evidence lost its availability caveat")

    # 7. if the envelope HAS a response-commitment fact it must survive
    env_categories = {f.category for f in envelope.eligible_company_facts}
    brief_categories = {e.category for e in brief.licensed_public_evidence}
    for cat in env_categories:
        if cat not in brief_categories:
            fail(f"eligible fact category silently dropped from the brief: {cat}")

    # 7b. evidence-derived option labels are exact fact phrases (M4 base sets
    #     are the only non-evidence values allowed).
    _base_need = {"repair", "maintenance", "replacement_quote", "unknown", "other"}
    _base_loc = {
        "north_texas",
        "central_texas",
        "gulf_coast",
        "other",
        "unknown",
    }
    fact_labels = {
        _option_label(p)
        for f in envelope.eligible_company_facts
        for p in (f.sanitized_phrase, f.verbatim_source_phrase)
    }
    for opt in brief.service_need_options:
        if opt not in _base_need and opt not in fact_labels:
            fail(f"service_need option not an eligible fact label: {opt!r}")
    for opt in brief.service_location_options:
        if opt not in _base_loc and opt not in fact_labels:
            fail(f"service_location option not an eligible fact label: {opt!r}")
    for cat in (_RESPONSE_COMMITMENT, _SERVICE_AVAILABILITY):
        bad = {
            _option_label(f.sanitized_phrase)
            for f in envelope.eligible_company_facts
            if f.category == cat
        }
        if bad & set(brief.service_need_options) or bad & set(brief.service_location_options):
            fail(f"{cat} phrase offered as a selectable option")

    # 8. mock actions: registered set only, marked mock
    registered = {a for a, _ in sk.mock_actions}
    for a in brief.mock_actions:
        if a.action_type not in registered:
            fail(f"unregistered mock action: {a.action_type}")
        if a.marking != "SIMULATED / MOCK_ONLY / NOT_CONNECTED":
            fail(f"mock action not marked MOCK_ONLY: {a.action_type}")

    # 9. strongest eligible anchor retained when one exists
    if envelope.eligible_company_facts and brief.primary_demo_anchor is None:
        fail("evidence present but no primary demo anchor selected")

    # 10. availability signal never paired with response wording in prose
    if _SERVICE_AVAILABILITY in env_categories:
        avail_phrases = [
            f.sanitized_phrase.lower()
            for f in envelope.eligible_company_facts
            if f.category == _SERVICE_AVAILABILITY
        ]
        response_words = ("respond", "response", "acknowledg", "callback", "call back", "reply")
        for ap in avail_phrases:
            for sentence in re.split(r"[.;\n]", prose):
                if ap and ap in sentence and any(w in sentence for w in response_words):
                    fail("service-availability phrase rendered with response wording")

    # 11. generic/thin evidence must not yield a bespoke claim
    _thin = (DemoMode.GENERIC_CAPABILITY_DEMO, DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH)
    if brief.demo_mode in _thin and "built around" in prose and "not built around" not in prose:
        fail("generic/thin evidence produced a bespoke 'built around' claim")

    # 12. RESPONSE_PERFORMANCE is an explicit UNKNOWN: the business-claim prose
    #     must never pair a response verb with a speed/quality qualifier (the
    #     published self-claim phrase can license the individual words, but the
    #     brief must not ASSERT the business responds fast / slow / on time).
    if any(u.component == "RESPONSE_PERFORMANCE" for u in envelope.explicit_unknowns):
        _resp = re.compile(
            r"\b(responds?|responded|answers?|answered|acknowledges?|acknowledged|"
            r"call(?:s|ed)?\s+back|callbacks?|repl(?:y|ies|ied))\b"
        )
        _speed = re.compile(
            r"\b(fast(?:er)?|quick(?:ly)?|slow(?:ly)?|prompt(?:ly)?|immediate(?:ly)?|"
            r"rapid(?:ly)?|minutes?|hours?|seconds?|same[- ]day|timely|on[- ]time|within)\b"
        )
        for sentence in re.split(r"[.;?!\n]", prose):
            if "no claim" in sentence or "unknown" in sentence or "not a" in sentence:
                continue
            if _resp.search(sentence) and _speed.search(sentence):
                fail("brief prose asserts a response-speed / performance claim (UNKNOWN)")


# --------------------------------------------------------------------------
# human-readable renderer: BuilderBrief -> paste-into-Lovable markdown
# --------------------------------------------------------------------------

_MODE_HEADER: dict[DemoMode, str] = {
    DemoMode.BESPOKE_DEMO: (
        "This demo IS meant to feel genuinely built around this specific business, "
        "using the public evidence below - not a generic template with a name pasted on."
    ),
    DemoMode.EVIDENCE_BOUND_DEMO: (
        "This demo is contextualised by the public evidence below, but the workflow "
        "mechanics stay generic. Do not over-claim specificity."
    ),
    DemoMode.GENERIC_CAPABILITY_DEMO: (
        "This demo shows a GENERIC commercial-HVAC intake capability. It is NOT built "
        "around anything specific to this business and must not imply that it is."
    ),
    DemoMode.DEMO_NOT_DISTINCTIVE_ENOUGH: (
        "The public evidence is too thin for a demo worth presenting. Do not build a "
        "bespoke-looking demo from it."
    ),
}


def render_builder_brief_markdown(brief: BuilderBrief) -> str:
    """A product-language brief a human can paste straight into a website/app
    builder. Internal provenance IDs/hashes appear only in the final appendix."""

    b = brief
    lines: list[str] = []
    add = lines.append
    add(f"# Builder brief - {b.demo_title}")
    add("")
    add(f"**Demo mode:** `{b.demo_mode.value}` - {_MODE_HEADER[b.demo_mode]}")
    add("")
    add(
        "> You are a presentation renderer. You decide how this looks and feels. You "
        "do NOT decide what the business does, what systems it uses, how fast it "
        "responds, how it is staffed, or anything about its economics or internal "
        "process. Use ONLY the wording in this brief for any claim, label, disclosure "
        "or workflow copy."
    )
    add("")

    add("## 1. Identity & context")
    add(f"- **Business display name:** {b.business_display_name}")
    add(
        f"- **Permitted reference identity:** {b.permitted_hostname} (display name + hostname only)"
    )
    add(f"- **Identity rule:** {b.identity_rule}")
    add(f"- **Target use case:** {b.target_use_case}")
    add("")

    add("## 2. Demo objective")
    add(b.demo_objective)
    add("")
    add("**Central demo story (use this framing, do not embellish):**")
    add("")
    add(f"> {b.central_demo_story}")
    add("")

    add("## 3. Licensed public evidence (the ONLY facts you may reflect)")
    add("")
    add("| rank | category | strength | phrase | how to use |")
    add("|---|---|---|---|---|")
    for e in b.licensed_public_evidence:
        if not e.is_selectable_demo_option:
            how = "context / story anchor - NEVER a selectable option"
        elif e.category == _SERVICE_AREA_CONTEXT:
            how = "selectable service-location option"
        else:
            how = "selectable service-need option"
        quote = f'"{e.phrase}"' if e.quotable else f"(paraphrase only; do not quote) {e.phrase}"
        add(f"| {e.anchor_rank} | {e.category} | {e.strength} | {quote} | {how} |")
    add("")
    if b.primary_demo_anchor is not None:
        pa = b.primary_demo_anchor
        add(
            f"**Primary anchor:** the `{pa.category}` fact - this is what makes the demo "
            "legitimately relevant. Build the story around it; never upgrade it into a "
            "stronger claim than its strength tier allows."
        )
        add("")
    if b.retained_context_not_selectable:
        add("**Retained as context, NEVER selectable, NEVER shown as performance:**")
        for ref, reason in b.retained_context_not_selectable:
            add(f"- {ref} - {reason}")
        add("")

    add("## 4. UNKNOWN - do not invent")
    add(
        "These are not knowable from public evidence. Do not state, imply, or visually "
        "suggest them:"
    )
    add("")
    for u in b.unknowns:
        line = f"- **{u.component}:** {u.text}"
        if u.hard_prohibition:
            line += f"  \n  _Hard prohibition:_ {u.hard_prohibition}"
        add(line)
    add("")

    add("## 5. Scenario")
    add(b.scenario_description)
    add("")

    add("## 6. Workflow (translate these steps into screens)")
    add("")
    for s in b.workflow_steps:
        add(f"### {s.ordinal}. {s.title}  `[{s.state_id}]`")
        if s.description:
            add(s.description)
        if s.builder_hint:
            add(f"_Presentation hint:_ {s.builder_hint}")
        add("")
    add(f"**Service-need options (exact labels, in order):** {list(b.service_need_options)}")
    add(
        f"**Service-location options (exact labels, in order):** {list(b.service_location_options)}"
    )
    add("")

    add("## 7. Simulated actions (previews only)")
    add("Every action below is a PREVIEW. Nothing is sent, booked, dispatched or updated.")
    add("")
    for a in b.mock_actions:
        add(f'- `{a.action_type}` - "{a.label}" - **{a.marking}**')
    add("")

    add("## 8. Required disclosures (must appear, materially intact)")
    add("")
    for d in b.required_disclosures:
        add(f"- **{d.slot_kind}** - {d.meaning}")
        add(f"  _Placement:_ {d.placement}")
    add("")

    add("## 9. DO NOT ADD (hard negative specification)")
    add("")
    for item in b.forbidden_additions:
        add(f"- {item}")
    add("")

    add("## 10. Look & feel (your call)")
    add(b.ux_presentation_brief)
    add("")

    add("---")
    add("")
    add("## Appendix - provenance (not for the rendered UI)")
    add("")
    add("| key | value |")
    add("|---|---|")
    for k, v in b.audit_appendix:
        add(f"| {k} | `{v}` |")
    add(f"| compiled_at | {b.compiled_at.isoformat()} |")
    add("")
    return "\n".join(lines)
