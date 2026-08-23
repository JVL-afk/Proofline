import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_m67_connectivity_runtime.py"
SPEC = importlib.util.spec_from_file_location("m67_runtime_proof", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def test_runtime_dependency_set_matches_repository_lock() -> None:
    assert runtime.EXPECTED_VERSIONS == {
        "boto3": "1.43.78",
        "botocore": "1.43.78",
        "jmespath": "1.1.0",
        "python-dateutil": "2.9.0.post0",
        "s3transfer": "0.19.2",
        "six": "1.17.0",
        "urllib3": "2.7.0",
    }
    requirements = (
        ROOT
        / "docs/readiness/m6.7-authorization"
        / "python313-boto3-runtime-requirements-2026-08-23.txt"
    ).read_text()
    assert set(runtime.EXPECTED_VERSIONS) <= {
        line.split("==", 1)[0] for line in requirements.splitlines()
    }
    assert requirements.count("--hash=sha256:") == 7


def test_pre_mutation_evidence_is_additive_and_bounded() -> None:
    path = (
        ROOT
        / "docs/readiness/m6.7-authorization"
        / "python313-runtime-pre-mutation-evidence-2026-08-23.json"
    )
    value = json.loads(path.read_text())
    assert value["target_executable"] == r"C:\Python313\python.exe"
    assert value["expected_changes"] == {
        "add": 4,
        "change": 1,
        "remove": 0,
        "python_upgrade": False,
        "pip_upgrade": False,
        "browser_or_ai_dependencies": False,
        "additions": [
            "boto3==1.43.78",
            "botocore==1.43.78",
            "jmespath==1.1.0",
            "s3transfer==0.19.2",
        ],
        "version_change": "urllib3 2.6.3 -> 2.7.0",
        "already_satisfied": [
            "python-dateutil==2.9.0.post0",
            "six==1.17.0",
        ],
    }
    assert value["installed_package_count"] == 117
    assert value["installed_package_inventory_sha256"] == (
        "4e62f61dbd0c998a255e7e0dff1ea52faa4bb03a60cc7f29d983aec5374e0797"
    )


def test_runtime_proof_blocks_all_network_before_client_construction() -> None:
    source = SCRIPT.read_text()
    assert 'patch("socket.getaddrinfo"' in source
    assert 'patch.object(\n                socket.socket,\n                "connect"' in source
    assert "client.get_parameter" not in source
    assert "urlopen" not in source


def test_repaired_runtime_evidence_precedes_successor_network_grant() -> None:
    directory = ROOT / "docs/readiness/m6.7-authorization"
    repair = json.loads(
        (directory / "python313-runtime-repair-evidence-2026-08-23.json").read_text()
    )
    successor = json.loads(
        (
            directory / "seed-source-connectivity-successor-preflight-configuration-2026-08-23.json"
        ).read_text()
    )
    assert repair["state"] == "RUNTIME_PREFLIGHT_BEFORE_GRANT_CONSUMPTION_PASS"
    assert repair["proof"]["dns_calls"] == 0
    assert repair["proof"]["socket_connect_calls"] == 0
    assert successor["state"] == "PREPARED_NOT_AUTHORIZED"
    assert successor["runtime_precondition"]["runtime_readiness_state"] == "PASS"
    assert successor["network_limits"]["http_requests"] == 0
    assert successor["network_limits"]["retries"] == 0
    assert successor["permission_effect"]["m6_7_changes"] == 0
