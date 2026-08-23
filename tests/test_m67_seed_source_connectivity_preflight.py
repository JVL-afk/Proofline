import importlib.util
import json
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_m67_seed_source_connectivity_preflight.py"
SPEC = importlib.util.spec_from_file_location("m67_connectivity_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def test_diagnosis_binds_local_sandbox_root_cause_without_mutation() -> None:
    value = json.loads(
        (
            ROOT
            / "docs/readiness/m6.7-authorization/seed-source-connectivity-diagnosis-2026-08-23.json"
        ).read_text()
    )
    assert value["root_cause"] == "LOCAL_CODEX_EXECUTION_SANDBOX_NETWORK_DISABLED"
    assert value["execution_path"]["not_ecs_or_vpc"] is True
    assert value["terraform"] == {
        "applicable": False,
        "creates": 0,
        "changes": 0,
        "replacements": 0,
        "destroys": 0,
    }
    assert value["successor_acquisition_authorization_prepared"] is False
    assert set(value["terminal_permissions"].values()) == {"NOT_AUTHORIZED"}


def test_configuration_is_exact_host_zero_http_preflight() -> None:
    directory = ROOT / "docs/readiness/m6.7-authorization"
    value = json.loads(
        (directory / "seed-source-connectivity-preflight-configuration-2026-08-23.json").read_text()
    )
    assert value["exact_hosts"] == list(preflight.HOSTS)
    assert value["dns"]["alternate_resolver"] is False
    assert value["tls"]["application_bytes_sent"] == 0
    assert value["tls"]["application_bytes_received"] == 0
    assert value["tls"]["http_requests"] == 0
    assert "CALLER_SUPPLIED_OR_WILDCARD_HOST" in value["prohibited"]


def test_public_address_projection_rejects_private_answers() -> None:
    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(RuntimeError, match="non-public DNS answer"):
        preflight._public_addresses("data.texas.gov", resolver)


def test_public_address_projection_hashes_without_persisting_raw_addresses() -> None:
    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.8", 443))]

    # Documentation ranges are not globally routable and therefore also fail closed.
    with pytest.raises(RuntimeError, match="non-public DNS answer"):
        preflight._public_addresses("data.texas.gov", resolver)


def test_preflight_refuses_missing_or_unapproved_authorization(tmp_path: Path) -> None:
    record = tmp_path / "authorization.json"
    record.write_text(
        json.dumps(
            {
                "event": preflight.AUTHORIZATION_EVENT,
                "state": "PREPARED_NOT_AUTHORIZED",
                "account_id": preflight.ACCOUNT,
                "region": preflight.REGION,
                "exact_hosts": list(preflight.HOSTS),
                "http_requests": 0,
                "source_response_bytes": 0,
            }
        )
    )
    with pytest.raises(RuntimeError, match="not approved"):
        preflight.run(root=tmp_path, authorization_record=record)


def test_hosts_are_compile_time_constants_and_have_no_cli_host_argument() -> None:
    source = (ROOT / "scripts/run_m67_seed_source_connectivity_preflight.py").read_text()
    assert preflight.HOSTS == ("data.texas.gov", "nominatim.openstreetmap.org")
    assert 'add_argument("--host"' not in source
    assert "urllib" not in source
    assert ".send(" not in source
    assert ".recv(" not in source
