"""Versioned deterministic rules for the single approved M2 opportunity definition."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from opintel_m0.ports import IdentifierFactory

from opintel_opportunity.domain import (
    AssumptionRevision,
    Band,
    EconomicEffect,
    EvidenceReference,
    FactorResult,
    GapPriority,
    HypothesisStatus,
    InferenceRevision,
    InformationGap,
    MissingBehavior,
    Observation,
    OpportunityHypothesisRevision,
    RevisionStatus,
    ScoreSnapshot,
    ValueState,
)
from opintel_opportunity.economics import checksum

DEFINITION_VERSION = "commercial_hvac.inbound_lead_response_qualification@1"
RULE_VERSION = "commercial_hvac.lead_response.rules@1"
FACTOR_CONFIG_VERSION = "commercial_hvac.lead_response.heuristic_bands@1"

SAFE_STATEMENT = (
    "Public pages show that the business invites commercial HVAC inquiries through observed "
    "digital channels. A structured acknowledgement and qualification workflow could be evaluated "
    "for those channels. Current response performance, internal routing, lead volume, conversion, "
    "feasibility, and economic impact remain unknown pending business verification."
)

ALTERNATIVES = (
    "Existing staff may answer calls or messages promptly.",
    "Existing CRM, answering-service, or routing automation may not be publicly visible.",
    "The public form may route to a well-staffed dispatcher.",
    "Customers may predominantly use phone, referrals, portals, or established-account channels.",
    "The captured website may be stale or incomplete relative to current operations.",
    "A third-party workflow may exist outside the permitted capture scope.",
    "Capacity constraints may make faster intake undesirable at present.",
)

FEASIBILITY_DEPENDENCIES = (
    "Authorized access to applicable inbound channels and routing configuration.",
    "A defined qualification rubric, service area, capacity constraints, and human-handoff policy.",
    "Named operational ownership and after-hours escalation behavior.",
    "Compatible approved form, email, phone, CRM, scheduling, and dispatch interfaces.",
    "Data-minimization, access-control, retention, monitoring, and fallback procedures.",
    "A prohibition on autonomous commitments, quotes, bookings, and unsafe emergency guidance.",
)

GAP_DEFINITIONS = (
    (
        "monthly_inquiries",
        "Applicable monthly inbound inquiry volume is unknown.",
        GapPriority.CRITICAL,
        "DEMAND_VOLUME",
        EconomicEffect.BLOCKS_MODEL,
        "Approximately how many new commercial service or quote inquiries arrive in a typical "
        "month, and through which channels?",
    ),
    (
        "response_performance",
        "Current acknowledgement and response performance is unknown.",
        GapPriority.CRITICAL,
        "RESPONSE_PERFORMANCE",
        EconomicEffect.BLOCKS_MODEL,
        "How are new inquiries acknowledged today, including after hours, and what response "
        "times are typical?",
    ),
    (
        "qualification_rate",
        "The qualified-inquiry definition and rate are unknown.",
        GapPriority.HIGH,
        "QUALIFICATION",
        EconomicEffect.MATERIALLY_CHANGES_MODEL,
        "What makes an inquiry qualified for your team, and roughly what share meet that "
        "definition?",
    ),
    (
        "conversion",
        "Baseline conversion from qualified inquiry to booked work is unknown.",
        GapPriority.CRITICAL,
        "CONVERSION",
        EconomicEffect.BLOCKS_MODEL,
        "Of qualified inquiries, what share typically becomes booked work?",
    ),
    (
        "customer_value",
        "Verified average customer value and value semantics are unknown.",
        GapPriority.CRITICAL,
        "CUSTOMER_VALUE",
        EconomicEffect.BLOCKS_MODEL,
        "What value measure should be used—revenue, gross profit, or contribution—and what range "
        "is typical for applicable work?",
    ),
    (
        "channel_mix_seasonality",
        "Inbound channel mix and seasonality are unknown.",
        GapPriority.HIGH,
        "DEMAND_VOLUME",
        EconomicEffect.MATERIALLY_CHANGES_MODEL,
        "How does inquiry volume vary by phone, email, web form, service area, and season?",
    ),
    (
        "tools_routing",
        "Current intake tools and routing are not publicly verifiable.",
        GapPriority.HIGH,
        "CURRENT_PROCESS",
        EconomicEffect.MATERIALLY_CHANGES_MODEL,
        "Which systems or services currently receive, route, and track new inquiries?",
    ),
    (
        "staffing_handoff",
        "Operational ownership, staffing, and human handoff are unknown.",
        GapPriority.HIGH,
        "FEASIBILITY",
        EconomicEffect.MATERIALLY_CHANGES_MODEL,
        "Who owns first response and qualification, and when must a human take over?",
    ),
    (
        "integration",
        "Authorized integration availability is unknown.",
        GapPriority.HIGH,
        "INTEGRATION",
        EconomicEffect.MATERIALLY_CHANGES_MODEL,
        "Which form, phone, email, CRM, scheduling, and dispatch systems would an approved "
        "workflow need to integrate with?",
    ),
    (
        "cost",
        "Implementation and operating cost constraints are unknown.",
        GapPriority.CRITICAL,
        "COST",
        EconomicEffect.BLOCKS_MODEL,
        "What implementation and ongoing cost constraints should the economic model use?",
    ),
)


def _matching(
    evidence: tuple[EvidenceReference, ...], terms: tuple[str, ...]
) -> list[EvidenceReference]:
    return [item for item in evidence if any(term in item.fragment.lower() for term in terms)]


def detect(
    analysis_run_id: UUID,
    workspace_id: UUID,
    business_id: UUID,
    evidence: tuple[EvidenceReference, ...],
    identifiers: IdentifierFactory,
    now: datetime,
) -> tuple[
    tuple[Observation, ...],
    InferenceRevision | None,
    OpportunityHypothesisRevision | None,
    tuple[InformationGap, ...],
    tuple[AssumptionRevision, ...],
]:
    industry = _matching(evidence, ("commercial hvac", "commercial heating", "commercial cooling"))
    inbound = _matching(
        evidence,
        (
            "request service",
            "request a quote",
            "service request",
            "contact our service",
            "service@example",
            "call ",
        ),
    )
    strong = _matching(evidence, ("company name", "service need", "urgency", "service area"))
    contradiction = _matching(
        evidence,
        ("24/7 staffed dispatch", "instant scheduling", "live qualification", "immediate routing"),
    )
    observations: list[Observation] = []
    for predicate, matches, value in (
        (
            "business.industry.commercial_hvac_supported",
            industry,
            "commercial HVAC publicly described",
        ),
        ("inbound_path.observed", inbound, "public inbound service path observed"),
        ("inbound_path.structured_fields", strong, "public structured intake details observed"),
        (
            "inbound_path.public_counterevidence",
            contradiction,
            "public response capability observed",
        ),
    ):
        for match in matches[:1]:
            observations.append(
                Observation(
                    id=identifiers.new(),
                    workspace_id=workspace_id,
                    business_id=business_id,
                    analysis_run_id=analysis_run_id,
                    evidence_id=match.id,
                    predicate=predicate,
                    value=value,
                    scope="captured public pages only",
                    normalizer_version=RULE_VERSION,
                    created_at=now,
                )
            )
    if not industry or not inbound:
        return tuple(observations), None, None, (), ()
    confidence = Band.LOW if contradiction else Band.HIGH if strong else Band.MEDIUM
    inference = InferenceRevision(
        id=identifiers.new(),
        logical_id=identifiers.new(),
        revision=1,
        analysis_run_id=analysis_run_id,
        statement=(
            "A bounded public inbound path exists; evaluating structured acknowledgement and "
            "qualification may be relevant. No internal response behavior is established."
        ),
        observation_ids=tuple(item.id for item in observations),
        evidence_ids=tuple(item.id for item in (*industry, *inbound, *strong)),
        contradictory_evidence_ids=tuple(item.id for item in contradiction),
        alternatives=ALTERNATIVES,
        rule_version=RULE_VERSION,
        confidence_band=confidence,
        status=RevisionStatus.ACTIVE,
        created_at=now,
    )
    logical_hypothesis_id = identifiers.new()
    gaps = tuple(
        InformationGap(
            id=identifiers.new(),
            hypothesis_id=logical_hypothesis_id,
            gap_type=key,
            description=description,
            priority=priority,
            affected_component=component,
            economic_effect=effect,
            blocks_review_readiness=False,
            suggested_validation_question=question,
            created_at=now,
        )
        for key, description, priority, component, effect, question in GAP_DEFINITIONS
    )
    assumption_specs = (
        ("monthly_inbound_leads", "leads", None, "month"),
        ("affected_share", "ratio", None, "dimensionless"),
        ("conversion_lift", "ratio", None, "dimensionless"),
        ("average_customer_value", "currency_per_win", "USD", "per_win"),
    )
    assumptions = tuple(
        AssumptionRevision(
            id=identifiers.new(),
            hypothesis_id=logical_hypothesis_id,
            key=key,
            revision=1,
            value_state=ValueState.UNKNOWN,
            decimal_value=None,
            unit=unit,
            currency=currency,
            time_basis=time_basis,
            source_kind="UNKNOWN",
            provenance=None,
            created_by="deterministic-rules",
            created_at=now,
        )
        for key, unit, currency, time_basis in assumption_specs
    )
    placeholder = identifiers.new()
    basis = {
        "definition": DEFINITION_VERSION,
        "observations": [str(item.id) for item in observations],
        "inference": str(inference.id),
        "evidence": [str(item.id) for item in evidence],
    }
    hypothesis = OpportunityHypothesisRevision(
        id=identifiers.new(),
        logical_id=logical_hypothesis_id,
        revision=1,
        workspace_id=workspace_id,
        business_id=business_id,
        analysis_run_id=analysis_run_id,
        definition_version=DEFINITION_VERSION,
        statement=SAFE_STATEMENT,
        status=HypothesisStatus.NEEDS_INFORMATION
        if contradiction
        else HypothesisStatus.READY_FOR_REVIEW,
        observation_ids=tuple(item.id for item in observations),
        inference_revision_ids=(inference.id,),
        supporting_evidence_ids=tuple(
            dict.fromkeys(item.id for item in (*industry, *inbound, *strong))
        ),
        contradictory_evidence_ids=tuple(item.id for item in contradiction),
        alternative_explanations=ALTERNATIVES,
        feasibility_dependencies=FEASIBILITY_DEPENDENCIES,
        assumption_revision_ids=tuple(item.id for item in assumptions),
        economic_run_id=placeholder,
        score_snapshot_id=placeholder,
        manifest_checksum=checksum(basis),
        created_by="deterministic-rules",
        created_at=now,
    )
    return tuple(observations), inference, hypothesis, gaps, assumptions


def score_snapshot(
    score_id: UUID,
    hypothesis: OpportunityHypothesisRevision,
    economic_status: str,
    has_structured_support: bool,
    now: datetime,
) -> ScoreSnapshot:
    contradicted = bool(hypothesis.contradictory_evidence_ids)
    evidence_band = Band.LOW if contradicted or not has_structured_support else Band.HIGH
    confidence_band = Band.LOW if contradicted else evidence_band
    factors = (
        FactorResult(
            "evidence_strength",
            evidence_band,
            MissingBehavior.LOWER_BAND,
            "Direct public HVAC and inbound-path evidence; scoped to captured pages.",
        ),
        FactorResult(
            "hypothesis_confidence",
            confidence_band,
            MissingBehavior.LOWER_BAND,
            "Deterministic predicate match with explicit contradiction handling.",
        ),
        FactorResult(
            "potential_value",
            Band.UNKNOWN,
            MissingBehavior.INCOMPLETE,
            f"Economic status is {economic_status}; no calibrated value bands exist.",
        ),
        FactorResult(
            "implementation_feasibility",
            Band.UNKNOWN,
            MissingBehavior.CAP_BAND,
            "Internal systems, ownership, access, and handoff are unknown.",
        ),
        FactorResult(
            "business_fit",
            Band.HIGH,
            MissingBehavior.BLOCK,
            "Public evidence supports the Commercial HVAC definition.",
        ),
        FactorResult(
            "important_unknowns",
            Band.HIGH,
            MissingBehavior.CAP_BAND,
            "Critical business-specific economic and process inputs remain unknown.",
        ),
    )
    priority = "HIGH" if has_structured_support and not contradicted else "LOW"
    return ScoreSnapshot(
        id=score_id,
        hypothesis_id=hypothesis.logical_id,
        config_version=FACTOR_CONFIG_VERSION,
        factors=factors,
        review_priority_band=priority,
        manifest_checksum=checksum(
            {"hypothesis": hypothesis.manifest_checksum, "factors": factors, "priority": priority}
        ),
        created_at=now,
    )
