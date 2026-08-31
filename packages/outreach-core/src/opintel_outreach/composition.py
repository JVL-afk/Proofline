"""Deterministic M5 projection, artifact composition, and non-overridable QC."""

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
from opintel_opportunity.personalization import (
    is_reader_specific,
    reader_fact_sentence,
    short_phrase,
)

from opintel_outreach.domain import (
    ArtifactAudience,
    ArtifactKind,
    ArtifactSegment,
    FollowUpUsability,
    InternalEconomicContext,
    OutreachArtifact,
    OutreachCanonicalInputs,
    OutreachClaimProjection,
    OutreachInputManifest,
    OutreachQcFinding,
    OutreachRevision,
    OutreachRevisionState,
    OutreachRisk,
    OutreachValidationQuestion,
    OutreachValidity,
    PersonalizationAssessment,
    ProjectionDisposition,
    ProjectionMode,
    QcSeverity,
    SegmentKind,
    TargetRole,
    TargetRoleSelection,
)

_FRAME_STOPWORDS = frozenset(
    {
        "your",
        "site",
        "offers",
        "describes",
        "covers",
        "has",
        "the",
        "and",
        "for",
        "new",
        "public",
        "request",
        "path",
        "contact",
        "page",
        "publishes",
        "response",
        "expectations",
        "inquiries",
        "work",
        "lists",
        "service",
        "area",
        "website",
        "with",
        "that",
        "this",
        "from",
    }
)
_WORD = re.compile(r"[A-Za-z]{3,}")


def _unresolved_slot_kinds(artifacts: tuple[OutreachArtifact, ...]) -> tuple[str, ...]:
    kinds: set[str] = set()
    for artifact in artifacts:
        if artifact.audience != ArtifactAudience.EXTERNAL:
            continue
        for segment in artifact.segments:
            if str(segment.kind) in _REQUIRED_SLOT_KINDS and _PLACEHOLDER.search(segment.text):
                kinds.add(str(segment.kind))
    return tuple(sorted(kinds))


def _assess_personalization(
    source: OutreachCanonicalInputs,
    projections: tuple[OutreachClaimProjection, ...],
    artifacts: tuple[OutreachArtifact, ...],
) -> PersonalizationAssessment:
    excerpt_by_evidence = {item.id: item.bounded_excerpt.lower() for item in source.evidence}
    fact_class_by_evidence = {
        fact.evidence_id: fact.fact_class for fact in source.opportunity.company_facts
    }
    projection_by_id = {item.id: item for item in projections}
    business_tokens = {token.lower() for token in _WORD.findall(source.business_name)}
    email = next(
        (item for item in artifacts if item.kind == ArtifactKind.FIRST_CONTACT_EMAIL), None
    )
    specific_evidence: list[UUID] = []
    fact_classes: set[str] = set()
    if email is not None:
        for segment in email.segments:
            if segment.kind != SegmentKind.BOUND_CLAIM or segment.projection_id is None:
                continue
            projection = projection_by_id.get(segment.projection_id)
            if projection is None or projection.mode != ProjectionMode.EVIDENCE_DERIVED_FACT:
                continue
            if not projection.evidence_ids:
                continue
            residual = {
                token.lower()
                for token in _WORD.findall(segment.text)
                if token.lower() not in _FRAME_STOPWORDS and token.lower() not in business_tokens
            }
            for evidence_id in projection.evidence_ids:
                excerpt = excerpt_by_evidence.get(evidence_id, "")
                if residual and any(token in excerpt for token in residual):
                    specific_evidence.append(evidence_id)
                    if evidence_id in fact_class_by_evidence:
                        fact_classes.add(fact_class_by_evidence[evidence_id])
                    break
    return PersonalizationAssessment(
        company_specific_segment_count=len(specific_evidence),
        distinct_fact_classes=len(fact_classes),
        rendered_evidence_ids=tuple(specific_evidence),
        passes_gate=len(specific_evidence) >= 1,
    )

OUTREACH_SCHEMA_VERSION = "outreach.schema@1"
TEMPLATE_VERSION = "commercial_hvac.lead_response.outreach.v3"
PROJECTION_POLICY_VERSION = "outreach.projection@2"
TARGET_ROLE_POLICY_VERSION = "outreach.roles.commercial_hvac@1"
CTA_POLICY_VERSION = "outreach.permission_cta@2"
QC_POLICY_VERSION = "outreach.qc@2"
APPROVED_DEFINITION = "commercial_hvac.inbound_lead_response_qualification@1"
CTA = (
    "Would it be useful to compare the simulation with your actual process and decide whether "
    "the idea is relevant?"
)
# EVIDENCE_PRESERVING_PERSONALIZATION_V2: plain-English rendering of the internal
# recommendation for reader-facing text. Semantics preserved; qualifier retained.
READER_RECOMMENDATION = (
    "a step that acknowledges and sorts new service requests could be evaluated."
)
NOT_CLAIMING = (
    "This is not a claim about how your team works today — we have no visibility into that."
)
_SCORE_LEAK = re.compile(
    r"\b(?:high|low)\b[^.]{0,40}\b(?:priority|confidence|band)\b|priority band|review priority",
    re.I,
)
_REQUIRED_SLOT_KINDS = frozenset(
    {
        "verified_sender_slot",
        "required_postal_disclosure_slot",
        "approved_opt_out_instruction_slot",
    }
)
_PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")
SIMULATION_DISCLOSURE = (
    "It is a simulation—not a system deployed, connected, official, or operated by the business."
)


