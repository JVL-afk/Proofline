import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT / "docs/readiness/m6.7-authorization/"
    "elevated-local-dns-resolver-remediation-configuration-2026-08-23.json"
)
SCRIPT = ROOT / "scripts/run_m67_elevated_local_dns_remediation.ps1"


def test_elevation_is_proven_before_grant_consumption() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    precondition = config["elevation_precondition"]
    assert precondition["checked_before_grant_consumption"] is True
    assert precondition["administrator_token_required"] is True
    assert precondition["minimum_integrity_rid"] == 12288
    assert precondition["network_operations"] == 0
    assert precondition["mutation_operations"] == 0

    script = SCRIPT.read_text(encoding="utf-8")
    elevation_check = script.index("$elevation = Get-ElevationEvidence")
    grant_consumption = script.index("$consumedAt =")
    first_mutation = script.index("netsh interface ipv4 set dnsservers")
    assert elevation_check < grant_consumption < first_mutation
    assert "ELEVATION_PRECONDITION_FAILED_GRANT_NOT_CONSUMED" in script


def test_successor_keeps_exact_dns_design_and_zero_http_tls_scope() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["target"]["interface_index"] == 13
    assert config["target"]["interface_guid"] == "{997EE793-757E-4FD9-8138-CE1BF9FA1B32}"
    assert config["elevation_precondition"]["expected_ipv4_dns"] == ["192.168.1.1"]
    assert config["mutation"]["resulting_ipv4_dns"] == ["8.8.8.8", "8.8.4.4"]
    assert config["mutation"]["ipv6_dns"] == "UNCHANGED"
    assert config["proof"]["exact_hosts"] == [
        "data.texas.gov",
        "nominatim.openstreetmap.org",
    ]
    assert config["proof"]["logical_dns_queries"] == 2
    assert config["proof"]["queries_per_host"] == 1
    assert config["proof"]["http_requests"] == 0
    assert config["proof"]["tls_connections"] == 0
    assert config["proof"]["source_content_bytes"] == 0
    assert config["proof"]["retries"] == 0


def test_failure_after_consumption_has_automatic_dhcp_rollback() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["rollback"]["automatic_on_any_apply_or_proof_failure"] is True
    assert any("source=dhcp" in command for command in config["rollback"]["commands"])
    assert config["predecessor"]["terminal"] is True
    assert config["predecessor"]["reusable"] is False
    assert config["guard_states"] == {
        "kill_switch": "TRIPPED",
        "all_seven_m6_7_permissions": "NOT_AUTHORIZED",
        "offline_projection": "0/1_UNCONSUMED",
        "seed_construction": "0/1_UNCONSUMED",
    }
