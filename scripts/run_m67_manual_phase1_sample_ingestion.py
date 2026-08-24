"""Ingest, freeze, and order exactly 24 owner-curated business-only records offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT = "AUTHORIZE_MANUAL_PHASE1_SAMPLE_INGESTION"
ACCOUNT = "785072247535"
REGION = "us-east-2"
ROOT = Path(__file__).resolve().parents[1]
AUTH_DIR = ROOT / "docs" / "readiness" / "m6.7-authorization"
BOUND_PATHS = {
    "input": ROOT / "local-data" / "m6.7" / "manual-phase1-sample" / "input" / "manual-phase1-sample.json",
    "attestation": ROOT / "local-data" / "m6.7" / "manual-phase1-sample" / "input" / "manual-phase1-sample-owner-attestation.json",
    "input_schema": AUTH_DIR / "manual-phase1-sample-input-v1.schema.json",
    "attestation_schema": AUTH_DIR / "manual-phase1-sample-owner-attestation-v1.schema.json",
    "output": ROOT / "local-data" / "m6.7" / "manual-phase1-sample" / "output" / "manual-phase1-ordered-sample.json",
    "private_seed_output": ROOT / "local-data" / "m6.7" / "manual-phase1-sample" / "private" / "ordering-seed.json",
    "evidence": AUTH_DIR / "manual-phase1-sample-ingestion-evidence-2026-08-24.json",
}
SAMPLE_SOURCE = "OWNER_CURATED_TDLR_NON_CHERRY_PICKED"
ORDERING_VERSION = "m6.7.manual-phase1-sample-order@1"
EXPECTED_INDICES = list(range(1, 25))
MAX_INPUT_BYTES = 100_000
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!.*\.\.)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$"
)
LICENSE_RE = re.compile(r"^[A-Za-z0-9._/-]{1,64}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)"
)
INPUT_KEYS = {
    "record_type",
    "schema_version",
    "sample_source",
    "automated_tdlr_discovery_validated",
    "candidates",
}
CANDIDATE_KEYS = {
    "submission_index",
    "public_business_name",
    "texas_city_or_service_area",
    "tdlr_reference",
    "candidate_hostname",
}
TDLR_KEYS = {"dataset_id", "license_number", "source_record_locator"}
ATTESTATION_KEYS = {
    "record_type",
    "schema_version",
    "state",
    "actor_ref",
    "input_artifact_sha256",
    "candidate_count",
    "selected_before_m1_m5",
    "selection_not_based_on_perceived_opportunity",
    "selection_not_based_on_website_weakness",
    "selection_not_based_on_sales_attractiveness",
    "selection_not_based_on_expected_result",
    "business_only_confirmed",
    "person_contact_data_absent",
    "no_outcome_based_exclusion_or_replacement",
    "candidate_hostnames_manually_identified",
    "automated_tdlr_discovery_validated",
    "phase1_sample_source",
    "attested_at",
    "exact_affirmation",
}
AFFIRMATION = (
    "I attest that I selected exactly 24 Texas Commercial HVAC businesses before any "
    "M1-M5 evaluation; I did not select them based on perceived opportunity, website "
    "weakness, sales attractiveness, expected result, or contactability; the submitted "
    "artifact contains business-only fields and manually identified candidate hostnames; "
    "and no later outcome may cause a submitted business or slot to be replaced."
)
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
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def seal(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def require_plain_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationFailure(f"{name}_INVALID")
    normalized = " ".join(value.split())
    if EMAIL_RE.search(normalized) or PHONE_RE.search(normalized):
        raise ValidationFailure(f"{name}_CONTACT_SHAPED")
    return normalized


def validate_input(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != INPUT_KEYS:
        raise ValidationFailure("INPUT_OBJECT_SCHEMA_MISMATCH")
    if (
        value["record_type"] != "M67_MANUAL_PHASE1_SAMPLE_INPUT"
        or value["schema_version"] != "1.0.0"
        or value["sample_source"] != SAMPLE_SOURCE
        or value["automated_tdlr_discovery_validated"] is not False
    ):
        raise ValidationFailure("INPUT_CONTROL_FIELDS_MISMATCH")
    rows = value["candidates"]
    if not isinstance(rows, list) or len(rows) != 24:
        raise ValidationFailure("CANDIDATE_COUNT_NOT_EXACTLY_24")
    prepared: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != CANDIDATE_KEYS:
            raise ValidationFailure("CANDIDATE_SCHEMA_MISMATCH")
        index = row["submission_index"]
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValidationFailure("SUBMISSION_INDEX_INVALID")
        name = require_plain_text(row["public_business_name"], "BUSINESS_NAME", 200)
        area = require_plain_text(row["texas_city_or_service_area"], "TEXAS_AREA", 120)
        hostname = row["candidate_hostname"]
        if not isinstance(hostname, str) or not HOST_RE.fullmatch(hostname):
            raise ValidationFailure("CANDIDATE_HOSTNAME_SYNTAX_INVALID")
        tdlr = row["tdlr_reference"]
        if tdlr is not None:
            if not isinstance(tdlr, dict) or set(tdlr) != TDLR_KEYS:
                raise ValidationFailure("TDLR_REFERENCE_SCHEMA_MISMATCH")
            if tdlr["dataset_id"] != "7358-krk7":
                raise ValidationFailure("TDLR_DATASET_ID_MISMATCH")
            if not isinstance(tdlr["license_number"], str) or not LICENSE_RE.fullmatch(
                tdlr["license_number"]
            ):
                raise ValidationFailure("TDLR_LICENSE_NUMBER_INVALID")
            locator = require_plain_text(tdlr["source_record_locator"], "TDLR_LOCATOR", 512)
            tdlr = {**tdlr, "source_record_locator": locator}
        prepared.append(
            {
                "submission_index": index,
                "public_business_name": name,
                "texas_city_or_service_area": area,
                "tdlr_reference": tdlr,
                "candidate_hostname": hostname,
            }
        )
    if [row["submission_index"] for row in prepared] != EXPECTED_INDICES:
        raise ValidationFailure("SUBMISSION_INDICES_MUST_BE_1_THROUGH_24_IN_ORDER")
    return prepared


def validate_attestation(value: object, input_sha256: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ATTESTATION_KEYS:
        raise ValidationFailure("ATTESTATION_SCHEMA_MISMATCH")
    exact_values = {
        "record_type": "M67_MANUAL_PHASE1_SAMPLE_OWNER_ATTESTATION",
        "schema_version": "1.0.0",
        "state": "SIGNED",
        "actor_ref": "OWNER_ACTOR",
        "input_artifact_sha256": input_sha256,
        "candidate_count": 24,
        "selected_before_m1_m5": True,
        "selection_not_based_on_perceived_opportunity": True,
        "selection_not_based_on_website_weakness": True,
        "selection_not_based_on_sales_attractiveness": True,
        "selection_not_based_on_expected_result": True,
        "business_only_confirmed": True,
        "person_contact_data_absent": True,
        "no_outcome_based_exclusion_or_replacement": True,
        "candidate_hostnames_manually_identified": True,
        "automated_tdlr_discovery_validated": False,
        "phase1_sample_source": SAMPLE_SOURCE,
        "exact_affirmation": AFFIRMATION,
    }
    for key, expected in exact_values.items():
        if value.get(key) != expected:
            raise ValidationFailure(f"ATTESTATION_{key.upper()}_MISMATCH")
    try:
        datetime.fromisoformat(str(value["attested_at"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationFailure("ATTESTATION_TIMESTAMP_INVALID") from error
    return dict(value)


def build_package(
    candidates: list[dict[str, Any]],
    *,
    input_sha256: str,
    attestation_sha256: str,
    created_at: str,
    seed: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(seed) != 32:
        raise ValidationFailure("CSPRNG_SEED_LENGTH_INVALID")
    frozen_candidates: list[dict[str, Any]] = []
    for row in candidates:
        candidate_ref = "manual-candidate-" + digest_bytes(canonical_bytes(row))
        frozen_candidates.append({**row, "candidate_ref": candidate_ref})
    frame_hash = digest_bytes(canonical_bytes({
        "sample_source": SAMPLE_SOURCE,
        "automated_tdlr_discovery_validated": False,
        "candidates": frozen_candidates,
    }))
    ranked: list[tuple[str, dict[str, Any]]] = []
    for row in frozen_candidates:
        ordering_key = hashlib.sha256(
            b"\0".join((ORDERING_VERSION.encode(), seed, frame_hash.encode(), row["candidate_ref"].encode()))
        ).hexdigest()
        ranked.append((ordering_key, row))
    ranked.sort(key=lambda item: (item[0], item[1]["candidate_ref"]))
    slots = [{**row, "slot": index} for index, (_, row) in enumerate(ranked, start=1)]
    seed_commitment = digest_bytes(seed)
    seed_evidence_sha256 = digest_bytes(canonical_bytes({
        "ordering_version": ORDERING_VERSION,
        "frozen_frame_sha256": frame_hash,
        "seed_commitment": seed_commitment,
        "seed_generated_after_frame_freeze": True,
    }))
    package: dict[str, Any] = {
        "record_type": "M67_MANUAL_PHASE1_ORDERED_SAMPLE",
        "schema_version": "1.0.0",
        "state": "FROZEN_AWAITING_EXACT_HOST_A09_AND_PUBLIC_RESEARCH_AUTHORIZATION",
        "account": ACCOUNT,
        "region": REGION,
        "created_at": created_at,
        "created_by_actor_ref": "OWNER_ACTOR",
        "AUTOMATED_TDLR_DISCOVERY_VALIDATED": False,
        "PHASE1_SAMPLE_SOURCE": SAMPLE_SOURCE,
        "automated_tdlr_defect_state": "OPEN_SEPARATE_ENGINEERING_WORKSTREAM",
        "input_artifact_sha256": input_sha256,
        "owner_attestation_sha256": attestation_sha256,
        "candidate_count": 24,
        "frozen_frame_sha256": frame_hash,
        "frame_frozen_before_seed_generation": True,
        "ordering_version": ORDERING_VERSION,
        "seed_commitment": seed_commitment,
        "seed_evidence_sha256": seed_evidence_sha256,
        "slots": slots,
        "reserve": [],
        "outcome_based_replacement_prohibited": True,
        "host_reviews": [
            {
                "slot": row["slot"],
                "exact_host": row["candidate_hostname"],
                "a09_state": "NOT_REVIEWED_NOT_AUTHORIZED",
                "first_party_network_access": "NOT_PERFORMED",
            }
            for row in slots
        ],
        "permissions": PERMISSIONS,
        "next_state": "READY_FOR_ORDERED_MANUAL_SAMPLE_AND_EXACT_HOST_REVIEW_AUTHORIZATION",
        "package_sha256": None,
    }
    package["package_sha256"] = digest_bytes(canonical_bytes({
        key: value for key, value in package.items() if key != "package_sha256"
    }))
    evidence = {
        "record_type": "M67_MANUAL_PHASE1_SAMPLE_INGESTION_EVIDENCE",
        "state": "MANUAL_PHASE1_SAMPLE_INGESTION_COMPLETE",
        "created_at": created_at,
        "input_sha256_computed_before_parse": input_sha256,
        "attestation_sha256": attestation_sha256,
        "candidate_count": 24,
        "frozen_frame_sha256": frame_hash,
        "seed_generated_after_frame_freeze": True,
        "seed_evidence_sha256": seed_evidence_sha256,
        "ordered_package_sha256": package["package_sha256"],
        "AUTOMATED_TDLR_DISCOVERY_VALIDATED": False,
        "PHASE1_SAMPLE_SOURCE": SAMPLE_SOURCE,
        "network_operations": 0,
        "m1_m5_operations": 0,
        "person_contact_records": 0,
        "outcome_based_exclusions_or_replacements": 0,
        "permissions": PERMISSIONS,
    }
    return package, evidence


def run(args: argparse.Namespace) -> None:
    for name, expected in BOUND_PATHS.items():
        if getattr(args, name).resolve() != expected.resolve():
            raise RuntimeError(f"path binding mismatch: {name}")
    for path in (args.output, args.private_seed_output, args.evidence):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite immutable output: {path}")
    authorization = json.loads(args.authorization.read_text(encoding="utf-8"))
    if authorization.get("state") != "APPROVED" or authorization.get("event") != EVENT:
        raise RuntimeError("exact manual-sample authorization is absent")
    if authorization.get("account") != ACCOUNT or authorization.get("region") != REGION:
        raise RuntimeError("manual-sample account or region binding mismatch")
    now = datetime.now(UTC)
    valid_from = datetime.fromisoformat(str(authorization["valid_from"]).replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(str(authorization["expires_at"]).replace("Z", "+00:00"))
    if not valid_from <= now <= expires_at:
        raise RuntimeError("manual-sample authorization window is not active")
    if authorization.get("exact_executable_sha256") != digest_file(Path(__file__)):
        raise RuntimeError("manual-sample executable hash mismatch")
    if authorization.get("input_schema_sha256") != digest_file(args.input_schema):
        raise RuntimeError("input schema hash mismatch")
    if authorization.get("attestation_schema_sha256") != digest_file(args.attestation_schema):
        raise RuntimeError("attestation schema hash mismatch")
    raw = args.input.read_bytes()
    input_sha256 = digest_bytes(raw)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValidationFailure("INPUT_BYTE_CEILING_EXCEEDED")
    attestation_raw = args.attestation.read_bytes()
    try:
        parsed = json.loads(raw)
        attestation_parsed = json.loads(attestation_raw)
        candidates = validate_input(parsed)
        validate_attestation(attestation_parsed, input_sha256)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationFailure) as error:
        seal(args.evidence, {
            "record_type": "M67_MANUAL_PHASE1_SAMPLE_INGESTION_EVIDENCE",
            "state": "MANUAL_PHASE1_SAMPLE_INGESTION_FAILED_CLOSED",
            "input_sha256_computed_before_parse": input_sha256,
            "safe_failure_code": str(error) if isinstance(error, ValidationFailure) else type(error).__name__,
            "seed_generated": False,
            "network_operations": 0,
            "m1_m5_operations": 0,
            "permissions": PERMISSIONS,
        })
        raise
    frame_probe = [{**row, "candidate_ref": "manual-candidate-" + digest_bytes(canonical_bytes(row))} for row in candidates]
    frame_probe_hash = digest_bytes(canonical_bytes({
        "sample_source": SAMPLE_SOURCE,
        "automated_tdlr_discovery_validated": False,
        "candidates": frame_probe,
    }))
    seed = secrets.token_bytes(32)
    package, evidence = build_package(
        candidates,
        input_sha256=input_sha256,
        attestation_sha256=digest_bytes(attestation_raw),
        created_at=now.isoformat().replace("+00:00", "Z"),
        seed=seed,
    )
    if package["frozen_frame_sha256"] != frame_probe_hash:
        raise RuntimeError("frame changed after freeze and before seed use")
    seal(args.private_seed_output, {"seed_hex": seed.hex(), "seed_commitment": digest_bytes(seed)})
    seal(args.output, package)
    seal(args.evidence, evidence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--input-schema", type=Path, required=True)
    parser.add_argument("--attestation-schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-seed-output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
