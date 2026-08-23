import runpy
from pathlib import Path

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "m67_nominatim_host_guard.py")
)
guard_projection = MODULE["guard_projection"]
ALLOWED_OSM_HOST_TAGS = MODULE["ALLOWED_OSM_HOST_TAGS"]

PROVENANCE = {
    "source_id": "OSM_NOMINATIM_PUBLIC_SEARCH_V1",
    "source_artifact_sha256": "a" * 64,
    "locator": "osm:node:42",
    "observed_at": "2026-08-23T14:30:00Z",
}


def projection(host: str) -> dict[str, object]:
    return {
        "state": "LOCATED_PENDING_EXACT_HOST_A09_REVIEW",
        "public_business_name": "Synthetic HVAC LLC",
        "texas_city_or_service_area": "Austin",
        "first_party_host_candidate": host,
        "locator": "osm:node:42",
        "provenance": PROVENANCE,
    }


def test_only_exact_osm_website_tag_is_allowlisted() -> None:
    assert ALLOWED_OSM_HOST_TAGS == ("website",)


def test_directories_marketplaces_social_and_shorteners_fail_closed() -> None:
    for host in (
        "yelp.com",
        "profile.thumbtack.com",
        "bbb.org",
        "maps.google.com",
        "facebook.com",
        "linktr.ee",
    ):
        result = guard_projection(projection(host))
        assert result["state"] == "AMBIGUOUS"
        assert result["reason"] == "THIRD_PARTY_HOST_REJECTED"
        assert "first_party_host_candidate" not in result
        assert "locator" not in result["provenance"]


def test_acceptable_host_remains_pending_exact_a09_review() -> None:
    result = guard_projection(projection("synthetic-hvac.example"))
    assert result == projection("synthetic-hvac.example")


def test_not_found_and_ambiguous_never_gain_a_fallback_host() -> None:
    for state in ("NOT_FOUND", "AMBIGUOUS", "QUARANTINED"):
        result = guard_projection({"state": state, "provenance": PROVENANCE})
        assert result["state"] == state
        assert "first_party_host_candidate" not in result


def test_unexpected_fields_fail_closed_before_durable_projection() -> None:
    value = projection("synthetic-hvac.example")
    value["email"] = "person@example.test"
    result = guard_projection(value)
    assert result["state"] == "AMBIGUOUS"
    assert "email" not in repr(result)