_CTA_QUESTION_HEAD = {
    "DEMAND_VOLUME": "roughly how many commercial inquiries arrive in a typical month",
    "RESPONSE_PERFORMANCE": "how after-hours ones are handled today",
}


def _derived_cta(
    company_facts: tuple[CompanyFact, ...], safe_components: tuple[str, ...]
) -> str:
    """Deterministic plain-English discovery CTA anchored on the already-safe
    demand-volume / response-performance questions. Falls back to the generic
    CTA when no company fact anchors it."""

    specific = [
        _clause(fact) for fact in company_facts if is_reader_specific(fact.category, fact.phrase)
    ]
    heads = [_CTA_QUESTION_HEAD[c] for c in safe_components if c in _CTA_QUESTION_HEAD]
    if not specific or not heads:
        return CTA
    tail = heads[0] if len(heads) == 1 else f"{heads[0]}, and {heads[1]}"
    return f"I noticed {specific[0]}. I'm curious — {tail}?"


_CATEGORY_RANK = {
    FactCategory.INTAKE_SURFACE: 0,
    FactCategory.COMMERCIAL_CONTEXT: 1,
    FactCategory.SERVICE_AREA_CONTEXT: 2,
    FactCategory.RESPONSE_COMMITMENT: 3,
}


def _ordered_company_facts(facts: tuple[CompanyFact, ...]) -> tuple[CompanyFact, ...]:
    """Reader-specific (quotable, digit-free) facts first, then response-commitment.
    Prefer two distinct fact_class among the first two."""

    reader = [f for f in facts if is_reader_specific(f.category, f.phrase)]
    other = [f for f in facts if not is_reader_specific(f.category, f.phrase)]
    reader.sort(key=lambda f: (_CATEGORY_RANK[f.category], str(f.evidence_id)))
    other.sort(key=lambda f: (_CATEGORY_RANK[f.category], str(f.evidence_id)))
    ordered = reader + other
    if len(ordered) >= 3 and ordered[0].fact_class == ordered[1].fact_class:
        for index in range(2, len(ordered)):
            if ordered[index].fact_class != ordered[0].fact_class:
                ordered[1], ordered[index] = ordered[index], ordered[1]
                break
    return tuple(ordered)


def _clause(fact: CompanyFact) -> str:
    value = short_phrase(fact.phrase, 7)
    if fact.category == FactCategory.INTAKE_SURFACE:
        return f'your site offers "{value}"'
    if fact.category == FactCategory.COMMERCIAL_CONTEXT:
        return f'your site describes "{value}"'
    return f'your site covers "{value}"'


_GENERIC_SUBJECT = "A question about commercial service-request intake"


def _subject(business_name: str, company_facts: tuple[CompanyFact, ...]) -> str:
    if company_facts:
        candidate = f"A note about the {business_name} service path"
        if len(candidate) <= 60:
            return candidate
    return _GENERIC_SUBJECT
