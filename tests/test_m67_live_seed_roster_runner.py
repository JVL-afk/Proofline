import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = runpy.run_path(str(SCRIPTS / "run_m67_live_seed_roster_acquisition.py"))
build_tdlr_url = MODULE["build_tdlr_url"]
project_tdlr_rows = MODULE["project_tdlr_rows"]
build_observation = MODULE["build_observation"]


def eligible_row(**overrides: str) -> dict[str, str]:
    value = {
        "license_type": "Air Conditioning Contractor",
        "license_number": "SYNTHETIC-1",
        "business_county": "TRAVIS",
        "business_name": "Synthetic Cooling LLC",
        "business_city_state_zip": "Austin, TX 78701",
        "license_expiration_date_mmddccyy": "08/23/2027",
        "license_subtype": "Commercial Refrigeration and Process Cooling",
    }
    value.update(overrides)
    return value


def test_tdlr_request_projects_only_exact_fields_and_stable_limit() -> None:
    url = build_tdlr_url()
    assert url.startswith("https://data.texas.gov/api/v3/views/7358-krk7/query.json?")
    assert "LIMIT+500" in url
    assert "owner" not in url.casefold()
    assert "telephone" not in url.casefold()
    assert "email" not in url.casefold()


def test_tdlr_projection_is_fail_closed_and_commercial_specific() -> None:
    cutoff = datetime(2026, 8, 23, tzinfo=UTC)
    rows = [
        eligible_row(),
        eligible_row(business_name="Natural Person", license_number="SYNTHETIC-2"),
        eligible_row(
            license_subtype="Environmental Air Conditioning",
            license_number="SYNTHETIC-3",
        ),
        eligible_row(
            license_expiration_date_mmddccyy="08/23/2025",
            license_number="SYNTHETIC-4",
        ),
    ]
    frozen, counts = project_tdlr_rows(rows, cutoff=cutoff)
    assert frozen == [eligible_row()]
    assert counts["tdlr_records_considered"] == 4
    assert counts["eligible_business_entities"] == 1
    assert counts["NATURAL_PERSON_SOLE_PROPRIETOR_OR_AMBIGUOUS_NAME"] == 1
    assert counts["COMMERCIAL_HVAC_B2B_NOT_EXPLICIT"] == 1
    assert counts["EXPIRED_OR_UNPARSEABLE_LICENSE"] == 1


def test_observation_contains_only_business_evidence_and_content_free_provenance() -> None:
    host = {
        "state": "LOCATED_PENDING_EXACT_HOST_A09_REVIEW",
        "first_party_host_candidate": "synthetic.example",
        "provenance": {
            "source_id": "OSM_NOMINATIM_PUBLIC_SEARCH_V1",
            "source_artifact_sha256": "b" * 64,
            "locator": "osm:node:42",
            "observed_at": "2026-08-23T14:30:00Z",
        },
    }
    result = build_observation(
        eligible_row(),
        host,
        tdlr_hash="a" * 64,
        observed_at="2026-08-23T14:30:00Z",
    )
    rendered = repr(result).casefold()
    assert result["first_party_host_candidate"] == "synthetic.example"
    assert "email" not in rendered
    assert "telephone" not in rendered
    assert "person" not in rendered
    assert len(result["provenance"]) == 2
