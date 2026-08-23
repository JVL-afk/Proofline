import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def test_locator_policy_is_exact_bounded_and_unconsumed() -> None:
    value = json.loads(
        (AUTH / "osm-nominatim-host-locator-configuration-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["state"] == "READY_FOR_OWNER_SOURCE_ACCEPTANCE_NOT_AUTHORIZED"
    assert value["endpoint"] == "https://nominatim.openstreetmap.org/search"
    assert value["query_contract"]["input_fields"] == [
        "public_business_name",
        "texas_city_or_service_area",
    ]
    envelope = value["execution_envelope"]
    assert envelope["maximum_candidates"] == 100
    assert envelope["maximum_logical_requests"] == 100
    assert envelope["maximum_attempts"] == 100
    assert envelope["minimum_delay_seconds"] >= 2
    assert envelope["concurrency"] == 1
    assert envelope["cost_ceiling_usd"] == 0
    assert envelope["browser_sessions"] == 0
    assert envelope["ai_calls"] == 0
    assert set(value["one_shot_grants"].values()) == {"0/1"}
    assert set(value["permissions"].values()) == {"NOT_AUTHORIZED"}
    assert value["live_source_operations_performed"] == 0
    assert value["candidate_records_processed"] == 0


def test_durable_fields_are_business_only_and_raw_is_ephemeral() -> None:
    value = json.loads(
        (AUTH / "osm-nominatim-host-locator-configuration-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    durable = set(value["durable_output_fields"])
    assert {"first_party_host_candidate", "source_artifact_sha256", "locator"} <= durable
    assert durable.isdisjoint(
        {"person_name", "email", "telephone", "raw_response_body", "display_name"}
    )
    assert value["minimization"]["raw_body_durable"] is False
    assert value["matching"]["outcome_based_replacement"] is False
    assert value["rights_and_obligations"]["credential"] == "NONE"
    assert value["qualified_source_review_required"] is False
