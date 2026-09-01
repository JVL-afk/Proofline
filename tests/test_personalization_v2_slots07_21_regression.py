"""Deterministic-engine correctness regression on the EXACT sealed Slot
07/18/19/20/21 M1 evidence (2026-09-01 fix: fact-propagation loss, SERVICE_AREA
selector precision, phrase sanitation).

The fixture is one bounded read-only in-VPC SELECT export
(``tests/fixtures/personalization_v2_slots07_21_sealed_evidence.json``); it is an
immutable frozen fixture and the historical Slot 07-24 artifacts are never
mutated or re-scored. The five companies are the ones that reached M5.

Targets (owner directive A/B/C):
* A. Slot 19 (A-Plus) RESPONSE_COMMITMENT survives M2 -> M4 semantic input set and
  M5 projection set (it must no longer be silently truncated);
* B. Slot 19 A-Plus nav-menu SERVICE_AREA and Slot 21 Comfort-Air
  installation-process SERVICE_AREA are rejected -- with no invented geography;
* C. Slot 18 Elite's leading-asterisk phrase is sanitised for downstream render
  while the exact verbatim fragment is retained on the CompanyFact;
* at least one genuine SERVICE_AREA still passes (Slots 07/18/20);
* identical frozen input -> byte-identical composer output.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

import pytest
from conftest import FakeClock
from fastapi.testclient import TestClient
from opintel_audit_local import SqlAlchemyAuditRepository
from opintel_demo_local import SqlAlchemyDemoRepository
from opintel_opportunity.domain import EvidenceReference, FactCategory
from opintel_opportunity.personalization import (
    SELECTOR_VERSION,
    _sanitize_phrase,
    _valid_service_area_phrase,
    select_company_facts,
)
from opintel_opportunity_local import (
    SqlAlchemyOpportunityRepository,
)
from opintel_outreach.composition import DeterministicOutreachComposer
from opintel_outreach.domain import ArtifactAudience, ArtifactKind, ProjectionMode
from opintel_outreach_local import SqlAlchemyOutreachRepository
from opintel_research_local import SqlAlchemyResearchRepository
from test_personalization_v2_fixtures import FixedIdentifiers, _run_pipeline

SEALED = Path(__file__).parent / "fixtures" / "personalization_v2_slots07_21_sealed_evidence.json"
_DATA = json.loads(SEALED.read_text(encoding="utf-8"))["companies"]

_NAME_BY_SLOT = {c["slot"]: name for name, c in _DATA.items()}


def _spec(slot: int) -> dict[str, object]:
    name = _NAME_BY_SLOT[slot]
    c = _DATA[name]
    return {
        "name": name,
        "pages_attempted": c["pages_attempted"],
        "pages_succeeded": c["pages_succeeded"],
        "run_status": c["run_status"],
        "fragments": [e["fragment"] for e in c["evidence"]],
        "fact_classes": [e["fact_class"] for e in c["evidence"]],
        "page_purposes": [e["page_purpose"] for e in c["evidence"]],
    }


def _refs(slot: int) -> tuple[EvidenceReference, ...]:
    name = _NAME_BY_SLOT[slot]
    now = datetime(2026, 9, 1, tzinfo=UTC)
    out = []
    for e in _DATA[name]["evidence"]:
        out.append(
            EvidenceReference(
                id=uuid5(UUID(int=0), e["id"]),
                workspace_id=UUID(int=1),
                business_id=UUID(int=2),
                research_run_id=UUID(int=3),
                snapshot_id=UUID(int=4),
                snapshot_version=e["snapshot_version"],
                source_uri=e["source_uri"],
                captured_at=now,
                content_sha256=e["content_sha256"],
                locator=e["locator"],
                fragment=e["fragment"],
                extractor_name=e["extractor_name"],
                extractor_version=e["extractor_version"],
                fact_class=e["fact_class"],
                page_purpose=e["page_purpose"],
            )
        )
    return tuple(out)


def _facts(slot: int):
    return select_company_facts(
        UUID(int=9), _refs(slot), FixedIdentifiers(), datetime(2026, 9, 1, tzinfo=UTC)
    )


# --- selector-level regression (no full pipeline) -----------------------------


def test_selector_is_at_least_v3() -> None:
    assert SELECTOR_VERSION == "commercial_hvac.company_fact_selector@3"


def test_slot19_aplus_response_commitment_selected() -> None:
    cats = {f.category for f in _facts(19)}
    assert FactCategory.RESPONSE_COMMITMENT in cats
    rc = next(f for f in _facts(19) if f.category == FactCategory.RESPONSE_COMMITMENT)
    assert "fast response times" in rc.phrase.lower()


def test_slot19_aplus_nav_menu_service_area_rejected() -> None:
    facts = _facts(19)
    area = [f for f in facts if f.category == FactCategory.SERVICE_AREA_CONTEXT]
    # the nav-menu concatenation ("... View All Heating Services View All Cooling
    # Services Handyman") must never be selected as a service area.
    for f in area:
        low = f.phrase.lower()
        assert "view all" not in low
        assert "handyman" not in low
        assert len(f.phrase.split()) <= 12
    # the specific bad string is rejected by the predicate directly
    bad = (
        "Air Conditioning Installation Services Austin, TX Heating & Cooling "
        "Heating Air Conditioning View All Heating Services View All Cooling "
        "Services Handyman"
    )
    assert _valid_service_area_phrase(bad) is False


def test_slot21_comfortair_installation_boilerplate_service_area_rejected() -> None:
    facts = _facts(21)
    for f in facts:
        if f.category == FactCategory.SERVICE_AREA_CONTEXT:
            low = f.phrase.lower()
            assert "installation process" not in low
            assert "can vary between" not in low
            assert "calculate the heating" not in low
    bad = (
        "Details can vary between sites and projects, but in general, the HVAC "
        "installation process includes: Calculate the heating and cooling demands "
        "of the property"
    )
    assert _valid_service_area_phrase(bad) is False


def test_valid_service_area_heads_still_pass() -> None:
    for good in (
        "Our Service Area",
        "Service Areas",
        "Just a Sample of Our Service Areas",
        "Areas We Serve",
        "Proudly Serving the Austin Area",
    ):
        assert _valid_service_area_phrase(good) is True
    # and the genuine frozen ones survive selection
    for slot in (7, 18, 20):
        area = [f for f in _facts(slot) if f.category == FactCategory.SERVICE_AREA_CONTEXT]
        assert len(area) == 1
        assert "service area" in area[0].phrase.lower()


def test_slot18_leading_asterisk_sanitised_verbatim_preserved() -> None:
    avail = next(f for f in _facts(18) if f.category == FactCategory.SERVICE_AVAILABILITY)
    assert not avail.phrase.startswith("*")
    assert avail.phrase == "About Our 24-Hour Service"
    assert avail.verbatim_phrase == "*About Our 24-Hour Service"
    assert avail.content_sha256  # still traceable to the minimized evidence


def test_sanitation_is_character_level_only() -> None:
    assert _sanitize_phrase("*About Our 24-Hour Service") == "About Our 24-Hour Service"
    assert _sanitize_phrase("  • our service area ") == "Our service area"
    # a trailing navigation tail is dropped
    assert (
        _sanitize_phrase("Commercial HVAC Repair View All Cooling Services")
        == "Commercial HVAC Repair"
    )
    # a mid-clause truncation loses its dangling connector
    assert _sanitize_phrase("air conditioning installation and") == "Air conditioning installation"
    # meaning-bearing punctuation and digits are untouched
    assert _sanitize_phrase("Do you offer 24/7 emergency HVAC services?") == (
        "Do you offer 24/7 emergency HVAC services?"
    )


def test_selector_is_deterministic() -> None:
    for slot in (7, 18, 19, 20, 21):
        a = [(f.category.value, f.phrase, f.verbatim_phrase) for f in _facts(slot)]
        b = [(f.category.value, f.phrase, f.verbatim_phrase) for f in _facts(slot)]
        assert a == b


# --- full-pipeline regression (M2 -> M5 on frozen evidence) -------------------


@pytest.fixture(scope="module")
def _slot_names() -> dict[int, str]:
    return _NAME_BY_SLOT


@pytest.mark.integration
def test_aplus_response_commitment_reaches_m4_and_m5(
    client: TestClient,
    auth_headers: dict[str, str],
    research_repository: SqlAlchemyResearchRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    audit_repository: SqlAlchemyAuditRepository,
    demo_repository: SqlAlchemyDemoRepository,
    outreach_repository: SqlAlchemyOutreachRepository,
    clock: FakeClock,
) -> None:
    result = _run_pipeline(
        client,
        auth_headers,
        research_repository,
        opportunity_repository,
        audit_repository,
        demo_repository,
        outreach_repository,
        clock,
        _spec(19),
        "s19aplus",
    )
    # M3 carries the response-commitment finding
    finding_kinds = {f["kind"] for f in result["m3"]["findings"]}  # type: ignore[index]
    assert "observed_response_commitment" in finding_kinds

    # A. M4 semantic input set records the response-commitment fact even though
    #    the demo does not render it as a synthetic option.
    spec = result["m4"]["specification"]  # type: ignore[index]
    sfi = {s["category"]: s for s in spec["semantic_fact_inputs"]}
    assert "response_commitment" in sfi
    assert sfi["response_commitment"]["rendered_as_demo_option"] is False
    assert sfi["response_commitment"]["non_option_reason"]
    assert sfi["response_commitment"]["retention"] == "SEMANTIC_INPUT_RETAINED"
    # every selected M2 fact reached M4
    m2_fact_categories = {
        cf["category"]
        for cf in result["m2"]["company_facts"]  # type: ignore[index]
    }
    assert m2_fact_categories == set(sfi)

    # A. M5 projects the response-commitment fact (available downstream) and
    #    records the omission from the first-contact body as policy-driven.
    m5 = result["m5"]
    derived = [
        p
        for p in m5.projections  # type: ignore[attr-defined]
        if p.mode == ProjectionMode.EVIDENCE_DERIVED_FACT
    ]
    assert len(derived) >= 3  # intake + commercial + response_commitment (+ service_area)
    p = m5.personalization  # type: ignore[attr-defined]
    assert p.available_fact_projection_count >= 3
    assert p.rendered_fact_projection_count <= 2
    assert "response_commitment" in p.omitted_fact_categories
    assert p.omission_policy_version == "outreach.projection@4"
    # nothing silently lost: no fact_projection_dropped QC finding
    assert not any(
        f.code == "fact_projection_dropped"
        for f in m5.qc_findings  # type: ignore[attr-defined]
    )


@pytest.mark.integration
def test_aplus_and_comfortair_bad_service_area_gone_from_m2_m3(
    client: TestClient,
    auth_headers: dict[str, str],
    research_repository: SqlAlchemyResearchRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    audit_repository: SqlAlchemyAuditRepository,
    demo_repository: SqlAlchemyDemoRepository,
    outreach_repository: SqlAlchemyOutreachRepository,
    clock: FakeClock,
) -> None:
    for slot, key in ((19, "s19aplus2"), (21, "s21comfort")):
        result = _run_pipeline(
            client,
            auth_headers,
            research_repository,
            opportunity_repository,
            audit_repository,
            demo_repository,
            outreach_repository,
            clock,
            _spec(slot),
            key,
        )
        statement = result["m2"]["hypothesis"]["statement"]  # type: ignore[index]
        assert "View All" not in statement
        assert "installation process includes" not in statement
        assert "Calculate the heating and cooling demands" not in statement
        for cf in result["m2"]["company_facts"]:  # type: ignore[index]
            if cf["category"] == "service_area_context":
                assert len(cf["phrase"].split()) <= 12
                assert "view all" not in cf["phrase"].lower()


@pytest.mark.integration
def test_frozen_pipeline_is_byte_identical(
    client: TestClient,
    auth_headers: dict[str, str],
    research_repository: SqlAlchemyResearchRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    audit_repository: SqlAlchemyAuditRepository,
    demo_repository: SqlAlchemyDemoRepository,
    outreach_repository: SqlAlchemyOutreachRepository,
    clock: FakeClock,
) -> None:
    result = _run_pipeline(
        client,
        auth_headers,
        research_repository,
        opportunity_repository,
        audit_repository,
        demo_repository,
        outreach_repository,
        clock,
        _spec(18),
        "s18",
    )
    source = result["m5_source"]
    first_compose = DeterministicOutreachComposer(FixedIdentifiers()).compose(
        package_id=UUID(int=7),
        revision_number=1,
        parent_revision_id=None,
        source=source,
        created_by="regression",
        now=clock.now(),
    )
    second_compose = DeterministicOutreachComposer(FixedIdentifiers()).compose(
        package_id=UUID(int=7),
        revision_number=1,
        parent_revision_id=None,
        source=source,
        created_by="regression",
        now=clock.now(),
    )
    assert first_compose.content_hash == second_compose.content_hash
    assert first_compose.revision_hash == second_compose.revision_hash
    # Slot 18 still surfaces a genuine service-area and a sanitised availability;
    # the raw asterisk fragment never reaches a reader-facing artifact.
    ext = "\n".join(
        art.rendered_text
        for art in result["m5"].artifacts  # type: ignore[attr-defined]
        if art.audience == ArtifactAudience.EXTERNAL
    )
    assert "*About Our 24-Hour Service" not in ext
    m3_avail = next(
        f
        for f in result["m3"]["findings"]  # type: ignore[index]
        if f["kind"] == "observed_service_availability"
    )
    assert not (m3_avail["supporting_excerpt"] or "").startswith("*")
    first = next(
        art
        for art in result["m5"].artifacts  # type: ignore[attr-defined]
        if art.kind == ArtifactKind.FIRST_CONTACT_EMAIL
    )
    assert "{{functional_role_or_team}}" in first.rendered_text  # still non-send-ready
