import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT / "docs/readiness/m6.7-authorization/"
    "elevated-local-dns-resolver-remediation-configuration-2026-08-23.json"
)
SCRIPT = ROOT / "scripts/run_m67_elevated_local_dns_remediation.ps1"
OWNER_GATE = (
    ROOT / "docs/readiness/m6.7-authorization/"
    "elevated-local-dns-resolver-remediation-owner-approval-ready-2026-08-23.json"
)
SUCCESSOR_CONFIG = (
    ROOT / "docs/readiness/m6.7-authorization/"
    "elevated-local-dns-resolver-remediation-successor-configuration-2026-08-23.json"
)


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


def test_owner_gate_binds_elevated_runner_and_manual_administrator_launch() -> None:
    gate = json.loads(OWNER_GATE.read_text(encoding="utf-8"))
    assert gate["state"] == "READY_FOR_ELEVATED_LOCAL_DNS_REMEDIATION_AUTHORIZATION"
    assert gate["preparation_commit"] == "92a7c283877b3476415beb2a0d0581b512c7d659"
    assert gate["exact_executable_sha256"] == (
        "f78cc0be997d7646cd76bb8c5ce1b2c7ddd9cca4b8a6c54039eff665d72302ed"
    )
    assert gate["grant_consumption_boundary"]["administrator_token"] == "REQUIRED"
    assert gate["grant_consumption_boundary"]["minimum_integrity"] == "HIGH"
    assert gate["grant_consumption_boundary"]["precondition_network_operations"] == 0
    assert "Run as administrator" in gate["execution"]["administrator_launch_instruction"]
    assert "-AuthorizationRecordPath" in gate["execution"]["exact_elevated_command"]
    statement = gate["exact_owner_approval_statement"]
    assert "failed elevation" in statement
    assert "does not consume the grant" in statement
    assert "zero HTTP requests" in statement


def test_successor_runner_is_windows_powershell_5_1_compatible() -> None:
    successor = json.loads(SUCCESSOR_CONFIG.read_text(encoding="utf-8"))
    compatibility = successor["compatibility_remediation"]
    assert compatibility["target_runtime"] == "WINDOWS_POWERSHELL_5_1"
    assert compatibility["removed_unsupported_parameter"] == (
        "ConvertFrom-Json -AsHashtable"
    )
    assert compatibility["dns_design_changed"] is False
    assert compatibility["network_scope_changed"] is False
    script = SCRIPT.read_text(encoding="utf-8")
    assert "ConvertFrom-Json -AsHashtable" not in script
    assert "ConvertFrom-Json" in script
    assert "[System.Collections.IDictionary]" in script
