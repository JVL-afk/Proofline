"""Validate the fail-closed M6.7 live seed-roster source review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
BLOCKER = AUTH / "live-seed-roster-source-review-blocker-2026-08-23.json"
ROLE = AUTH / "primary-a-live-discovery-role-gate-2026-08-23.json"
PACKAGE = AUTH / "live-seed-roster-source-review-package-2026-08-23.json"
EXPECTED_PERMISSIONS = {
    "REAL_BUSINESS_DISCOVERY",
    "REAL_PUBLIC_RESEARCH",
    "PROFESSIONAL_IDENTITY_RESOLUTION",
    "REAL_CONTACT_STORAGE",
    "CONTACT_VERIFICATION",
    "SHADOW_ELIGIBILITY_EVALUATION",
    "SHADOW_READY_ASSESSMENT",
}


def validate() -> list[str]:
    value = cast(dict[str, Any], json.loads(BLOCKER.read_text(encoding="utf-8")))
    role = cast(dict[str, Any], json.loads(ROLE.read_text(encoding="utf-8")))
    package = cast(dict[str, Any], json.loads(PACKAGE.read_text(encoding="utf-8")))
    errors: list[str] = []
    expected_state = (
        "BLOCKED_PENDING_TDLR_EXACT_SOURCE_REVIEW_"
        "HOST_LOCATOR_SOURCE_REVIEW_AND_PRIMARY_A_AUTHENTICATION"
    )
    if value.get("state") != expected_state:
        errors.append("incorrect blocker state")
    if value.get("live_source_operations_performed") != 0:
        errors.append("live source access occurred during design")
    if value.get("owner_approval_statement") is not None:
        errors.append("approval statement emitted despite source blocker")
    sources = cast(list[dict[str, Any]], value.get("source_candidates", []))
    if len(sources) != 4:
        errors.append("source analysis must enumerate four bounded source roles")
    if any(source.get("a09_state") in {"APPROVED", "AUTHORIZED"} for source in sources):
        errors.append("a source was approved without exact review")
    fields = cast(dict[str, str], value.get("tdlr_field_support", {}))
    if fields.get("business_entity_vs_natural_person_discriminator") != (
        "NOT_VERIFIED_CRITICAL_PRIVACY_BLOCKER"
    ):
        errors.append("natural-person discriminator is not fail closed")
    for unsupported in (
        "organization_grouping_or_franchise_hint",
        "first_party_host_candidate",
        "b2b_evidence",
    ):
        if not fields.get(unsupported, "").startswith("NOT_SUPPORTED"):
            errors.append(f"unsupported TDLR field inferred: {unsupported}")
    permissions = cast(dict[str, str], value.get("permissions", {}))
    if set(permissions) != EXPECTED_PERMISSIONS or set(permissions.values()) != {"NOT_AUTHORIZED"}:
        errors.append("successor permission changed")
    grants = cast(dict[str, str], value.get("unconsumed_grants", {}))
    if set(grants.values()) != {"0/1"}:
        errors.append("an existing one-shot grant was consumed")
    gate = cast(dict[str, Any], value.get("role_and_permission_gate", {}))
    if gate.get("operation_semantics") != "REAL_BUSINESS_DISCOVERY":
        errors.append("live acquisition permission semantics weakened")
    if gate.get("primary_a_required_before_live_acquisition_authorization") is not True:
        errors.append("PRIMARY_A gate omitted")
    if role.get("state") != "REQUIRED_PENDING_INDEPENDENT_AUTHENTICATION":
        errors.append("PRIMARY_A state is not pending")
    if role.get("owner_actor_substitution_prohibited") is not True:
        errors.append("OWNER_ACTOR substitution not prohibited")
    if role.get("permissions_granted") != []:
        errors.append("role gate granted a permission")
    for artifact in cast(list[dict[str, str]], package.get("artifacts", [])):
        path = ROOT / artifact["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            errors.append(f"package artifact hash mismatch: {artifact['path']}")
    if package.get("approval_statement_emitted") is not False:
        errors.append("package claims an approval statement")
    if package.get("permissions_changed") is not False:
        errors.append("package claims a permission change")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        return 1
    print("M6.7 live seed source readiness remains correctly fail closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
