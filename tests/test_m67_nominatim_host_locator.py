import runpy
from pathlib import Path

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "m67_nominatim_host_locator.py")
)
build_query = MODULE["build_query"]
project_response = MODULE["project_response"]
response_sha256 = MODULE["response_sha256"]

HASH = "a" * 64
OBSERVED = "2026-08-23T15:00:00Z"


def test_query_is_exact_field_limited_and_deterministic() -> None:
    query = build_query("Synthetic HVAC LLC", "Austin")
    assert query.startswith("https://nominatim.openstreetmap.org/search?")
    assert "q=Synthetic+HVAC+LLC%2C+Austin%2C+Texas" in query
    assert "countrycodes=us" in query
    assert "limit=3" in query
    assert query == build_query("Synthetic HVAC LLC", "Austin")


def test_only_business_host_and_content_free_provenance_survive() -> None:
    raw = [
        {
            "osm_type": "node",
            "osm_id": 42,
            "name": "Synthetic HVAC, LLC",
            "address": {"state": "Texas", "phone": "+1 555 0100"},
            "extratags": {
                "website": "https://www.synthetic-hvac.example/contact?person=Alice",
                "email": "alice@synthetic-hvac.example",
                "phone": "+1 555 0100",
                "contact:person": "Alice Example",
            },
            "display_name": "Synthetic HVAC, Alice Example, Austin, Texas",
        }
    ]
    result = project_response(
        public_business_name="Synthetic HVAC LLC",
        texas_city_or_service_area="Austin",
        response=raw,
        raw_artifact_sha256=HASH,
        observed_at=OBSERVED,
    )
    assert result["state"] == "LOCATED_PENDING_EXACT_HOST_A09_REVIEW"
    assert result["first_party_host_candidate"] == "www.synthetic-hvac.example"
    rendered = repr(result)
    assert "alice" not in rendered.casefold()
    assert "555" not in rendered
    assert "contact?" not in rendered


def test_ambiguous_hosts_and_unsafe_results_fail_closed() -> None:
    shared = {
        "name": "Synthetic HVAC LLC",
        "address": {"ISO3166-2-lvl4": "US-TX"},
        "osm_type": "way",
    }
    response = [
        {**shared, "osm_id": 1, "extratags": {"website": "https://one.example"}},
        {**shared, "osm_id": 2, "extratags": {"website": "https://two.example"}},
    ]
    result = project_response(
        public_business_name="Synthetic HVAC LLC",
        texas_city_or_service_area="Austin",
        response=response,
        raw_artifact_sha256=HASH,
        observed_at=OBSERVED,
    )
    assert result["state"] == "AMBIGUOUS"
    assert "first_party_host_candidate" not in result


def test_non_texas_social_and_contact_website_do_not_project() -> None:
    response = [
        {
            "osm_type": "node",
            "osm_id": 1,
            "name": "Synthetic HVAC LLC",
            "address": {"state": "Oklahoma"},
            "extratags": {"website": "https://synthetic.example"},
        },
        {
            "osm_type": "node",
            "osm_id": 2,
            "name": "Synthetic HVAC LLC",
            "address": {"state": "Texas"},
            "extratags": {
                "website": "https://facebook.com/synthetic",
                "contact:website": "https://synthetic.example",
            },
        },
    ]
    result = project_response(
        public_business_name="Synthetic HVAC LLC",
        texas_city_or_service_area="Austin",
        response=response,
        raw_artifact_sha256=HASH,
        observed_at=OBSERVED,
    )
    assert result["state"] == "NOT_FOUND"


def test_raw_response_hashing_requires_no_durable_body() -> None:
    assert response_sha256(b"synthetic raw with email alice@example.test") == (
        "bc4f57769d6ff2808cc7572a3023286da0b0804e0c8e6f86a98bd27715f68127"
    )
