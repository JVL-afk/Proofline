"""Hash-bound zero-HTTP DNS/TLS preflight after local DNS remediation."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import ssl
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import boto3
import botocore

HOSTS = ("data.texas.gov", "nominatim.openstreetmap.org")
EVENT = "AUTHORIZE_POST_DNS_REMEDIATION_CONNECTIVITY_PREFLIGHT"
EXPECTED_DNS = ["8.8.8.8", "8.8.4.4"]
EVIDENCE = Path(
    "local-data/m6.7/seed-source-connectivity/post-dns-connectivity-preflight-evidence.json"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pre_network_checks(root: Path, authorization: Path) -> dict[str, object]:
    if Path(sys.executable).resolve() != Path(r"C:\Python313\python.exe").resolve():
        raise RuntimeError("EXACT_RUNTIME_MISMATCH_GRANT_NOT_CONSUMED")
    if boto3.__version__ != "1.43.78" or botocore.__version__ != "1.43.78":
        raise RuntimeError("LOCKED_DEPENDENCY_MISMATCH_GRANT_NOT_CONSUMED")
    record = json.loads(authorization.read_text(encoding="utf-8"))
    if record.get("event") != EVENT or record.get("state") != "APPROVED":
        raise RuntimeError("AUTHORIZATION_INVALID_GRANT_NOT_CONSUMED")
    if record.get("exact_hosts") != list(HOSTS):
        raise RuntimeError("HOST_SCOPE_MISMATCH_GRANT_NOT_CONSUMED")
    own_hash = sha256(Path(__file__).read_bytes())
    if record.get("exact_executable_sha256") != own_hash:
        raise RuntimeError("EXECUTABLE_HASH_MISMATCH_GRANT_NOT_CONSUMED")
    command = (
        "(Get-DnsClientServerAddress -InterfaceIndex 13 -AddressFamily IPv4)."
        "ServerAddresses | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )
    dns = json.loads(completed.stdout)
    if dns != EXPECTED_DNS:
        raise RuntimeError("DNS_CONFIGURATION_MISMATCH_GRANT_NOT_CONSUMED")
    return {
        "runtime": str(Path(sys.executable).resolve()),
        "boto3": boto3.__version__,
        "botocore": botocore.__version__,
        "ipv4_dns": dns,
        "authorization_sha256": sha256(authorization.read_bytes()),
        "executable_sha256": own_hash,
        "pre_network_boundary": "PASS",
        "network_operations": 0,
    }


def resolve_public(host: str) -> list[tuple[int, str]]:
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    values: set[tuple[int, str]] = set()
    for family, _kind, _protocol, _canonical, address in answers:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        parsed = ipaddress.ip_address(address[0])
        if not parsed.is_global:
            raise RuntimeError(f"NON_PUBLIC_DNS_ANSWER:{host}")
        values.add((family, parsed.compressed))
    if not values:
        raise RuntimeError(f"NO_PUBLIC_DNS_ANSWER:{host}")
    return sorted(values, key=lambda item: (item[0] != socket.AF_INET, item[1]))


def tls_by_family(host: str, addresses: list[tuple[int, str]]) -> list[dict[str, object]]:
    context = ssl.create_default_context()
    results: list[dict[str, object]] = []
    seen: set[int] = set()
    for family, address in addresses:
        if family in seen:
            continue
        seen.add(family)
        raw = socket.socket(family, socket.SOCK_STREAM)
        raw.settimeout(10)
        destination = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        try:
            raw.connect(destination)
            with context.wrap_socket(raw, server_hostname=host) as secured:
                certificate = secured.getpeercert(binary_form=True)
                if not certificate:
                    raise RuntimeError("PEER_CERTIFICATE_MISSING")
                results.append(
                    {
                        "family": "IPv6" if family == socket.AF_INET6 else "IPv4",
                        "success": True,
                        "tls_version": secured.version(),
                        "cipher": secured.cipher()[0] if secured.cipher() else None,
                        "certificate_sha256": sha256(certificate),
                    }
                )
        finally:
            raw.close()
    if not any(item["success"] for item in results):
        raise RuntimeError(f"TLS_VALIDATION_FAILED:{host}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authorization-record", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    authorization = args.authorization_record.resolve()
    readiness = pre_network_checks(root, authorization)
    results: list[dict[str, object]] = []
    for host in HOSTS:
        addresses = resolve_public(host)
        results.append(
            {
                "hostname": host,
                "dns_success": True,
                "public_address_count": len(addresses),
                "address_set_sha256": sha256(
                    ("\n".join(address for _family, address in addresses) + "\n").encode()
                ),
                "tls": tls_by_family(host, addresses),
            }
        )
    evidence = {
        "record_type": "M67_POST_DNS_CONNECTIVITY_PREFLIGHT_EVIDENCE",
        "version": "1.0.0",
        "state": "SEED_SOURCE_CONNECTIVITY_PREFLIGHT_PASS",
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "pre_network_readiness": readiness,
        "hosts": results,
        "totals": {
            "dns_resolutions": 2,
            "maximum_tls_handshakes": 4,
            "http_requests": 0,
            "source_content_bytes": 0,
            "retries": 0,
            "alternate_resolvers": 0,
        },
        "kill_switch": "TRIPPED_UNCHANGED",
        "all_seven_m6_7_permissions": "NOT_AUTHORIZED",
        "offline_projection": "0/1_UNCONSUMED",
        "seed_construction": "0/1_UNCONSUMED",
    }
    target = root / EVIDENCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
