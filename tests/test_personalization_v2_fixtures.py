"""EVIDENCE_PRESERVING_PERSONALIZATION_V2 deterministic regression fixtures.

The three company fixtures are the EXACT sealed Slot 02-04 M1 evidence rows, from
one bounded read-only in-VPC SELECT export
(``tests/fixtures/personalization_v2_sealed_evidence.json``). They are immutable
frozen fixtures: no real research is run and the historical Slot 02-04 artifacts
are never mutated or reinterpreted.

Validation targets (implementation + deploy-prep authorization):
* Webb Air, BNCAIR and All Elements produce materially different M2/M3/M4/M5
  outputs where their evidence differs;
* identical evidence produces byte-identical composer output;
* Webb Air's actual contact-page response language survives into reader-facing
  output as a RESPONSE_COMMITMENT;
* bare service-availability claims ("24 Hour Emergency Services",
  "Fast & Reliable Service, 24/7") are SERVICE_AVAILABILITY, never
  RESPONSE_COMMITMENT (owner semantic review, 2026-08-31);
* All Elements partial-crawl status is visible in M3; its absence of
  public_service_area evidence is an accepted exact-fixture correction (the
  synthetic M4 location fallback is preserved);
* BNCAIR stays appropriately sparse rather than padded;
* the company name alone never satisfies the personalization gate;
* all-public_other evidence fails company-specific M5 approval;
* unresolved required placeholders produce DRAFT_INCOMPLETE;
* no HIGH/LOW / review-priority language leaks into external artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid5

import pytest
from conftest import FakeClock
from fastapi.testclient import TestClient
from opintel_audit import AuditWorkflowRunner
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
from opintel_demo import DemoWorkflowRunner
from opintel_demo.composition import DeterministicDemoComposer
from opintel_demo_local import CanonicalDemoSourceCatalog, SqlAlchemyDemoRepository
from opintel_m0_local import UuidFactory
from opintel_opportunity import OpportunityWorkflowRunner
from opintel_opportunity_local import (
    EchoMockReasoner,
    ResearchEvidenceCatalog,
    SqlAlchemyOpportunityRepository,
)
from opintel_outreach.composition import DeterministicOutreachComposer
from opintel_outreach.domain import ArtifactAudience, OutreachRevisionState, ProjectionMode
from opintel_outreach_local import SqlAlchemyOutreachRepository
from opintel_research_local import SqlAlchemyResearchRepository
from test_m2_opportunity_engine import seed_research_evidence

GOLDEN = Path(__file__).parent / "fixtures" / "personalization_v2_golden.json"
SEALED = Path(__file__).parent / "fixtures" / "personalization_v2_sealed_evidence.json"

_SEALED_DATA = json.loads(SEALED.read_text(encoding="utf-8"))["companies"]


def _sealed_spec(name: str) -> dict[str, object]:
    c = _SEALED_DATA[name]
    return {
        "name": name,
        "pages_attempted": c["pages_attempted"],
        "pages_succeeded": c["pages_succeeded"],
        "run_status": c["run_status"],
        "fragments": [e["fragment"] for e in c["evidence"]],
        "fact_classes": [e["fact_class"] for e in c["evidence"]],
        "page_purposes": [e["page_purpose"] for e in c["evidence"]],
    }


class FixedIdentifiers:
    def __init__(self) -> None:
        self.index = 0

    def new(self) -> UUID:
        self.index += 1
        return uuid5(UUID(int=0), f"pv2-fixed-{self.index}")


# --- fixtures: EXACT sealed Slot 02-04 M1 evidence (in-VPC SELECT export) ------

WEBB_AIR = _sealed_spec("Webb Air")
BNCAIR = _sealed_spec("BNCAIR")
ALL_ELEMENTS = _sealed_spec("All Elements Heating & Air")

# Negative: evidence forced to public_other; still triggers an M2 hypothesis via
# the fragment text but yields no CompanyFact.
ALL_PUBLIC_OTHER = {
    "name": "Placeholder Air",
    "pages_attempted": 4,
    "pages_succeeded": 4,
    "run_status": "succeeded",
    "fragments": [
        "commercial hvac contractor overview",
        "request service by calling our team",
    ],
    "fact_classes": ["public_other", "public_other"],
}


def _run_pipeline(
    client: TestClient,
    headers: dict[str, str],
    research: SqlAlchemyResearchRepository,
    opportunities: SqlAlchemyOpportunityRepository,
    audits: SqlAlchemyAuditRepository,
    demos: SqlAlchemyDemoRepository,
    outreach: SqlAlchemyOutreachRepository,
    clock: FakeClock,
    spec: dict[str, object],
    key: str,
) -> dict[str, object]:
    business, run = seed_research_evidence(
        client,
        headers,
        research,
        clock,
        list(spec["fragments"]),
        key,
        business_name=str(spec["name"]),
        pages_attempted=int(spec["pages_attempted"]),
        pages_succeeded=int(spec["pages_succeeded"]),
        run_status=str(spec["run_status"]),
        fact_classes=spec.get("fact_classes"),  # type: ignore[arg-type]
        page_purposes=spec.get("page_purposes"),  # type: ignore[arg-type]
    )
    created = client.post(
        f"/api/v1/businesses/{business['id']}/opportunity-analysis-runs",
        headers={**headers, "Idempotency-Key": f"pv2-an-{key}"},
        json={"research_run_id": run["id"]},
    )
    assert created.status_code == 202, created.text
    OpportunityWorkflowRunner(
        opportunities, ResearchEvidenceCatalog(research), EchoMockReasoner(), clock, UuidFactory()
    ).run_once()
    m2 = client.get(
        f"/api/v1/opportunity-analysis-runs/{created.json()['id']}/result", headers=headers
    ).json()
    result: dict[str, object] = {"business": business, "m2": m2}
    if m2["hypothesis"] is None:
        return result
    hypothesis = m2["hypothesis"]
    accepted = client.post(
        f"/api/v1/opportunities/{hypothesis['logical_id']}/review-decisions",
        headers=headers,
        json={
            "expected_hypothesis_revision_id": hypothesis["id"],
            "decision": "accept",
            "reason": "PV2 fixture acceptance.",
        },
    )
    assert accepted.status_code == 200, accepted.text

    audit_source = CanonicalAuditSourceCatalog(opportunities, research)
    created_audit = client.post(
        f"/api/v1/opportunities/{hypothesis['logical_id']}/audit-revisions",
        headers={**headers, "Idempotency-Key": f"pv2-au-{key}"},
        json={"expected_hypothesis_revision_id": hypothesis["id"]},
    )
    assert created_audit.status_code == 202, created_audit.text
    AuditWorkflowRunner(
        audits, audit_source, DeterministicAuditComposerFixed(), clock
    ).run_once()
    audit_op = client.get(
        f"/api/v1/audit-operations/{created_audit.json()['operation']['id']}", headers=headers
    ).json()["operation"]
    audit = client.get(
        f"/api/v1/audit-revisions/{audit_op['audit_revision_id']}", headers=headers
    ).json()
    result["m3"] = audit["revision"]
    approved = client.post(
        f"/api/v1/audit-revisions/{audit['revision']['id']}/review-decisions",
        headers=headers,
        json={
            "expected_revision_hash": audit["revision"]["revision_hash"],
            "expected_manifest_hash": audit["revision"]["manifest"]["checksum"],
            "decision": "approve",
            "reason": "PV2 fixture audit approval.",
        },
    )
    assert approved.status_code == 200, approved.text

    demo_source = CanonicalDemoSourceCatalog(
        client.app.state.audit_repository, opportunities, research
    )
    created_demo = client.post(
        f"/api/v1/audit-revisions/{audit['revision']['id']}/demo-revisions",
        headers={**headers, "Idempotency-Key": f"pv2-de-{key}"},
        json={"expected_audit_revision_hash": audit["revision"]["revision_hash"]},
    )
    assert created_demo.status_code == 202, created_demo.text
    DemoWorkflowRunner(
        demos, demo_source, DeterministicDemoComposer(UuidFactory()), clock
    ).run_once()
    demo_op = client.get(
        f"/api/v1/demo-operations/{created_demo.json()['operation']['id']}", headers=headers
    ).json()["operation"]
    demo = client.get(
        f"/api/v1/demo-revisions/{demo_op['demo_revision_id']}", headers=headers
    ).json()
    result["m4"] = demo["revision"]
    approve_demo = client.post(
        f"/api/v1/demo-revisions/{demo['revision']['id']}/review-decisions",
        headers=headers,
        json={
            "expected_revision_hash": demo["revision"]["revision_hash"],
            "expected_manifest_hash": demo["revision"]["manifest"]["checksum"],
            "expected_specification_hash": demo["revision"]["specification_hash"],
            "decision": "approve",
            "reason": "PV2 fixture demo approval.",
        },
    )
    assert approve_demo.status_code == 200, approve_demo.text

    outreach_source = client.app.state.outreach_source
    source = outreach_source.get_inputs(
        UUID(demo["revision"]["workspace_id"]), UUID(demo["revision"]["id"])
    )
    assert source is not None
    revision = DeterministicOutreachComposer(FixedIdentifiers()).compose(
        package_id=UUID(int=7),
        revision_number=1,
        parent_revision_id=None,
        source=source,
        created_by="pv2-fixture",
        now=clock.now(),
    )
    result["m5"] = revision
    result["m5_source"] = source
    return result


class DeterministicAuditComposerFixed:
    """Wraps the real deterministic audit composer with fixed ids for byte-stable
    audit revisions in fixtures."""

    def __init__(self) -> None:
        from opintel_audit.composition import DeterministicAuditComposer

        self._inner = DeterministicAuditComposer(FixedIdentifiers())

    def compose(self, **kwargs: object) -> object:
        return self._inner.compose(**kwargs)  # type: ignore[arg-type]


@pytest.fixture
def pipelines(
    client: TestClient,
    auth_headers: dict[str, str],
    research_repository: SqlAlchemyResearchRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    audit_repository: SqlAlchemyAuditRepository,
    demo_repository: SqlAlchemyDemoRepository,
    outreach_repository: SqlAlchemyOutreachRepository,
    clock: FakeClock,
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for key, spec in (
        ("webbair", WEBB_AIR),
        ("bncair", BNCAIR),
        ("allelements", ALL_ELEMENTS),
    ):
        out[key] = _run_pipeline(
            client,
            auth_headers,
            research_repository,
            opportunity_repository,
            audit_repository,
            demo_repository,
            outreach_repository,
            clock,
            spec,
            key,
        )
    return out


def _first_email_text(revision: object) -> str:
    for artifact in revision.artifacts:  # type: ignore[attr-defined]
        if artifact.kind.value == "first_contact_email":
            return artifact.rendered_text
    raise AssertionError("no first-contact email")


def _personalization_dict(revision: object) -> dict[str, object]:
    p = revision.personalization  # type: ignore[attr-defined]
    return {
        "company_specific_segment_count": p.company_specific_segment_count,
        "distinct_fact_classes": p.distinct_fact_classes,
        "passes_gate": p.passes_gate,
    }


def _external_text(revision: object) -> str:
    return "\n".join(
        a.rendered_text
        for a in revision.artifacts  # type: ignore[attr-defined]
        if a.audience == ArtifactAudience.EXTERNAL
    )


# --- validation targets -------------------------------------------------------


@pytest.mark.integration
def test_webbair_response_and_service_facts_survive_to_reader_output(
    pipelines: dict[str, dict[str, object]],
) -> None:
    webb = pipelines["webbair"]
    statement = webb["m2"]["hypothesis"]["statement"].lower()  # type: ignore[index]
    assert "webb air" in statement
    assert "commercial" in statement
    # Webb Air's actual contact-page response language qualifies as a
    # RESPONSE_COMMITMENT (phones answered / email responses / contacted after).
    assert "how inbound inquiries are answered" in statement
    assert "unknown" in statement and "response performance" in statement  # truth tail intact

    email = _first_email_text(webb["m5"]).lower()
    assert "commercial" in email  # service fact
    assert "request" in email  # intake fact
    finding_kinds = {f["kind"] for f in webb["m3"]["findings"]}  # type: ignore[index]
    assert "observed_response_commitment" in finding_kinds
    assert "observed_service_area" in finding_kinds
    assert "observed_commercial_context" in finding_kinds
    # The Webb response-commitment finding cites a fragment that actually
    # describes inbound handling, not mere availability.
    resp = next(
        f for f in webb["m3"]["findings"]  # type: ignore[index]
        if f["kind"] == "observed_response_commitment"
    )
    excerpt = (resp["supporting_excerpt"] or "").lower()
    assert any(
        cue in excerpt
        for cue in ("phones are answered", "email response", "contacted after", "next business day")
    )


@pytest.mark.integration
def test_bare_availability_is_never_a_response_commitment(
    pipelines: dict[str, dict[str, object]],
) -> None:
    """Owner semantic review (2026-08-31): '24 Hour Emergency Services' /
    'Fast & Reliable Service, 24/7' are SERVICE_AVAILABILITY, not
    RESPONSE_COMMITMENT."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from opintel_opportunity.domain import EvidenceReference, FactCategory
    from opintel_opportunity.personalization import _bucket

    def bucket(fragment: str, fact_class: str) -> FactCategory | None:
        return _bucket(
            EvidenceReference(
                uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), "v", "u",
                datetime.now(UTC), "x" * 64, "l", fragment, "e", "1", fact_class, "unclassified",
            )
        )

    # bare availability -> SERVICE_AVAILABILITY, not RESPONSE_COMMITMENT
    assert bucket("24 Hour Emergency Services and Free Quotes", "public_other") == (
        FactCategory.SERVICE_AVAILABILITY
    )
    assert bucket("Fast & Reliable Service, 24/7", "public_other") == (
        FactCategory.SERVICE_AVAILABILITY
    )
    assert bucket("Same-day service available", "public_other") == (
        FactCategory.SERVICE_AVAILABILITY
    )
    # genuine inbound-response language -> RESPONSE_COMMITMENT
    assert bucket(
        "Phones are answered 24 hours; email responses are sent the next business day.",
        "public_inbound_path",
    ) == FactCategory.RESPONSE_COMMITMENT
    assert bucket(
        "We will call you back within one business day of your request.", "public_faq"
    ) == FactCategory.RESPONSE_COMMITMENT
    assert bucket(
        "Requests submitted after 10pm are contacted after 8am the following day.",
        "public_inbound_path",
    ) == FactCategory.RESPONSE_COMMITMENT
    # availability text is still recognised as an availability fact, not dropped
    assert bucket("Around the clock emergency service", "public_service_description") == (
        FactCategory.SERVICE_AVAILABILITY
    )