FOLLOW_UP_PRECONDITION = (
    "A human must verify outside M5 that a lawful first contact was actually sent through an "
    "approved future process."
)
ROLE_PRIORITY = (
    TargetRole.SERVICE_OPERATIONS_LEAD,
    TargetRole.COMMERCIAL_SERVICE_LEAD,
    TargetRole.DISPATCH_OR_INTAKE_LEAD,
    TargetRole.OWNER_OR_EXECUTIVE,
    TargetRole.BUSINESS_DEVELOPMENT_LEAD,
    TargetRole.UNKNOWN_RELEVANT_ROLE,
)
FACT_PRIORITY = (
    "inbound_path.observed",
    "business.industry.commercial_hvac_supported",
    "inbound_path.structured_fields",
)
FACT_WORDING = {
    "inbound_path.observed": (
        "The public website invites commercial HVAC service or quote inquiries through an "
        "observed contact path."
    ),
    "business.industry.commercial_hvac_supported": (
        "Approved public evidence identifies commercial HVAC services."
    ),
    "inbound_path.structured_fields": (
        "The observed public request path asks for structured service-request details."
    ),
}
FINANCIAL_EXTERNAL = re.compile(
    r"(?:[$€£]|\b\d+(?:\.\d+)?\s*(?:%|percent|usd|dollars?|leads?|hours?|minutes?)\b|"
    r"\b(?:roi|revenue|savings?|lost revenue|conversion rate|lead volume|customer value)\b)",
    re.I,
)
PERSONAL_CONTACT = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})"
)
ACTIVE_OR_EXTERNAL = re.compile(
    r"(?:https?://|mailto:|javascript:|<\s*/?\s*(?:script|iframe|object|embed|form)|"
    r"on(?:error|load|click)\s*=|\beval\s*\(|\bimport\s*\()",
    re.I,
)
PROHIBITED = re.compile(
    r"(?:you(?:r team)? (?:miss|lose|responds? slowly)|no crm|without a crm|no automation|"
    r"manual process|manual workflow|understaffed|requested (?:this|the) (?:audit|demo)|"
    r"thanks for (?:requesting|speaking|meeting)|referred by|customer testimonial|case study|"
    r"limited time|act now|urgent opportunity|deployed (?:for|at)|live at|official (?:demo|system)|"
    r"ignore (?:all |the )?(?:previous|prior) instructions|system message|prompt injection)",
    re.I,
)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class DeterministicOutreachComposer:
    def __init__(self, identifiers: IdentifierFactory, *, select_second_fact: bool = False) -> None:
        self._ids = identifiers
        self._select_second_fact = select_second_fact

    def compose(
        self,
        *,
        package_id: UUID,
        revision_number: int,
        parent_revision_id: UUID | None,
        source: OutreachCanonicalInputs,
        created_by: str,
        now: datetime,
    ) -> OutreachRevision:
        opportunity = source.opportunity
        hypothesis = opportunity.hypothesis
        economic = opportunity.economic_run
        score = opportunity.score_snapshot
        if hypothesis is None or economic is None or score is None:
            raise ValueError("complete canonical M2 lineage is required")
        manifest = self._manifest(source, now)
        projections = self._projections(source)
        role = TargetRoleSelection(
            ROLE_PRIORITY[0],
            1,
            "Suggested functional audience for service-intake workflow evaluation; "
            "not an employment assertion.",
            False,
            "NO_PERSON_IDENTIFIED",
        )
        questions = tuple(
            OutreachValidationQuestion(
                item.id,
                str(item.priority),
                item.affected_component,
                str(item.economic_effect),
                item.suggested_validation_question,
                index < 2,
            )
            for index, item in enumerate(opportunity.gaps)
        )
        risks = self._risks(source)
        economic_context = InternalEconomicContext(
            str(economic.status),
            economic.formula_version,
            economic.result_label,
            tuple((item.id, item.key, str(item.value_state)) for item in opportunity.assumptions),
            economic.monthly_potential_incremental_revenue,
            economic.annualized_potential_incremental_revenue,
            economic.currency,
            False,
        )
        artifacts = self._artifacts(source, projections, questions, risks, economic_context)
        personalization = _assess_personalization(source, projections, artifacts)
        unresolved = _unresolved_slot_kinds(artifacts)
        findings = OutreachQualityPolicy(self._ids).evaluate(
            manifest,
            source,
            projections,
            artifacts,
            role,
            questions,
            risks,
            economic_context,
            personalization,
        )
        if any(item.severity == QcSeverity.HARD_FAILURE for item in findings):
            state = OutreachRevisionState.QC_FAILED
        elif unresolved:
            state = OutreachRevisionState.DRAFT_INCOMPLETE
        else:
            state = OutreachRevisionState.READY_FOR_REVIEW
        content_hash = stable_hash([asdict(item) for item in artifacts])
        body = {
            "manifest": manifest.checksum,
            "role": asdict(role),
            "projections": [asdict(item) for item in projections],
            "artifacts": [asdict(item) for item in artifacts],
            "questions": [asdict(item) for item in questions],
            "risks": [asdict(item) for item in risks],
            "economic_context": asdict(economic_context),
            "personalization": asdict(personalization),
            "unresolved_slot_kinds": list(unresolved),
            "content_hash": content_hash,
        }
        return OutreachRevision(
            self._ids.new(),
            package_id,
            revision_number,
            parent_revision_id,
            hypothesis.workspace_id,
            hypothesis.business_id,
            hypothesis.logical_id,
            source.audit.revision.audit_id,
            source.demo.revision.demo_id,
            manifest,
            role,
            projections,
            artifacts,
            questions,
            risks,
            economic_context,
            findings,
            state,
            OutreachValidity.CURRENT,
            content_hash,
            stable_hash(body),
            created_by,
            now,
            personalization,
            unresolved,
        )

    def _manifest(self, source: OutreachCanonicalInputs, now: datetime) -> OutreachInputManifest:
        demo = source.demo
        audit = source.audit
        opportunity = source.opportunity
        hypothesis = opportunity.hypothesis
        economic = opportunity.economic_run
        score = opportunity.score_snapshot
        assert hypothesis and economic and score and opportunity.latest_review
        assert audit.latest_review and demo.latest_review
        values = {
            "workspace_id": hypothesis.workspace_id,
            "business_id": hypothesis.business_id,
            "business_profile_hash": source.business_profile_hash,
            "opportunity_revision_id": hypothesis.id,
            "opportunity_manifest_hash": hypothesis.manifest_checksum,
            "opportunity_review_id": opportunity.latest_review.id,
            "opportunity_review_manifest_hash": opportunity.latest_review.manifest_checksum,
            "audit_revision_id": audit.revision.id,
            "audit_revision_hash": audit.revision.revision_hash,
            "audit_manifest_hash": audit.revision.manifest.checksum,
            "audit_review_id": audit.latest_review.id,
            "demo_revision_id": demo.revision.id,
            "demo_revision_hash": demo.revision.revision_hash,
            "demo_manifest_hash": demo.revision.manifest.checksum,
            "demo_specification_hash": demo.revision.specification_hash,
            "demo_review_id": demo.latest_review.id,
            "evidence_ids": tuple(item.id for item in source.evidence),
            "evidence_fingerprints": tuple(
                f"{item.id}:{item.snapshot_version}:{item.content_sha256}:{item.freshness}"
                for item in source.evidence
            ),
            "information_gap_ids": tuple(item.id for item in opportunity.gaps),
            "assumption_revision_ids": hypothesis.assumption_revision_ids,
            "economic_run_id": economic.id,
            "economic_formula_version": economic.formula_version,
            "score_snapshot_id": score.id,
            "score_config_version": score.config_version,
            "outreach_schema_version": OUTREACH_SCHEMA_VERSION,
            "template_version": TEMPLATE_VERSION,
            "projection_policy_version": PROJECTION_POLICY_VERSION,
            "target_role_policy_version": TARGET_ROLE_POLICY_VERSION,
            "cta_policy_version": CTA_POLICY_VERSION,
            "qc_policy_version": QC_POLICY_VERSION,
        }
        return OutreachInputManifest(
            self._ids.new(),
            hypothesis.workspace_id,
            hypothesis.business_id,
            source.business_profile_hash,
            hypothesis.id,
            hypothesis.manifest_checksum,
            opportunity.latest_review.id,
            opportunity.latest_review.manifest_checksum,
            audit.revision.id,
            audit.revision.revision_hash,
            audit.revision.manifest.checksum,
            audit.latest_review.id,
            demo.revision.id,
            demo.revision.revision_hash,
            demo.revision.manifest.checksum,
            demo.revision.specification_hash,
            demo.latest_review.id,
            tuple(item.id for item in source.evidence),
            tuple(
                f"{item.id}:{item.snapshot_version}:{item.content_sha256}:{item.freshness}"
                for item in source.evidence
            ),
            tuple(item.id for item in opportunity.gaps),
            hypothesis.assumption_revision_ids,
            economic.id,
            economic.formula_version,
            score.id,
            score.config_version,
            OUTREACH_SCHEMA_VERSION,
            TEMPLATE_VERSION,
            PROJECTION_POLICY_VERSION,
            TARGET_ROLE_POLICY_VERSION,
            CTA_POLICY_VERSION,
            QC_POLICY_VERSION,
            stable_hash(values),
            now,
        )

    def _projections(self, source: OutreachCanonicalInputs) -> tuple[OutreachClaimProjection, ...]:
        claims = source.audit.revision.claims
        projections: list[OutreachClaimProjection] = []
        company_facts = _ordered_company_facts(source.opportunity.company_facts)
        if company_facts:
            for fact in company_facts[:2]:
                claim = next(
                    (
                        item
                        for item in claims
                        if item.claim_type == ClaimType.FACT
                        and item.predicate == f"finding.{fact.category.value}"
                        and fact.evidence_id in item.evidence_ids
                    ),
                    None,
                )
                if claim is None:
                    continue
                projections.append(
                    OutreachClaimProjection(
                        self._ids.new(),
                        claim.id,
                        str(claim.claim_type),
                        ProjectionMode.EVIDENCE_DERIVED_FACT,
                        ProjectionDisposition.EXTERNAL_ALLOWED,
                        reader_fact_sentence(source.business_name, fact.category, fact.phrase),
                        claim.evidence_ids,
                        claim.observation_ids,
                        claim.inference_revision_ids,
                        contradictory_evidence_ids=claim.contradictory_evidence_ids,
                    )
                )
        else:
            facts = sorted(
                (
                    item
                    for item in claims
                    if item.claim_type == ClaimType.FACT and item.predicate in FACT_WORDING
                ),
                key=lambda item: FACT_PRIORITY.index(item.predicate),
            )
            selected_facts = facts[: 2 if self._select_second_fact else 1]
            projections.extend(
                OutreachClaimProjection(
                    self._ids.new(),
                    item.id,
                    str(item.claim_type),
                    ProjectionMode.DIRECT_FACT_RESTATEMENT,
                    ProjectionDisposition.EXTERNAL_ALLOWED,
                    FACT_WORDING[item.predicate],
                    item.evidence_ids,
                    item.observation_ids,
                    item.inference_revision_ids,
                    contradictory_evidence_ids=item.contradictory_evidence_ids,
                )
                for item in selected_facts
            )
        scoped_absence = next(
            (
                item
                for item in claims
                if item.claim_type == ClaimType.FACT
                and item.predicate.endswith(".not_observed_in_scope")
            ),
            None,
        )
        if scoped_absence is not None:
            projections.append(
                OutreachClaimProjection(
                    self._ids.new(),
                    scoped_absence.id,
                    str(scoped_absence.claim_type),
                    ProjectionMode.SCOPED_ABSENCE,
                    ProjectionDisposition.EXTERNAL_ALLOWED,
                    (
                        "The captured public pages did not describe acknowledgement or routing. "
                        "That scoped observation does not establish how the business operates "
                        "internally."
                    ),
                    scoped_absence.evidence_ids,
                    scoped_absence.observation_ids,
                    contradictory_evidence_ids=scoped_absence.contradictory_evidence_ids,
                    required_qualifiers=("captured public pages", "does not establish"),
                )
            )
        inference = next(
            (
                item
                for item in claims
                if item.claim_type == ClaimType.INFERENCE
                and item.predicate == "m2.opportunity_hypothesis"
            ),
            None,
        )
        if inference is not None:
            projections.append(
                OutreachClaimProjection(
                    self._ids.new(),
                    inference.id,
                    str(inference.claim_type),
                    ProjectionMode.CONDITIONAL_INFERENCE,
                    ProjectionDisposition.EXTERNAL_ALLOWED,
                    (
                        "The approved public evidence may support evaluating an inbound "
                        "acknowledgement and qualification opportunity; internal performance "
                        "remains unknown."
                    ),
                    inference.evidence_ids,
                    inference.observation_ids,
                    inference.inference_revision_ids,
                    contradictory_evidence_ids=inference.contradictory_evidence_ids,
                    required_qualifiers=("may", "remains unknown"),
                )
            )
        recommendation = next(
            (item for item in claims if item.claim_type == ClaimType.RECOMMENDATION), None
        )
        if recommendation is not None:
            projections.append(
                OutreachClaimProjection(
                    self._ids.new(),
                    recommendation.id,
                    str(recommendation.claim_type),
                    ProjectionMode.CONDITIONAL_RECOMMENDATION,
                    ProjectionDisposition.EXTERNAL_ALLOWED,
                    (
                        READER_RECOMMENDATION
                        if company_facts
                        else (
                            "A structured acknowledgement and qualification workflow could be "
                            "evaluated for that public request path."
                        )
                    ),
                    dependency_claim_ids=recommendation.dependency_claim_ids,
                    required_qualifiers=("could", "evaluated"),
                )
            )
        for item in claims:
            if item.claim_type == ClaimType.ESTIMATE:
                projections.append(
                    OutreachClaimProjection(
                        self._ids.new(),
                        item.id,
                        str(item.claim_type),
                        ProjectionMode.ECONOMIC_CONTEXT_INTERNAL_ONLY,
                        ProjectionDisposition.INTERNAL_ONLY,
                        item.display_text,
                        assumption_revision_ids=item.assumption_revision_ids,
                        economic_run_id=item.economic_run_id,
                    )
                )
        return tuple(projections)

    def _risks(self, source: OutreachCanonicalInputs) -> tuple[OutreachRisk, ...]:
        hypothesis = source.opportunity.hypothesis
        assert hypothesis is not None
        risks = [
            OutreachRisk(
                self._ids.new(),
                "material_contradiction",
                "Approved lineage contains contradictory public evidence; external claims must "
                "not conflict with it.",
                hypothesis.contradictory_evidence_ids,
                "QUALIFY_OR_EXCLUDE",
            )
            for _ in hypothesis.contradictory_evidence_ids[:1]
        ]
        risks.extend(
            OutreachRisk(
                self._ids.new(),
                "alternative_explanation",
                text,
                hypothesis.inference_revision_ids,
                "INTERNAL_VISIBLE",
            )
            for text in hypothesis.alternative_explanations
        )
        return tuple(risks)

    def _artifacts(
        self,
        source: OutreachCanonicalInputs,
        projections: tuple[OutreachClaimProjection, ...],
        questions: tuple[OutreachValidationQuestion, ...],
        risks: tuple[OutreachRisk, ...],
        economic: InternalEconomicContext,
    ) -> tuple[OutreachArtifact, ...]:
        facts = [
            item
            for item in projections
            if item.mode
            in {ProjectionMode.EVIDENCE_DERIVED_FACT, ProjectionMode.DIRECT_FACT_RESTATEMENT}
            and item.disposition == ProjectionDisposition.EXTERNAL_ALLOWED
        ]
        recommendation = next(
            (
                item
                for item in projections
                if item.mode == ProjectionMode.CONDITIONAL_RECOMMENDATION
            ),
            None,
        )
        company_facts = source.opportunity.company_facts
        safe_questions = tuple(item for item in questions if item.safe_for_first_contact)[:2]
        cta_text = _derived_cta(
            company_facts, tuple(item.affected_component for item in safe_questions)
        )
        subject = _subject(source.business_name, company_facts)
        email_segments = [
            ArtifactSegment(
                self._ids.new(), SegmentKind.SALUTATION, "Hello {{functional_role_or_team}},"
            ),
        ]
        email_segments.extend(
            ArtifactSegment(self._ids.new(), SegmentKind.BOUND_CLAIM, item.rendered_text, item.id)
            for item in facts
        )
        if recommendation:
            email_segments.append(
                ArtifactSegment(
                    self._ids.new(),
                    SegmentKind.BOUND_CLAIM,
                    recommendation.rendered_text,
                    recommendation.id,
                )
            )
        if company_facts:
            email_segments.append(
                ArtifactSegment(self._ids.new(), SegmentKind.TRANSITION, NOT_CLAIMING)
            )
        email_segments.extend(
            (
                ArtifactSegment(
                    self._ids.new(),
                    SegmentKind.TRANSITION,
                    "We prepared a short deterministic simulation based only on approved public "
                    "information.",
                ),
                ArtifactSegment(
                    self._ids.new(), SegmentKind.SIMULATION_DISCLOSURE, SIMULATION_DISCLOSURE
                ),
                ArtifactSegment(self._ids.new(), SegmentKind.CTA, cta_text),
                ArtifactSegment(
                    self._ids.new(),
                    SegmentKind.VERIFIED_SENDER_SLOT,
                    "{{verified_sender_signature}}",
                ),
                ArtifactSegment(
                    self._ids.new(),
                    SegmentKind.REQUIRED_POSTAL_DISCLOSURE_SLOT,
                    "{{required_postal_disclosure}}",
                ),
                ArtifactSegment(
                    self._ids.new(),
                    SegmentKind.APPROVED_OPT_OUT_INSTRUCTION_SLOT,
                    "{{approved_opt_out_instruction}}",
                ),
            )
        )
        first_body = "\n\n".join(item.text for item in email_segments)
        followup_segments = (
            ArtifactSegment(
                self._ids.new(),
                SegmentKind.TRANSITION,
                "This optional follow-up may be used only after a human verifies the required "
                "external precondition.",
            ),
            ArtifactSegment(self._ids.new(), SegmentKind.CTA, cta_text),
            ArtifactSegment(
                self._ids.new(), SegmentKind.VERIFIED_SENDER_SLOT, "{{verified_sender_signature}}"
            ),
            ArtifactSegment(
                self._ids.new(),
                SegmentKind.REQUIRED_POSTAL_DISCLOSURE_SLOT,
                "{{required_postal_disclosure}}",
            ),
            ArtifactSegment(
                self._ids.new(),
                SegmentKind.APPROVED_OPT_OUT_INSTRUCTION_SLOT,
                "{{approved_opt_out_instruction}}",
            ),
        )
        call_segments = (
            ArtifactSegment(
                self._ids.new(),
                SegmentKind.VERIFIED_SENDER_SLOT,
                "{{truthful_verified_sender_introduction}}",
            ),
            ArtifactSegment(
                self._ids.new(),
                SegmentKind.TRANSITION,
                "Is now an appropriate time for a brief question?",
            ),
            ArtifactSegment(
                self._ids.new(), SegmentKind.BOUND_CLAIM, facts[0].rendered_text, facts[0].id
            ),
            ArtifactSegment(
                self._ids.new(), SegmentKind.SIMULATION_DISCLOSURE, SIMULATION_DISCLOSURE
            ),
            ArtifactSegment(self._ids.new(), SegmentKind.CTA, cta_text),
        )
        question_text = "\n".join(f"- {item.wording}" for item in safe_questions)
        risk_text = "\n".join(f"- [{item.kind}] {item.description}" for item in risks) or (
            "No material contradiction was present in the approved source manifest."
        )
        economic_text = json.dumps(asdict(economic), sort_keys=True, default=str)
        prep_text = (
            f"Business: {source.business_name}\n"
            "Target: functional role only; NO_PERSON_IDENTIFIED.\n"
            "Do not claim the audit/demo was requested or the simulation is deployed.\n"
            f"Validation questions:\n{question_text}"
        )

        def artifact(
            kind: ArtifactKind,
            audience: ArtifactAudience,
            title: str,
            segments: tuple[ArtifactSegment, ...],
            rendered: str,
            usability: FollowUpUsability | None = None,
            precondition: str | None = None,
        ) -> OutreachArtifact:
            return OutreachArtifact(
                self._ids.new(),
                kind,
                audience,
                title,
                segments,
                rendered,
                stable_hash({"kind": kind, "audience": audience, "text": rendered}),
                usability,
                precondition,
            )

        return (
            artifact(
                ArtifactKind.SUBJECT,
                ArtifactAudience.EXTERNAL,
                "Subject",
                (ArtifactSegment(self._ids.new(), SegmentKind.TRANSITION, subject),),
                subject,
            ),
            artifact(
                ArtifactKind.FIRST_CONTACT_EMAIL,
                ArtifactAudience.EXTERNAL,
                "First-contact email",
                tuple(email_segments),
                first_body,
            ),
            artifact(
                ArtifactKind.FOLLOW_UP_DRAFT,
                ArtifactAudience.EXTERNAL,
                "Conditional follow-up draft",
                followup_segments,
                "\n\n".join(item.text for item in followup_segments),
                FollowUpUsability.CONDITIONALLY_USABLE,
                FOLLOW_UP_PRECONDITION,
            ),
            artifact(
                ArtifactKind.CALL_OPENING_SCRIPT,
                ArtifactAudience.EXTERNAL,
                "Call-opening script",
                call_segments,
                "\n\n".join(item.text for item in call_segments),
            ),
            artifact(
                ArtifactKind.VALIDATION_QUESTIONS,
                ArtifactAudience.EXTERNAL,
                "Permission-oriented validation questions",
                (ArtifactSegment(self._ids.new(), SegmentKind.TRANSITION, question_text),),
                question_text,
            ),
            artifact(
                ArtifactKind.INTERNAL_CALL_PREP,
                ArtifactAudience.INTERNAL,
                "Internal call-preparation notes",
                (ArtifactSegment(self._ids.new(), SegmentKind.INTERNAL_CONTEXT, prep_text),),
                prep_text,
            ),
            artifact(
                ArtifactKind.INTERNAL_ECONOMIC_CONTEXT,
                ArtifactAudience.INTERNAL,
                "Internal economic context",
                (ArtifactSegment(self._ids.new(), SegmentKind.INTERNAL_CONTEXT, economic_text),),
                economic_text,
            ),
            artifact(
                ArtifactKind.INTERNAL_RISK_REGISTER,
                ArtifactAudience.INTERNAL,
                "Internal contradiction and risk register",
                (ArtifactSegment(self._ids.new(), SegmentKind.INTERNAL_CONTEXT, risk_text),),
                risk_text,
            ),
        )


