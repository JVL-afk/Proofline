"""Prove the selected Python runtime is ready without any network operation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

EXPECTED_EXECUTABLE = Path(r"C:\Python313\python.exe")
EXPECTED_VERSIONS = {
    "boto3": "1.43.78",
    "botocore": "1.43.78",
    "jmespath": "1.1.0",
    "python-dateutil": "2.9.0.post0",
    "s3transfer": "0.19.2",
    "six": "1.17.0",
    "urllib3": "2.7.0",
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _blocked(operation: str, calls: list[str]) -> None:
    calls.append(operation)
    raise AssertionError(f"network operation attempted during runtime proof: {operation}")


def verify(root: Path) -> dict[str, Any]:
    if Path(sys.executable).resolve() != EXPECTED_EXECUTABLE.resolve():
        raise RuntimeError("runtime proof used the wrong Python executable")

    configuration_path = (
        root
        / "docs/readiness/m6.7-authorization"
        / "seed-source-connectivity-preflight-configuration-2026-08-23.json"
    )
    failure_schema_path = (
        root
        / "docs/readiness/m6.7-authorization"
        / "seed-source-connectivity-preflight-attempt-2026-08-23.json"
    )
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    prior_evidence = json.loads(failure_schema_path.read_text(encoding="utf-8"))
    if configuration["exact_hosts"] != [
        "data.texas.gov",
        "nominatim.openstreetmap.org",
    ]:
        raise RuntimeError("preflight configuration host set changed")
    if prior_evidence["counts"]["http_requests"] != 0:
        raise RuntimeError("prior evidence schema is not zero-HTTP")

    import boto3
    import botocore
    import dateutil
    import jmespath
    import s3transfer
    import six
    import urllib3

    versions = {
        "boto3": boto3.__version__,
        "botocore": botocore.__version__,
        "jmespath": jmespath.__version__,
        "python-dateutil": dateutil.__version__,
        "s3transfer": s3transfer.__version__,
        "six": six.__version__,
        "urllib3": urllib3.__version__,
    }
    if versions != EXPECTED_VERSIONS:
        raise RuntimeError("installed dependency versions do not match repository lock")

    preflight_path = root / "scripts/run_m67_seed_source_connectivity_preflight.py"
    specification = importlib.util.spec_from_file_location(
        "m67_connectivity_preflight_runtime_proof", preflight_path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("preflight module could not be loaded")

    calls: list[str] = []
    prior_metadata = os.environ.get("AWS_EC2_METADATA_DISABLED")
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    try:
        with (
            patch("socket.getaddrinfo", side_effect=lambda *_a, **_k: _blocked("dns", calls)),
            patch.object(
                socket.socket,
                "connect",
                side_effect=lambda *_a, **_k: _blocked("socket_connect", calls),
            ),
        ):
            module = importlib.util.module_from_spec(specification)
            specification.loader.exec_module(module)
            session = boto3.Session(
                aws_access_key_id="synthetic-runtime-proof",
                aws_secret_access_key="synthetic-runtime-proof",
                region_name="us-east-2",
            )
            client = session.client("ssm", endpoint_url="https://ssm.us-east-2.amazonaws.com")
            if client.meta.region_name != "us-east-2":
                raise RuntimeError("SSM client region mismatch")
    finally:
        if prior_metadata is None:
            os.environ.pop("AWS_EC2_METADATA_DISABLED", None)
        else:
            os.environ["AWS_EC2_METADATA_DISABLED"] = prior_metadata

    if calls:
        raise RuntimeError("network guard observed a forbidden operation")
    return {
        "record_type": "M67_PYTHON313_RUNTIME_READINESS_EVIDENCE",
        "version": "1.0.0",
        "state": "RUNTIME_PREFLIGHT_BEFORE_GRANT_CONSUMPTION_PASS",
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "dependency_versions": versions,
        "configuration_sha256": sha256_bytes(configuration_path.read_bytes()),
        "prior_terminal_evidence_schema_loaded": True,
        "preflight_module_loaded": True,
        "ssm_client_constructed_without_request": True,
        "final_pre_network_boundary_reached": True,
        "network_guard": {
            "dns_calls": 0,
            "socket_connect_calls": 0,
            "http_requests": 0,
            "tls_connections": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = verify(args.root.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
