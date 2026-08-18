"""Pure deterministic interpreter for approved M4 specifications."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from opintel_demo.composition import REGISTERED_ACTIONS, REGISTERED_EVENTS
from opintel_demo.domain import (
    DemoSpecification,
    DemoValidationError,
    MockActionReceipt,
    MockClassification,
    RuntimeSession,
    RuntimeTerminal,
    SessionState,
)
from opintel_demo.policy import DISCLOSURE_TEMPLATE


class DeterministicDemoRuntime:
    def disclosure(self, business: str) -> str:
        return DISCLOSURE_TEMPLATE.format(business=business)

    def advance(
        self,
        session: RuntimeSession,
        specification: DemoSpecification,
        event: str,
        value: str | None,
    ) -> RuntimeSession:
        if session.state != SessionState.ACTIVE:
            raise DemoValidationError("runtime session is not active")
        if event not in REGISTERED_EVENTS:
            raise DemoValidationError("event is not registered")
        self._validate_value(session.current_state, specification, event, value)
        if session.transition_count >= specification.maximum_transitions:
            raise DemoValidationError("transition bound reached")
        candidates = tuple(
            item
            for item in specification.transitions
            if item.from_state == session.current_state and item.event == event
        )
        selected = next(
            (item for item in candidates if self._matches(item.guard, item.guard_value, value)),
            None,
        )
        if selected is None:
            raise DemoValidationError("event is invalid for the current state")
        receipts = session.receipts
        if selected.mock_action_id is not None:
            action = next(
                (item for item in specification.mock_actions if item.id == selected.mock_action_id),
                None,
            )
            if action is None or action.action_type not in REGISTERED_ACTIONS:
                raise DemoValidationError("mock action is not registered")
            receipt_id = hashlib.sha256(
                f"{session.seed}:{session.persona_id}:{action.id}:{session.transition_count}".encode()
            ).hexdigest()[:20]
            status = "FAILED_MOCK" if event == "mock_failure" else "SIMULATED"
            receipts = (
                *receipts,
                MockActionReceipt(
                    action.id,
                    MockClassification.MOCK_ONLY,
                    status,
                    f"SIM-{receipt_id.upper()}",
                    f"{action.display_label}: {status}. No external system was contacted.",
                ),
            )
        target = next(item for item in specification.states if item.id == selected.to_state)
        state = (
            SessionState.ENDED if target.terminal != RuntimeTerminal.ACTIVE else SessionState.ACTIVE
        )
        return replace(
            session,
            state=state,
            current_state=target.id,
            transition_count=session.transition_count + 1,
            event_history=(*session.event_history, event),
            receipts=receipts,
        )

    @staticmethod
    def _matches(guard: str, expected: str | None, actual: str | None) -> bool:
        if guard == "always":
            return True
        if guard == "equals":
            return actual == expected
        if guard == "not_equals":
            return actual != expected
        return False

    @staticmethod
    def _validate_value(
        state: str,
        specification: DemoSpecification,
        event: str,
        value: str | None,
    ) -> None:
        question_states = {
            "service_need": "service_need",
            "facility_type": "facility_type",
            "service_location": "service_location",
            "urgency": "urgency",
            "equipment_context": "equipment_context",
            "contact_preference": "contact_preference",
        }
        question_id = question_states.get(state)
        if event == "answer" and question_id is not None:
            question = next(item for item in specification.questions if item.id == question_id)
            if value not in question.allowed_values:
                raise DemoValidationError("answer is not an approved synthetic value")
        if (
            state == "qualification_result"
            and event == "continue"
            and value not in {"outside_scope", "review_recommended"}
        ):
            raise DemoValidationError("qualification route is not registered")