@pytest.mark.integration
def test_all_elements_availability_not_response_after_correction(
    pipelines: dict[str, dict[str, object]],
) -> None:
    ae = pipelines["allelements"]
    finding_kinds = {f["kind"] for f in ae["m3"]["findings"]}  # type: ignore[index]
    # All Elements' only response-cue evidence is "24/7" / "24 hour emergency
    # service" -> availability, NOT a response commitment.
    assert "observed_response_commitment" not in finding_kinds
    assert "observed_service_availability" in finding_kinds
    # no manufactured service-area option (no public_service_area evidence)
    assert "observed_service_area" not in finding_kinds
    q = next(
        x for x in ae["m4"]["specification"]["questions"]  # type: ignore[index]
        if x["id"] == "service_location"
    )
    assert list(q["allowed_values"]) == [
        "north_texas", "central_texas", "gulf_coast", "other", "unknown",
    ]


@pytest.mark.integration
def test_all_elements_partial_crawl_visible_in_m3(
    pipelines: dict[str, dict[str, object]],
) -> None:
    findings = pipelines["allelements"]["m3"]["findings"]  # type: ignore[index]
    coverage = next(f for f in findings if f["kind"] == "crawl_coverage")
    assert "partial" in coverage["text"].lower()
    assert "13 of 20" in coverage["text"]
    scope = next(
        s for s in pipelines["allelements"]["m3"]["sections"]  # type: ignore[index]
        if s["key"] == "scope"
    )
    assert "partial" in json.dumps(scope["structured_items"]).lower()


