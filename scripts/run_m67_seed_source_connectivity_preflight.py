"""Exact-host DNS and TLS preflight for the M6.7 seed-source path.

This diagnostic sends no HTTP request and reads no source payload. Network use is
limited structurally to one DNS resolution and at most two TLS connection
attempts for each frozen source hostname.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import ssl
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3

ACCOUNT = "785072247535"
REGION = "us-east-2"
PROFILE = "m67-phase1-owner"
KILL_SWITCH = "/m67-phase1/kill-switch"
HOSTS = ("data.texas.gov", "nominatim.openstreetmap.org")
PORT = 443
TIMEOUT_SECONDS = 10.0
EVIDENCE_PATH = Path(
    "local-data/m6.7/seed-source-connectivity/seed-source-connectivity-preflight-evidence.json"
)
AUTHORIZATION_EVENT = "AUTHORIZE_SEED_SOURCE_CONNECTIVITY_PREFLIGHT"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_authorization(root: Path, authorization_record: Path) -> None:
    path = authorization_record.resolve()
    if root not in path.parents:
        raise RuntimeError("authorization record must be inside the repository")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("event") != AUTHORIZATION_EVENT or value.get("state") != "APPROVED":
        raise RuntimeError("connectivity preflight is not approved")
    if value.get("account_id") != ACCOUNT or value.get("region") != REGION:
        raise RuntimeError("preflight authorization account or region mismatch")
    if value.get("exact_hosts") != list(HOSTS):
        raise RuntimeError("preflight authorization host set mismatch")
    if value.get("http_requests") != 0 or value.get("source_response_bytes") != 0:
        raise RuntimeError("preflight authorization exceeds zero-HTTP scope")


def _public_addresses(
    host: str,
    resolver: Callable[..., Sequence[tuple[Any, ...]]] = socket.getaddrinfo,
) -> tuple[list[tuple[int, str]], str]:
    answers = resolver(host, PORT, type=socket.SOCK_STREAM)
    normalized: set[tuple[int, str]] = set()
    for family, _socktype, _protocol, _canonname, sockaddr in answers:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        address = str(sockaddr[0])
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global:
            raise RuntimeError(f"non-public DNS answer for approved host {host}")
        normalized.add((family, parsed.compressed))
    if not normalized:
        raise RuntimeError(f"no public DNS answer for approved host {host}")
    ordered = sorted(normalized, key=lambda item: (item[0] != socket.AF_INET, item[1]))
    digest = sha256_bytes(canonical_bytes([address for _family, address in ordered]))
    return ordered, digest


def _tls_probe(
    host: str,
    addresses: Sequence[tuple[int, str]],
    *,
    socket_factory: Callable[..., socket.socket] = socket.socket,
    context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    tls = context or ssl.create_default_context()
    failures: list[str] = []
    attempts = 0
    seen_families: set[int] = set()
    for family, address in addresses:
        if family in seen_families:
            continue
        seen_families.add(family)
        attempts += 1
        if attempts > 2:
            break
        raw = socket_factory(family, socket.SOCK_STREAM)
        raw.settimeout(TIMEOUT_SECONDS)
        try:
            destination: tuple[Any, ...]
            destination = (address, PORT, 0, 0) if family == socket.AF_INET6 else (address, PORT)
            raw.connect(destination)
            with tls.wrap_socket(raw, server_hostname=host) as secured:
                certificate = secured.getpeercert(binary_form=True)
                if not certificate:
                    raise RuntimeError("peer certificate missing")
                return {
                    "tls_connected": True,
                    "tls_version": secured.version(),
                    "cipher": secured.cipher()[0] if secured.cipher() else None,
                    "peer_certificate_sha256": sha256_bytes(certificate),
                    "connection_attempts": attempts,
                    "application_bytes_sent": 0,
                    "application_bytes_received": 0,
                }
        except (OSError, ssl.SSLError, RuntimeError) as error:
            failures.append(type(error).__name__)
            raw.close()
    raise RuntimeError(f"TLS preflight failed for {host}: {','.join(failures)}")


def run(
    *,
    root: Path,
    authorization_record: Path,
    resolver: Callable[..., Sequence[tuple[Any, ...]]] = socket.getaddrinfo,
    tls_probe: Callable[[str, Sequence[tuple[int, str]]], dict[str, Any]] = _tls_probe,
) -> dict[str, Any]:
    _verify_authorization(root, authorization_record)

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != ACCOUNT:
        raise RuntimeError("AWS account mismatch")
    ssm = session.client("ssm")
    before = ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]
    if before["Value"] != "TRIPPED":
        raise RuntimeError("kill switch is not TRIPPED")

    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    results: list[dict[str, Any]] = []
    for host in HOSTS:
        addresses, answer_digest = _public_addresses(host, resolver)
        families = sorted(
            {"IPv4" if family == socket.AF_INET else "IPv6" for family, _ in addresses}
        )
        result = {
            "hostname": host,
            "dns_resolved": True,
            "public_answer_count": len(addresses),
            "address_families": families,
            "answer_set_sha256": answer_digest,
            "logical_dns_resolutions": 1,
        }
        result.update(tls_probe(host, addresses))
        results.append(result)

    after = ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]
    if after["Value"] != "TRIPPED":
        raise RuntimeError("kill switch changed during read-only preflight")

    evidence = {
        "record_type": "M67_SEED_SOURCE_CONNECTIVITY_PREFLIGHT_EVIDENCE",
        "version": "1.0.0",
        "state": "CONNECTIVITY_PROVEN_PENDING_SUCCESSOR_ACQUISITION_AUTHORIZATION",
        "execution_path": "LOCAL_WINDOWS_CPYTHON_3_13_EXACT_HASH_BOUND_PREFLIGHT",
        "account_id": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at,
        "source_hosts": results,
        "totals": {
            "logical_dns_resolutions": 2,
            "maximum_tls_connection_attempts": 4,
            "http_requests": 0,
            "http_response_bytes": 0,
            "source_payloads_parsed": 0,
        },
        "negative_boundary": {
            "hostnames_are_compile_time_constants": True,
            "caller_supplied_hostname_argument": False,
            "redirects": 0,
            "alternate_resolvers": 0,
            "proxy_vpn_or_browser": False,
            "unrelated_public_destination_attempts": 0,
        },
        "kill_switch_before": before["Value"],
        "kill_switch_after": after["Value"],
        "permissions_changed": False,
        "real_business_discovery": "NOT_AUTHORIZED",
        "downstream_grants": {
            "offline_projection": "0/1_UNCONSUMED",
            "bounded_seed_construction": "0/1_UNCONSUMED",
        },
    }
    target = root / EVIDENCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_bytes(evidence))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authorization-record", type=Path, required=True)
    args = parser.parse_args()
    run(
        root=args.root.resolve(),
        authorization_record=args.authorization_record.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
