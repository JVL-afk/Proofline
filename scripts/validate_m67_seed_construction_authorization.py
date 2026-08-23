"""Validate the offline-only M6.7 seed-construction authorization package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
READY = AUTH / "seed-construction-authorization-ready-2026-08-23.json"
EXPECTED_PERMISSIONS = {
    "REAL_BUSINESS_DISCOVERY",
    "REAL_PUBLIC_RESEARCH",
    "PROFESSIONAL_IDENTITY_RESOLUTION",
    "REAL_CONTACT_STORAGE",
    "CONTACT_VERIFICATION",
    "SHADOW_ELIGIBILITY_EVALUATION",
    "SHADOW_READY_ASSESSMENT",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: dict[str, Any], omitted: str) -> str:
    payload = {key: item for key, item in value.items() if key != omitted}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate() -> list[str]:
    value = cast(dict[str, Any], json.loads(READY.read_text(encoding="utf-8")))
    errors: list[str] = []
    if value.get("state") != "READY_FOR_SEED_CONSTRUCTION_AUTHORIZATION":
        errors.append("readiness state is not exact")
    if value.get("grant_type") != "ONE_SHOT_EXECUTION_GRANT_NOT_A_SUCCESSOR_PERMISSION":
        errors.append("grant is not explicitly below successor-permission authority")
    if value.get("configuration_hash") != canonical_hash(value, "configuration_hash"):
        errors.append("configuration hash mismatch")
    permissions = cast(dict[str, str], value.get("permissions_before_during_after", {}))
    if set(permissions) != EXPECTED_PERMISSIONS or set(permissions.values()) != {"NOT_AUTHORIZED"}:
        errors.append("successor permission boundary changed")
    caps = cast(dict[str, int], value.get("operation_caps", {}))
    for name in (
        "dns_queries",
        "http_requests",
        "browser_sessions",
        "ai_provider_calls",
        "external_communications",
        "person_contact_records",
        "opportunity_scores",
        "aws_infrastructure_mutations",
    ):
        if caps.get(name) != 0:
            errors.append(f"{name} must be zero")
    if caps.get("business_input_artifacts") != 1 or caps.get("candidate_observations") != 100:
        errors.append("offline artifact or candidate cap mismatch")
    bindings = cast(dict[str, str], value["bindings"])
    expected_files = {
        "seed_policy_accepted_record_sha256": AUTH
        / "seed-policy-owner-approval-accepted-2026-08-23.json",
        "generator_sha256": ROOT / "scripts/generate_m67_seed_source_package.py",
        "input_schema_sha256": AUTH / "phase1-seed-construction-input-v1.schema.json",
        "scope_document_sha256": AUTH / "seed-construction-authorization-scope-2026-08-23.md",
        "input_attestation_template_sha256": AUTH
        / "seed-construction-input-attestation.template.json",
        "primary_a_challenge_template_sha256": AUTH
        / "primary-a-independent-authentication-challenge.template.json",
    }
    for field, path in expected_files.items():
        if bindings.get(field) != sha256(path):
            errors.append(f"binding mismatch: {field}")
    if (
        value.get("real_candidates_present") != 0
        or value.get("live_business_operations_performed") != 0
    ):
        errors.append("readiness package contains or reports live data")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1
    print("M6.7 bounded seed-construction authorization validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
