import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def load(name: str) -> dict[str, object]:
    return json.loads((AUTH / name).read_text(encoding="utf-8"))


def test_host_derivation_is_exact_and_has_no_fallback() -> None:
    value = load("nominatim-host-derivation-verification-2026-08-23.json")
    assert value["state"] == "VERIFIED_FAIL_CLOSED"
    assert value["request"]["extratags"] == 1
    assert value["allowlisted_osm_host_tags"] == ["extratags.website"]
    failure = value["failure_semantics"]
    assert failure["zero_surviving_hosts"] == "NOT_FOUND"
    assert failure["multiple_surviving_hosts"] == "AMBIGUOUS"
    assert failure["fallback_locator"] == "PROHIBITED"
    assert failure["retry"] == "PROHIBITED_FOR_NOMINATIM"
    assert failure["candidate_replacement"] == "PROHIBITED"
    assert value["execution_envelope_changed"] is False
    assert value["live_requests_performed"] == 0


def test_live_release_preserves_exact_global_envelope() -> None:
    value = load("live-seed-roster-acquisition-authorization-configuration-2026-08-23.json")
    assert value["state"] == "PREPARED_NOT_AUTHORIZED"
    caps = value["global_hard_caps"]
    assert caps == {
        "maximum_source_records_considered": 500,
        "minimum_output_observations": 24,
        "maximum_output_observations": 100,
        "logical_http_requests": 120,
        "attempts": 360,
        "aggregate_response_bytes": 36_000_000,
        "concurrency": 1,
        "minimum_per_host_delay_seconds": 2,
        "source_cost_usd": 0,
        "ai_calls": 0,
        "browser_sessions": 0,
    }
    assert value["live_operations_performed_during_preparation"] == 0
    assert value["candidate_records_processed_during_preparation"] == 0
    assert set(value["existing_one_shot_grants_before_run"].values()) == {"0/1"}


def test_only_real_business_discovery_temporarily_changes() -> None:
    value = load("live-seed-roster-acquisition-authorization-configuration-2026-08-23.json")
    transition = value["permission_transition"]
    assert transition["REAL_BUSINESS_DISCOVERY_before"] == "NOT_AUTHORIZED"
    assert transition["REAL_BUSINESS_DISCOVERY_during"] == (
        "AUTHORIZED_ONLY_FOR_M67_LIVE_SEED_ROSTER_ACQUISITION_V1"
    )
    assert transition["REAL_BUSINESS_DISCOVERY_after"] == "NOT_AUTHORIZED"
    assert transition["all_other_six_permissions_before_during_after"] == "NOT_AUTHORIZED"


def test_exact_source_set_and_tdlr_projection_remain_narrow() -> None:
    value = load("live-seed-roster-acquisition-authorization-configuration-2026-08-23.json")
    sources = value["sources"]
    assert [item["source_id"] for item in sources] == [
        "TX_OPEN_DATA_TDLR_ALL_LICENSES::7358-krk7",
        "OSM_NOMINATIM_PUBLIC_SEARCH_V1",
    ]
    assert sources[0]["allowed_fields"] == [
        "license_type",
        "license_number",
        "business_county",
        "business_name",
        "business_city_state_zip",
        "license_expiration_date_mmddccyy",
        "license_subtype",
    ]
    assert sources[1]["allowlisted_host_tag"] == "extratags.website"
    assert sources[1]["automatic_retry"] is False
    assert value["unused_cap_cannot_be_reassigned_to_unapproved_sources"] is True


def test_owner_gate_is_exact_and_does_not_preconsume_existing_grants() -> None:
    value = load("live-seed-roster-acquisition-owner-approval-ready-2026-08-23.json")
    assert value["state"] == "READY_FOR_LIVE_SEED_ROSTER_ACQUISITION_AUTHORIZATION"
    assert value["authority"]["REAL_BUSINESS_DISCOVERY_before"] == "NOT_AUTHORIZED"
    assert value["authority"]["REAL_BUSINESS_DISCOVERY_after"] == "NOT_AUTHORIZED"
    assert value["authority"]["other_six_permissions_before_during_after"] == "NOT_AUTHORIZED"
    assert set(value["existing_one_shot_grants_before_run"].values()) == {"0/1"}
    assert value["no_live_source_operations_during_preparation"] is True
    statement = value["exact_owner_approval_statement"]
    assert "AUTHORIZE_LIVE_PHASE1_SEED_ROSTER_ACQUISITION" in statement
    assert "temporarily sets REAL_BUSINESS_DISCOVERY" in statement
    assert "Nominatim exactly once without retry" in statement
    assert "first-party-host DNS or HTTP access" in statement
    assert "remain NOT_AUTHORIZED before, during and after" in statement
