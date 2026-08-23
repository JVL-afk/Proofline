"""Validate the fail-closed M6.7 PRIMARY_A authentication preparation package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
DEPLOY = ROOT / "docs" / "readiness" / "m6.7-deployment"
PACKAGE = AUTH / "primary-a-authentication-package-2026-08-23.json"
MANIFEST = AUTH / "primary-a-authentication-preparation-manifest-2026-08-23.json"
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


def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate() -> list[str]:
    package = load(PACKAGE)
    manifest = load(MANIFEST)
    statements = load(AUTH / "primary-a-owner-statements-2026-08-23.json")
    schema = load(AUTH / "primary-a-authentication-evidence-v1.schema.json")
    template = load(AUTH / "primary-a-authentication-evidence.template.json")
    predecessor = load(AUTH / "primary-a-independent-authentication-step-2026-08-23.json")
    role_gate = load(AUTH / "primary-a-live-discovery-role-gate-2026-08-23.json")
    challenge = load(AUTH / "primary-a-independent-authentication-challenge.template.json")
    assignments = load(AUTH / "role-assignments.predeployment.json")
    environment = load(DEPLOY / "consolidated-environment-acceptance-accepted-2026-08-23.json")
    errors: list[str] = []
    if package.get("state") != "BLOCKED_PENDING_PRIMARY_A_AUTHENTICATION_ONLY_IDP_ASSIGNMENT":
        errors.append("incorrect readiness state")
    if predecessor.get("state") != "PENDING_INDEPENDENT_AUTHENTICATION":
        errors.append("authoritative authentication state changed")
    if role_gate.get("state") != "REQUIRED_PENDING_INDEPENDENT_AUTHENTICATION":
        errors.append("authoritative live discovery role state changed")
    if challenge.get("state") != "NOT_ISSUED":
        errors.append("challenge was issued")
    if environment.get("state") != "ACCEPTED_FROZEN":
        errors.append("environment acceptance not frozen")
    primary = [
        item
        for item in cast(list[dict[str, Any]], assignments["assignments"])
        if item.get("role") == "INDEPENDENT_SECOND_REVIEWER"
    ]
    if len(primary) != 1 or primary[0].get("approved_actor_binding") != "PRIMARY_A_ACTOR":
        errors.append("PRIMARY_A role assignment mismatch")
    permissions = cast(dict[str, str], package.get("permissions", {}))
    if set(permissions) != EXPECTED_PERMISSIONS or set(permissions.values()) != {"NOT_AUTHORIZED"}:
        errors.append("successor permission changed")
    if package.get("live_authentication_performed") is not False:
        errors.append("package claims a live authentication")
    if package.get("challenge_issued") is not False:
        errors.append("package claims a challenge was issued")
    if package.get("permissions_changed") is not False:
        errors.append("package claims a permission change")
    for artifact in cast(list[dict[str, str]], manifest.get("artifacts", [])):
        path = ROOT / artifact["path"]
        if sha256(path) != artifact["sha256"]:
            errors.append(f"manifest artifact hash mismatch: {artifact['path']}")
    if manifest.get("challenge_issued") is not False:
        errors.append("manifest claims a challenge was issued")
    if manifest.get("live_authentication_performed") is not False:
        errors.append("manifest claims a live authentication")
    if statements.get("state") != "BLOCKED_PENDING_AUTHENTICATION_ONLY_IDP_ASSIGNMENT":
        errors.append("owner statement package bypasses IdP prerequisite")
    if statements.get("already_approved_not_repeated", {}).get("actor_designation") != (
        "PRIMARY_A_ACTOR"
    ):
        errors.append("approved actor designation was not preserved")
    required_schema_fields = set(cast(list[str], schema.get("required", [])))
    if required_schema_fields != set(template):
        errors.append("evidence template and schema fields differ")
    if template.get("permissions_granted") != []:
        errors.append("evidence template grants permissions")
    form = (AUTH / "primary-a-independent-authentication-form-2026-08-23.md").read_text(
        encoding="utf-8"
    )
    for forbidden in ("access token:", "password:", "session cookie:", "recovery code:"):
        if forbidden in form.lower():
            errors.append(f"form solicits sensitive field: {forbidden}")
    if "I, the human independently authenticating as PRIMARY_A_ACTOR" not in form:
        errors.append("PRIMARY_A affirmation missing")
    expected_hashes = {
        "authentication_step": (
            AUTH / "primary-a-independent-authentication-step-2026-08-23.json",
            "ae24e1106c61dd2853a8b3fb88c34963123549b56dd4a79f633f46d90630e8db",
        ),
        "role_gate": (
            AUTH / "primary-a-live-discovery-role-gate-2026-08-23.json",
            "efdca50dccd995c293cb19d5c4b670b21198754ddddbcae574e95f916830ec7f",
        ),
        "challenge_template": (
            AUTH / "primary-a-independent-authentication-challenge.template.json",
            "699e4880b3f80a68b80f6e272df46f23acb79e7b2428c0049d4c14a8102b4b42",
        ),
        "assignments": (
            AUTH / "role-assignments.predeployment.json",
            "bcb8b9aaaa3b7bf692e32e0df9e417991cb336d7b2d6acfa67261a3e22cb3292",
        ),
        "environment": (
            DEPLOY / "consolidated-environment-acceptance-accepted-2026-08-23.json",
            "713062b65cdb340e8d552f6562cdd22431c2aee057bb3baa8a74411c06648103",
        ),
    }
    for name, (path, expected) in expected_hashes.items():
        if sha256(path) != expected:
            errors.append(f"authoritative predecessor changed: {name}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        return 1
    print("M6.7 PRIMARY_A authentication package remains correctly fail closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
