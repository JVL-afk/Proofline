"""Deterministic M3 composition and non-overridable semantic QC."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from opintel_m0.ports import IdentifierFactory
from opintel_opportunity.domain import (
    CompanyFact,
    EconomicStatus,
    FactCategory,
    OpportunityBundle,
    ResearchRunStats,
    RevisionStatus,
    ValueState,
)

from opintel_audit.domain import (
    AuditClaim,
    AuditEvidence,
    AuditFinding,
    AuditInputManifest,
    AuditKind,
    AuditQcError,
    AuditRevision,
    AuditRevisionState,
    AuditSection,
    AuditValidity,
    ClaimType,
    FindingKind,
    FreshnessState,
    QcFinding,
    QcSeverity,
)

AUDIT_SCHEMA_VERSION = "audit.schema@1"
COMPOSITION_POLICY_VERSION = "audit.commercial_hvac.deterministic@2"
QC_POLICY_VERSION = "audit.qc@1"

# EVIDENCE_PRESERVING_PERSONALIZATION_V2: fixed finding frames. The frame inserts
# a supported, verbatim-derived phrase; it never adds a claim or strengthens it.
_FINDING_KIND_BY_CATEGORY: dict[FactCategory, FindingKind] = {
    FactCategory.INTAKE_SURFACE: FindingKind.OBSERVED_INTAKE_SURFACE,
    FactCategory.COMMERCIAL_CONTEXT: FindingKind.OBSERVED_COMMERCIAL_CONTEXT,
    FactCategory.RESPONSE_COMMITMENT: FindingKind.OBSERVED_RESPONSE_COMMITMENT,
    FactCategory.SERVICE_AREA_CONTEXT: FindingKind.OBSERVED_SERVICE_AREA,
}


def _finding_frame(category: FactCategory, phrase: str) -> str:
    value = phrase.strip().rstrip(".;:,")
    if category == FactCategory.INTAKE_SURFACE:
        return (
            "Observed intake surface: the captured public pages present a request path "
            f'("{value}").'
        )
    if category == FactCategory.COMMERCIAL_CONTEXT:
        return (
            "Observed commercial-service context: the captured public pages describe "
            f'commercial HVAC work ("{value}").'
        )
    if category == FactCategory.RESPONSE_COMMITMENT:
        return (
            "Observed response commitment: the captured contact page publishes response "
            "expectations for new inquiries."
        )
    return (
        "Observed service-area context: the captured public pages list a service area "
        f'("{value}").'
    )

SECTION_DEFINITIONS = (
    ("scope", "Audit scope and limitations"),
    ("business_scope", "Business and research scope"),
    ("facts", "Publicly observed facts"),
    ("inferences", "Relevant inferences"),
    ("opportunity", "Opportunity hypothesis"),
    ("contradictions", "Contradictions and alternative explanations"),
    ("gaps", "Information gaps and validation questions"),
    ("economics", "Economic scenarios"),
    ("solution", "Proposed solution and feasibility constraints"),
    ("validation", "Recommended validation steps"),
    ("methodology", "Methodology and provenance"),
)

UNSAFE_MARKUP = re.compile(
    r"<\s*(?:script|iframe|object|embed|svg|math)|on\w+\s*=|javascript:", re.I
)
NUMBER = re.compile(r"(?<![\w])(?:[$€£])?\d[\d,]*(?:\.\d+)?%?")
PROHIBITED = (
    "responds slowly",
    "waits until monday",
    "misses leads",
    "no crm",
    "lost revenue",
    "actual impact",
    "guaranteed savings",
)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class DeterministicAuditComposer:
    def __init__(self, identifiers: IdentifierFactory) -> None:
        self._ids = identifiers

    def compose(
        self,
        *,
        audit_id: UUID,
        revision_number: int,
        parent_revision_id: UUID | None,
        kind: AuditKind,
        source: OpportunityBundle,
        evidence: tuple[AuditEvidence, ...],
        created_by: str,
        now: datetime,
    ) -> AuditRevision:
        hypothesis = source.hypothesis
        inference = source.inference
        economic = source.economic_run
        score = source.score_snapshot
        if hypothesis is None or inference is None or economic is None or score is None:
            raise AuditQcError("complete canonical M2 lineage is required")
        evidence_by_id = {item.id: item for item in evidence}
        manifest = self._manifest(source, evidence, now)
        claims_by_section: dict[str, list[AuditClaim]] = {key: [] for key, _ in SECTION_DEFINITIONS}

        audit_findings: list[AuditFinding] = []
        company_facts: tuple[CompanyFact, ...] = source.company_facts
        observation_by_evidence = {item.evidence_id: item for item in source.observations}
        for fact in company_facts:
            item = evidence_by_id.get(fact.evidence_id)
            if item is None:
                continue
            observation = observation_by_evidence.get(fact.evidence_id)
            observation_ids = (observation.id,) if observation is not None else ()
            claim = self._claim(
                "facts",
                ClaimType.FACT,
                hypothesis.business_id,
                f"finding.{fact.category.value}",
                _finding_frame(fact.category, fact.phrase),
                evidence_ids=(item.id,),
                observation_ids=observation_ids,
            )
            claims_by_section["facts"].append(claim)
            audit_findings.append(
                AuditFinding(
                    id=self._ids.new(),
                    kind=_FINDING_KIND_BY_CATEGORY[fact.category],
                    text=claim.display_text,
                    claim_id=claim.id,
                    evidence_ids=(item.id,),
                    observation_ids=observation_ids,
                    fact_class=fact.fact_class,
                    supporting_excerpt=item.bounded_excerpt[:280],
                )
            )

        for observation in source.observations:
            item = evidence_by_id.get(observation.evidence_id)
            if item is None:
                continue
            headline = (
                f"Supporting public excerpt ({observation.predicate}): {item.bounded_excerpt}"
                if company_facts
                else f"The captured public surface states or exposes: {item.bounded_excerpt}"
            )
            claims_by_section["facts"].append(
                self._claim(
                    "facts",
                    ClaimType.FACT,
                    hypothesis.business_id,
                    observation.predicate,
                    headline,
                    evidence_ids=(item.id,),
                    observation_ids=(observation.id,),
                )
            )

        inference_claim = self._claim(
            "inferences",
            ClaimType.INFERENCE,
            hypothesis.business_id,
            "m2.inference",
            f"Inference: {inference.statement}",
            evidence_ids=inference.evidence_ids,
            observation_ids=inference.observation_ids,
            inference_revision_ids=(inference.id,),
            contradictory_evidence_ids=inference.contradictory_evidence_ids,
        )
        claims_by_section["inferences"].append(inference_claim)
        hypothesis_claim = self._claim(
            "opportunity",
            ClaimType.INFERENCE,
            hypothesis.business_id,
            "m2.opportunity_hypothesis",
            f"Opportunity hypothesis: {hypothesis.statement}",
            evidence_ids=hypothesis.supporting_evidence_ids,
            observation_ids=hypothesis.observation_ids,
            inference_revision_ids=hypothesis.inference_revision_ids,
            contradictory_evidence_ids=hypothesis.contradictory_evidence_ids,
        )
        claims_by_section["opportunity"].append(hypothesis_claim)

        for evidence_id in hypothesis.contradictory_evidence_ids:
            item = evidence_by_id.get(evidence_id)
            if item is not None:
                claims_by_section["contradictions"].append(
                    self._claim(
                        "contradictions",
                        ClaimType.FACT,
                        hypothesis.business_id,
                        "m2.material_contradiction",
                        f"Contradictory public evidence: {item.bounded_excerpt}",
                        evidence_ids=(item.id,),
                    )
                )

        if economic.status != EconomicStatus.INSUFFICIENT_DATA:
            label = (
                "Hypothetical scenario"
                if economic.status == EconomicStatus.HYPOTHETICAL
                else "Calculated scenario"
            )
            claims_by_section["economics"].append(
                self._claim(
                    "economics",
                    ClaimType.ESTIMATE,
                    hypothesis.business_id,
                    "m2.economic_scenario",
                    f"{label}: monthly potential incremental revenue "
                    f"{economic.monthly_potential_incremental_revenue} {economic.currency}; "
                    f"annualized {economic.annualized_potential_incremental_revenue} "
                    f"{economic.currency}. This is not actual loss or guaranteed impact.",
                    assumption_revision_ids=economic.assumption_revision_ids,
                    economic_run_id=economic.id,
                )
            )

        fact_ids = tuple(item.id for item in claims_by_section["facts"])
        recommendation = self._claim(
            "solution",
            ClaimType.RECOMMENDATION,
            hypothesis.business_id,
            "solution.evaluate_structured_acknowledgment",
            "Recommendation: evaluate a structured acknowledgement and qualification workflow "
            "for the observed inbound channels, subject to verification of current routing, "
            "capacity, systems, governance, and required human handoff.",
            dependency_claim_ids=(*fact_ids, inference_claim.id, hypothesis_claim.id),
        )
        claims_by_section["solution"].append(recommendation)

        stats = source.run_stats
        scope_limitation = (
            "This audit is limited to cited public digital surfaces and canonical M2 "
            "records. Internal operations and actual business impact remain unknown "
            "unless explicitly verified."
        )
        if stats is not None and stats.partial:
            scope_limitation += (
                f" Coverage was partial ({stats.pages_succeeded} of {stats.pages_attempted} "
                "pages captured); absence of a fact may reflect incomplete capture."
            )
        section_items: dict[str, tuple[dict[str, object], ...]] = {
            "scope": ({"limitation": scope_limitation},),
            "facts": (
                {
                    "coverage": {
                        "status": stats.status if stats is not None else "not_recorded",
                        "pages_attempted": stats.pages_attempted if stats is not None else 0,
                        "pages_succeeded": stats.pages_succeeded if stats is not None else 0,
                        "pages_failed": stats.pages_failed if stats is not None else 0,
                        "partial": bool(stats is not None and stats.partial),
                        "fact_class_histogram": (
                            [list(pair) for pair in stats.fact_class_histogram]
                            if stats is not None
                            else []
                        ),
                        "captured_page_purposes": (
                            [list(pair) for pair in stats.captured_page_purposes]
                            if stats is not None
                            else []
                        ),
                    }
                },
            ),
            "business_scope": (
                {
                    "business_id": str(hypothesis.business_id),
                    "research_run_id": str(source.run.research_run_id),
                    "definition_version": hypothesis.definition_version,
                },
            ),
            "contradictions": tuple(
                {"alternative_explanation": text} for text in hypothesis.alternative_explanations
            ),
            "gaps": tuple(
                {
                    "priority": gap.priority,
                    "component": gap.affected_component,
                    "economic_effect": gap.economic_effect,
                    "description": gap.description,
                    "validation_question": gap.suggested_validation_question,
                }
                for gap in source.gaps
            ),
            "economics": (
                {
                    "status": economic.status,
                    "formula_version": economic.formula_version,
                    "result_label": economic.result_label,
                    "assumptions": tuple(
                        {
                            "id": str(item.id),
                            "key": item.key,
                            "state": item.value_state,
                            "value": item.decimal_value,
                            "unit": item.unit,
                            "currency": item.currency,
                            "source_kind": item.source_kind,
                            "provenance": item.provenance,
                        }
                        for item in source.assumptions
                    ),
                },
            ),
            "solution": tuple(
                {"feasibility_dependency": item} for item in hypothesis.feasibility_dependencies
            ),
            "validation": tuple(
                {"question": item.suggested_validation_question} for item in source.gaps
            ),
            "methodology": (
                {
                    "manifest_hash": manifest.checksum,
                    "composition_policy": COMPOSITION_POLICY_VERSION,
                    "qc_policy": QC_POLICY_VERSION,
                },
            ),
        }
        sections: list[AuditSection] = []
        claims: list[AuditClaim] = []
        for ordinal, (key, title) in enumerate(SECTION_DEFINITIONS, start=1):
            selected = tuple(claims_by_section[key])
            claims.extend(selected)
            sections.append(
                AuditSection(
                    self._ids.new(),
                    key,
                    title,
                    ordinal,
                    tuple(item.id for item in selected),
                    section_items.get(key, ()),
                )
            )
        audit_findings.extend(self._coverage_findings(source))
        claim_tuple = tuple(claims)
        section_tuple = tuple(sections)
        finding_tuple = tuple(audit_findings)
        findings = AuditQualityPolicy(self._ids).evaluate(
            manifest, source, evidence, section_tuple, claim_tuple
        )
        hard_failure = any(item.severity == QcSeverity.HARD_FAILURE for item in findings)
        rendered = self._render(
            section_tuple, {item.id: item for item in claim_tuple}, finding_tuple
        )
        body = {
            "manifest": manifest.checksum,
            "sections": [asdict(item) for item in section_tuple],
            "claims": [asdict(item) for item in claim_tuple],
            "findings": [asdict(item) for item in finding_tuple],
            "rendered": rendered,
        }
        return AuditRevision(
            id=self._ids.new(),
            audit_id=audit_id,
            revision=revision_number,
            parent_revision_id=parent_revision_id,
            workspace_id=hypothesis.workspace_id,
            business_id=hypothesis.business_id,
            hypothesis_id=hypothesis.logical_id,
            kind=kind,
            manifest=manifest,
            sections=section_tuple,
            claims=claim_tuple,
            qc_findings=findings,
            state=AuditRevisionState.QC_FAILED
            if hard_failure
            else AuditRevisionState.REVIEW_REQUIRED,
            validity=AuditValidity.CURRENT,
            revision_hash=stable_hash(body),
            rendered_text=rendered,
            created_by=created_by,
            created_at=now,
            findings=finding_tuple,
        )

    def _coverage_findings(self, source: OpportunityBundle) -> list[AuditFinding]:
        blocking = sorted(
            {
                gap.affected_component
                for gap in source.gaps
                if str(gap.economic_effect) == "blocks_model"
            }
        )
        unknown = AuditFinding(
            id=self._ids.new(),
            kind=FindingKind.WHAT_REMAINS_UNKNOWN,
            text=(
                "What remains unknown: internal response performance, routing, lead volume, "
                "conversion, and verified customer value are not publicly observable"
                + (f" (blocking gaps: {', '.join(blocking)})." if blocking else ".")
            ),
        )
        stats: ResearchRunStats | None = source.run_stats
        if stats is None:
            coverage_text = "Crawl coverage: not recorded for this analysis run."
        elif stats.partial:
            coverage_text = (
                f"Crawl coverage: {stats.pages_succeeded} of {stats.pages_attempted} pages "
                "captured (partial); absence of a fact may reflect incomplete capture."
            )
        else:
            coverage_text = (
                f"Crawl coverage: {stats.pages_succeeded} of {stats.pages_attempted} pages "
                "captured (complete)."
            )
        coverage = AuditFinding(
            id=self._ids.new(), kind=FindingKind.CRAWL_COVERAGE, text=coverage_text
        )
        return [unknown, coverage]

    def _manifest(
        self, source: OpportunityBundle, evidence: tuple[AuditEvidence, ...], now: datetime
    ) -> AuditInputManifest:
        hypothesis = source.hypothesis
        economic = source.economic_run
        score = source.score_snapshot
        assert hypothesis is not None and economic is not None and score is not None
        values = {
            "workspace_id": hypothesis.workspace_id,
            "business_id": hypothesis.business_id,
            "research_run_id": source.run.research_run_id,
            "analysis_run_id": source.run.id,
            "hypothesis_id": hypothesis.logical_id,
            "hypothesis_revision_id": hypothesis.id,
            "hypothesis_manifest_checksum": hypothesis.manifest_checksum,
            "opportunity_review_id": source.latest_review.id if source.latest_review else None,
            "opportunity_review_manifest_checksum": (
                source.latest_review.manifest_checksum if source.latest_review else None
            ),
            "opportunity_definition_version": hypothesis.definition_version,
            "observation_ids": hypothesis.observation_ids,
            "inference_revision_ids": hypothesis.inference_revision_ids,
            "evidence_ids": tuple(item.id for item in evidence),
            "evidence_fingerprints": tuple(
                f"{item.id}:{item.snapshot_version}:{item.content_sha256}:{item.freshness}"
                for item in evidence
            ),
            "contradictory_evidence_ids": hypothesis.contradictory_evidence_ids,
            "information_gap_ids": tuple(item.id for item in source.gaps),
            "assumption_revision_ids": hypothesis.assumption_revision_ids,
            "economic_run_id": economic.id,
            "economic_formula_version": economic.formula_version,
            "score_snapshot_id": score.id,
            "score_config_version": score.config_version,
            "audit_schema_version": AUDIT_SCHEMA_VERSION,
            "composition_policy_version": COMPOSITION_POLICY_VERSION,
            "qc_policy_version": QC_POLICY_VERSION,
        }
        return AuditInputManifest(
            id=self._ids.new(),
            workspace_id=hypothesis.workspace_id,
            business_id=hypothesis.business_id,
            research_run_id=source.run.research_run_id,
            analysis_run_id=source.run.id,
            hypothesis_id=hypothesis.logical_id,
            hypothesis_revision_id=hypothesis.id,
            hypothesis_manifest_checksum=hypothesis.manifest_checksum,
            opportunity_review_id=source.latest_review.id if source.latest_review else None,
            opportunity_review_manifest_checksum=(
                source.latest_review.manifest_checksum if source.latest_review else None
            ),
            opportunity_definition_version=hypothesis.definition_version,
            observation_ids=hypothesis.observation_ids,
            inference_revision_ids=hypothesis.inference_revision_ids,
            evidence_ids=tuple(item.id for item in evidence),
            evidence_fingerprints=tuple(
                f"{item.id}:{item.snapshot_version}:{item.content_sha256}:{item.freshness}"
                for item in evidence
            ),
            contradictory_evidence_ids=hypothesis.contradictory_evidence_ids,
            information_gap_ids=tuple(item.id for item in source.gaps),
            assumption_revision_ids=hypothesis.assumption_revision_ids,
            economic_run_id=economic.id,
            economic_formula_version=economic.formula_version,
            score_snapshot_id=score.id,
            score_config_version=score.config_version,
            audit_schema_version=AUDIT_SCHEMA_VERSION,
            composition_policy_version=COMPOSITION_POLICY_VERSION,
            qc_policy_version=QC_POLICY_VERSION,
            checksum=stable_hash(values),
            created_at=now,
        )

    def _claim(
        self,
        section: str,
        claim_type: ClaimType,
        business_id: UUID,
        predicate: str,
        text: str,
        evidence_ids: tuple[UUID, ...] = (),
        observation_ids: tuple[UUID, ...] = (),
        inference_revision_ids: tuple[UUID, ...] = (),
        assumption_revision_ids: tuple[UUID, ...] = (),
        economic_run_id: UUID | None = None,
        dependency_claim_ids: tuple[UUID, ...] = (),
        contradictory_evidence_ids: tuple[UUID, ...] = (),
    ) -> AuditClaim:
        return AuditClaim(
            self._ids.new(),
            section,
            claim_type,
            business_id,
            predicate,
            text,
            evidence_ids,
            observation_ids,
            inference_revision_ids,
            assumption_revision_ids,
            economic_run_id,
            dependency_claim_ids,
            contradictory_evidence_ids,
        )

    @staticmethod
    def _render(
        sections: tuple[AuditSection, ...],
        claims: dict[UUID, AuditClaim],
        findings: tuple[AuditFinding, ...] = (),
    ) -> str:
        lines: list[str] = []
        for section in sections:
            lines.append(section.title)
            lines.extend(
                f"[{claims[item].claim_type.upper()}] {claims[item].display_text}"
                for item in section.claim_ids
            )
            for structured in section.structured_items:
                lines.append(json.dumps(structured, sort_keys=True, default=str))
        if findings:
            lines.append("Findings")
            lines.extend(f"[{finding.kind.upper()}] {finding.text}" for finding in findings)
        return "\n".join(lines)


class AuditQualityPolicy:
    def __init__(self, identifiers: IdentifierFactory) -> None:
        self._ids = identifiers

    def evaluate(
        self,
        manifest: AuditInputManifest,
        source: OpportunityBundle,
        evidence: tuple[AuditEvidence, ...],
        sections: tuple[AuditSection, ...],
        claims: tuple[AuditClaim, ...],
    ) -> tuple[QcFinding, ...]:
        findings: list[QcFinding] = []
        evidence_by_id = {item.id: item for item in evidence}
        claim_ids = {item.id for item in claims}
        manifest_evidence = set(manifest.evidence_ids)
        hypothesis = source.hypothesis
        inference = source.inference
        economic = source.economic_run
        assert hypothesis is not None and inference is not None and economic is not None

        def fail(code: str, message: str, claim_id: UUID | None = None) -> None:
            findings.append(
                QcFinding(self._ids.new(), code, QcSeverity.HARD_FAILURE, message, claim_id)
            )

        for item in evidence:
            if (
                item.workspace_id != manifest.workspace_id
                or item.business_id != manifest.business_id
            ):
                fail(
                    "entity_workspace_mismatch", "Evidence does not belong to the manifest entity."
                )
            if item.freshness in {FreshnessState.INVALID, FreshnessState.SUPERSEDED}:
                fail(
                    "prohibited_evidence_state",
                    "Invalid or superseded evidence cannot support an audit.",
                )
            elif item.freshness in {
                FreshnessState.STALE_PERMITTED,
                FreshnessState.STALE_REQUIRES_ACKNOWLEDGMENT,
            }:
                findings.append(
                    QcFinding(
                        self._ids.new(),
                        "stale_evidence",
                        QcSeverity.WARNING,
                        "A cited evidence item is stale under its versioned freshness policy.",
                        acknowledgment_required=item.freshness
                        == FreshnessState.STALE_REQUIRES_ACKNOWLEDGMENT,
                    )
                )
        for claim in claims:
            if claim.subject_business_id != manifest.business_id:
                fail(
                    "entity_workspace_mismatch",
                    "Claim subject differs from the manifest business.",
                    claim.id,
                )
            if UNSAFE_MARKUP.search(claim.display_text):
                fail("unsafe_markup", "Unsafe active markup is prohibited.", claim.id)
            lowered = claim.display_text.lower()
            if any(text in lowered for text in PROHIBITED):
                fail(
                    "prohibited_hvac_claim",
                    "The claim uses prohibited business-impact wording.",
                    claim.id,
                )
            if not set(claim.evidence_ids).issubset(manifest_evidence):
                fail(
                    "content_outside_manifest",
                    "Claim references evidence outside the manifest.",
                    claim.id,
                )
            if not set(claim.observation_ids).issubset(manifest.observation_ids):
                fail(
                    "content_outside_manifest",
                    "Claim references observations outside the manifest.",
                    claim.id,
                )
            if not set(claim.inference_revision_ids).issubset(manifest.inference_revision_ids):
                fail(
                    "content_outside_manifest",
                    "Claim references inference revisions outside the manifest.",
                    claim.id,
                )
            if not set(claim.assumption_revision_ids).issubset(manifest.assumption_revision_ids):
                fail(
                    "content_outside_manifest",
                    "Claim references assumptions outside the manifest.",
                    claim.id,
                )
            if claim.predicate in {"m2.inference", "m2.opportunity_hypothesis"} and (
                claim.claim_type != ClaimType.INFERENCE
            ):
                fail(
                    "inference_as_fact",
                    "Canonical inference content cannot be represented as fact.",
                    claim.id,
                )
            if claim.claim_type == ClaimType.FACT:
                if not claim.evidence_ids:
                    fail(
                        "fact_without_evidence",
                        "A factual claim requires exact evidence.",
                        claim.id,
                    )
                for evidence_id in claim.evidence_ids:
                    evidence_item = evidence_by_id.get(evidence_id)
                    if evidence_item is None:
                        fail(
                            "invented_evidence_id", "A factual citation does not resolve.", claim.id
                        )
                    elif any(
                        token not in evidence_item.bounded_excerpt
                        for token in NUMBER.findall(claim.display_text)
                    ):
                        fail(
                            "unsupported_precision",
                            "A factual number is absent from its evidence.",
                            claim.id,
                        )
            if claim.claim_type == ClaimType.INFERENCE:
                if not claim.inference_revision_ids:
                    fail(
                        "inference_without_lineage",
                        "An inference requires an exact revision.",
                        claim.id,
                    )
                if inference.status != RevisionStatus.ACTIVE:
                    fail(
                        "rejected_or_superseded_inference",
                        "Inactive inference cannot support an audit.",
                        claim.id,
                    )
            if claim.claim_type == ClaimType.ESTIMATE:
                if claim.economic_run_id != economic.id or set(
                    claim.assumption_revision_ids
                ) != set(economic.assumption_revision_ids):
                    fail(
                        "economic_lineage_mismatch",
                        "Estimate lineage does not match canonical economics.",
                        claim.id,
                    )
                allowed_numbers = {
                    value
                    for value in (
                        economic.monthly_potential_incremental_revenue,
                        economic.annualized_potential_incremental_revenue,
                    )
                    if value is not None
                }
                for token in NUMBER.findall(claim.display_text):
                    normalized = token.strip("$€£%,")
                    if normalized not in allowed_numbers:
                        fail(
                            "unsupported_precision",
                            "Estimate contains an unbound number.",
                            claim.id,
                        )
                if "verified" in lowered and any(
                    assumption.value_state == ValueState.PROPOSED
                    for assumption in source.assumptions
                ):
                    fail(
                        "proposed_rendered_verified",
                        "Proposed inputs cannot be rendered as verified.",
                        claim.id,
                    )
            if claim.claim_type == ClaimType.RECOMMENDATION and (
                not claim.dependency_claim_ids
                or not set(claim.dependency_claim_ids).issubset(claim_ids)
            ):
                fail(
                    "recommendation_without_dependencies",
                    "Recommendation dependencies are incomplete.",
                    claim.id,
                )
            if (
                claim.claim_type == ClaimType.ESTIMATE
                and "known" in lowered
                and any(
                    assumption.value_state == ValueState.UNKNOWN
                    for assumption in source.assumptions
                )
            ):
                fail("unknown_to_known", "Unknown input cannot silently become known.", claim.id)

        required_sections = {key for key, _ in SECTION_DEFINITIONS}
        if {item.key for item in sections} != required_sections:
            fail("incomplete_manifest", "The required eleven-section schema is incomplete.")
        if hypothesis.contradictory_evidence_ids:
            presented = {
                evidence_id
                for claim in claims
                for evidence_id in claim.evidence_ids
                if claim.section_key == "contradictions"
            }
            if not set(hypothesis.contradictory_evidence_ids).issubset(presented):
                fail("material_contradiction_suppressed", "A material contradiction was omitted.")
        if hypothesis.alternative_explanations and not any(
            section.key == "contradictions"
            and len(section.structured_items) >= len(hypothesis.alternative_explanations)
            for section in sections
        ):
            fail("material_alternative_omitted", "Required alternative explanations were omitted.")
        return tuple(findings)
