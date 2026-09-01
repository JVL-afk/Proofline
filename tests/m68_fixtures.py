"""Frozen M6.8 semantic-envelope fixtures for A-Plus, Elite, and E+M.

Grounded in the exact sealed Slot 07/18/21 M1 evidence (the same values in
``tests/fixtures/personalization_v2_slots07_21_sealed_evidence.json``). These are
immutable frozen fixtures: no historical Slot artifact is mutated.

* A-Plus  - strong ``RESPONSE_COMMITMENT`` ("fast response times"), plus intake +
  commercial + a genuine service-area heading.
* Elite   - intake + commercial + service-area + a ``SERVICE_AVAILABILITY``
  signal (leading "*" sanitised); NO response commitment.
* E+M     - only generic public labels; expected
  ``COMMUNICATION_NOT_DISTINCTIVE_ENOUGH``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from opintel_communication.domain import (
    BusinessIdentity,
    ConditionalInference,
    EconomicsState,
    M3FindingRef,
    Recommendation,
    ReferenceArtifacts,
    SemanticEnvelope,
    SourceLineage,
)
from opintel_communication.envelope import assemble_envelope
from opintel_opportunity.domain import CompanyFact, FactCategory

_NS = UUID("00000000-0000-4000-8000-0000000068a1")
_NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _uid(tag: str) -> UUID:
    return uuid5(_NS, tag)


def _cf(
    tag: str,
    category: FactCategory,
    phrase: str,
    fact_class: str,
    page_purpose: str,
    verbatim: str | None = None,
) -> CompanyFact:
    return CompanyFact(
        id=_uid(tag),
        hypothesis_id=_uid("hyp"),
        category=category,
        phrase=phrase,
        evidence_id=_uid(tag + ":ev"),
        fact_class=fact_class,
        page_purpose=page_purpose,
        source_uri="https://example.com/" + page_purpose,
        content_sha256="a" * 64,
        selector_version="commercial_hvac.company_fact_selector@3",
        created_at=_NOW,
        verbatim_phrase=verbatim or phrase,
    )


def _lineage(tag: str) -> SourceLineage:
    return SourceLineage(
        workspace_id=_uid("ws"),
        business_id=_uid(tag + ":biz"),
        research_run_id=_uid(tag + ":run"),
        opportunity_hypothesis_revision_id=_uid(tag + ":hyprev"),
        audit_revision_id=_uid(tag + ":aud"),
        audit_revision_hash="b" * 64,
        demo_revision_id=_uid(tag + ":demo"),
        demo_specification_hash="c" * 64,
        outreach_revision_id=_uid(tag + ":out"),
        outreach_content_hash="d" * 64,
        m2_m5_bundle_sha256="a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7",
        policy_versions=(
            ("company_fact_selector", "commercial_hvac.company_fact_selector@3"),
            ("phrase_sanitation", "commercial_hvac.phrase_sanitation@1"),
            ("demo_composition", "demo.commercial_hvac.lead_response@3"),
            ("outreach_projection", "outreach.projection@4"),
            ("outreach_qc", "outreach.qc@3"),
        ),
    )


_ECONOMICS = EconomicsState(
    status="insufficient_data",
    result_label="insufficient data — required business inputs are unknown",
    external_use_permitted=False,
    usage_rule=(
        "Economics are internal-only and INSUFFICIENT. Claude MUST NOT mention any figure, "
        "range, estimate, percentage, or monetary benefit."
    ),
)

_INFERENCE = ConditionalInference(
    inference_id="inf-opportunity",
    text=(
        "The approved public evidence may support evaluating an inbound acknowledgement and "
        "qualification opportunity; internal performance remains unknown."
    ),
    required_qualifiers=("may", "remains unknown"),
    usage_rule=(
        "Claude MAY express this idea in natural language; the conditionality ('may', 'could', "
        "'appears') and the explicit unknown MUST be preserved."
    ),
)

_RECOMMENDATION = Recommendation(
    recommendation_id="rec-structured-acknowledgement",
    text="A step that acknowledges and sorts new service requests could be evaluated.",
    required_qualifiers=("could", "evaluated"),
    dependency_finding_ids=("f-intake", "f-commercial"),
    usage_rule=(
        "Claude MAY phrase this as an offer to compare a simulated intake step with the real "
        "process. MUST remain conditional. MUST NOT assert the business needs it or lacks it."
    ),
)

_UNKNOWN_FINDING = M3FindingRef(
    finding_id="f-unknown",
    kind="what_remains_unknown",
    claim_type="FACT",
    predicate=None,
    rendered_text=(
        "What remains unknown: internal response performance, routing, lead volume, conversion, "
        "and verified customer value are not publicly observable (blocking gaps: CONVERSION, COST, "
        "CUSTOMER_VALUE, DEMAND_VOLUME, RESPONSE_PERFORMANCE)."
    ),
    supporting_excerpt=None,
    evidence_ids=(),
    usage_rule="Claude may acknowledge this uncertainty; may not resolve it.",
)

_COVERAGE_FINDING = M3FindingRef(
    finding_id="f-coverage",
    kind="crawl_coverage",
    claim_type="FACT",
    predicate=None,
    rendered_text="Crawl coverage: partial; absence of a fact may reflect incomplete capture.",
    supporting_excerpt=None,
    evidence_ids=(),
    usage_rule="Claude MUST NOT claim completeness.",
)


def _observed_finding(fid: str, kind: str, predicate: str, excerpt: str, text: str) -> M3FindingRef:
    return M3FindingRef(
        finding_id=fid,
        kind=kind,
        claim_type="FACT",
        predicate=predicate,
        rendered_text=text,
        supporting_excerpt=excerpt,
        evidence_ids=(),
        usage_rule="Claude may rely on the finding text as licensed; may not extend it.",
    )


# --------------------------------------------------------------------------
# A-Plus
# --------------------------------------------------------------------------

_APLUS_INTAKE = "When to Schedule AC Replacement"
_APLUS_COMMERCIAL = "Commercial Air Conditioning Repairs"
_APLUS_RESPONSE = (
    "Austin homeowners choose us for flat-rate pricing, fast response times, and technicians "
    "registered with the State of Texas."
)
_APLUS_AREA = "Service Area"

_APLUS_REFERENCE = ReferenceArtifacts(
    subject="A question about commercial service-request intake",
    first_contact_email=(
        "Hello {{functional_role_or_team}},\n\n"
        'your website has a public request path — "When to Schedule AC Replacement".\n\n'
        'your site describes commercial HVAC work — "Commercial Air Conditioning Repairs".\n\n'
        "a step that acknowledges and sorts new service requests could be evaluated.\n\n"
        "This is not a claim about how your team works today — we have no visibility into that.\n\n"
        "We prepared a short deterministic simulation based only on approved public "
        "information.\n\n"
        "It is a simulation—not a system deployed, connected, official, or operated by the "
        "business.\n\n"
        'I noticed your site offers "When to Schedule AC Replacement". I\'m curious — roughly how '
        "many commercial inquiries arrive in a typical month, and how after-hours ones are handled "
        "today?\n\n"
        "{{verified_sender_signature}}\n\n{{required_postal_disclosure}}\n\n"
        "{{approved_opt_out_instruction}}"
    ),
    follow_up_draft='I noticed your site offers "When to Schedule AC Replacement". ...',
    call_opening_script="{{truthful_verified_sender_introduction}} ...",
    note="Semantic floor and fallback; Claude is not asked to rewrite these.",
)


def aplus_envelope(candidate_count: int = 3) -> SemanticEnvelope:
    facts = (
        _cf(
            "f-intake",
            FactCategory.INTAKE_SURFACE,
            _APLUS_INTAKE,
            "public_inbound_path",
            "request_service_scheduling",
        ),
        _cf(
            "f-commercial",
            FactCategory.COMMERCIAL_CONTEXT,
            _APLUS_COMMERCIAL,
            "public_service_description",
            "commercial_hvac",
        ),
        _cf(
            "f-response",
            FactCategory.RESPONSE_COMMITMENT,
            _APLUS_RESPONSE,
            "public_inbound_path",
            "heating",
        ),
        _cf(
            "f-area",
            FactCategory.SERVICE_AREA_CONTEXT,
            _APLUS_AREA,
            "public_service_area",
            "service_area_location",
        ),
    )
    rendered = frozenset({str(facts[0].id), str(facts[1].id)})
    omission = {
        str(facts[2].id): (
            "outreach.projection@4: the fixed first-contact frame renders only the first two "
            "ordered facts; recorded as an intentional omission, not dropped."
        ),
        str(facts[3].id): "outreach.projection@4: thin fact, not rendered in the first contact.",
    }
    findings = (
        _observed_finding(
            "f-intake",
            "observed_intake_surface",
            "finding.intake_surface",
            _APLUS_INTAKE,
            f"Observed intake surface: the captured public pages present a request path "
            f'("{_APLUS_INTAKE}").',
        ),
        _observed_finding(
            "f-commercial",
            "observed_commercial_context",
            "finding.commercial_context",
            _APLUS_COMMERCIAL,
            f"Observed commercial-service context: the captured public pages describe commercial "
            f'HVAC work ("{_APLUS_COMMERCIAL}").',
        ),
        _observed_finding(
            "f-response",
            "observed_response_commitment",
            "finding.response_commitment",
            _APLUS_RESPONSE,
            "Observed response commitment: the captured contact page states how inbound inquiries "
            f'are answered or returned ("{_APLUS_RESPONSE}").',
        ),
        _observed_finding(
            "f-area",
            "observed_service_area",
            "finding.service_area_context",
            _APLUS_AREA,
            f"Observed service-area context: the captured public pages list a service area "
            f'("{_APLUS_AREA}").',
        ),
        _UNKNOWN_FINDING,
        _COVERAGE_FINDING,
    )
    return assemble_envelope(
        generated_at=_NOW,
        source_lineage=_lineage("aplus"),
        business_identity=BusinessIdentity(
            display_name="A-Plus Air Conditioning & Home Solutions",
            name_tokens=("A-Plus", "Air", "Conditioning", "Home", "Solutions"),
            exact_public_hostname="www.aplusac.com",
            identity_note=(
                "Display name and hostname are the only identity assertions permitted. No "
                "inferred location, size, ownership, tenure, or affiliation."
            ),
        ),
        company_facts=facts,
        rendered_fact_ids=rendered,
        deterministic_omission_by_fact_id=omission,
        m3_findings=findings,
        conditional_inferences=(_INFERENCE,),
        recommendations=(_RECOMMENDATION,),
        economics=_ECONOMICS,
        available_validation_questions=(
            "Approximately how many new commercial service or quote inquiries arrive in a typical "
            "month, and through which channels?",
            "How are new inquiries acknowledged today, including after hours, and what response "
            "times are typical?",
        ),
        reference_artifacts=_APLUS_REFERENCE,
        candidate_count=candidate_count,
    )


# --------------------------------------------------------------------------
# Elite
# --------------------------------------------------------------------------

_ELITE_INTAKE = "Need to schedule a service call?"
_ELITE_COMMERCIAL = "Commercial HVAC Services"
_ELITE_AREA = "Just a Sample of Our Service Areas"
_ELITE_AVAIL = "About Our 24-Hour Service"
_ELITE_AVAIL_VERBATIM = "*About Our 24-Hour Service"

_ELITE_REFERENCE = ReferenceArtifacts(
    subject="A question about commercial service-request intake",
    first_contact_email=(
        "Hello {{functional_role_or_team}},\n\n"
        'your website has a public request path — "Need to schedule a service call?".\n\n'
        'your site describes commercial HVAC work — "Commercial HVAC Services".\n\n'
        "a step that acknowledges and sorts new service requests could be evaluated.\n\n"
        "This is not a claim about how your team works today — we have no visibility into that.\n\n"
        "We prepared a short deterministic simulation based only on approved public "
        "information.\n\n"
        "It is a simulation—not a system deployed, connected, official, or operated by the "
        "business.\n\n"
        'I noticed your site offers "Need to schedule a service call?". I\'m curious — roughly how '
        "many commercial inquiries arrive in a typical month, and how after-hours ones are handled "
        "today?\n\n"
        "{{verified_sender_signature}}\n\n{{required_postal_disclosure}}\n\n"
        "{{approved_opt_out_instruction}}"
    ),
    follow_up_draft="...",
    call_opening_script="...",
    note="Semantic floor and fallback.",
)


def elite_envelope(candidate_count: int = 3) -> SemanticEnvelope:
    facts = (
        _cf(
            "e-intake",
            FactCategory.INTAKE_SURFACE,
            _ELITE_INTAKE,
            "public_inbound_path",
            "contact_mechanism",
        ),
        _cf(
            "e-commercial",
            FactCategory.COMMERCIAL_CONTEXT,
            _ELITE_COMMERCIAL,
            "public_service_description",
            "commercial_hvac",
        ),
        _cf(
            "e-area",
            FactCategory.SERVICE_AREA_CONTEXT,
            _ELITE_AREA,
            "public_service_area",
            "contact_mechanism",
        ),
        _cf(
            "e-avail",
            FactCategory.SERVICE_AVAILABILITY,
            _ELITE_AVAIL,
            "public_other",
            "contact_mechanism",
            verbatim=_ELITE_AVAIL_VERBATIM,
        ),
    )
    rendered = frozenset({str(facts[0].id), str(facts[1].id)})
    omission = {
        str(facts[2].id): "outreach.projection@4: not in the first-contact frame.",
        str(facts[3].id): (
            "demo.commercial_hvac.lead_response@3: a bare availability signal is retained as "
            "semantic input but not rendered as an option or in the first contact."
        ),
    }
    findings = (
        _observed_finding(
            "e-intake",
            "observed_intake_surface",
            "finding.intake_surface",
            _ELITE_INTAKE,
            f"Observed intake surface: the captured public pages present a request path "
            f'("{_ELITE_INTAKE}").',
        ),
        _observed_finding(
            "e-commercial",
            "observed_commercial_context",
            "finding.commercial_context",
            _ELITE_COMMERCIAL,
            f"Observed commercial-service context: the captured public pages describe commercial "
            f'HVAC work ("{_ELITE_COMMERCIAL}").',
        ),
        _observed_finding(
            "e-area",
            "observed_service_area",
            "finding.service_area_context",
            _ELITE_AREA,
            f"Observed service-area context: the captured public pages list a service area "
            f'("{_ELITE_AREA}").',
        ),
        _observed_finding(
            "e-avail",
            "observed_service_availability",
            "finding.service_availability",
            _ELITE_AVAIL,
            "Observed service availability: the captured public pages reference round-the-clock or "
            f'emergency service availability ("{_ELITE_AVAIL}"). This is an availability signal, '
            "not a statement of inbound response or acknowledgement behaviour.",
        ),
        _UNKNOWN_FINDING,
        _COVERAGE_FINDING,
    )
    return assemble_envelope(
        generated_at=_NOW,
        source_lineage=_lineage("elite"),
        business_identity=BusinessIdentity(
            display_name="Elite Air Conditioning & Plumbing",
            name_tokens=("Elite", "Air", "Conditioning", "Plumbing"),
            exact_public_hostname="eliteaustinac.com",
            identity_note="Display name and hostname only.",
        ),
        company_facts=facts,
        rendered_fact_ids=rendered,
        deterministic_omission_by_fact_id=omission,
        m3_findings=findings,
        conditional_inferences=(_INFERENCE,),
        recommendations=(_RECOMMENDATION,),
        economics=_ECONOMICS,
        available_validation_questions=(
            "Approximately how many new commercial service or quote inquiries arrive in a typical "
            "month, and through which channels?",
            "How are new inquiries acknowledged today, including after hours, and what response "
            "times are typical?",
        ),
        reference_artifacts=_ELITE_REFERENCE,
        candidate_count=candidate_count,
    )


# --------------------------------------------------------------------------
# E+M (weak)
# --------------------------------------------------------------------------

_EM_REFERENCE = ReferenceArtifacts(
    subject="A note about the E+M Emergency Air Conditioning service path",
    first_contact_email=(
        "Hello {{functional_role_or_team}},\n\n"
        'your website has a public request path — "Request Service".\n\n'
        'your site describes commercial HVAC work — "Commercial AC".\n\n'
        "a step that acknowledges and sorts new service requests could be evaluated.\n\n"
        "This is not a claim about how your team works today — we have no visibility into that.\n\n"
        "We prepared a short deterministic simulation based only on approved public "
        "information.\n\n"
        "It is a simulation—not a system deployed, connected, official, or operated by the "
        "business.\n\n"
        'I noticed your site offers "Request Service". I\'m curious — roughly how many commercial '
        "inquiries arrive in a typical month, and how after-hours ones are handled today?\n\n"
        "{{verified_sender_signature}}\n\n{{required_postal_disclosure}}\n\n"
        "{{approved_opt_out_instruction}}"
    ),
    follow_up_draft="...",
    call_opening_script="...",
    note="Semantic floor and fallback.",
)


def em_envelope(candidate_count: int = 3) -> SemanticEnvelope:
    facts = (
        _cf(
            "m-intake",
            FactCategory.INTAKE_SURFACE,
            "Request Service",
            "public_inbound_path",
            "request_service_scheduling",
        ),
        _cf(
            "m-commercial",
            FactCategory.COMMERCIAL_CONTEXT,
            "Commercial AC",
            "public_service_description",
            "commercial_hvac",
        ),
        _cf(
            "m-area",
            FactCategory.SERVICE_AREA_CONTEXT,
            "Service Areas",
            "public_service_area",
            "request_service_scheduling",
        ),
    )
    rendered = frozenset({str(facts[0].id), str(facts[1].id)})
    findings = (
        _observed_finding(
            "m-intake",
            "observed_intake_surface",
            "finding.intake_surface",
            "Request Service",
            "Observed intake surface: the captured public pages present a request path "
            '("Request Service").',
        ),
        _observed_finding(
            "m-commercial",
            "observed_commercial_context",
            "finding.commercial_context",
            "Commercial AC",
            "Observed commercial-service context: the captured public pages describe commercial "
            'HVAC work ("Commercial AC").',
        ),
        _observed_finding(
            "m-area",
            "observed_service_area",
            "finding.service_area_context",
            "Service Areas",
            "Observed service-area context: the captured public pages list a service area "
            '("Service Areas").',
        ),
        _UNKNOWN_FINDING,
        _COVERAGE_FINDING,
    )
    return assemble_envelope(
        generated_at=_NOW,
        source_lineage=_lineage("em"),
        business_identity=BusinessIdentity(
            display_name="E+M Emergency Air Conditioning",
            name_tokens=("E", "M", "Emergency", "Air", "Conditioning"),
            exact_public_hostname="www.emergencyac.org",
            identity_note="Display name and hostname only.",
        ),
        company_facts=facts,
        rendered_fact_ids=rendered,
        deterministic_omission_by_fact_id={
            str(facts[2].id): "outreach.projection@4: not in the first-contact frame."
        },
        m3_findings=findings,
        conditional_inferences=(_INFERENCE,),
        recommendations=(_RECOMMENDATION,),
        economics=_ECONOMICS,
        available_validation_questions=(
            "Approximately how many new commercial service or quote inquiries arrive in a typical "
            "month, and through which channels?",
        ),
        reference_artifacts=_EM_REFERENCE,
        candidate_count=candidate_count,
    )
