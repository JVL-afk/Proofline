"""Deterministic M4 composition and non-overridable demo QC."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from opintel_audit.domain import ClaimType
from opintel_m0.ports import IdentifierFactory
from opintel_opportunity.domain import CompanyFact, FactCategory

from opintel_demo.domain import (
    ComponentInstance,
    DemoCanonicalInputs,
    DemoInputManifest,
    DemoQcFinding,
    DemoRevision,
    DemoRevisionState,
    DemoSpecification,
    DemoStatementBinding,
    DemoStatementKind,
    DemoStateNode,
    DemoTransition,
    DemoValidity,
    MockActionDefinition,
    MockClassification,
    QcSeverity,
    QualificationQuestion,
    RecordingCue,
    RuntimeTerminal,
    SemanticFactInput,
    ServiceAreaOption,
    ServiceCategoryOption,
    SyntheticPersona,
    TechnicalDemoSpecification,
)
from opintel_demo.policy import SAFETY_HANDOFF_MESSAGE

DEMO_SCHEMA_VERSION = "demo.schema@1"
COMPOSITION_POLICY_VERSION = "demo.commercial_hvac.lead_response@3"
# @3 (2026-09-01): every selected M2 CompanyFact class now reaches M4 as a
# recorded semantic input (``DemoSpecification.semantic_fact_inputs``). Facts the
# demo does not surface as a synthetic option carry an explicit, policy-driven
# ``non_option_reason``; a dropped fact is a hard QC failure.
_NON_OPTION_REASON: dict[str, str] = {
    "response_commitment": (
        "demo.commercial_hvac.lead_response@3: a published response-commitment is "
        "retained in the semantic input set and remains available to M5, but is "
        "not offered as a synthetic dropdown option -- a viewer must not be able "
        "to 'select' the business's own published response promise inside the "
        "simulation."
    ),
    "service_availability": (
        "demo.commercial_hvac.lead_response@3: a bare service-availability signal "
        "is retained as semantic input but is not a synthetic service-need or "
        "service-location option; it is an availability statement, not an intake "
        "or territory choice."
    ),
}
_OPTION_RETENTION: dict[str, str] = {
    "commercial_context": "DEMO_SERVICE_NEED_OPTION",
    "intake_surface": "DEMO_SERVICE_NEED_OPTION",
    "service_area_context": "DEMO_SERVICE_LOCATION_OPTION",
}
COMPONENT_REGISTRY_VERSION = "demo.components@1"
STATE_MACHINE_VERSION = "demo.lead_response.machine@1"
QUESTION_SET_VERSION = "demo.commercial_hvac.questions@2"
_OPTION_FACT_CLASSES = frozenset(
    {"public_inbound_path", "public_service_description", "public_service_area"}
)


def _option_label(phrase: str, limit: int = 48) -> str:
    text = " ".join(phrase.split()).strip().rstrip(".;:,")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].strip()
    return text


SYNTHETIC_DATASET_VERSION = "demo.synthetic_personas@1"
RUNTIME_VERSION = "demo.runtime@1"
SECURITY_PROFILE_VERSION = "demo.security.local_separate_origin@1"
TELEMETRY_POLICY_VERSION = "demo.telemetry.minimal@1"
DISCLAIMER_POLICY_VERSION = "demo.disclosure@1"
QC_POLICY_VERSION = "demo.qc@1"
SCENARIO_ID = "commercial_hvac.inbound_lead_response"
APPROVED_DEFINITION = "commercial_hvac.inbound_lead_response_qualification@1"
NEUTRAL_THEME = "neutral-slate@1"

REGISTERED_COMPONENTS = frozenset(
    {
        "SimulationNotice",
        "ScenarioIntroduction",
        "SingleChoiceQuestion",
        "BoundedTextQuestion",
        "ContactPreferenceQuestion",
        "InputReview",
        "QualificationSummary",
        "HumanHandoffPanel",
        "MockActionReceipt",
        "SafetyHandoffPanel",
        "ErrorNotice",
        "CompletionPanel",
    }
)
REGISTERED_EVENTS = frozenset(
    {
        "acknowledge",
        "start",
        "answer",
        "confirm",
        "continue",
        "handoff_acknowledged",
        "mock_success",
        "mock_failure",
        "finish",
        "end",
    }
)
REGISTERED_GUARDS = frozenset({"always", "equals", "not_equals"})
REGISTERED_ACTIONS = frozenset(
    {
        "CREATE_INTAKE_RECORD",
        "CREATE_CRM_LEAD",
        "QUEUE_HUMAN_CALLBACK",
        "NOTIFY_DISPATCH",
        "REQUEST_SCHEDULING_REVIEW",
        "CREATE_ACKNOWLEDGMENT_PREVIEW",
    }
)
ALLOWED_FACT_PREDICATES = frozenset(
    {
        "business.industry.commercial_hvac_supported",
        "inbound_path.observed",
        "inbound_path.structured_fields",
    }
)
ACTIVE_CONTENT = re.compile(
    r"<\s*/?\s*(?:script|iframe|object|embed|style|form)|javascript:|data:text/html|"
    r"on(?:error|load|click)\s*=|https?://|\beval\s*\(|\bimport\s*\(",
    re.I,
)
PERSONAL_DATA = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})"
)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class DeterministicDemoComposer:
    def __init__(self, identifiers: IdentifierFactory) -> None:
        self._ids = identifiers

    def compose(
        self,
        *,
        demo_id: UUID,
        revision_number: int,
        parent_revision_id: UUID | None,
        source: DemoCanonicalInputs,
        created_by: str,
        now: datetime,
    ) -> DemoRevision:
        manifest = self._manifest(source, now)
        specification = self._specification(source)
        findings = DemoQualityPolicy(self._ids).evaluate(manifest, source, specification)
        hard_failure = any(item.severity == QcSeverity.HARD_FAILURE for item in findings)
        specification_hash = stable_hash(asdict(specification))
        revision_hash = stable_hash(
            {
                "manifest": manifest.checksum,
                "specification": specification_hash,
                "qc": [asdict(item) for item in findings],
            }
        )
        audit = source.audit.revision
        return DemoRevision(
            id=self._ids.new(),
            demo_id=demo_id,
            revision=revision_number,
            parent_revision_id=parent_revision_id,
            workspace_id=audit.workspace_id,
            business_id=audit.business_id,
            opportunity_id=audit.hypothesis_id,
            audit_id=audit.audit_id,
            manifest=manifest,
            specification=specification,
            qc_findings=findings,
            state=DemoRevisionState.QC_FAILED
            if hard_failure
            else DemoRevisionState.REVIEW_REQUIRED,
            validity=DemoValidity.CURRENT,
            specification_hash=specification_hash,
            revision_hash=revision_hash,
            created_by=created_by,
            created_at=now,
        )

    def _manifest(self, source: DemoCanonicalInputs, now: datetime) -> DemoInputManifest:
        audit = source.audit.revision
        opportunity = source.opportunity.hypothesis
        audit_review = source.audit.latest_review
        opportunity_review = source.opportunity.latest_review
        economic = source.opportunity.economic_run
        score = source.opportunity.score_snapshot
        assert opportunity is not None
        assert audit_review is not None and opportunity_review is not None
        assert economic is not None and score is not None
        values = {
            "workspace_id": audit.workspace_id,
            "business_id": audit.business_id,
            "business_profile_hash": source.business_profile_hash,
            "opportunity_id": opportunity.logical_id,
            "opportunity_revision_id": opportunity.id,
            "opportunity_manifest_hash": opportunity.manifest_checksum,
            "opportunity_review_id": opportunity_review.id,
            "opportunity_review_manifest_hash": opportunity_review.manifest_checksum,
            "opportunity_definition_version": opportunity.definition_version,
            "audit_id": audit.audit_id,
            "audit_revision_id": audit.id,
            "audit_revision_hash": audit.revision_hash,
            "audit_manifest_hash": audit.manifest.checksum,
            "audit_review_id": audit_review.id,
            "audit_review_revision_hash": audit_review.revision_hash,
            "audit_qc_policy_version": audit.manifest.qc_policy_version,
            "audit_claim_ids": tuple(item.id for item in audit.claims),
            "evidence_ids": tuple(item.id for item in source.evidence),
            "evidence_fingerprints": tuple(
                f"{item.id}:{item.snapshot_id}:{item.snapshot_version}:{item.source_uri}:"
                f"{item.captured_at.isoformat()}:{item.content_sha256}:{item.locator}:"
                f"{item.extractor_name}:{item.extractor_version}"
                for item in source.evidence
            ),
            "information_gap_ids": tuple(item.id for item in source.opportunity.gaps),
            "assumption_revision_ids": opportunity.assumption_revision_ids,
            "economic_run_id": economic.id,
            "economic_formula_version": economic.formula_version,
            "score_snapshot_id": score.id,
            "score_config_version": score.config_version,
            "demo_schema_version": DEMO_SCHEMA_VERSION,
            "composition_policy_version": COMPOSITION_POLICY_VERSION,
            "component_registry_version": COMPONENT_REGISTRY_VERSION,
            "state_machine_version": STATE_MACHINE_VERSION,
            "question_set_version": QUESTION_SET_VERSION,
            "synthetic_dataset_version": SYNTHETIC_DATASET_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "security_profile_version": SECURITY_PROFILE_VERSION,
            "telemetry_policy_version": TELEMETRY_POLICY_VERSION,
            "disclaimer_policy_version": DISCLAIMER_POLICY_VERSION,
            "qc_policy_version": QC_POLICY_VERSION,
        }
        return DemoInputManifest(
            self._ids.new(),
            audit.workspace_id,
            audit.business_id,
            source.business_profile_hash,
            opportunity.logical_id,
            opportunity.id,
            opportunity.manifest_checksum,
            opportunity_review.id,
            opportunity_review.manifest_checksum,
            opportunity.definition_version,
            audit.audit_id,
            audit.id,
            audit.revision_hash,
            audit.manifest.checksum,
            audit_review.id,
            audit_review.revision_hash,
            audit.manifest.qc_policy_version,
            tuple(item.id for item in audit.claims),
            tuple(item.id for item in source.evidence),
            tuple(
                f"{item.id}:{item.snapshot_id}:{item.snapshot_version}:{item.source_uri}:"
                f"{item.captured_at.isoformat()}:{item.content_sha256}:{item.locator}:"
                f"{item.extractor_name}:{item.extractor_version}"
                for item in source.evidence
            ),
            tuple(item.id for item in source.opportunity.gaps),
            opportunity.assumption_revision_ids,
            economic.id,
            economic.formula_version,
            score.id,
            score.config_version,
            DEMO_SCHEMA_VERSION,
            COMPOSITION_POLICY_VERSION,
            COMPONENT_REGISTRY_VERSION,
            STATE_MACHINE_VERSION,
            QUESTION_SET_VERSION,
            SYNTHETIC_DATASET_VERSION,
            RUNTIME_VERSION,
            SECURITY_PROFILE_VERSION,
            TELEMETRY_POLICY_VERSION,
            DISCLAIMER_POLICY_VERSION,
            QC_POLICY_VERSION,
            stable_hash(values),
            now,
        )

    def _specification(self, source: DemoCanonicalInputs) -> DemoSpecification:
        audit = source.audit.revision
        evidence_ids = {item.id for item in source.evidence}
        statements: list[DemoStatementBinding] = []
        for claim in audit.claims:
            if claim.claim_type != ClaimType.FACT or claim.predicate not in ALLOWED_FACT_PREDICATES:
                continue
            if not claim.evidence_ids or not set(claim.evidence_ids).issubset(evidence_ids):
                continue
            statements.append(
                DemoStatementBinding(
                    self._ids.new(),
                    DemoStatementKind.SOURCE_FACT,
                    claim.display_text,
                    claim.id,
                    claim.claim_type,
                    claim.evidence_ids,
                )
            )
        recommendation = next(
            (item for item in audit.claims if item.claim_type == ClaimType.RECOMMENDATION),
            None,
        )
        statements.append(
            DemoStatementBinding(
                self._ids.new(),
                DemoStatementKind.PROPOSED_WORKFLOW,
                "Proposed workflow: collect synthetic intake details and route the case to an "
                "approved human review process before any commitment or operational action.",
                audit_claim_id=recommendation.id if recommendation else None,
                audit_claim_type=recommendation.claim_type if recommendation else None,
                visibly_conditional=True,
                dependency_claim_ids=recommendation.dependency_claim_ids if recommendation else (),
            )
        )
        personas = (
            SyntheticPersona(
                "facility_manager_avery",
                "Avery Example",
                "Synthetic facility manager",
                "Example Commerce Center",
                "Synthetic Texas region",
                True,
                SYNTHETIC_DATASET_VERSION,
            ),
            SyntheticPersona(
                "property_manager_jordan",
                "Jordan Example",
                "Synthetic property manager",
                "Example Multi-Site Portfolio",
                "Synthetic Texas region",
                True,
                SYNTHETIC_DATASET_VERSION,
            ),
        )
        company_facts: tuple[CompanyFact, ...] = source.opportunity.company_facts
        evidence_id_set = {item.id for item in source.evidence}
        service_categories: list[ServiceCategoryOption] = []
        service_area_context: list[ServiceAreaOption] = []
        provenance: list[tuple[str, UUID]] = []
        semantic_fact_inputs: list[SemanticFactInput] = []
        seen_labels: set[str] = set()
        for fact in company_facts:
            if fact.evidence_id not in evidence_id_set:
                continue
            category = fact.category.value
            rendered_option = False
            if fact.category in (
                FactCategory.COMMERCIAL_CONTEXT,
                FactCategory.INTAKE_SURFACE,
                FactCategory.SERVICE_AREA_CONTEXT,
            ):
                label = _option_label(fact.phrase)
                if label and label.lower() not in seen_labels:
                    if fact.category == FactCategory.SERVICE_AREA_CONTEXT:
                        service_area_context.append(
                            ServiceAreaOption(label, fact.evidence_id, fact.fact_class)
                        )
                    else:
                        service_categories.append(
                            ServiceCategoryOption(label, fact.evidence_id, fact.fact_class)
                        )
                    seen_labels.add(label.lower())
                    provenance.append((label, fact.evidence_id))
                    rendered_option = True
            semantic_fact_inputs.append(
                SemanticFactInput(
                    category=category,
                    phrase=fact.phrase,
                    verbatim_phrase=fact.verbatim_phrase or fact.phrase,
                    evidence_id=fact.evidence_id,
                    fact_class=fact.fact_class,
                    page_purpose=fact.page_purpose,
                    rendered_as_demo_option=rendered_option,
                    retention=(
                        _OPTION_RETENTION[category]
                        if rendered_option
                        else "SEMANTIC_INPUT_RETAINED"
                    ),
                    non_option_reason=(
                        None
                        if rendered_option
                        else _NON_OPTION_REASON.get(
                            category,
                            "demo.commercial_hvac.lead_response@3: retained as semantic "
                            "input; not rendered as a synthetic option.",
                        )
                    ),
                )
            )
        if service_categories:
            need_values: tuple[str, ...] = (
                *(item.label for item in service_categories),
                "other",
                "unknown",
            )
        else:
            need_values = ("repair", "maintenance", "replacement_quote", "unknown")
        if service_area_context:
            location_values: tuple[str, ...] = (
                *(item.label for item in service_area_context),
                "other",
                "unknown",
            )
        else:
            location_values = ("north_texas", "central_texas", "gulf_coast", "other", "unknown")
        questions = (
            QualificationQuestion(
                "service_need",
                "Which simulated commercial HVAC need best matches this scenario?",
                "single_choice",
                need_values,
                True,
                "Demonstrate service-intent collection without asserting business policy.",
            ),
            QualificationQuestion(
                "facility_type",
                "What synthetic commercial facility type is involved?",
                "single_choice",
                ("office", "retail", "warehouse", "hospitality", "other", "unknown"),
                True,
                "Demonstrate bounded commercial context collection.",
            ),
            QualificationQuestion(
                "service_location",
                "Select a simulated service location for this scenario."
                if service_area_context
                else "Select a synthetic Texas service region.",
                "single_choice",
                location_values,
                True,
                "Route geography uncertainty to human validation; no service-area promise.",
            ),
            QualificationQuestion(
                "urgency",
                "How should this simulated request be categorized?",
                "single_choice",
                ("routine", "urgent", "safety_critical", "unknown"),
                True,
                "Demonstrate fixed safety handoff without emergency advice.",
            ),
            QualificationQuestion(
                "equipment_context",
                "What synthetic equipment context is available?",
                "single_choice",
                ("rooftop_unit", "split_system", "chiller", "other", "unknown"),
                False,
                "Preserve unknown equipment details.",
            ),
            QualificationQuestion(
                "contact_preference",
                "Which simulated follow-up channel should the preview show?",
                "simulated_channel",
                ("simulated_phone", "simulated_email"),
                True,
                "Select a preview channel without collecting a destination.",
                False,
            ),
        )
        states = self._states()
        transitions = self._transitions()
        actions = tuple(
            MockActionDefinition(action.lower(), action, MockClassification.MOCK_ONLY, label)
            for action, label in (
                ("CREATE_INTAKE_RECORD", "Simulated intake record"),
                ("CREATE_CRM_LEAD", "Simulated CRM lead"),
                ("QUEUE_HUMAN_CALLBACK", "Simulated human callback queue"),
                ("NOTIFY_DISPATCH", "Simulated dispatch notification preview"),
                ("REQUEST_SCHEDULING_REVIEW", "Simulated scheduling review"),
                ("CREATE_ACKNOWLEDGMENT_PREVIEW", "Acknowledgment preview"),
            )
        )
        cues = tuple(
            RecordingCue(index, state, narration, event)
            for index, (state, narration, event) in enumerate(
                (
                    (
                        "simulation_notice",
                        "Open with the persistent statement that this is a simulation and no "
                        "external action occurs.",
                        "acknowledge",
                    ),
                    (
                        "service_need",
                        "Select a synthetic commercial service need.",
                        "answer",
                    ),
                    (
                        "human_handoff",
                        "Show that a human review is required before any commitment.",
                        "handoff_acknowledged",
                    ),
                    (
                        "mock_actions",
                        "Show structurally mock-only intake, CRM, and acknowledgment previews.",
                        "mock_success",
                    ),
                    (
                        "ended",
                        "Close by repeating that nothing was sent, booked, dispatched, or updated.",
                        None,
                    ),
                ),
                start=1,
            )
        )
        technical = TechnicalDemoSpecification(
            trigger="Synthetic commercial HVAC inbound inquiry.",
            inputs=tuple(item.id for item in questions),
            handoff_conditions=(
                "Safety-critical or emergency wording.",
                "Unknown or unsupported qualification data.",
                "Any quote, commitment, booking, availability, scheduling, or dispatch decision.",
            ),
            proposed_integrations=(
                "CRM — NOT_CONNECTED / MOCK_ONLY",
                "Scheduling — NOT_CONNECTED / MOCK_ONLY",
                "Dispatch — NOT_CONNECTED / MOCK_ONLY",
                "Email/SMS/phone — NOT_CONNECTED / MOCK_ONLY",
            ),
            safeguards=(
                "Persistent anti-impersonation disclosure.",
                "Synthetic input only.",
                "Deterministic registered state transitions.",
                "No external side effects.",
            ),
            deployment_status="PROPOSED SIMULATION — NOT IMPLEMENTED FOR THE TARGET BUSINESS",
        )
        commercial_phrase = next(
            (
                item.label
                for item in service_categories
                if any(
                    fact.category == FactCategory.COMMERCIAL_CONTEXT
                    and _option_label(fact.phrase) == item.label
                    for fact in company_facts
                )
            ),
            None,
        )
        welcome = (
            "This scripted simulation demonstrates a proposed intake workflow for "
            f'{source.business_name} ("{commercial_phrase}").'
            if commercial_phrase
            else "This scripted simulation demonstrates a proposed intake workflow."
        )
        return DemoSpecification(
            DEMO_SCHEMA_VERSION,
            source.business_name,
            NEUTRAL_THEME,
            SCENARIO_ID,
            STATE_MACHINE_VERSION,
            "simulation_notice",
            24,
            tuple(sorted(REGISTERED_COMPONENTS)),
            personas,
            questions,
            states,
            transitions,
            actions,
            tuple(statements),
            (
                ("welcome", welcome),
                ("clarify", "Please choose one of the available synthetic responses."),
                ("handoff", "This simulated case now requires human review."),
            ),
            cues,
            technical,
            tuple(service_categories),
            tuple(service_area_context),
            tuple(provenance),
            tuple(semantic_fact_inputs),
        )

    @staticmethod
    def _states() -> tuple[DemoStateNode, ...]:
        def state(
            state_id: str,
            component: str,
            terminal: RuntimeTerminal = RuntimeTerminal.ACTIVE,
            props: tuple[tuple[str, str], ...] = (),
        ) -> DemoStateNode:
            return DemoStateNode(
                state_id,
                (ComponentInstance(f"{state_id}_component", component, props),),
                terminal,
            )

        return (
            state("simulation_notice", "SimulationNotice"),
            state("scenario_start", "ScenarioIntroduction"),
            state("service_need", "SingleChoiceQuestion"),
            state("facility_type", "SingleChoiceQuestion"),
            state("service_location", "SingleChoiceQuestion"),
            state("urgency", "SingleChoiceQuestion"),
            state("equipment_context", "SingleChoiceQuestion"),
            state("contact_preference", "ContactPreferenceQuestion"),
            state("review", "InputReview"),
            state("qualification_result", "QualificationSummary"),
            state("human_handoff", "HumanHandoffPanel"),
            state("mock_actions", "MockActionReceipt"),
            state("success", "CompletionPanel", RuntimeTerminal.SUCCESSFUL_SIMULATION),
            state("not_qualified", "CompletionPanel", RuntimeTerminal.OUTSIDE_DEMO_SCOPE),
            state(
                "safety_handoff",
                "SafetyHandoffPanel",
                RuntimeTerminal.SAFETY_HANDOFF,
                (("message", SAFETY_HANDOFF_MESSAGE),),
            ),
            state("mock_error", "ErrorNotice", RuntimeTerminal.MOCK_ACTION_FAILED),
            state("ended", "CompletionPanel", RuntimeTerminal.USER_ENDED),
        )

    @staticmethod
    def _transitions() -> tuple[DemoTransition, ...]:
        return (
            DemoTransition("simulation_notice", "acknowledge", "scenario_start"),
            DemoTransition("scenario_start", "start", "service_need"),
            DemoTransition("service_need", "answer", "facility_type"),
            DemoTransition("facility_type", "answer", "service_location"),
            DemoTransition("service_location", "answer", "urgency"),
            DemoTransition("urgency", "answer", "safety_handoff", "equals", "safety_critical"),
            DemoTransition(
                "urgency", "answer", "equipment_context", "not_equals", "safety_critical"
            ),
            DemoTransition("equipment_context", "answer", "contact_preference"),
            DemoTransition("contact_preference", "answer", "review"),
            DemoTransition("review", "confirm", "qualification_result"),
            DemoTransition(
                "qualification_result", "continue", "not_qualified", "equals", "outside_scope"
            ),
            DemoTransition(
                "qualification_result", "continue", "human_handoff", "not_equals", "outside_scope"
            ),
            DemoTransition(
                "human_handoff",
                "handoff_acknowledged",
                "mock_actions",
                mock_action_id="create_intake_record",
            ),
            DemoTransition(
                "mock_actions", "mock_success", "success", mock_action_id="create_crm_lead"
            ),
            DemoTransition(
                "mock_actions", "mock_failure", "mock_error", mock_action_id="create_crm_lead"
            ),
            DemoTransition("success", "finish", "ended"),
            DemoTransition("not_qualified", "finish", "ended"),
            DemoTransition("safety_handoff", "end", "ended"),
            DemoTransition("mock_error", "finish", "ended"),
        )


class DemoQualityPolicy:
    def __init__(self, identifiers: IdentifierFactory) -> None:
        self._ids = identifiers

    def evaluate(
        self,
        manifest: DemoInputManifest,
        source: DemoCanonicalInputs,
        specification: DemoSpecification,
    ) -> tuple[DemoQcFinding, ...]:
        findings: list[DemoQcFinding] = []

        def fail(code: str, message: str) -> None:
            findings.append(DemoQcFinding(self._ids.new(), code, QcSeverity.HARD_FAILURE, message))

        if specification.neutral_theme != NEUTRAL_THEME:
            fail("non_neutral_theme", "Initial M4 requires the neutral registered theme.")
        if set(specification.components) != REGISTERED_COMPONENTS:
            fail("component_registry_mismatch", "Specification component registry is not exact.")
        for state in specification.states:
            if any(item.component_type not in REGISTERED_COMPONENTS for item in state.components):
                fail("unknown_component", "A state references an unregistered component.")
        for transition in specification.transitions:
            if (
                transition.event not in REGISTERED_EVENTS
                or transition.guard not in REGISTERED_GUARDS
            ):
                fail(
                    "unknown_transition", "A transition references an unregistered event or guard."
                )
        for action in specification.mock_actions:
            if (
                action.action_type not in REGISTERED_ACTIONS
                or action.classification != MockClassification.MOCK_ONLY
            ):
                fail("non_mock_action", "Every operational action must be registered MOCK_ONLY.")
        if any(not item.synthetic for item in specification.personas):
            fail("non_synthetic_persona", "Every persona must be explicitly synthetic.")
        if any(item.collects_contact_destination for item in specification.questions):
            fail("contact_collection", "M4 may not collect an operative contact destination.")
        serialized = json.dumps(asdict(specification), sort_keys=True, default=str)
        if ACTIVE_CONTENT.search(serialized):
            fail("active_content", "Active content, code, or external URLs are prohibited.")
        for persona in specification.personas:
            if PERSONAL_DATA.search(f"{persona.display_name} {persona.facility}"):
                fail("personal_data", "Persona content resembles operative contact data.")
        source_claims = {item.id: item for item in source.audit.revision.claims}
        manifest_evidence = set(manifest.evidence_ids)

        option_lineage: list[tuple[UUID, str]] = [
            (item.evidence_id, item.fact_class) for item in specification.service_categories
        ]
        option_lineage.extend(
            (item.evidence_id, item.fact_class) for item in specification.service_area_context
        )
        for evidence_id, fact_class in option_lineage:
            if evidence_id not in manifest_evidence or fact_class not in _OPTION_FACT_CLASSES:
                fail(
                    "unsupported_option_personalization",
                    "A company-derived demo option lacks allowed evidence lineage.",
                )

        # demo.commercial_hvac.lead_response@3: every selected M2 CompanyFact
        # class must reach M4 as a recorded semantic input; a downstream omission
        # from the synthetic options must be an explicit, reasoned decision.
        eligible_fact_evidence = {
            fact.evidence_id
            for fact in source.opportunity.company_facts
            if fact.evidence_id in manifest_evidence
        }
        semantic_input_evidence = {item.evidence_id for item in specification.semantic_fact_inputs}
        if eligible_fact_evidence - semantic_input_evidence:
            fail(
                "company_fact_input_dropped",
                "A selected M2 CompanyFact did not reach M4 as a semantic input; "
                "the strongest eligible fact must not be silently lost.",
            )
        for sfi in specification.semantic_fact_inputs:
            if sfi.evidence_id not in manifest_evidence:
                fail(
                    "semantic_input_outside_manifest",
                    "A semantic fact input lacks manifest evidence lineage.",
                )
            if not sfi.rendered_as_demo_option and not (sfi.non_option_reason or "").strip():
                fail(
                    "semantic_input_missing_reason",
                    "A fact omitted from the synthetic options lacks an explicit "
                    "policy-driven reason.",
                )
        provenance_labels = {label for label, _ in specification.personalization_provenance}
        _SYNTHETIC_OPTION_BASE = {
            "repair",
            "maintenance",
            "replacement_quote",
            "unknown",
            "north_texas",
            "central_texas",
            "gulf_coast",
            "other",
        }
        for question in specification.questions:
            if question.id not in {"service_need", "service_location"}:
                continue
            for value in question.allowed_values:
                if value not in _SYNTHETIC_OPTION_BASE and value not in provenance_labels:
                    fail(
                        "unsupported_option_personalization",
                        "An injected demo option is not bound to accepted evidence provenance.",
                    )

        for statement in specification.statements:
            if statement.kind == DemoStatementKind.SOURCE_FACT:
                claim = (
                    source_claims.get(statement.audit_claim_id)
                    if statement.audit_claim_id is not None
                    else None
                )
                if (
                    claim is None
                    or claim.claim_type != ClaimType.FACT
                    or claim.predicate not in ALLOWED_FACT_PREDICATES
                    or not statement.evidence_ids
                    or not set(statement.evidence_ids).issubset(manifest_evidence)
                ):
                    fail("unsupported_personalization", "A projected fact lacks allowed lineage.")
            elif statement.kind == DemoStatementKind.PROPOSED_WORKFLOW:
                claim = (
                    source_claims.get(statement.audit_claim_id)
                    if statement.audit_claim_id is not None
                    else None
                )
                if (
                    claim is None
                    or claim.claim_type != ClaimType.RECOMMENDATION
                    or not statement.visibly_conditional
                    or not statement.dependency_claim_ids
                    or set(statement.dependency_claim_ids) != set(claim.dependency_claim_ids)
                ):
                    fail(
                        "unsupported_proposed_workflow",
                        "A proposed workflow must retain its recommendation dependencies.",
                    )
        state_ids = {item.id for item in specification.states}
        if specification.initial_state not in state_ids:
            fail("invalid_initial_state", "The initial state is absent.")
        reachable = {specification.initial_state}
        changed = True
        while changed:
            changed = False
            for item in specification.transitions:
                if item.from_state in reachable and item.to_state not in reachable:
                    reachable.add(item.to_state)
                    changed = True
        if state_ids != reachable:
            fail("unreachable_state", "Every state must be reachable from the initial state.")
        terminals = {
            item.terminal
            for item in specification.states
            if item.terminal != RuntimeTerminal.ACTIVE
        }
        required = {
            RuntimeTerminal.SUCCESSFUL_SIMULATION,
            RuntimeTerminal.OUTSIDE_DEMO_SCOPE,
            RuntimeTerminal.SAFETY_HANDOFF,
            RuntimeTerminal.MOCK_ACTION_FAILED,
            RuntimeTerminal.USER_ENDED,
        }
        if not required.issubset(terminals):
            fail("missing_terminal", "Required success, safety, error, and end states are absent.")
        if not any(item.id == "human_handoff" for item in specification.states):
            fail("missing_handoff", "A human handoff state is mandatory.")
        safety = next((item for item in specification.states if item.id == "safety_handoff"), None)
        if (
            safety is None
            or not safety.components
            or dict(safety.components[0].props).get("message") != SAFETY_HANDOFF_MESSAGE
        ):
            fail("safety_handoff_wording", "The fixed non-business safety handoff is mandatory.")
        if specification.maximum_transitions > 24 or specification.maximum_transitions < 1:
            fail("unbounded_state_machine", "Transition bound is invalid.")
        return tuple(findings)
