"""One-request TDLR SODA3 response-shape diagnostic.

Invariant: response metadata is sealed before parser/schema validation. Raw
response bytes and source values are never written to durable evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_TDLR_RESPONSE_SHAPE_DIAGNOSTIC"
ENDPOINT = "https://data.texas.gov/api/v3/views/7358-krk7/query.json"
STARTS_AT = datetime.fromisoformat("2026-08-24T07:30:00+00:00")
EXPIRES_AT = datetime.fromisoformat("2026-08-31T07:30:00+00:00")
MAX_BYTES = 50_000
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
    "page": {"pageNumber": 1, "pageSize": 1},
    "includeSynthetic": False,
}


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


def json_type(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "OBJECT"
    if isinstance(value, str):
        return "STRING"
    if isinstance(value, (int, float)):
        return "NUMBER"
    raise TypeError("unsupported parsed JSON type")


def structural_metadata(value: object) -> dict[str, Any]:
    kind = json_type(value)
    result: dict[str, Any] = {
        "top_level_json_type": kind,
        "top_level_object_keys": [],
        "array_length": None,
        "first_row_field_names": [],
        "list_valued_top_level_keys": [],
        "wrapped_array_lengths": {},
        "wrapped_array_first_row_field_names": {},
    }
    if isinstance(value, list):
        result["array_length"] = len(value)
        if value and isinstance(value[0], dict):
            result["first_row_field_names"] = sorted(str(key) for key in value[0])
    elif isinstance(value, dict):
        result["top_level_object_keys"] = sorted(str(key) for key in value)
        list_keys = sorted(str(key) for key, item in value.items() if isinstance(item, list))
        result["list_valued_top_level_keys"] = list_keys
        result["wrapped_array_lengths"] = {
            str(key): len(item) for key, item in value.items() if isinstance(item, list)
        }
        result["wrapped_array_first_row_field_names"] = {
            str(key): sorted(str(field) for field in item[0])
            for key, item in value.items()
            if isinstance(item, list) and item and isinstance(item[0], dict)
        }
    return result


def seal(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def locate_rows(parsed: object) -> tuple[str | None, list[object] | None]:
    if isinstance(parsed, list):
        return "$", parsed
    if isinstance(parsed, dict):
        for key in ("data", "results", "rows"):
            value = parsed.get(key)
            if isinstance(value, list):
                return f"$.{key}", value
    return None, None


def schema_result(parsed: object) -> dict[str, Any]:
    location, rows = locate_rows(parsed)
    result: dict[str, Any] = {
        "row_array_location": location,
        "row_count": None if rows is None else len(rows),
        "expected_fields": list(FIELDS),
        "first_row_missing_fields": [],
        "first_row_unexpected_fields": [],
        "first_row_is_object": False,
        "license_type_filter_matches": None,
    }
    if rows is None:
        result["parser_schema_result"] = "FAIL_ROW_ARRAY_LOCATION_UNKNOWN"
        return result
    if not rows:
        result["parser_schema_result"] = "FAIL_ROW_ARRAY_EMPTY"
        return result
    if not isinstance(rows[0], dict):
        result["parser_schema_result"] = "FAIL_FIRST_ROW_NOT_OBJECT"
        return result
    first = rows[0]
    result["first_row_is_object"] = True
    result["first_row_missing_fields"] = sorted(set(FIELDS) - set(first))
    result["first_row_unexpected_fields"] = sorted(set(first) - set(FIELDS))
    result["license_type_filter_matches"] = (
        first.get("license_type") == "Air Conditioning Contractor"
    )
    if result["first_row_missing_fields"]:
        result["parser_schema_result"] = "FAIL_EXPECTED_FIELDS_MISSING"
    elif result["first_row_unexpected_fields"]:
        result["parser_schema_result"] = "FAIL_UNEXPECTED_FIELDS_PRESENT"
    elif not result["license_type_filter_matches"]:
        result["parser_schema_result"] = "FAIL_FILTER_VALUE_MISMATCH"
    else:
        result["parser_schema_result"] = "PASS"
    return result


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
        raise RuntimeError("exact response-shape diagnostic authorization is absent")
    if authorization.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("response-shape diagnostic executable hash mismatch")

    body = canonical_bytes(REQUEST_BODY)
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "User-Agent": "M67Phase1TDLRResponseShapeDiagnostic/1.0",
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

    parse_error_type: str | None = None
    parsed: object | None = None
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        parse_error_type = type(error).__name__

    evidence: dict[str, Any] = {
        "schema_version": "m67-tdlr-response-shape-diagnostic-evidence-v1",
        "state": "TDLR_RESPONSE_SHAPE_CAPTURED_PENDING_SCHEMA_VALIDATION",
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "invariants": {
            "RESPONSE_METADATA_CAPTURE_BEFORE_SCHEMA_VALIDATION": "PASS",
            "SOURCE_API_CONTRACT_PREFLIGHT": "REQUIRED_BEFORE_FUTURE_ONE_SHOT_ACQUISITION",
        },
        "request": {
            "method": "POST",
            "url": ENDPOINT,
            "content_type": "application/json",
            "app_token_supplied": False,
            "body_sha256": sha256_bytes(body),
            "body_shape": REQUEST_BODY,
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
                "list_valued_top_level_keys": [],
                "wrapped_array_lengths": {},
                "wrapped_array_first_row_field_names": {},
            }),
            "raw_body_persisted": False,
            "field_values_persisted": False,
        },
        "parser_schema_result": "NOT_RUN_METADATA_ALREADY_SEALED",
        "failure_stage": None,
        "nominatim_requests": 0,
        "candidate_or_roster_creation": False,
        "seed_or_csprng_activity": False,
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
    seal(evidence_path, evidence)

    if final_url != ENDPOINT:
        evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "ENDPOINT_BOUNDARY"
    elif len(raw) > MAX_BYTES:
        evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "BYTE_CEILING"
    elif status < 200 or status >= 300:
        evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "HTTP_STATUS"
    elif parse_error_type is not None:
        evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
        evidence["failure_stage"] = "JSON_PARSE"
    else:
        schema = schema_result(parsed)
        evidence["parser_schema_result"] = schema
        if schema["parser_schema_result"] == "PASS":
            evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_PASS"
        else:
            evidence["state"] = "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
            evidence["failure_stage"] = "ROW_ARRAY_OR_FIELD_SCHEMA"
    seal(evidence_path, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.authorization, args.evidence)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