@pytest.mark.integration
def test_bncair_is_sparse_not_padded(pipelines: dict[str, dict[str, object]]) -> None:
    bncair = pipelines["bncair"]
    finding_kinds = {f["kind"] for f in bncair["m3"]["findings"]}  # type: ignore[index]
    # No response-commitment / service-area / availability evidence -> those
    # findings are absent, not invented.
    assert "observed_response_commitment" not in finding_kinds
    assert "observed_service_area" not in finding_kinds
    assert "observed_service_availability" not in finding_kinds
    m5 = bncair["m5"]
    derived = [p for p in m5.projections if p.mode == ProjectionMode.EVIDENCE_DERIVED_FACT]  # type: ignore[attr-defined]
    assert 1 <= len(derived) <= 2
    assert m5.personalization.passes_gate is True  # type: ignore[attr-defined]


@pytest.mark.integration
def test_company_name_alone_never_satisfies_gate(
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
        ALL_PUBLIC_OTHER,
        "negative",
    )
    m5 = result["m5"]
    assert m5.personalization.passes_gate is False  # type: ignore[attr-defined]
    assert any(
        f.code == "no_company_specific_evidence" for f in m5.qc_findings  # type: ignore[attr-defined]
    )
    assert m5.state == OutreachRevisionState.QC_FAILED  # type: ignore[attr-defined]


