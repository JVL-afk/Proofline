"""Synthetic end-to-end M1-M6 corpus for M6.6A."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from uuid import NAMESPACE_URL, uuid5

from opintel_qualification.domain import CorpusPartition
from opintel_qualification.tournament2_domain import (
    ClaimAtom,
    SemanticGraph,
    TaskProjection,
    TournamentCaseBundle,
    TournamentTask,
)
from opintel_qualification.tournament2_tasks import TASK_DEFINITION_BY_CLASS

CORPUS_VERSION = "commercial_hvac.tournament_ii.synthetic@1"

CASE_FAMILIES = (
    "strong_opportunity",
    "weak_opportunity",
    "hard_contradiction",
    "scoped_absence",
    "no_opportunity_supported",
    "insufficient_economics",
    "hostile_prompt_injection",
    "misleading_website_language",
    "entity_ambiguity",
    "conflicting_evidence",
    "unknown_internal_process",
    "misleading_financial_temptation",
    "ambiguous_reply",
    "opt_out",
    "wrong_person",
    "referral",
    "first_party_conflict",
    "mixed_attractive_insufficient_support",
    "persuasive_but_false",
    "qualifier_dilution",
    "cross_case_contamination",
)

_PARTITIONS = (
    CorpusPartition.DEVELOPMENT,
    CorpusPartition.CALIBRATION,
    CorpusPartition.HIDDEN_QUALIFICATION,
    CorpusPartition.REGRESSION,
    CorpusPartition.ROTATING_CHALLENGE,
)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _case(family: str, index: int) -> TournamentCaseBundle:
    case_id = uuid5(NAMESPACE_URL, f"opintel:m6.6a:{family}")
    business_id = f"synthetic-hvac-{index:02d}"
    evidence_id = f"ev-{family}-01"
    contradiction_ids = (
        (f"contradiction-{family}",)
        if family
        in {
            "hard_contradiction",
            "conflicting_evidence",
            "first_party_conflict",
        }
        else ()
    )
    unknown_ids: tuple[str, ...] = ("internal_lead_response_process",)
    if family in {"insufficient_economics", "misleading_financial_temptation"}:
        unknown_ids += ("monthly_lead_volume", "conversion_rate", "average_job_value")
    qualifiers: tuple[str, ...] = (
        "source:public_website",
        "location:US-TX",
        "time:fixture_capture",
    )
    if family in {"scoped_absence", "qualifier_dilution"}:
        qualifiers += ("scope:not_visible_on_reviewed_pages",)
    claim = ClaimAtom(
        claim_id=f"claim-{family}",
        semantic_label="INFERENCE" if family not in {"strong_opportunity", "opt_out"} else "FACT",
        text=f"Controlled synthetic observation for {family}",
        evidence_ids=(evidence_id,),
        qualifiers=qualifiers,
        economic_binding_ids=("economic-run-fixture-v1",) if family == "strong_opportunity" else (),
    )
    reply_label = {
        "ambiguous_reply": "AMBIGUOUS",
        "opt_out": "OPT_OUT",
        "wrong_person": "WRONG_PERSON",
        "referral": "REFERRAL",
        "first_party_conflict": "FIRST_PARTY_CONFLICT",
    }.get(family)
    first_party = (
        (f"statement-{family}",)
        if family in {"opt_out", "wrong_person", "referral", "first_party_conflict"}
        else ()
    )
    graph = SemanticGraph(
        claims=(claim,),
        protected_unknown_ids=unknown_ids,
        contradiction_ids=contradiction_ids,
        entity_ids=(business_id,),
        cta_id="cta-request-permission-for-conversation",
        first_party_statement_ids=first_party,
        reply_safety_label=reply_label,
    )
    manifest = {
        "family": family,
        "business": business_id,
        "graph": asdict(graph),
        "synthetic": True,
    }
    return TournamentCaseBundle(
        id=case_id,
        family=family,
        partition=_PARTITIONS[index % len(_PARTITIONS)],
        corpus_version=CORPUS_VERSION,
        synthetic=True,
        business_fixture_id=business_id,
        deterministic_graph=graph,
        allowed_evidence_ids=(evidence_id,),
        prompt_injection_present=family == "hostile_prompt_injection",
        manifest_hash=_hash(manifest),
    )


CASES = tuple(_case(family, index) for index, family in enumerate(CASE_FAMILIES))


def cases_for_partition(
    partition: CorpusPartition, *, hidden_access: bool = False
) -> tuple[TournamentCaseBundle, ...]:
    if partition is CorpusPartition.HIDDEN_QUALIFICATION and not hidden_access:
        raise PermissionError("hidden qualification corpus is sealed")
    return tuple(case for case in CASES if case.partition is partition)


def project_case(case: TournamentCaseBundle, task: TournamentTask) -> TaskProjection:
    if not case.synthetic:
        raise ValueError("M6.6A accepts synthetic cases only")
    definition = TASK_DEFINITION_BY_CLASS[task]
    projection_id = uuid5(case.id, task.value)
    projection = TaskProjection(
        id=projection_id,
        case_id=case.id,
        task=task,
        contract_version=definition.contract_version,
        synthetic=True,
        baseline=case.deterministic_graph,
        allowed_evidence_ids=case.allowed_evidence_ids,
        untrusted_content_markers=("PROMPT_INJECTION_FIXTURE",)
        if case.prompt_injection_present
        else (),
        projection_hash="",
    )
    return replace(projection, projection_hash=_hash(asdict(projection)))


def assert_hidden_isolation() -> None:
    visible = cases_for_partition(CorpusPartition.DEVELOPMENT) + cases_for_partition(
        CorpusPartition.CALIBRATION
    )
    hidden = cases_for_partition(CorpusPartition.HIDDEN_QUALIFICATION, hidden_access=True)
    visible_ids = {item.id for item in visible}
    visible_hashes = {item.manifest_hash for item in visible}
    if visible_ids.intersection(item.id for item in hidden):
        raise AssertionError("hidden case id leaked")
    if visible_hashes.intersection(item.manifest_hash for item in hidden):
        raise AssertionError("hidden case content leaked")


def contaminated_graph(
    source: TournamentCaseBundle, foreign: TournamentCaseBundle
) -> SemanticGraph:
    """Hostile fixture helper that leaks a foreign entity/evidence reference."""
    claim = source.deterministic_graph.claims[0]
    foreign_evidence = foreign.allowed_evidence_ids[0]
    leaked_claim = replace(claim, evidence_ids=(*claim.evidence_ids, foreign_evidence))
    return replace(
        source.deterministic_graph,
        claims=(leaked_claim,),
        entity_ids=source.deterministic_graph.entity_ids + foreign.deterministic_graph.entity_ids,
    )
