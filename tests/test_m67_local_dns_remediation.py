import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "docs/readiness/m6.7-authorization"


def test_inspection_binds_actual_active_route_and_dhcp_dns_origin() -> None:
    value = json.loads((DIRECTORY / "local-dns-resolver-inspection-2026-08-23.json").read_text())
    assert value["root_cause"] == "LOCAL_WINDOWS_CURRENT_SYSTEM_DNS_RESOLVER_PATH_FAILURE"
    assert value["active_adapter"]["interface_alias"] == "Wi-Fi"
    assert value["active_adapter"]["interface_index"] == 13
    assert value["ipv4_before"]["dns_origin"] == "DHCP_DERIVED"
    assert value["ipv4_before"]["effective_dns_servers"] == ["192.168.1.1"]
    assert value["ipv6_before"]["change_required"] is False
    assert value["live_dns_queries_during_inspection"] == 0


def test_plan_changes_only_exact_adapter_ipv4_dns_and_is_rollbackable() -> None:
    value = json.loads(
        (DIRECTORY / "local-dns-resolver-remediation-plan-2026-08-23.json").read_text()
    )
    assert value["state"] == "PREPARED_NOT_AUTHORIZED"
    assert value["target"] == {
        "interface_alias": "Wi-Fi",
        "interface_index": 13,
        "interface_guid": "{997EE793-757E-4FD9-8138-CE1BF9FA1B32}",
        "address_family": "IPv4_ONLY",
    }
    assert value["after"]["dns_servers"] == ["8.8.8.8", "8.8.4.4"]
    assert value["after"]["ipv4_addressing"] == "DHCP_ENABLED_UNCHANGED"
    assert value["after"]["ipv6_dns"] == "UNCHANGED"
    assert any("source=dhcp" in command for command in value["rollback_commands"])
    assert value["network_proof_limits"]["http_requests"] == 0
    assert value["network_proof_limits"]["source_content_bytes"] == 0
    assert value["terraform"]["applicable"] is False
    assert "M6_7_PERMISSIONS" in value["explicitly_unchanged"]


def test_owner_gate_binds_only_ipv4_dns_and_two_zero_http_proofs() -> None:
    ready_path = DIRECTORY / "local-dns-resolver-remediation-owner-approval-ready-2026-08-23.json"
    value = json.loads(ready_path.read_text())
    assert value["state"] == "READY_FOR_LOCAL_DNS_RESOLVER_REMEDIATION_AUTHORIZATION"
    assert value["target"]["interface_index"] == 13
    assert value["target"]["address_family"] == "IPv4_ONLY"
    assert value["after"]["dns_servers"] == ["8.8.8.8", "8.8.4.4"]
    assert value["proof"]["logical_dns_queries"] == 2
    assert value["proof"]["http_requests"] == 0
    assert value["proof"]["source_content_bytes"] == 0
    assert value["rollback"]["automatic_on_any_apply_or_proof_failure"] is True
    assert all(value["unchanged"].values())
    statement = value["exact_owner_approval_statement"]
    assert "all traffic using that adapter" in statement
    assert "does not authorize another connectivity preflight or live acquisition" in statement
