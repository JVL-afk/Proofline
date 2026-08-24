"""One-shot DNS-only diagnostic for the immutable Slot 01 A-09 host."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

import boto3

ACCOUNT = "785072247535"
REGION = "us-east-2"
PROFILE = "m67-phase1-owner"
EVENT = "AUTHORIZE_SLOT01_EXACT_HOST_A09_DNS_DIAGNOSTIC"
HOST = "bobsmithac.com"
PORT = 443
KILL_SWITCH = "/m67-phase1/kill-switch"
EXPECTED_ORDERED_PACKAGE_SHA256 = "755279cb8e5ac06c579c411857bfc6d380602722813de1cda21175b9385b5467"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def public_answer_evidence(answers: Sequence[tuple[Any, ...]]) -> dict[str, Any]:
    values: set[tuple[str, str]] = set()
    for family, _socktype, _protocol, _canonname, sockaddr in answers:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        address = ipaddress.ip_address(str(sockaddr[0]))
        if not address.is_global:
            raise RuntimeError("non-public DNS answer rejected")
        values.add(("IPv4" if family == socket.AF_INET else "IPv6", address.compressed))
    if not values:
        raise RuntimeError("no public DNS answers")
    ordered = sorted(values)
    return {
        "answer_count": len(ordered),
        "address_families": sorted({family for family, _address in ordered}),
        "answer_set_sha256": sha256_bytes(canonical_bytes(ordered)),
        "raw_addresses_persisted": False,
    }


def run(
    authorization_path: Path,
    configuration_path: Path,
    ordered_package_path: Path,
    output_path: Path,
    *,
    resolver: Callable[..., Sequence[tuple[Any, ...]]] = socket.getaddrinfo,
    session_factory: Callable[..., Any] = boto3.Session,
    now: datetime | None = None,
) -> dict[str, Any]:
    config_raw = configuration_path.read_bytes()
    config = json.loads(config_raw)
    auth = json.loads(authorization_path.read_text(encoding="utf-8"))
    observed_at = now or datetime.now(UTC)
    starts = datetime.fromisoformat(config["window"]["starts_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(config["window"]["expires_at"].replace("Z", "+00:00"))
    if not starts <= observed_at <= expires:
        raise RuntimeError("authorization window is not active")
    if auth.get("event") != EVENT or auth.get("state") != "APPROVED":
        raise RuntimeError("Slot 01 DNS diagnostic authorization is absent")
    if auth.get("configuration_sha256") != sha256_bytes(config_raw):
        raise RuntimeError("configuration hash mismatch")
    if auth.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("executable hash mismatch")
    if sha256_bytes(ordered_package_path.read_bytes()) != EXPECTED_ORDERED_PACKAGE_SHA256:
        raise RuntimeError("ordered package hash mismatch")
    if output_path.exists():
        raise RuntimeError("terminal diagnostic evidence already exists")

    # Pre-consumption: an expired SSO session or non-TRIPPED switch performs no DNS operation.
    session = session_factory(profile_name=PROFILE, region_name=REGION)
    value = session.client("ssm").get_parameter(Name=KILL_SWITCH, WithDecryption=False)["Parameter"]["Value"]
    if value != "TRIPPED":
        raise RuntimeError("kill switch is not TRIPPED")

    state = "SLOT01_A09_DNS_DIAGNOSTIC_FAIL"
    failure: str | None = None
    answer_evidence: dict[str, Any] | None = None
    try:
        answers = resolver(HOST, PORT, type=socket.SOCK_STREAM)
        answer_evidence = public_answer_evidence(answers)
        state = "SLOT01_A09_DNS_DIAGNOSTIC_PASS"
    except socket.gaierror as error:
        failure = f"DNS_GETADDRINFO_FAILED::{error.errno}"

    evidence = {
        "schema_version": "m67-slot01-a09-dns-diagnostic-evidence-v1",
        "state": state,
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "slot": 1,
        "candidate_hostname": HOST,
        "current_system_dns_resolutions": 1,
        "retries": 0,
        "tls_connections": 0,
        "http_requests": 0,
        "source_content_bytes": 0,
        "kill_switch_before": "TRIPPED",
        "kill_switch_mutations": 0,
        "answer_evidence": answer_evidence,
        "failure": failure,
        "m67_permissions": {name: "NOT_AUTHORIZED" for name in (
            "REAL_BUSINESS_DISCOVERY", "REAL_PUBLIC_RESEARCH", "PROFESSIONAL_IDENTITY_RESOLUTION",
            "REAL_CONTACT_STORAGE", "CONTACT_VERIFICATION", "SHADOW_ELIGIBILITY_EVALUATION",
            "SHADOW_READY_ASSESSMENT",
        )},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as handle:
        handle.write(canonical_bytes(evidence))
        handle.flush()
        os.fsync(handle.fileno())
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--ordered-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.authorization, args.configuration, args.ordered_package, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"].endswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
