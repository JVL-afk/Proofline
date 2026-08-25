"""Validate, freeze, and order the owner-curated 100-company replacement frame offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import os
import re
import secrets
import unicodedata
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_REPLACEMENT_100_COMPANY_PHASE1_FRAME_INGESTION"
ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INPUT_SHA256 = "6604b3bad0ff9c363255ca56bcb1efc80bb6fa9d7f7b17bda312a0061c64b35c"
EXPECTED_COLUMNS = ("company_name", "company_website", "county", "city")
SAMPLE_SOURCE = "OWNER_CURATED_TEXAS_HVAC_WITH_MANUALLY_VERIFIED_REACHABLE_WEBSITE"
ELIGIBILITY_SOURCE = "OWNER_MANUAL_SELECTION_AT_FRAME_CONSTRUCTION"
REPRESENTATION_SCOPE = (
    "OWNER_CURATED_TEXAS_HVAC_WITH_MANUALLY_VERIFIED_REACHABLE_WEB_PRESENCE_NOT_ALL_TEXAS_HVAC"
)
PRIOR_SAMPLE_SUPERSESSION_STATE = (
    "SUPERSEDED_BEFORE_PUBLIC_RESEARCH_DUE_TO_OWNER_DISCOVERED_HOST_VALIDITY_DEFECT"
)
OWNER_AFFIRMATION = (
    "I attest that all 100 submitted records are Texas HVAC businesses selected for this "
    "Phase 1 sampling frame; all submitted websites were manually checked and appeared "
    "reachable at preparation time; selection occurred before M1-M5 evaluation; selection "
    "was not based on perceived opportunity strength, website weakness, expected result, "
    "sales attractiveness, or contactability; and no later A-09 or M1-M5 outcome may cause "
    "a submitted company, slot, or frame position to be redrawn or replaced."
)
BOUND_PATHS = {
    "input": Path(r"C:\Users\eugen\Downloads\manual_discovery_HVAC_companies.csv"),
    "input_copy": ROOT
    / "local-data/m6.7/replacement-100-company-frame/input/manual_discovery_HVAC_companies.csv",
    "attestation_output": ROOT
    / "local-data/m6.7/replacement-100-company-frame/input/owner-attestation.json",
    "normalized_frame_output": ROOT
    / "local-data/m6.7/replacement-100-company-frame/output/normalized-frame.json",
    "private_seed_output": ROOT
    / "local-data/m6.7/replacement-100-company-frame/private/ordering-seed.json",
    "ordered_package_output": ROOT
    / "local-data/m6.7/replacement-100-company-frame/output/ordered-package.json",
    "evidence_output": ROOT
    / (
        "docs/readiness/m6.7-authorization/"
        "replacement-100-company-phase1-frame-ingestion-evidence-2026-08-25.json"
    ),
    "supersession_output": ROOT
    / (
        "docs/readiness/m6.7-authorization/"
        "prior-24-company-phase1-sample-supersession-accepted-2026-08-25.json"
    ),
    "normalized_frame_schema": ROOT
    / "docs/readiness/m6.7-authorization/replacement-100-company-normalized-frame-v1.schema.json",
}
ORDERING_VERSION = "m6.7.phase1.replacement100.seeded-order@1"
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!.*\.\.)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$"
)
PROHIBITED_SUFFIXES = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "x.com",
    "youtube.com",
    "yelp.com",
    "angi.com",
    "homeadvisor.com",
    "thumbtack.com",
    "bbb.org",
    "houzz.com",
    "nextdoor.com",
    "google.com",
    "googleapis.com",
    "maps.apple.com",
    "mapquest.com",
    "yellowpages.com",
    "amazon.com",
    "ebay.com",
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "linktr.ee",
    "wixsite.com",
    "weebly.com",
}
PERMISSIONS = {
    name: "NOT_AUTHORIZED"
    for name in (
        "REAL_BUSINESS_DISCOVERY",
        "REAL_PUBLIC_RESEARCH",
        "PROFESSIONAL_IDENTITY_RESOLUTION",
        "REAL_CONTACT_STORAGE",
        "CONTACT_VERIFICATION",
        "SHADOW_ELIGIBILITY_EVALUATION",
        "SHADOW_READY_ASSESSMENT",
    )
}


class ValidationFailure(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def plain_value(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationFailure(f"{field.upper()}_MISSING_BLANK_OR_TOO_LONG")
    if any(ord(char) < 32 and char not in "\t" for char in value):
        raise ValidationFailure(f"{field.upper()}_CONTROL_CHARACTER")
    if EMAIL_RE.search(value) or PHONE_RE.search(value):
        raise ValidationFailure(f"{field.upper()}_CONTACT_SHAPED_VALUE")
    return value


def normalize_website(value: str) -> tuple[str, dict[str, bool | str]]:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValidationFailure("COMPANY_WEBSITE_HTTP_HTTPS_URL_REQUIRED")
    if parsed.username or parsed.password:
        raise ValidationFailure("COMPANY_WEBSITE_EMBEDDED_CREDENTIALS")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValidationFailure("COMPANY_WEBSITE_INVALID_PORT") from error
    if port is not None and port not in {80, 443}:
        raise ValidationFailure("COMPANY_WEBSITE_NONDEFAULT_PORT")
    raw_host = parsed.hostname
    if not raw_host:
        raise ValidationFailure("COMPANY_WEBSITE_HOST_MISSING")
    try:
        host = raw_host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValidationFailure("COMPANY_WEBSITE_IDNA_INVALID") from error
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationFailure("COMPANY_WEBSITE_IP_LITERAL")
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValidationFailure("COMPANY_WEBSITE_LOCAL_HOST")
    if not HOST_RE.fullmatch(host):
        raise ValidationFailure("COMPANY_WEBSITE_HOSTNAME_MALFORMED")
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in PROHIBITED_SUFFIXES):
        raise ValidationFailure("COMPANY_WEBSITE_PROHIBITED_THIRD_PARTY_HOST")
    findings: dict[str, bool | str] = {
        "scheme": parsed.scheme.lower(),
        "www_preserved": host.startswith("www."),
        "path_stripped": parsed.path not in {"", "/"},
        "query_stripped": bool(parsed.query),
        "fragment_stripped": bool(parsed.fragment),
        "host_case_or_idna_normalized": raw_host != host,
    }
    return host, findings


def validate_csv(raw: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationFailure("INPUT_NOT_UTF8") from error
    reader = csv.DictReader(text.splitlines(), strict=True)
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise ValidationFailure("EXACT_FOUR_COLUMN_SCHEMA_MISMATCH")
    source_rows = list(reader)
    if len(source_rows) != 100:
        raise ValidationFailure("ROW_COUNT_NOT_EXACTLY_100")
    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    name_indices: dict[str, list[int]] = {}
    host_indices: dict[str, list[int]] = {}
    finding_counts: Counter[str] = Counter()
    for index, row in enumerate(source_rows, start=1):
        try:
            if set(row) != set(EXPECTED_COLUMNS) or row.get(None):
                raise ValidationFailure("ROW_COLUMN_SCHEMA_MISMATCH")
            company_name = plain_value(row["company_name"], "company_name", 240)
            website = plain_value(row["company_website"], "company_website", 2048)
            county = plain_value(row["county"], "county", 160)
            city = plain_value(row["city"], "city", 160)
            name_key = normalize_name(company_name)
            if not name_key:
                raise ValidationFailure("COMPANY_NAME_NORMALIZATION_EMPTY")
            host, findings = normalize_website(website)
            name_indices.setdefault(name_key, []).append(index)
            host_indices.setdefault(host, []).append(index)
            for key, finding in findings.items():
                finding_counts[f"{key}::{finding}"] += 1
            original = {
                "company_name": company_name,
                "company_website": website,
                "county": county,
                "city": city,
            }
            prepared.append(
                {
                    "submission_index": index,
                    "company_name": company_name,
                    "company_website_original": website,
                    "county": county,
                    "city": city,
                    "normalized_company_name_key": name_key,
                    "candidate_hostname": host,
                    "source_row_sha256": sha256_bytes(canonical_bytes(original)),
                }
            )
        except ValidationFailure as error:
            failures.append({"row": index, "reason": str(error)})
    duplicate_names = {key: rows for key, rows in name_indices.items() if len(rows) > 1}
    duplicate_hosts = {key: rows for key, rows in host_indices.items() if len(rows) > 1}
    if duplicate_names:
        failures.extend(
            {"row": rows, "reason": "NORMALIZED_COMPANY_NAME_DUPLICATE"}
            for rows in duplicate_names.values()
        )
    if duplicate_hosts:
        failures.extend(
            {"row": rows, "reason": "NORMALIZED_HOSTNAME_DUPLICATE"}
            for rows in duplicate_hosts.values()
        )
    report = {
        "input_row_count": len(source_rows),
        "columns": list(EXPECTED_COLUMNS),
        "structural_failure_count": len(failures),
        "structural_failures": failures,
        "duplicate_company_name_groups": list(duplicate_names.values()),
        "duplicate_hostname_groups": list(duplicate_hosts.values()),
        "url_normalization_findings": dict(sorted(finding_counts.items())),
    }
    return prepared, report


def build_frame(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    frame = {
        "schema_version": "m67-replacement-100-company-normalized-frame-v1",
        "PHASE1_SAMPLE_SOURCE": SAMPLE_SOURCE,
        "HVAC_ELIGIBILITY_SOURCE": ELIGIBILITY_SOURCE,
        "AUTOMATED_TDLR_DISCOVERY_VALIDATED": False,
        "representation_scope": REPRESENTATION_SCOPE,
        "companies": rows,
    }
    return frame, sha256_bytes(canonical_bytes(frame))


def build_ordered_package(
    frame: dict[str, Any],
    frame_hash: str,
    seed: bytes,
    *,
    input_hash: str,
    attestation_hash: str,
    created_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(seed) != 32:
        raise ValidationFailure("CSPRNG_SEED_LENGTH_INVALID")
    ranked: list[tuple[str, str, dict[str, Any]]] = []
    for row in frame["companies"]:
        stable_key = sha256_bytes(canonical_bytes(row))
        ordering_key = hashlib.sha256(
            b"\0".join((ORDERING_VERSION.encode(), seed, frame_hash.encode(), stable_key.encode()))
        ).hexdigest()
        ranked.append((ordering_key, stable_key, row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    ordered = [
        {**row, "position": index} for index, (_key, _stable, row) in enumerate(ranked, start=1)
    ]
    slots = [{**row, "slot": row["position"]} for row in ordered[:24]]
    remainder = ordered[24:]
    seed_commitment = sha256_bytes(seed)
    seed_evidence = {
        "ordering_version": ORDERING_VERSION,
        "frozen_frame_sha256": frame_hash,
        "seed_commitment": seed_commitment,
        "seed_generated_after_frame_freeze": True,
    }
    package: dict[str, Any] = {
        "schema_version": "m67-replacement-100-company-ordered-phase1-package-v1",
        "state": "FROZEN_AWAITING_NEW_EXACT_HOST_A09_REVIEW",
        "account": ACCOUNT,
        "region": REGION,
        "created_at": created_at,
        "PHASE1_SAMPLE_SOURCE": SAMPLE_SOURCE,
        "HVAC_ELIGIBILITY_SOURCE": ELIGIBILITY_SOURCE,
        "AUTOMATED_TDLR_DISCOVERY_VALIDATED": False,
        "prior_sample_state": PRIOR_SAMPLE_SUPERSESSION_STATE,
        "input_artifact_sha256": input_hash,
        "owner_attestation_sha256": attestation_hash,
        "frozen_frame_count": 100,
        "frozen_frame_sha256": frame_hash,
        "frame_frozen_before_seed_generation": True,
        "ordering_version": ORDERING_VERSION,
        "seed_commitment": seed_commitment,
        "seed_evidence_sha256": sha256_bytes(canonical_bytes(seed_evidence)),
        "slots": slots,
        "frame_remainder": remainder,
        "reserve_for_outcome_replacement": [],
        "outcome_based_replacement_prohibited": True,
        "a09_stubs": [
            {
                "slot": row["slot"],
                "exact_host": row["candidate_hostname"],
                "state": "NOT_APPROVED_NEW_REVIEW_REQUIRED",
            }
            for row in slots
        ],
        "permissions": PERMISSIONS,
        "package_sha256": None,
    }
    package["package_sha256"] = sha256_bytes(
        canonical_bytes({key: value for key, value in package.items() if key != "package_sha256"})
    )
    return package, seed_evidence


def seal(path: Path, value: object | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value if isinstance(value, bytes) else canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def preflight(input_path: Path, report_path: Path) -> None:
    raw = input_path.read_bytes()
    rows, report = validate_csv(raw)
    _frame, frame_hash = build_frame(rows)
    safe = {
        "schema_version": "m67-replacement-100-company-preflight-v1",
        "state": "PREFLIGHT_PASS_READY_FOR_OWNER_AUTHORIZATION"
        if not report["structural_failures"]
        else "PREFLIGHT_FAIL_INPUT_CORRECTION_REQUIRED",
        "input_artifact_sha256": sha256_bytes(raw),
        "input_bytes": len(raw),
        **report,
        "preflight_normalized_frame_sha256_not_frozen": frame_hash
        if not report["structural_failures"]
        else None,
        "seed_generated": False,
        "network_operations": 0,
        "m1_m5_operations": 0,
        "permissions": PERMISSIONS,
    }
    seal(report_path, safe)


def execute(args: argparse.Namespace) -> None:
    auth_raw = args.authorization.read_bytes()
    auth = json.loads(auth_raw)
    if auth.get("state") != "APPROVED" or auth.get("event") != EVENT:
        raise RuntimeError("exact replacement-frame authorization is absent")
    if auth.get("account") != ACCOUNT or auth.get("region") != REGION:
        raise RuntimeError("account or region binding mismatch")
    if auth.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("executable hash mismatch")
    for name, expected in BOUND_PATHS.items():
        if getattr(args, name).resolve() != expected.resolve():
            raise RuntimeError(f"path binding mismatch: {name}")
    if auth.get("normalized_frame_schema_sha256") != sha256_bytes(
        args.normalized_frame_schema.read_bytes()
    ):
        raise RuntimeError("normalized frame schema hash mismatch")
    if auth.get("exact_owner_attestation") != OWNER_AFFIRMATION:
        raise RuntimeError("owner attestation mismatch")
    now = datetime.now(UTC)
    starts = datetime.fromisoformat(auth["valid_from"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(auth["expires_at"].replace("Z", "+00:00"))
    if not starts <= now <= expires:
        raise RuntimeError("authorization window is not active")
    for path in (
        args.input_copy,
        args.attestation_output,
        args.normalized_frame_output,
        args.private_seed_output,
        args.ordered_package_output,
        args.evidence_output,
        args.supersession_output,
    ):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite immutable output: {path}")
    raw = args.input.read_bytes()
    if (
        sha256_bytes(raw) != EXPECTED_INPUT_SHA256
        or auth.get("input_artifact_sha256") != EXPECTED_INPUT_SHA256
    ):
        raise ValidationFailure("INPUT_ARTIFACT_HASH_MISMATCH")
    rows, report = validate_csv(raw)
    if report["structural_failures"]:
        seal(
            args.evidence_output,
            {
                "state": "FAILED_CLOSED_STRUCTURAL_VALIDATION",
                "input_artifact_sha256": EXPECTED_INPUT_SHA256,
                **report,
                "seed_generated": False,
                "network_operations": 0,
                "permissions": PERMISSIONS,
            },
        )
        raise ValidationFailure("STRUCTURAL_VALIDATION_FAILED")
    frame, frame_hash = build_frame(rows)
    if auth.get("preflight_normalized_frame_sha256") != frame_hash:
        raise ValidationFailure("NORMALIZED_FRAME_PREFLIGHT_HASH_MISMATCH")
    attestation = {
        "actor_ref": "OWNER_ACTOR",
        "input_artifact_sha256": EXPECTED_INPUT_SHA256,
        "candidate_count": 100,
        "all_are_owner_selected_texas_hvac_businesses": True,
        "websites_manually_checked_reachable_at_preparation_time": True,
        "selected_before_m1_m5": True,
        "not_selected_by_opportunity_website_weakness_expected_result_or_sales_"
        "attractiveness": True,
        "no_later_outcome_replacement": True,
        "exact_affirmation": auth["exact_owner_attestation"],
    }
    attestation_hash = sha256_bytes(canonical_bytes(attestation))
    # Freeze the input, attestation, and complete normalized frame before any
    # CSPRNG seed exists.
    seal(args.input_copy, raw)
    seal(args.attestation_output, attestation)
    seal(args.normalized_frame_output, frame)
    seed = secrets.token_bytes(32)
    package, seed_evidence = build_ordered_package(
        frame,
        frame_hash,
        seed,
        input_hash=EXPECTED_INPUT_SHA256,
        attestation_hash=attestation_hash,
        created_at=now.isoformat().replace("+00:00", "Z"),
    )
    seal(args.private_seed_output, {"seed_hex": seed.hex(), "seed_commitment": sha256_bytes(seed)})
    seal(args.ordered_package_output, package)
    seal(
        args.supersession_output,
        {
            "schema_version": "m67-prior-24-company-phase1-sample-supersession-accepted-v1",
            "state": PRIOR_SAMPLE_SUPERSESSION_STATE,
            "supersession_reason": "INPUT_FRAME_WEBSITE_VALIDITY_DEFECT",
            "supersession_outcome_based": False,
            "m1_m5_executions_under_prior_sample": 0,
            "public_research_outcomes_observed": 0,
            "person_contact_operations": 0,
            "outreach_delivery_operations": 0,
            "prior_frozen_frame_sha256": (
                "aebd0c6c1df4290cfa0209b4f8d65d48d15a6cf013c071dad985e385da6da0ea"
            ),
            "prior_ordered_package_semantic_sha256": (
                "8a0703e6a441e28a62ae5f5ed32faf0279502c695d34779132ffa48979074050"
            ),
            "prior_a09_terminal_evidence_sha256": (
                "1bf1fc7eaf6eef75539a69bed17d43f15d113efc03e972156cf004e12c19a107"
            ),
            "consumed_grants_remain_consumed": True,
            "old_grant_reuse_prohibited": True,
            "replacement_frozen_frame_sha256": frame_hash,
        },
    )
    seal(
        args.evidence_output,
        {
            "schema_version": "m67-replacement-100-company-ingestion-evidence-v1",
            "state": "REPLACEMENT_100_COMPANY_FRAME_FROZEN_AND_ORDERED",
            "input_artifact_sha256": EXPECTED_INPUT_SHA256,
            "owner_attestation_sha256": attestation_hash,
            "frozen_frame_count": 100,
            "frozen_frame_sha256": frame_hash,
            "seed_evidence_sha256": sha256_bytes(canonical_bytes(seed_evidence)),
            "ordered_package_sha256": package["package_sha256"],
            "slot_count": 24,
            "frame_remainder_count": 76,
            "a09_stub_count": 24,
            "network_operations": 0,
            "m1_m5_operations": 0,
            "person_contact_operations": 0,
            "outreach_delivery_operations": 0,
            "replacements": 0,
            "permissions": PERMISSIONS,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("preflight")
    check.add_argument("--input", type=Path, required=True)
    check.add_argument("--report", type=Path, required=True)
    run = sub.add_parser("execute")
    for name in (
        "authorization",
        "input",
        "input_copy",
        "attestation_output",
        "normalized_frame_output",
        "private_seed_output",
        "ordered_package_output",
        "evidence_output",
        "supersession_output",
        "normalized_frame_schema",
    ):
        run.add_argument(f"--{name.replace('_', '-')}", dest=name, type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "preflight":
        preflight(args.input, args.report)
    else:
        execute(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