@pytest.mark.integration
def test_all_public_other_fails_company_specific_m5_approval(
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
        ALL_PUBLIC_OTHER,
        "negative2",
    )
    m5 = result["m5"]
    assert not m5.hard_qc_passed  # type: ignore[attr-defined]
    # M2 statement fell back to the exact legacy text (no company fact).
    from opintel_opportunity.personalization import LEGACY_SAFE_STATEMENT

    assert result["m2"]["hypothesis"]["statement"] == LEGACY_SAFE_STATEMENT  # type: ignore[index]


@pytest.mark.integration
def test_unresolved_placeholders_produce_draft_incomplete(
    pipelines: dict[str, dict[str, object]],
) -> None:
    for key in ("webbair", "bncair", "allelements"):
        m5 = pipelines[key]["m5"]
        assert m5.state == OutreachRevisionState.DRAFT_INCOMPLETE  # type: ignore[attr-defined]
        assert set(m5.unresolved_slot_kinds) == {  # type: ignore[attr-defined]
            "approved_opt_out_instruction_slot",
            "required_postal_disclosure_slot",
            "verified_sender_slot",
        }


@pytest.mark.integration
def test_no_score_language_leaks_into_external_artifacts(
    pipelines: dict[str, dict[str, object]],
) -> None:
    import re

    leak = re.compile(r"\b(high|low)\b.{0,40}\b(priority|confidence|band)\b|review priority", re.I)
    for key in ("webbair", "bncair", "allelements"):
        text = _external_text(pipelines[key]["m5"])
        assert not leak.search(text), key
        assert "HIGH" not in text and "LOW" not in text


