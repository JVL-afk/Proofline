"""Generate the immutable M6.7 owner decision and pseudonymous actor bindings.

The public record contains random opaque references and a commitment to the reconciliation salt.
The salt itself is written only beneath ignored local-data and must later move to the approved
secrets system before OIDC reconciliation. No human name, email, credential, or OIDC subject is
accepted by this generator.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RECORD = (
    ROOT / "docs/readiness/m6.7-authorization/consolidated-owner-approval-2026-08-21.json"
)
PRIVATE_RECORD = ROOT / "local-data/m67-identity/reconciliation-secret.json"

OWNER_ROLES = (
    "PROJECT_OWNER",
    "OPPORTUNITY_REVIEWER",
    "INCIDENT_OWNER",
    "PRIVACY_DATA_OWNER",
    "KILL_SWITCH_OPERATOR",
    "SECURITY_ENVIRONMENT_OWNER",
)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_records(created_at: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    salt = secrets.token_bytes(32)
    actors = {
        alias: f"m67-subject-{secrets.token_hex(32)}"
        for alias in ("OWNER_ACTOR", "PRIMARY_A_ACTOR", "EXTERNAL_ATTORNEY_A17_ACTOR")
    }
    private_record = {
        "record_type": "M67_PREDEPLOYMENT_RECONCILIATION_SECRET",
        "version": "1.0.0",
        "created_at": created_at.isoformat(),
        "salt_base64": base64.b64encode(salt).decode(),
        "purpose": "Later OIDC issuer/sub reconciliation only",
        "repository_storage_prohibited": True,
    }
    decisions = {
        "jurisdiction": "US-TX",
        "vertical": "COMMERCIAL_HVAC",
        "context": "B2B",
        "opportunity": "INBOUND_LEAD_RESPONSE",
        "candidate_frame_maximum": 100,
        "frozen_cohort_target": 24,
        "aws_region": "us-east-2",
        "terraform_authority": "PRODUCTION_AND_DEPLOYMENT_SUBJECT_TO_REVIEWED_PLANS",
        "monetary_hard_ceiling_usd": "250.00",
        "ai_budget_usd": "0.00",
        "worker_concurrency": 1,
        "browser": "DISABLED",
        "person_contact_processing": "NOT_AUTHORIZED",
        "delivery": "UNAVAILABLE",
        "outcome_based_cohort_replacement": "PROHIBITED",
        "negative_qa_rate_basis_points": 2500,
        "negative_qa_minimum": 3,
        "execution_sequence": ["SLOT_1", "PAUSE", "SLOTS_2_TO_6", "PAUSE", "SLOTS_7_TO_24"],
        "operator_session_maximum_seconds": 14_400,
        "access_review_interval_days": 90,
        "backup_rpo_seconds": 86_400,
        "backup_rto_seconds": 86_400,
        "discovery_release_validity_seconds": 604_800,
    }
    public_record: dict[str, Any] = {
        "record_type": "M67_CONSOLIDATED_OWNER_APPROVAL",
        "version": "1.0.0",
        "state": "OWNER_APPROVED_RECORDED",
        "created_at": created_at.isoformat(),
        "approval_origin": "PROJECT_OWNER_CURRENT_SESSION_ATTESTATION",
        "classification": {
            "owner_decisions": list(decisions),
            "external_facts": ["AWS_ACCOUNT", "AWS_ORGANIZATION_IF_ANY", "AWS_SSO_ENTRY_POINT"],
            "system_derived_values": [
                "RESOURCE_NAMES",
                "ROLE_ARNS",
                "IMAGE_DIGEST",
                "PLAN_AND_CONFIGURATION_HASHES",
                "SEED_AND_MANIFEST_HASHES",
                "RELEASE_START_AND_EXPIRY_FROM_SIGNATURE_TIME",
            ],
            "post_deployment_evidence": [
                "AWS_RESOURCE_IDENTIFIERS",
                "CONTROL_PLANE_ATTESTATIONS",
                "BACKUP_AND_RESTORE_EVIDENCE",
                "KILL_SWITCH_EVIDENCE",
            ],
        },
        "decisions": decisions,
        "actors": {
            "OWNER_ACTOR": {
                "subject_ref": actors["OWNER_ACTOR"],
                "roles": list(OWNER_ROLES),
            },
            "PRIMARY_A_ACTOR": {
                "subject_ref": actors["PRIMARY_A_ACTOR"],
                "roles": ["INDEPENDENT_SECOND_REVIEWER"],
            },
            "EXTERNAL_ATTORNEY_A17_ACTOR": {
                "subject_ref": actors["EXTERNAL_ATTORNEY_A17_ACTOR"],
                "roles": ["QUALIFIED_LEGAL_REVIEWER"],
                "scope": "COMPLETED_A17_REVIEW_ONLY",
            },
        },
        "binding": {
            "scheme": "RANDOM_256_BIT_PREDEPLOYMENT_PSEUDONYM_V1",
            "state": "APPROVED_PENDING_OIDC_RECONCILIATION",
            "association_evidence": "PROJECT_OWNER_CURRENT_SESSION_ATTESTATION",
            "salt_commitment_sha256": hashlib.sha256(salt).hexdigest(),
            "private_custody_ref": "local-data/m67-identity/reconciliation-secret.json",
            "live_actor_oidc_reconciliation_required_before_discovery": [
                "OWNER_ACTOR",
                "PRIMARY_A_ACTOR",
            ],
            "attorney_record_reconciliation_required": True,
            "underlying_human_identity_fabricated": False,
        },
        "authority": {
            "real_business_discovery": "NOT_AUTHORIZED",
            "real_public_research": "NOT_AUTHORIZED",
            "slot_1": "NOT_AUTHORIZED",
        },
    }
    public_record["configuration_hash"] = canonical_hash(public_record)
    private_record["public_record_hash"] = public_record["configuration_hash"]
    return public_record, private_record


def write_once(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite immutable record: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--created-at", default=None)
    args = parser.parse_args()
    created_at = (
        datetime.fromisoformat(args.created_at).astimezone(UTC)
        if args.created_at
        else datetime.now(UTC)
    )
    if created_at.tzinfo is None:
        raise ValueError("created-at must be timezone aware")
    public_record, private_record = build_records(created_at)
    write_once(PRIVATE_RECORD, private_record)
    write_once(PUBLIC_RECORD, public_record)
    print(
        json.dumps(
            {
                "public_record": str(PUBLIC_RECORD.relative_to(ROOT)),
                "private_custody": str(PRIVATE_RECORD.relative_to(ROOT)),
                "configuration_hash": public_record["configuration_hash"],
                "recommended_release_expires_at": (created_at + timedelta(days=7)).isoformat(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
