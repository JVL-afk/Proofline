"""One-request, non-acquisition TDLR SODA3 contract preflight.

The response body is held only in memory. Durable evidence contains transport
metadata, hashes, counts, and schema assertions; it never contains source rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_TDLR_SOURCE_API_CONTRACT_PREFLIGHT"
ENDPOINT = "https://data.texas.gov/api/v3/views/7358-krk7/query.json"
STARTS_AT = datetime.fromisoformat("2026-08-24T07:00:00+00:00")
EXPIRES_AT = datetime.fromisoformat("2026-08-31T07:00:00+00:00")
MAX_BYTES = 100_000
FIELDS = (
    "license_type",
    "license_number",
    "business_county",
    "business_name",
    "business_city_state_zip",
    "license_expiration_date_mmddccyy",
    "license_subtype",
)
QUERY = (
    "SELECT " + ", ".join(f"`{field}`" for field in FIELDS)
    + " WHERE `license_type` = 'Air Conditioning Contractor'"
    + " ORDER BY `license_number` ASC, `business_name` ASC"
)
REQUEST_BODY = {
    "query": QUERY,
    "page": {"pageNumber": 1, "pageSize": 5},
    "includeSynthetic": False,
}
CONTACT_SHAPE = re.compile(
    r"(?i)(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d))"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_headers(headers: Any) -> dict[str, str]:
    allowed = {"content-type", "content-length", "etag", "last-modified", "date", "server"}
    result: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower in allowed or lower.startswith(("x-soda", "x-socrata", "x-tyler")):
            result[lower] = str(value)
    return dict(sorted(result.items()))


def validate_rows(parsed: object) -> dict[str, Any]:
    if not isinstance(parsed, list) or not 1 <= len(parsed) <= 5:
        raise RuntimeError("response is not a row-bearing JSON array of one to five rows")
    row_hashes: list[str] = []
    for row in parsed:
        if not isinstance(row, dict):
            raise RuntimeError("response row is not an object")
        if set(row) != set(FIELDS):
            raise RuntimeError("response row does not contain exactly the seven approved fields")
        if any(not isinstance(row[field], str) for field in FIELDS):
            raise RuntimeError("approved projected field is not text")
        if row["license_type"] != "Air Conditioning Contractor":
            raise RuntimeError("license_type filter did not return the exact intended value")
        if any(CONTACT_SHAPE.search(row[field]) for field in FIELDS):
            raise RuntimeError("contact-shaped content appeared in an approved projection field")
        row_hashes.append(sha256_bytes(canonical_bytes({field: row[field] for field in FIELDS})))
    return {
        "row_count": len(parsed),
        "exact_field_set": list(FIELDS),
        "license_type_exact_match_count": len(parsed),
        "content_free_projected_row_hashes": row_hashes,
    }


def run(
    authorization_path: Path,
    evidence_path: Path,
    *,
    opener: urllib.request.OpenerDirector | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = now or datetime.now(UTC)
    if not STARTS_AT <= observed_at <= EXPIRES_AT:
        raise RuntimeError("authorization window is not active")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if authorization.get("event") != EVENT or authorization.get("state") != "APPROVED":
        raise RuntimeError("exact TDLR contract-preflight authorization is absent")
    if authorization.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("contract-preflight executable hash mismatch")

    body = canonical_bytes(REQUEST_BODY)
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "User-Agent": "M67Phase1TDLRContractPreflight/1.0",
        },
    )
    client = opener or urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    with client.open(request, timeout=30) as response:
        if response.geturl() != ENDPOINT:
            raise RuntimeError("response escaped the exact approved endpoint")
        status = int(response.status)
        headers = _safe_headers(response.headers)
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError("response byte ceiling exceeded")
    if status < 200 or status >= 300:
        raise RuntimeError(f"unexpected HTTP status {status}")
    parsed = json.loads(raw)
    validation = validate_rows(parsed)
    evidence = {
        "schema_version": "m67-tdlr-source-api-contract-preflight-evidence-v1",
        "state": "TDLR_SOURCE_API_CONTRACT_PREFLIGHT_PASS",
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "request": {
            "method": "POST",
            "url": ENDPOINT,
            "content_type": "application/json",
            "app_token_supplied": False,
            "body_sha256": sha256_bytes(body),
            "body_shape": {
                "query": QUERY,
                "page": {"pageNumber": 1, "pageSize": 5},
                "includeSynthetic": False,
            },
            "logical_requests": 1,
            "retries": 0,
        },
        "response": {
            "status": status,
            "headers": headers,
            "body_length": len(raw),
            "body_sha256": sha256_bytes(raw),
            "syntactically_valid_json": True,
            **validation,
            "raw_body_persisted": False,
            "business_values_persisted": False,
        },
        "nominatim_requests": 0,
        "candidate_selection": False,
        "roster_created": False,
        "seed_generated": False,
        "m67_permissions": {name: "NOT_AUTHORIZED" for name in (
            "REAL_BUSINESS_DISCOVERY",
            "REAL_PUBLIC_RESEARCH",
            "PROFESSIONAL_IDENTITY_RESOLUTION",
            "REAL_CONTACT_STORAGE",
            "CONTACT_VERIFICATION",
            "SHADOW_ELIGIBILITY_EVALUATION",
            "SHADOW_READY_ASSESSMENT",
        )},
    }
    evidence_path.write_bytes(canonical_bytes(evidence))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.authorization, args.evidence), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
