"""``demo.scenario_skeleton@1`` - the fixed, business-independent M4 scenario.

Owner authorization 2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM". The
``commercial_hvac.inbound_lead_response`` scenario's states, transitions,
question set, mock actions, handoff conditions, proposed integrations,
safeguards and disclosure semantics are identical for every target business -
only the evidence-derived options and statements vary. This module exposes that
skeleton read-only so a downstream deterministic compiler (``demo.builder_brief``)
can translate it into a builder-facing brief WITHOUT recomposing a full
``DemoSpecification`` and WITHOUT changing any M4 composition or QC behaviour.

Nothing here is new truth: every value is re-exported from
``opintel_demo.composition`` or ``opintel_demo.policy``.
"""

from __future__ import annotations

from dataclasses import dataclass

from opintel_demo.composition import (
    APPROVED_DEFINITION,
    COMPONENT_REGISTRY_VERSION,
    DEMO_SCHEMA_VERSION,
    NEUTRAL_THEME,
    QUESTION_SET_VERSION,
    SCENARIO_ID,
    STATE_MACHINE_VERSION,
    DeterministicDemoComposer,
)
from opintel_demo.policy import SAFETY_HANDOFF_MESSAGE

DEMO_SCENARIO_SKELETON_VERSION = "demo.scenario_skeleton@1"

# The six mock operational actions, in workflow order. Every one is
# structurally MOCK_ONLY / NOT_CONNECTED (``opintel_demo.composition`` registers
# them and QC fails closed on any non-mock action).
MOCK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("CREATE_INTAKE_RECORD", "Simulated intake record"),
    ("CREATE_CRM_LEAD", "Simulated CRM lead"),
    ("QUEUE_HUMAN_CALLBACK", "Simulated human callback queue"),
    ("NOTIFY_DISPATCH", "Simulated dispatch notification preview"),
    ("REQUEST_SCHEDULING_REVIEW", "Simulated scheduling review"),
    ("CREATE_ACKNOWLEDGMENT_PREVIEW", "Acknowledgment preview"),
)

# Fixed human/safety handoff conditions (``TechnicalDemoSpecification``).
HANDOFF_CONDITIONS: tuple[str, ...] = (
    "Safety-critical or emergency wording.",
    "Unknown or unsupported qualification data.",
    "Any quote, commitment, booking, availability, scheduling, or dispatch decision.",
)

PROPOSED_INTEGRATIONS: tuple[str, ...] = (
    "CRM - NOT_CONNECTED / MOCK_ONLY",
    "Scheduling - NOT_CONNECTED / MOCK_ONLY",
    "Dispatch - NOT_CONNECTED / MOCK_ONLY",
    "Email/SMS/phone - NOT_CONNECTED / MOCK_ONLY",
)

SAFEGUARDS: tuple[str, ...] = (
    "Persistent anti-impersonation disclosure.",
    "Synthetic input only.",
    "Deterministic registered state transitions.",
    "No external side effects.",
)

DEPLOYMENT_STATUS = "PROPOSED SIMULATION - NOT IMPLEMENTED FOR THE TARGET BUSINESS"

# The base qualification questions that do not depend on company evidence
# (``service_need`` and ``service_location`` gain evidence-derived option labels
# in composition; here we record only their fixed prompt + purpose).
BASE_QUESTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "service_need",
        "Which simulated commercial HVAC need best matches this scenario?",
        "Demonstrate service-intent collection without asserting business policy.",
    ),
    (
        "facility_type",
        "What synthetic commercial facility type is involved?",
        "Demonstrate bounded commercial context collection.",
    ),
    (
        "service_location",
        "Select a simulated service location for this scenario.",
        "Route geography uncertainty to human validation; no service-area promise.",
    ),
    (
        "urgency",
        "How should this simulated request be categorized?",
        "Demonstrate fixed safety handoff without emergency advice.",
    ),
    (
        "equipment_context",
        "What synthetic equipment context is available?",
        "Preserve unknown equipment details.",
    ),
    (
        "contact_preference",
        "Which simulated follow-up channel should the preview show?",
        "Select a preview channel without collecting a destination.",
    ),
)


@dataclass(frozen=True, slots=True)
class ScenarioState:
    id: str
    component: str
    terminal: str


@dataclass(frozen=True, slots=True)
class ScenarioTransition:
    from_state: str
    event: str
    to_state: str
    guard: str
    guard_value: str | None
    mock_action_id: str | None


@dataclass(frozen=True, slots=True)
class DemoScenarioSkeleton:
    version: str
    scenario_id: str
    approved_definition: str
    demo_schema_version: str
    state_machine_version: str
    question_set_version: str
    component_registry_version: str
    neutral_theme: str
    initial_state: str
    maximum_transitions: int
    states: tuple[ScenarioState, ...]
    transitions: tuple[ScenarioTransition, ...]
    base_questions: tuple[tuple[str, str, str], ...]
    mock_actions: tuple[tuple[str, str], ...]
    handoff_conditions: tuple[str, ...]
    proposed_integrations: tuple[str, ...]
    safeguards: tuple[str, ...]
    deployment_status: str
    safety_handoff_message: str


def demo_scenario_skeleton() -> DemoScenarioSkeleton:
    """The fixed ``commercial_hvac.inbound_lead_response`` skeleton, re-derived
    from ``opintel_demo.composition`` statics. Pure; no side effects."""

    states = tuple(
        ScenarioState(node.id, node.components[0].component_type, node.terminal.value)
        for node in DeterministicDemoComposer._states()
    )
    transitions = tuple(
        ScenarioTransition(
            t.from_state, t.event, t.to_state, t.guard, t.guard_value, t.mock_action_id
        )
        for t in DeterministicDemoComposer._transitions()
    )
    return DemoScenarioSkeleton(
        version=DEMO_SCENARIO_SKELETON_VERSION,
        scenario_id=SCENARIO_ID,
        approved_definition=APPROVED_DEFINITION,
        demo_schema_version=DEMO_SCHEMA_VERSION,
        state_machine_version=STATE_MACHINE_VERSION,
        question_set_version=QUESTION_SET_VERSION,
        component_registry_version=COMPONENT_REGISTRY_VERSION,
        neutral_theme=NEUTRAL_THEME,
        initial_state="simulation_notice",
        maximum_transitions=24,
        states=states,
        transitions=transitions,
        base_questions=BASE_QUESTIONS,
        mock_actions=MOCK_ACTIONS,
        handoff_conditions=HANDOFF_CONDITIONS,
        proposed_integrations=PROPOSED_INTEGRATIONS,
        safeguards=SAFEGUARDS,
        deployment_status=DEPLOYMENT_STATUS,
        safety_handoff_message=SAFETY_HANDOFF_MESSAGE,
    )
