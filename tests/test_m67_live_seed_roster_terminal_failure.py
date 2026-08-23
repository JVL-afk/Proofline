import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = (
    ROOT / "docs/readiness/m6.7-authorization/live-seed-roster-acquisition-attempt-2026-08-23.json"
)


def test_terminal_failure_consumes_only_live_attempt_and_is_fail_closed() -> None:
    value = json.loads(RECORD.read_text(encoding="utf-8"))
    assert value["state"] == "TERMINAL_FAILED_DNS_BEFORE_TDLR_RESPONSE"
    assert value["terminal_failure"]["response_received"] is False
    assert value["terminal_failure"]["nominatim_called"] is False
    assert value["terminal_failure"]["retry_performed"] is False
    assert value["counts"]["tdlr_records_considered"] == 0
    assert value["counts"]["compliant_final_observations"] == 0
    grants = value["grant_consumption"]
    assert grants["live_seed_roster_acquisition"].startswith("1/1_CONSUMED")
    assert grants["offline_seed_source_acquisition"].startswith("0/1_UNCONSUMED")
    assert grants["bounded_seed_construction"].startswith("0/1_UNCONSUMED")
    assert grants["csprng_seeds_generated"] == 0


def test_terminal_controls_are_restored_and_no_artifacts_exist() -> None:
    value = json.loads(RECORD.read_text(encoding="utf-8"))
    assert value["kill_switch_evidence"]["terminal"] == "TRIPPED"
    assert value["kill_switch_evidence"]["terminal_parameter_version"] == 5
    assert set(value["terminal_permissions"].values()) == {"NOT_AUTHORIZED"}
    artifacts = value["artifact_evidence"]
    assert set(item for key, item in artifacts.items() if key.endswith("_exists")) == {False}
    assert artifacts["raw_or_contact_shaped_durable_artifact_created"] is False
    assert value["retry_prohibited"] is True
