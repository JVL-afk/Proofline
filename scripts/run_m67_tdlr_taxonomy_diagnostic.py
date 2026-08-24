"""One-request classification-only TDLR license_type diagnostic.

Only taxonomy strings, aggregate counts, and safe transport metadata may be
durably retained. No row-level business field is requested or persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_TDLR_TAXONOMY_DISCOVERY_SUCCESSOR"
ENDPOINT = "https://data.texas.gov/api/v3/views/7358-krk7/query.json"
STARTS_AT = datetime.fromisoformat("2026-08-24T10:20:00+00:00")
EXPIRES_AT = datetime.fromisoformat("2026-08-31T10:20:00+00:00")
MAX_BYTES = 50_000
PAGE_SIZE = 250
QUERY = (
    "SELECT `license_type`, count(*) AS `record_count`"
    " WHERE `license_type` IS NOT NULL"
    " GROUP BY `license_type`"
    " ORDER BY `license_type` ASC"
)
REQUEST_BODY = {
    "query": QUERY,
    "page": {"pageNumber": 1, "pageSize": PAGE_SIZE},
    "includeSynthetic": False,
}
CONTACT_SHAPE = re.compile(
    r"(?i)(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d))"
)
TERMINOLOGY = ("air conditioning", "refrigeration", "hvac", "acr", "contractor")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_headers(headers: Any) -> dict[str, str]:
    allowed = {"content-type", "content-length", "etag", "last-modified", "date", "server"}
    result: dict[str, str] = {}
    for name, value in headers.items():
        lower = str(name).lower()
        if lower in allowed or lower.startswith(("x-soda", "x-socrata", "x-tyler")):
            result[lower] = str(value)
    return dict(sorted(result.items()))


def structural_metadata(value: object) -> dict[str, Any]:
    if value is None:
        kind = "NULL"
    elif isinstance(value, bool):
        kind = "BOOLEAN"
    elif isinstance(value, list):
        kind = "ARRAY"
    elif isinstance(value, dict):
        kind = "OBJECT"
    elif isinstance(value, str):
        kind = "STRING"
    elif isinstance(value, (int, float)):
        kind = "NUMBER"
    else:
        kind = "UNKNOWN"
    result: dict[str, Any] = {
        "top_level_json_type": kind,
        "top_level_object_keys": sorted(value) if isinstance(value, dict) else [],
        "array_length": len(value) if isinstance(value, list) else None,
        "first_row_field_names": [],
    }
    if isinstance(value, list) and value and isinstance(value[0], dict):
        result["first_row_field_names"] = sorted(value[0])
    return result


def seal(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


class TaxonomyValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_taxonomy(parsed: object) -> dict[str, Any]:
    if not isinstance(parsed, list):
        raise TaxonomyValidationError("TOP_LEVEL_NOT_ARRAY")
    if not 1 <= len(parsed) < PAGE_SIZE:
        raise TaxonomyValidationError("EMPTY_OR_PAGE_CEILING_COMPLETENESS_UNPROVEN")
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in parsed:
        if not isinstance(row, dict) or set(row) != {"license_type", "record_count"}:
            raise TaxonomyValidationError("ROW_FIELDS_NOT_EXACT")
        license_type = row["license_type"]
        raw_count = row["record_count"]
        if not isinstance(license_type, str) or not license_type.strip() or len(license_type) > 256:
            raise TaxonomyValidationError("LICENSE_TYPE_INVALID")
        if CONTACT_SHAPE.search(license_type):
            raise TaxonomyValidationError("CONTACT_SHAPED_VALUE")
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as error:
            raise TaxonomyValidationError("AGGREGATE_COUNT_INVALID") from error
        if count <= 0:
            raise TaxonomyValidationError("AGGREGATE_COUNT_NOT_POSITIVE")
        normalized = license_type.strip()
        uniqueness_key = normalized.casefold()
        if uniqueness_key in seen:
            raise TaxonomyValidationError("LICENSE_TYPE_NOT_UNIQUE")
        seen.add(uniqueness_key)
        folded = normalized.casefold()
        values.append({
            "observed_dataset_value": normalized,
            "field": "license_type",
            "observed_count": count,
            "official_terminology_hits": [term for term in TERMINOLOGY if term in folded],
            "target_category_interpretation": "PENDING_DETERMINISTIC_POST_DIAGNOSTIC_REVIEW",
        })
    return {
        "parser_schema_result": "PASS",
        "classification_value_count": len(values),
        "classification_values": values,
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
        raise RuntimeError("exact taxonomy diagnostic authorization is absent")
    if authorization.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("taxonomy diagnostic executable hash mismatch")

    body = canonical_bytes(REQUEST_BODY)
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "User-Agent": "M67Phase1TDLRTaxonomyDiagnostic/1.0",
        },
    )
    client = opener or urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    response: Any
    try:
        response = client.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        final_url = response.geturl()
        status = int(response.status)
        headers = safe_headers(response.headers)
        raw = response.read(MAX_BYTES + 1)

    parsed: object | None = None
    parse_error_type: str | None = None
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        parse_error_type = type(error).__name__

    evidence: dict[str, Any] = {
        "schema_version": "m67-tdlr-taxonomy-diagnostic-evidence-v2",
        "state": "TDLR_TAXONOMY_METADATA_CAPTURED_PENDING_VALIDATION",
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "invariants": {
            "RESPONSE_METADATA_CAPTURE_BEFORE_SCHEMA_VALIDATION": "PASS",
            "SOURCE_API_CONTRACT_PREFLIGHT": "PASS_BOUND_TO_78210d95a9693c57cbc75955227f2c33fc1d0737c1e4ea424da35b72b9e05de3",
            "TDLR_TAXONOMY_FILTER_PROVEN": "PENDING_THIS_DIAGNOSTIC",
            "PREDECESSOR_TAXONOMY_DIAGNOSTIC": "PERMANENTLY_CONSUMED_BOUND_TO_E0DE2DECC29F1DBFFDA939A94EDB2AE7C90F6C6C138BE936D5CE50F195CD8415",
        },
        "request": {
            "method": "POST",
            "url": ENDPOINT,
            "body_sha256": sha256_bytes(body),
            "body_shape": REQUEST_BODY,
            "projected_source_fields": ["license_type"],
            "aggregate_fields": ["record_count"],
            "business_row_fields_requested": [],
            "app_token_supplied": False,
            "logical_requests": 1,
            "retries": 0,
        },
        "response": {
            "status": status,
            "allowlisted_headers": headers,
            "declared_content_type": headers.get("content-type"),
            "declared_content_length": headers.get("content-length"),
            "actual_response_byte_length": len(raw),
            "raw_body_sha256": sha256_bytes(raw),
            "byte_ceiling_exceeded": len(raw) > MAX_BYTES,
            "json_parse_success": parse_error_type is None,
            "json_parse_error_type": parse_error_type,
            **(structural_metadata(parsed) if parse_error_type is None else {
                "top_level_json_type": "UNAVAILABLE_PARSE_FAILED",
                "top_level_object_keys": [],
                "array_length": None,
                "first_row_field_names": [],
            }),
            "raw_body_persisted": False,
            "business_row_values_persisted": False,
        },
        "taxonomy_validation": "NOT_RUN_METADATA_ALREADY_SEALED",
        "failure_stage": None,
        "nominatim_requests": 0,
        "candidate_or_roster_creation": False,
        "discovery_authority": False,
        "seed_or_csprng_activity": False,
        "all_seven_m6_7_permissions": "NOT_AUTHORIZED",
    }
    seal(evidence_path, evidence)

    if final_url != ENDPOINT:
        evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "ENDPOINT_BOUNDARY"
    elif len(raw) > MAX_BYTES:
        evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "BYTE_CEILING"
    elif status < 200 or status >= 300:
        evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "HTTP_STATUS"
    elif parse_error_type is not None:
        evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "JSON_PARSE"
    else:
        try:
            taxonomy = validate_taxonomy(parsed)
        except TaxonomyValidationError as error:
            evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
            evidence["failure_stage"] = "TAXONOMY_SCHEMA"
            evidence["taxonomy_validation"] = {
                "parser_schema_result": "FAIL",
                "safe_failure_code": error.code,
            }
        else:
            evidence["state"] = "TDLR_TAXONOMY_DIAGNOSTIC_PASS_PENDING_INTERPRETATION"
            evidence["taxonomy_validation"] = taxonomy
    seal(evidence_path, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.authorization, args.evidence)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "TDLR_TAXONOMY_DIAGNOSTIC_PASS_PENDING_INTERPRETATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