@pytest.mark.integration
def test_three_companies_diverge_where_evidence_differs(
    pipelines: dict[str, dict[str, object]],
) -> None:
    statements = {
        key: pipelines[key]["m2"]["hypothesis"]["statement"]  # type: ignore[index]
        for key in ("webbair", "bncair", "allelements")
    }
    assert len(set(statements.values())) == 3

    emails = {key: _first_email_text(pipelines[key]["m5"]) for key in statements}
    assert len(set(emails.values())) == 3
    assert emails["webbair"] != emails["bncair"] != emails["allelements"]

    subjects = {
        key: next(
            a.rendered_text
            for a in pipelines[key]["m5"].artifacts  # type: ignore[attr-defined]
            if a.kind.value == "subject"
        )
        for key in statements
    }
    assert len(set(subjects.values())) == 3

    # M4 service option sets differ.
    def need_options(key: str) -> tuple[str, ...]:
        spec = pipelines[key]["m4"]["specification"]  # type: ignore[index]
        q = next(x for x in spec["questions"] if x["id"] == "service_need")
        return tuple(q["allowed_values"])

    assert need_options("webbair") != need_options("bncair")
    assert need_options("webbair") != need_options("allelements")

    # Webb Air alone is internally HIGH; the others LOW; never surfaced externally.
    bands = {
        key: pipelines[key]["m2"]["score_snapshot"]["review_priority_band"]  # type: ignore[index]
        for key in statements
    }
    assert bands["webbair"] == "HIGH"
    assert bands["bncair"] == "LOW" and bands["allelements"] == "LOW"
    hints = {
        key: pipelines[key]["m2"]["score_snapshot"]["review_rank_hint"]  # type: ignore[index]
        for key in statements
    }
    assert hints["allelements"]["partial_crawl"] is True
    assert hints["webbair"]["partial_crawl"] is False


