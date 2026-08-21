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
    assert "A08_FINAL_RETENTION_APPROVAL_REQUIRED" in blockers
    assert "A09_EXACT_DISCOVERY_SOURCE_APPROVAL_REQUIRED" in blockers
    assert "A17_QUALIFIED_LEGAL_APPROVAL_REQUIRED" in blockers
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


def test_no_executable_cloud_provisioning_or_credentials_were_added() -> None:
    phase1 = ROOT / "infra/aws/phase1"
    files = {path.name for path in phase1.iterdir() if path.is_file()}
    assert files == {
        "README.md",
        "deployed-environment-evidence.template.json",
        "provisioning-spec.json",
    }
    assert not any(ROOT.rglob("*.tf"))
    specification = json.loads((phase1 / "provisioning-spec.json").read_text(encoding="utf-8"))
    assert not specification["executable_iac_present"]
    assert not specification["deployment_performed"]
    assert specification["forbidden_credentials"] == [
        "AI",
        "BROWSER",
        "M6",
        "SENDER",
        "DELIVERY",
    ]
