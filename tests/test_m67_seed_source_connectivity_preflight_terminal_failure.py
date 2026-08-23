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
        "preflight",
        "owner",
        "approval",
        "accepted",
        "2026",
        "08",
        "23.json",
    ]
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preflight_approval_and_terminal_failure_are_immutable_and_fail_closed() -> None:
    failure = DIRECTORY / "seed-source-connectivity-preflight-attempt-2026-08-23.json"
    value = json.loads(failure.read_text())
    assert value["approval_sha256"] == sha256(APPROVAL)
    assert value["state"] == "TERMINAL_FAILED_BEFORE_DNS_RUNTIME_DEPENDENCY_MISSING"
    assert value["terminal_failure"]["missing_module"] == "boto3"
    assert value["counts"] == {
        "logical_dns_resolutions": 0,
        "tls_connection_attempts": 0,
        "http_requests": 0,
        "application_bytes_sent": 0,
        "application_bytes_received": 0,
        "source_content_bytes": 0,
    }
    assert value["independent_post_failure_observation"]["kill_switch"] == "TRIPPED"
    assert value["grant_state"]["connectivity_preflight"].startswith("1/1_CONSUMED")
    assert value["grant_state"]["offline_projection"] == "0/1_UNCONSUMED"
    assert value["grant_state"]["bounded_seed_construction"] == "0/1_UNCONSUMED"
    assert set(value["terminal_permissions"].values()) == {"NOT_AUTHORIZED"}
    assert value["retry_prohibited"] is True
    assert value["successor_live_acquisition_authorization_prepared"] is False


def test_both_exact_hosts_record_no_dns_or_tls_attempt() -> None:
    value = json.loads(
        (DIRECTORY / "seed-source-connectivity-preflight-attempt-2026-08-23.json").read_text()
    )
    assert [item["hostname"] for item in value["host_results"]] == [
        "data.texas.gov",
        "nominatim.openstreetmap.org",
    ]
    assert all(item["dns"] == "NOT_ATTEMPTED" for item in value["host_results"])
    assert all(item["tls"] == "NOT_ATTEMPTED" for item in value["host_results"])