class OutreachQualityPolicy:
    def __init__(self, identifiers: IdentifierFactory) -> None:
        self._ids = identifiers

    def evaluate(
        self,
        manifest: OutreachInputManifest,
        source: OutreachCanonicalInputs,
        projections: tuple[OutreachClaimProjection, ...],
        artifacts: tuple[OutreachArtifact, ...],
        role: TargetRoleSelection,
        questions: tuple[OutreachValidationQuestion, ...],
        risks: tuple[OutreachRisk, ...],
        economic: InternalEconomicContext,
        personalization: PersonalizationAssessment | None = None,
    ) -> tuple[OutreachQcFinding, ...]:
        findings: list[OutreachQcFinding] = []

        def fail(
            code: str,
            message: str,
            projection_id: UUID | None = None,
            artifact_id: UUID | None = None,
        ) -> None:
            findings.append(
                OutreachQcFinding(
                    self._ids.new(),
                    code,
                    QcSeverity.HARD_FAILURE,
                    message,
                    projection_id,
                    artifact_id,
                )
            )

        claims = {item.id: item for item in source.audit.revision.claims}
        evidence_ids = set(manifest.evidence_ids)
        projection_ids = {item.id for item in projections}
        if (
            role.role not in ROLE_PRIORITY
            or role.person_identified
            or role.person_marker != "NO_PERSON_IDENTIFIED"
        ):
            fail(
                "person_targeting",
                "M5 may target only an approved functional role without a person.",
            )
        if economic.external_use_permitted:
            fail("economic_externalization", "Initial M5 economics are structurally internal-only.")
        for projection in projections:
            claim = claims.get(projection.source_claim_id)
            if claim is None or claim.subject_business_id != manifest.business_id:
                fail(
                    "claim_lineage",
                    "A projection lacks an exact same-business M3 claim.",
                    projection.id,
                )
                continue
            if projection.mode in {
                ProjectionMode.DIRECT_FACT_RESTATEMENT,
                ProjectionMode.EVIDENCE_DERIVED_FACT,
            } and (
                claim.claim_type != ClaimType.FACT
                or not projection.evidence_ids
                or not set(projection.evidence_ids).issubset(evidence_ids)
            ):
                fail(
                    "fact_evidence",
                    "An external fact lacks exact evidence lineage.",
                    projection.id,
                )
            if projection.mode in {
                ProjectionMode.CONDITIONAL_INFERENCE,
                ProjectionMode.CONDITIONAL_RECOMMENDATION,
            } and not all(
                term in projection.rendered_text.lower() for term in projection.required_qualifiers
            ):
                fail(
                    "removed_qualifier",
                    "Conditional wording lost a required qualifier.",
                    projection.id,
                )
            if projection.mode == ProjectionMode.SCOPED_ABSENCE and (
                claim.claim_type != ClaimType.FACT
                or not projection.evidence_ids
                or not all(
                    term in projection.rendered_text.lower()
                    for term in projection.required_qualifiers
                )
            ):
                fail(
                    "scoped_absence",
                    "Scoped absence must retain exact public scope and explicit uncertainty.",
                    projection.id,
                )
            if (
                projection.mode == ProjectionMode.ECONOMIC_CONTEXT_INTERNAL_ONLY
                and projection.disposition != ProjectionDisposition.INTERNAL_ONLY
            ):
                fail(
                    "economic_projection",
                    "Economic claims must remain internal-only.",
                    projection.id,
                )
        required = set(ArtifactKind)
        present = {item.kind for item in artifacts}
        if required != present:
            fail("artifact_inventory", "The exact approved artifact inventory is required.")
        external_artifacts = [
            item for item in artifacts if item.audience == ArtifactAudience.EXTERNAL
        ]
        if personalization is not None and not personalization.passes_gate:
            fail(
                "no_company_specific_evidence",
                "The reader-visible first contact contains no materially company-specific "
                "evidence-backed observation; the company name alone does not qualify.",
            )
        for item in external_artifacts:
            if _SCORE_LEAK.search(item.rendered_text):
                fail(
                    "internal_score_language_leak",
                    "Internal HIGH/LOW review-priority language must not appear externally.",
                    artifact_id=item.id,
                )
            if FINANCIAL_EXTERNAL.search(item.rendered_text):
                fail(
                    "external_financial_value",
                    "External artifacts may not contain financial values.",
                    artifact_id=item.id,
                )
            if PERSONAL_CONTACT.search(item.rendered_text):
                fail(
                    "personal_contact",
                    "External artifacts may not contain personal contact data.",
                    artifact_id=item.id,
                )
            if ACTIVE_OR_EXTERNAL.search(item.rendered_text):
                fail(
                    "external_or_active_content",
                    "Links and active content are prohibited.",
                    artifact_id=item.id,
                )
            if PROHIBITED.search(item.rendered_text):
                fail(
                    "prohibited_claim",
                    "An external artifact contains prohibited or deceptive wording.",
                    artifact_id=item.id,
                )
            for segment in item.segments:
                if (
                    segment.kind == SegmentKind.BOUND_CLAIM
                    and segment.projection_id not in projection_ids
                ):
                    fail(
                        "unbound_segment",
                        "A business statement lacks a projection binding.",
                        artifact_id=item.id,
                    )
        subject = next(item for item in artifacts if item.kind == ArtifactKind.SUBJECT)
        if len(subject.rendered_text) > 60 or re.match(
            r"^(?:re|fwd):", subject.rendered_text, re.I
        ):
            fail(
                "subject_policy",
                "Subject length or fake-thread policy failed.",
                artifact_id=subject.id,
            )
        first = next(item for item in artifacts if item.kind == ArtifactKind.FIRST_CONTACT_EMAIL)
        if len(first.rendered_text.split()) > 130:
            fail(
                "first_contact_length",
                "First-contact body exceeds 130 words.",
                artifact_id=first.id,
            )
        projection_mode = {projection.id: projection.mode for projection in projections}
        first_facts = sum(
            1
            for item in first.segments
            if item.projection_id is not None
            and projection_mode.get(item.projection_id)
            in {
                ProjectionMode.DIRECT_FACT_RESTATEMENT,
                ProjectionMode.EVIDENCE_DERIVED_FACT,
            }
        )
        if first_facts < 1 or first_facts > 2:
            fail(
                "fact_count",
                "First contact must contain one or at most two fact projections.",
                artifact_id=first.id,
            )
        cta_segment = next(
            (segment for segment in first.segments if segment.kind == SegmentKind.CTA), None
        )
        if (
            cta_segment is None
            or first.rendered_text.count(cta_segment.text) != 1
            or SIMULATION_DISCLOSURE not in first.rendered_text
        ):
            fail(
                "cta_or_disclosure",
                "First contact requires one CTA and the simulation disclosure.",
                artifact_id=first.id,
            )
        followup = next(item for item in artifacts if item.kind == ArtifactKind.FOLLOW_UP_DRAFT)
        if (
            followup.follow_up_usability != FollowUpUsability.CONDITIONALLY_USABLE
            or followup.external_precondition != FOLLOW_UP_PRECONDITION
        ):
            fail(
                "follow_up_precondition",
                "Follow-up must remain conditionally usable.",
                artifact_id=followup.id,
            )
        if any(item.safe_for_first_contact for item in questions[2:]):
            fail("question_limit", "At most two validation questions may be first-contact safe.")
        contradiction_ids = set(source.opportunity.hypothesis.contradictory_evidence_ids)  # type: ignore[union-attr]
        if contradiction_ids and not any(item.kind == "material_contradiction" for item in risks):
            fail("hidden_contradiction", "Material contradictions must remain internally visible.")
        if (
            manifest.template_version != TEMPLATE_VERSION
            or manifest.qc_policy_version != QC_POLICY_VERSION
        ):
            fail(
                "configuration_drift",
                "Manifest configuration versions are not the accepted M5 versions.",
            )
        return tuple(findings)
