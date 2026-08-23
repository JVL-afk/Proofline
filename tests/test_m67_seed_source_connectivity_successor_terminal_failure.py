import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "docs/readiness/m6.7-authorization"
APPROVAL = DIRECTORY / "-".join(
    [
        "seed",
        "source",
        "connectivity",
        "successor",
        "preflight",
        "owner",
        "approval",
        "accepted",
        "2026",
        "08",
        "23.json",
    ]
)
ATTEMPT = DIRECTORY / "seed-source-connectivity-successor-preflight-attempt-2026-08-23.json"


def test_successor_preflight_is_consumed_at_exact_dns_blocker() -> None:
    value = json.loads(ATTEMPT.read_text())
    assert value["approval_sha256"] == hashlib.sha256(APPROVAL.read_bytes()).hexdigest()
    assert value["state"] == "TERMINAL_FAILED_CURRENT_SYSTEM_DNS_DATA_TEXAS_GOV"
    assert value["terminal_failure"]["hostname"] == "data.texas.gov"
    assert value["terminal_failure"]["windows_error"] == 11001
    assert value["terminal_failure"]["retry_performed"] is False
    assert value["counts"] == {
        "logical_dns_resolutions": 1,
        "accepted_public_addresses": 0,
        "tls_connection_attempts": 0,
        "http_requests": 0,
        "application_bytes_sent": 0,
        "application_bytes_received": 0,
        "source_content_bytes": 0,
    }
    assert value["post_failure_observation"]["kill_switch"] == "TRIPPED"
    assert value["grant_state"]["successor_connectivity_preflight"].startswith("1/1_CONSUMED")
    assert value["retry_prohibited"] is True
    assert value["successor_live_acquisition_authorization_prepared"] is False


def test_failure_preserves_downstream_grants_and_permissions() -> None:
    value = json.loads(ATTEMPT.read_text())
    assert value["grant_state"]["offline_projection"] == "0/1_UNCONSUMED"
    assert value["grant_state"]["bounded_seed_construction"] == "0/1_UNCONSUMED"
    assert set(value["terminal_permissions"].values()) == {"NOT_AUTHORIZED"}
    assert value["host_results"][1]["hostname"] == "nominatim.openstreetmap.org"
    assert value["host_results"][1]["dns"].startswith("NOT_ATTEMPTED")