@pytest.mark.integration
def test_identical_evidence_is_byte_identical(
    pipelines: dict[str, dict[str, object]],
    clock: FakeClock,
) -> None:
    source = pipelines["webbair"]["m5_source"]
    first = DeterministicOutreachComposer(FixedIdentifiers()).compose(
        package_id=UUID(int=7),
        revision_number=1,
        parent_revision_id=None,
        source=source,
        created_by="pv2-fixture",
        now=clock.now(),
    )
    second = DeterministicOutreachComposer(FixedIdentifiers()).compose(
        package_id=UUID(int=7),
        revision_number=1,
        parent_revision_id=None,
        source=source,
        created_by="pv2-fixture",
        now=clock.now(),
    )
    assert first.content_hash == second.content_hash
    assert first.revision_hash == second.revision_hash


@pytest.mark.integration
def test_golden_renders_match(pipelines: dict[str, dict[str, object]]) -> None:
    rendered = {}
    for key in ("webbair", "bncair", "allelements"):
        p = pipelines[key]
        rendered[key] = {
            "m2_statement": p["m2"]["hypothesis"]["statement"],  # type: ignore[index]
            "m2_priority_band": p["m2"]["score_snapshot"]["review_priority_band"],  # type: ignore[index]
            "m3_finding_kinds": sorted({f["kind"] for f in p["m3"]["findings"]}),  # type: ignore[index]
            "m4_service_need": list(
                next(
                    q["allowed_values"]
                    for q in p["m4"]["specification"]["questions"]  # type: ignore[index]
                    if q["id"] == "service_need"
                )
            ),
            "m4_service_location": list(
                next(
                    q["allowed_values"]
                    for q in p["m4"]["specification"]["questions"]  # type: ignore[index]
                    if q["id"] == "service_location"
                )
            ),
            "m5_subject": next(
                a.rendered_text
                for a in p["m5"].artifacts  # type: ignore[attr-defined]
                if a.kind.value == "subject"
            ),
            "m5_first_email": _first_email_text(p["m5"]),
            "m5_personalization": _personalization_dict(p["m5"]),
        }
    if not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(rendered, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        pytest.skip("golden written")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert rendered == expected
