from __future__ import annotations

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = runpy.run_path(str(ROOT / "scripts/validate_m67_authorization_package.py"))
AuthorizationPackageError = cast(type[ValueError], VALIDATOR["AuthorizationPackageError"])
validate_package = cast(Callable[[], dict[str, Any]], VALIDATOR["validate_package"])
validate_seed_manifest = cast(Callable[..., None], VALIDATOR["validate_seed_manifest"])
deployed_environment_blockers = cast(
    Callable[[dict[str, Any]], tuple[str, ...]], VALIDATOR["deployed_environment_blockers"]
)


def test_owner_package_is_exact_and_discovery_remains_not_ready() -> None:
    report = validate_package()
    assert report["state"] == "NOT_READY_TO_AUTHORIZE_DISCOVERY"
    assert report["real_business_discovery"] == "NOT_AUTHORIZED"
    assert report["real_public_research"] == "NOT_AUTHORIZED"
    assert report["real_businesses_accessed"] == 0
    assert report["real_people_or_contacts_processed"] == 0
    assert report["external_communications"] == 0


def test_exact_human_environment_and_policy_blockers_are_visible() -> None:
    blockers = set(validate_package()["blockers"])
    assert "ROLE_SUBJECT_REQUIRED:PROJECT_OWNER" in blockers
    assert "ROLE_SUBJECT_REQUIRED:INDEPENDENT_SECOND_REVIEWER" in blockers
    assert "ROLE_SUBJECT_REQUIRED:QUALIFIED_LEGAL_REVIEWER" in blockers
    assert "ACTUAL_ENVIRONMENT_NOT_DEPLOYED_OR_ATTESTED" in blockers
    assert "A08_FINAL_RETENTION_APPROVAL_REQUIRED" not in blockers
    assert "A09_EXACT_DISCOVERY_SOURCE_APPROVAL_REQUIRED" in blockers
    assert "A17_QUALIFIED_LEGAL_APPROVAL_REQUIRED" not in blockers
    assert "ADR_0071_ACCEPTANCE_REQUIRED" in blockers
    assert "OWNER_DISCOVERY_RELEASE_SIGNATURE_REQUIRED" in blockers


def test_seed_template_contains_no_real_business_or_person_contact_data() -> None:
    path = ROOT / "docs/readiness/m6.7-authorization/phase1-owner-seed-manifest-v1.template.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_seed_manifest(value)
    assert value["state"] == "DRAFT"
    assert value["candidate_frame_maximum"] == 100
    assert value["candidates"] == []


def test_seed_schema_rejects_person_contact_and_opportunity_fields() -> None:
    value = {
        "record_type": "PHASE1_OWNER_SEED_MANIFEST_V1",
        "schema_version": "1.0.0",
        "state": "FROZEN",
        "candidate_frame_maximum": 100,
        "candidates": [
            {
                "candidate_ref": "synthetic-business-001",
                "public_business_name": "Synthetic HVAC Fixture",
                "email": "prohibited@fixture.invalid",
                "provenance": [{"source_id": "synthetic-offline-fixture"}],
            }
        ],
    }
    with pytest.raises(AuthorizationPackageError, match="unapproved field"):
        validate_seed_manifest(value, allow_populated=True)


def test_deployment_template_cannot_satisfy_actual_environment_evidence() -> None:
    path = ROOT / "infra/aws/phase1/deployed-environment-evidence.template.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    blockers = deployed_environment_blockers(value)
    assert "ACTUAL_ENVIRONMENT_NOT_DEPLOYED_OR_ATTESTED" in blockers
    assert "ACTUAL_INFRASTRUCTURE_OBSERVATION_REQUIRED" in blockers
    assert "DEPLOYMENT_EVIDENCE_REQUIRED:account_id" in blockers
    assert "DEPLOYMENT_EVIDENCE_REQUIRED:configuration_hash" in blockers


def test_provisioning_spec_still_records_no_deployment_or_credentials() -> None:
    phase1 = ROOT / "infra/aws/phase1"
    files = {path.name for path in phase1.iterdir() if path.is_file()}
    assert files == {
        "README.md",
        "deployed-environment-evidence.template.json",
        "provisioning-spec.json",
    }
    specification = json.loads((phase1 / "provisioning-spec.json").read_text(encoding="utf-8"))
    assert specification["executable_iac_present"]
    assert not specification["deployment_performed"]
    assert specification["forbidden_credentials"] == [
        "AI",
        "BROWSER",
        "M6",
        "SENDER",
        "DELIVERY",
    ]


def test_role_and_legal_templates_do_not_invent_human_decisions() -> None:
    roles = json.loads(
        (ROOT / "docs/readiness/m6.7-authorization/role-assignments.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(item["subject_ref"] is None for item in roles["assignments"])
    assert roles["constraints"]["opportunity_reviewer_must_differ_from_independent_second"]
    assert roles["constraints"]["project_owner_must_differ_from_qualified_legal_reviewer"]

    legal = json.loads(
        (ROOT / "docs/readiness/m6.7-authorization/a17-qualified-review.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert legal["state"] == "BLOCKED_PENDING_QUALIFIED_LEGAL_REVIEW"
    assert legal["reviewer_subject_ref"] is None
    assert len(legal["issues"]) == 14
    assert all(item["conclusion"] is None for item in legal["issues"])


def test_discovery_signature_template_is_unsigned_and_cannot_collapse_authorities() -> None:
    value = json.loads(
        (ROOT / "docs/readiness/m6.7-authorization/discovery-signature.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["state"] == "UNSIGNED_NOT_AUTHORIZED"
    assert value["only_effect_if_validly_signed"] == "REAL_BUSINESS_DISCOVERY_AUTHORIZED"
    assert not value["research_authorized"]
    assert not value["slot_1_authorized"]
    assert not value["person_contact_authorized"]
    assert value["owner_signature"] is None


def test_terraform_package_is_pinned_zero_worker_and_secret_minimized() -> None:
    root = ROOT / "infra/terraform/phase1"
    versions = (root / "versions.tf").read_text(encoding="utf-8")
    variables = (root / "variables.tf").read_text(encoding="utf-8")
    database = (root / "database.tf").read_text(encoding="utf-8")
    assert 'required_version = ">= 1.15.9, < 1.16.0"' in versions
    assert 'version = "= 6.53.0"' in versions
    assert 'default     = "us-east-2"' in variables
    assert 'variable "worker_desired_count"' in variables
    assert "manage_master_user_password         = true" in database
    lock = (root / ".terraform.lock.hcl").read_text(encoding="utf-8")
    assert 'version     = "6.53.0"' in lock
    assert lock.count("h1:") >= 2

    blockers = set(validate_package()["blockers"])
    assert "TERRAFORM_PROVIDER_LOCK_REQUIRED" not in blockers
    assert "AWS_CHARGE_AUTHORIZATION_REQUIRED" in blockers
    assert "AWS_AUTHENTICATED_PLAN_APPLY_AUTHORITY_REQUIRED" in blockers
