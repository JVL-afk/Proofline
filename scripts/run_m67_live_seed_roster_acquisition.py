"""One-shot M6.7 TDLR/Nominatim seed-roster acquisition.

The executable is fail closed and is only callable with the exact accepted authorization record.
It writes the two authorized roster artifacts only when at least 24 complete observations survive.
Raw HTTP bodies exist only in memory and are never logged or written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import boto3
from m67_nominatim_host_guard import guard_projection
from m67_nominatim_host_locator import build_query, project_response, response_sha256

ACCOUNT = "785072247535"
REGION = "us-east-2"
PROFILE = "m67-phase1-owner"
RELEASE_ID = "M67_LIVE_SEED_ROSTER_ACQUISITION_V2"
TDLR_ENDPOINT = "https://data.texas.gov/api/v3/views/7358-krk7/query.json"
KILL_SWITCH = "/m67-phase1/kill-switch"
STARTS_AT = datetime.fromisoformat("2026-08-24T06:30:00+00:00")
EXPIRES_AT = datetime.fromisoformat("2026-08-31T06:30:00+00:00")
TDLR_FIELDS = (
    "license_type",
    "license_number",
    "business_county",
    "business_name",
    "business_city_state_zip",
    "license_expiration_date_mmddccyy",
    "license_subtype",
)
ENTITY_SUFFIX = re.compile(
    r"(?i)(?:,?\s+|\b)(?:LLC|L\.L\.C\.|INC\.?|INCORPORATED|CORP\.?|CORPORATION|"
    r"LTD\.?|LIMITED|LP|L\.P\.|LLP|PLLC|P\.C\.|P\.A\.|CO\.?|COMPANY)\s*$"
)
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")
MAX_TDLR_BYTES = 31_000_000
MAX_NOMINATIM_BYTES = 50_000
MAX_TOTAL_BYTES = 36_000_000
USER_AGENT = "M67Phase1SeedLocator/1.0"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_tdlr_url() -> str:
    fields = ", ".join(TDLR_FIELDS)
    query = (
        f"SELECT {fields} WHERE upper(license_type) like '%AIR CONDITION%' "
        "ORDER BY license_number ASC, business_name ASC LIMIT 500"
    )
    return f"{TDLR_ENDPOINT}?{urllib.parse.urlencode({'query': query})}"


def project_tdlr_rows(
    response: object, *, cutoff: datetime
) -> tuple[list[dict[str, str]], Counter[str]]:
    rows = _extract_rows(response)
    counts: Counter[str] = Counter()
    frozen: list[dict[str, str]] = []
    for raw in rows[:500]:
        counts["tdlr_records_considered"] += 1
        if not isinstance(raw, dict):
            counts["UNCLASSIFIABLE_RECORD"] += 1
            continue
        row = {field: raw.get(field) for field in TDLR_FIELDS}
        if any(not isinstance(value, str) or not value.strip() for value in row.values()):
            counts["MISSING_APPROVED_FIELD"] += 1
            continue
        projected = cast(dict[str, str], row)
        name = projected["business_name"].strip()
        if EMAIL.search(name) or PHONE.search(name) or not ENTITY_SUFFIX.search(name):
            counts["NATURAL_PERSON_SOLE_PROPRIETOR_OR_AMBIGUOUS_NAME"] += 1
            continue
        license_type = projected["license_type"].casefold()
        if "air condition" not in license_type or "contractor" not in license_type:
            counts["NOT_APPROVED_HVAC_LICENSE_TYPE"] += 1
            continue
        subtype = projected["license_subtype"].casefold()
        commercial = "commercial" in subtype and "refrigeration" in subtype
        process_cooling = "process" in subtype and "cool" in subtype
        if not (commercial or process_cooling):
            counts["COMMERCIAL_HVAC_B2B_NOT_EXPLICIT"] += 1
            continue
        location = projected["business_city_state_zip"]
        if not re.search(r"(?i)(?:,|\s)(?:TX|TEXAS)(?:\s|,|$)", location):
            counts["TEXAS_LOCATION_NOT_EXPLICIT"] += 1
            continue
        expiration = _parse_expiration(projected["license_expiration_date_mmddccyy"])
        if expiration is None or expiration.date() < cutoff.date():
            counts["EXPIRED_OR_UNPARSEABLE_LICENSE"] += 1
            continue
        frozen.append({field: projected[field].strip() for field in TDLR_FIELDS})
        counts["eligible_business_entities"] += 1
        if len(frozen) == 100:
            break
    return frozen, counts


def build_observation(
    row: dict[str, str], host_result: dict[str, Any], *, tdlr_hash: str, observed_at: str
) -> dict[str, Any]:
    license_number = row["license_number"]
    host = str(host_result["first_party_host_candidate"])
    osm = cast(dict[str, str], host_result["provenance"])
    tdlr_locator = f"tdlr-license:{license_number}"
    source_ref = f"sha256:{tdlr_hash}"
    return {
        "public_business_name": row["business_name"],
        "texas_city_or_service_area": row["business_city_state_zip"],
        "first_party_host_candidate": host,
        "organization_group_hint": row["business_name"],
        "lead_flow_unit_hint": host,
        "identity_ambiguous": False,
        "eligibility_observations": {
            "identity": [f"{tdlr_locator}:business_name"],
            "texas": [f"{tdlr_locator}:business_city_state_zip"],
            "commercial_hvac": [
                f"{tdlr_locator}:license_type",
                f"{tdlr_locator}:license_subtype",
            ],
            "b2b": [f"{tdlr_locator}:license_subtype:explicit_commercial_or_process_cooling"],
            "operational": [f"{tdlr_locator}:license_expiration"],
            "first_party_host": [str(osm["locator"])],
        },
        "provenance": [
            {
                "source_id": "TX_OPEN_DATA_TDLR_ALL_LICENSES::7358-krk7",
                "source_artifact_ref": source_ref,
                "source_artifact_sha256": tdlr_hash,
                "locator": tdlr_locator,
                "observed_at": observed_at,
            },
            {
                "source_id": "OSM_NOMINATIM_PUBLIC_SEARCH_V1",
                "source_artifact_ref": f"sha256:{osm['source_artifact_sha256']}",
                "source_artifact_sha256": osm["source_artifact_sha256"],
                "locator": osm["locator"],
                "observed_at": osm["observed_at"],
            },
        ],
    }


def run(
    *, root: Path, authorization_record: Path, opener: urllib.request.OpenerDirector | None = None
) -> dict[str, Any]:
    now = datetime.now(UTC)
    if not STARTS_AT <= now <= EXPIRES_AT:
        raise RuntimeError("authorization window is not active")
    authorization = json.loads(authorization_record.read_text(encoding="utf-8"))
    if authorization.get("event") != "AUTHORIZE_SUCCESSOR_LIVE_PHASE1_SEED_ROSTER_ACQUISITION":
        raise RuntimeError("successor acquisition authorization event mismatch")
    if authorization.get("state") != "APPROVED":
        raise RuntimeError("successor acquisition is not approved")
    if authorization.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("successor acquisition executable hash mismatch")
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != ACCOUNT:
        raise RuntimeError("AWS account mismatch")
    ssm = session.client("ssm")
    before = ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]
    if before["Value"] != "TRIPPED":
        raise RuntimeError("kill switch is not TRIPPED")

    counts: Counter[str] = Counter()
    total_bytes = 0
    observations: list[dict[str, Any]] = []
    started_at = datetime.now(UTC)
    terminal_state = "FAILED_BEFORE_SOURCE_REQUEST"
    ssm.put_parameter(Name=KILL_SWITCH, Value="RUN", Type="String", Overwrite=True)
    try:
        active = ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]
        if active["Value"] != "RUN":
            raise RuntimeError("kill switch RUN transition not observed")
        http = opener or urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
        )
        counts["logical_http_requests"] += 1
        counts["attempts"] += 1
        tdlr_raw = _request(http, build_tdlr_url(), MAX_TDLR_BYTES)
        total_bytes += len(tdlr_raw)
        tdlr_hash = response_sha256(tdlr_raw)
        frozen, tdlr_counts = project_tdlr_rows(json.loads(tdlr_raw), cutoff=started_at)
        counts.update(tdlr_counts)
        for index, row in enumerate(frozen):
            if index:
                time.sleep(2)
            if ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]["Value"] != "RUN":
                raise RuntimeError("kill switch tripped during acquisition")
            observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            try:
                counts["logical_http_requests"] += 1
                counts["attempts"] += 1
                raw = _request(
                    http,
                    build_query(row["business_name"], row["business_city_state_zip"]),
                    MAX_NOMINATIM_BYTES,
                )
                total_bytes += len(raw)
                if total_bytes > MAX_TOTAL_BYTES:
                    raise RuntimeError("aggregate response byte cap exceeded")
                projected = project_response(
                    public_business_name=row["business_name"],
                    texas_city_or_service_area=row["business_city_state_zip"],
                    response=json.loads(raw),
                    raw_artifact_sha256=response_sha256(raw),
                    observed_at=observed_at,
                )
                guarded = guard_projection(projected)
            except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
                guarded = {"state": "AMBIGUOUS", "reason": "TECHNICAL_FAILURE_NO_RETRY"}
            state = guarded.get("state")
            if state == "LOCATED_PENDING_EXACT_HOST_A09_REVIEW":
                counts["hostname_FOUND"] += 1
                observations.append(
                    build_observation(row, guarded, tdlr_hash=tdlr_hash, observed_at=observed_at)
                )
            elif guarded.get("reason") == "THIRD_PARTY_HOST_REJECTED":
                counts["hostname_REJECTED_BY_GUARD"] += 1
            elif state == "NOT_FOUND":
                counts["hostname_NOT_FOUND"] += 1
            else:
                counts["hostname_AMBIGUOUS"] += 1
            print(
                f"progress={index + 1}/{len(frozen)} found={counts['hostname_FOUND']} "
                f"not_found={counts['hostname_NOT_FOUND']} "
                f"ambiguous={counts['hostname_AMBIGUOUS']} "
                f"guard={counts['hostname_REJECTED_BY_GUARD']}",
                flush=True,
            )

        counts["compliant_final_observations"] = len(observations)
        if len(observations) < 24:
            terminal_state = "FAILED_FEWER_THAN_24_COMPLIANT_OBSERVATIONS"
        else:
            _write_success(root, observations, counts, started_at, tdlr_hash)
            terminal_state = "ROSTER_AND_ATTESTATION_SEALED"
        return {
            "state": terminal_state,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "counts": dict(sorted(counts.items())),
            "aggregate_response_bytes": total_bytes,
            "tdlr_response_sha256": tdlr_hash,
        }
    finally:
        ssm.put_parameter(Name=KILL_SWITCH, Value="TRIPPED", Type="String", Overwrite=True)
        observed = ssm.get_parameter(Name=KILL_SWITCH)["Parameter"]
        if observed["Value"] != "TRIPPED":
            raise RuntimeError("terminal kill-switch restoration failed")


def _request(opener: urllib.request.OpenerDirector, url: str, maximum: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    with opener.open(request, timeout=30) as response:
        if response.geturl().split("?", 1)[0] not in {
            TDLR_ENDPOINT,
            "https://nominatim.openstreetmap.org/search",
        }:
            raise RuntimeError("response escaped exact endpoint")
        body = response.read(maximum + 1)
    if len(body) > maximum:
        raise RuntimeError("response byte cap exceeded")
    return body


def _extract_rows(response: object) -> list[object]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("data", "results", "rows"):
            value = response.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("unrecognized TDLR response shape")


def _parse_expiration(value: str) -> datetime | None:
    for pattern in ("%m/%d/%Y", "%m%d%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value.strip(), pattern).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def _write_success(
    root: Path,
    observations: list[dict[str, Any]],
    counts: Counter[str],
    started_at: datetime,
    tdlr_hash: str,
) -> None:
    target = root / "local-data/m6.7/seed-source-acquisition/input"
    target.mkdir(parents=True, exist_ok=True)
    roster = target / "offline-business-roster.json"
    roster_bytes = canonical_bytes(observations)
    roster.write_bytes(roster_bytes)
    roster_hash = sha256_bytes(roster_bytes)
    attestation: dict[str, Any] = {
        "record_type": "M67_OFFLINE_SEED_SOURCE_INSTANCE_ATTESTATION",
        "version": "1.0.0",
        "state": "SEALED_APPROVED_LIVE_SOURCE_OUTPUT",
        "source_class": "OWNER_CONTROLLED_FIELD_LIMITED_OFFLINE_BUSINESS_ROSTER_V1",
        "source_kind": "DISCOVERY_SOURCE_SUBSTAGE",
        "artifact_ref": (
            "local-data/m6.7/seed-source-acquisition/input/offline-business-roster.json"
        ),
        "artifact_sha256_before_parse": roster_hash,
        "artifact_bytes": len(roster_bytes),
        "record_count": len(observations),
        "complete_predeclared_frame": True,
        "origin_and_construction_method": (
            "M67_LIVE_SEED_ROSTER_ACQUISITION_V2_EXACT_TDLR_AND_NOMINATIM"
        ),
        "row_level_provenance_present": True,
        "permitted_use_and_reuse_basis": (
            "TDLR_APPROVED_WITH_CONTROLS_AND_OSM_ODBL_1_0_INTERNAL_USE"
        ),
        "terms_access_review": "ACCEPTED_SOURCE_RECORDS_BOUND_BY_RELEASE",
        "robots_review": "NOT_APPLICABLE_DOCUMENTED_APIS_NO_HTML_CRAWLING",
        "third_party_restrictions": (
            "OSM_ATTRIBUTION_INTERNAL_USE_AND_EXACT_HOST_A09_REVIEW_REQUIRED"
        ),
        "business_only_field_limited_export": True,
        "prohibited_field_scan_result": "PASS_DETERMINISTIC_FIELD_PROJECTION",
        "opportunity_or_outcome_selection_absent": True,
        "accountable_owner_actor_ref": "OWNER_ACTOR",
        "privacy_source_reviewer_actor_ref": "OWNER_ACTOR",
        "qualified_source_review_state": (
            "TDLR_REVIEW_ACCEPTED_NOMINATIM_EXPLICIT_LICENSE_NO_NEW_REVIEW_REQUIRED"
        ),
        "effective_at": started_at.isoformat(),
        "expires_at": EXPIRES_AT.isoformat(),
        "tdlr_ephemeral_artifact_sha256": tdlr_hash,
        "counts": dict(sorted(counts.items())),
        "configuration_hash": None,
    }
    payload = {key: value for key, value in attestation.items() if key != "configuration_hash"}
    attestation["configuration_hash"] = sha256_bytes(canonical_bytes(payload))
    (target / "offline-business-roster-attestation.json").write_bytes(canonical_bytes(attestation))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authorization-record", type=Path, required=True)
    args = parser.parse_args()
    result = run(root=args.root.resolve(), authorization_record=args.authorization_record.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "ROSTER_AND_ATTESTATION_SEALED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
