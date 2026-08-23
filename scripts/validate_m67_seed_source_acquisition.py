"""Validate the M6.7 offline seed source-acquisition authorization gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
DEPLOY = ROOT / "docs" / "readiness" / "m6.7-deployment"
READY = AUTH / "seed-source-acquisition-authorization-ready-2026-08-23.json"
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


def canonical_hash(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "configuration_hash"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate() -> list[str]:
    value = cast(dict[str, Any], json.loads(READY.read_text(encoding="utf-8")))
    errors: list[str] = []
    if value.get("state") != "READY_FOR_SEED_SOURCE_ACQUISITION_AUTHORIZATION":
        errors.append("incorrect readiness state")
    if value.get("configuration_hash") != canonical_hash(value):
        errors.append("configuration hash mismatch")
    source_set = cast(list[dict[str, Any]], value.get("source_set", []))
    if len(source_set) != 1 or source_set[0].get("network_hosts") != []:
        errors.append("source set is not one exact offline class")
    limits = cast(dict[str, int], value.get("limits", {}))
    for name in (
        "external_requests",
        "dns_queries",
        "http_attempts",
        "retries",
        "ai_calls",
        "browser_sessions",
        "monetary_cost_usd",
    ):
        if limits.get(name) != 0:
            errors.append(f"{name} must remain zero")
    if limits.get("input_artifacts") != 1 or limits.get("input_bytes") != 5_000_000:
        errors.append("input count/byte bound mismatch")
    permissions = cast(dict[str, str], value.get("permissions_before_during_after", {}))
    if set(permissions) != EXPECTED_PERMISSIONS or set(permissions.values()) != {"NOT_AUTHORIZED"}:
        errors.append("successor permission changed")
    bindings = cast(dict[str, str], value["bindings"])
    files = {
        "blocker_record_sha256": AUTH / "seed-input-artifact-blocker-2026-08-23.json",
        "seed_construction_grant_sha256": AUTH
        / "seed-construction-owner-approval-accepted-2026-08-23.json",
        "accepted_environment_record_sha256": DEPLOY
        / "consolidated-environment-acceptance-accepted-2026-08-23.json",
        "a08_live_effectiveness_sha256": DEPLOY
        / "a08-retention-live-effectiveness-ready-2026-08-22.json",
        "adr0071_sha256": DEPLOY / "adr-0071-acceptance-ready-2026-08-22.json",
        "a17_attorney_result_sha256": AUTH / "a17-attorney-result-2026-08-21.json",
        "source_policy_document_sha256": AUTH / "seed-source-acquisition-policy-2026-08-23.md",
        "source_instance_attestation_template_sha256": AUTH
        / "offline-seed-source-instance-attestation.template.json",
        "output_schema_sha256": AUTH / "phase1-seed-construction-input-v1.schema.json",
        "output_attestation_template_sha256": AUTH
        / "seed-construction-input-attestation.template.json",
    }
    for field, path in files.items():
        if bindings.get(field) != sha256(path):
            errors.append(f"binding mismatch: {field}")
    if value.get("live_source_operations_performed") != 0:
        errors.append("live source operation reported during design")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        return 1
    print("M6.7 offline seed source-acquisition authorization validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
