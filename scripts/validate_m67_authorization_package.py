"""Validate the M6.7 owner package without authorizing or accessing live data."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
OWNER_PACKAGE = ROOT / "docs/readiness/m6.7-authorization/owner-control-package.json"
SEED_TEMPLATE = (
    ROOT / "docs/readiness/m6.7-authorization/phase1-owner-seed-manifest-v1.template.json"
)
PROVISIONING_SPEC = ROOT / "infra/aws/phase1/provisioning-spec.json"
DEPLOYMENT_EVIDENCE = ROOT / "infra/aws/phase1/deployed-environment-evidence.template.json"
ROLE_ASSIGNMENTS = ROOT / "docs/readiness/m6.7-authorization/role-assignments.template.json"
A17_REVIEW = ROOT / "docs/readiness/m6.7-authorization/a17-qualified-review.template.json"
DISCOVERY_SIGNATURE = ROOT / "docs/readiness/m6.7-authorization/discovery-signature.template.json"
TERRAFORM_ROOT = ROOT / "infra/terraform/phase1"

ROLE_NAMES = (
    "PROJECT_OWNER",
    "OPPORTUNITY_REVIEWER",
    "INDEPENDENT_SECOND_REVIEWER",
    "INCIDENT_OWNER",
    "PRIVACY_DATA_OWNER",
    "KILL_SWITCH_OPERATOR",
    "SECURITY_ENVIRONMENT_OWNER",
    "QUALIFIED_LEGAL_REVIEWER",
)

SEED_CANDIDATE_FIELDS = frozenset(
    {
        "candidate_ref",
        "public_business_name",
        "public_business_aliases",
        "texas_city_or_service_area",
        "identity_business_evidence_refs",
        "texas_eligibility_evidence_refs",
        "commercial_hvac_evidence_refs",
        "b2b_relevance_evidence_refs",
        "first_party_host_candidate",
        "first_party_host_evidence_refs",
        "organization_group_hint",
        "franchise_or_shared_brand_hint",
        "lead_flow_unit_hint",
        "distinct_lead_flow_evidence_refs",
        "provenance",
    }
)

PROHIBITED_SEED_TERMS = (
    "person",
    "contact",
    "email",
    "phone",
    "employee",
    "owner_name",
    "decision_maker",
    "opportunity_score",
    "lead_response",
    "conversion",
    "revenue",
    "crm",
)

REQUIRED_DEPLOYMENT_FIELDS = (
    "evidence_origin",
    "observed_at",
    "observed_by_subject_ref",
    "account_id",
    "vpc_id",
    "private_subnet_ids",
    "route_table_ids",
    "egress_control_refs",
    "ecs_cluster_arn",
    "ecs_task_definition_arn",
    "container_image_digest",
    "rds_instance_arn",
    "rds_database_identity_ref",
    "rds_kms_key_arn",
    "rds_grants_evidence_ref",
    "s3_bucket_arn",
    "s3_versioning_evidence_ref",
    "s3_lifecycle_evidence_ref",
    "s3_access_logging_evidence_ref",
    "kms_key_arns",
    "kms_policy_evidence_refs",
    "operator_identity_evidence_ref",
    "workload_role_arns",
    "mfa_access_policy_evidence_ref",
    "cloudtrail_destination_ref",
    "alarm_destination_refs",
    "backup_configuration_evidence_ref",
    "restore_test_evidence_ref",
    "kill_switch_integration_evidence_ref",
    "public_application_ingress_absent_evidence_ref",
    "forbidden_credentials_absent_evidence_ref",
    "approval_ids",
    "security_environment_owner_approval_id",
    "raw_evidence_artifact_hashes",
    "effective_at",
    "expires_at",
    "configuration_hash",
)


class AuthorizationPackageError(ValueError):
    """The frozen authorization package is internally inconsistent."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuthorizationPackageError(f"{path.name} must contain a JSON object")
    return cast(dict[str, Any], value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorizationPackageError(message)


def validate_owner_package(value: dict[str, Any]) -> None:
    scope = cast(dict[str, Any], value.get("scope"))
    selection = cast(dict[str, Any], value.get("selection"))
    qa = cast(dict[str, Any], value.get("quality_assurance"))
    workload = cast(dict[str, Any], value.get("workload_and_budget"))
    authority = cast(dict[str, Any], value.get("authority"))
    roles = cast(dict[str, Any], value.get("role_slots"))
    stages = cast(list[dict[str, Any]], value.get("stages"))

    _require(value.get("record_type") == "M67_PHASE1_OWNER_CONTROL_PACKAGE", "wrong owner type")
    _require(
        scope
        == {
            "candidate_frame_maximum": 100,
            "cohort_target": 24,
            "jurisdiction": "US-TX",
            "vertical": "COMMERCIAL_HVAC",
            "business_context": "B2B",
            "opportunity": "INBOUND_LEAD_RESPONSE",
        },
        "owner scope drift",
    )
    _require(selection.get("algorithm") == "SEEDED_SHA256_SYSTEMATIC_ORDER_V1", "algorithm drift")
    _require(selection.get("seed_frozen_before_opportunity_research") is True, "late seed")
    _require(selection.get("outcome_based_replacement_allowed") is False, "replacement drift")
    _require(qa.get("negative_outcome_rate_basis_points") == 2500, "QA rate drift")
    _require(qa.get("minimum_negative_outcome_cases") == 3, "QA minimum drift")
    _require(
        [stage.get("slots") for stage in stages] == [[1], list(range(2, 7)), list(range(7, 25))],
        "staged slot sequence drift",
    )
    _require(all(stage.get("mandatory_pause_after") is True for stage in stages), "pause drift")
    _require(workload.get("logical_fetch_cap") == 120, "logical fetch cap drift")
    _require(workload.get("attempt_cap") == 360, "attempt cap drift")
    _require(workload.get("aggregate_response_byte_cap") == 36_000_000, "byte cap drift")
    _require(workload.get("monetary_hard_cap_usd") == "250.00", "money cap drift")
    _require(workload.get("ai_budget_usd") == "0.00", "AI budget must be zero")
    _require(authority.get("browser") == "DISABLED", "browser must be disabled")
    _require(
        authority.get("person_contact_processing") == "NOT_AUTHORIZED",
        "person/contact must remain unauthorized",
    )
    _require(authority.get("delivery") == "UNAVAILABLE", "delivery must be unavailable")
    _require(authority.get("real_business_discovery") == "NOT_AUTHORIZED", "discovery authority")
    _require(authority.get("real_public_research") == "NOT_AUTHORIZED", "research authority")
    _require(tuple(roles) == ROLE_NAMES, "role slots must be exact and ordered")
    owner = roles["PROJECT_OWNER"]
    opportunity_reviewer = roles["OPPORTUNITY_REVIEWER"]
    second_reviewer = roles["INDEPENDENT_SECOND_REVIEWER"]
    legal_reviewer = roles["QUALIFIED_LEGAL_REVIEWER"]
    if opportunity_reviewer and second_reviewer:
        _require(
            opportunity_reviewer != second_reviewer,
            "opportunity and independent reviewers must be different humans",
        )
    if owner and legal_reviewer:
        _require(owner != legal_reviewer, "qualified legal reviewer must not be project owner")


def validate_seed_manifest(value: dict[str, Any], *, allow_populated: bool = False) -> None:
    _require(value.get("record_type") == "PHASE1_OWNER_SEED_MANIFEST_V1", "wrong seed type")
    _require(value.get("schema_version") == "1.0.0", "wrong seed schema version")
    _require(value.get("candidate_frame_maximum") == 100, "seed frame limit drift")
    candidates = value.get("candidates")
    _require(isinstance(candidates, list), "seed candidates must be a list")
    candidate_list = cast(list[dict[str, Any]], candidates)
    _require(len(candidate_list) <= 100, "seed candidate frame exceeds 100")
    if not allow_populated:
        _require(candidate_list == [], "repository template cannot contain real candidates")
    for candidate in candidate_list:
        keys = frozenset(candidate)
        _require(keys <= SEED_CANDIDATE_FIELDS, "seed candidate contains an unapproved field")
        lowered = " ".join(keys).lower()
        _require(
            not any(term in lowered for term in PROHIBITED_SEED_TERMS),
            "seed candidate contains a person/contact/opportunity field",
        )
        _require(bool(candidate.get("provenance")), "every seed candidate requires provenance")


def validate_provisioning_spec(value: dict[str, Any]) -> None:
    _require(
        value.get("status") == "REVIEWABLE_TERRAFORM_PACKAGE_NOT_INITIALIZED",
        "provisioning specification state drift",
    )
    _require(value.get("executable_iac_present") is True, "Terraform package must be present")
    _require(value.get("deployment_performed") is False, "deployment is not authorized")
    _require(value.get("provider") == "AWS", "provider baseline drift")
    _require(value.get("region") == "us-east-2", "region baseline drift")
    _require(value.get("iac_tool") == "TERRAFORM_1_15", "Terraform selection drift")
    _require(
        value.get("remote_state_backend") == "S3_KMS_USE_LOCKFILE_PARTIAL_CONFIGURATION_REQUIRED",
        "remote-state policy drift",
    )
    network = cast(dict[str, Any], value.get("network"))
    compute = cast(dict[str, Any], value.get("compute"))
    _require(network.get("public_application_ingress") is False, "public ingress prohibited")
    _require(compute.get("worker_concurrency") == 1, "worker concurrency must be one")
    _require(
        value.get("forbidden_credentials") == ["AI", "BROWSER", "M6", "SENDER", "DELIVERY"],
        "forbidden credential set drift",
    )


def validate_role_assignments(value: dict[str, Any]) -> None:
    _require(value.get("record_type") == "M67_OPERATIONAL_ROLE_ASSIGNMENTS", "wrong role type")
    assignments = cast(list[dict[str, Any]], value.get("assignments"))
    _require([item.get("role") for item in assignments] == list(ROLE_NAMES), "role order drift")
    by_role = {str(item["role"]): item.get("subject_ref") for item in assignments}
    primary = by_role["OPPORTUNITY_REVIEWER"]
    second = by_role["INDEPENDENT_SECOND_REVIEWER"]
    owner = by_role["PROJECT_OWNER"]
    legal = by_role["QUALIFIED_LEGAL_REVIEWER"]
    if primary and second:
        _require(primary != second, "opportunity reviewer separation violated")
    if owner and legal:
        _require(owner != legal, "project owner/legal reviewer separation violated")


def validate_a17_template(value: dict[str, Any]) -> None:
    _require(value.get("record_type") == "A17_QUALIFIED_LEGAL_REVIEW", "wrong A-17 type")
    issues = cast(list[dict[str, Any]], value.get("issues"))
    _require(
        [item.get("issue_id") for item in issues]
        == [f"A17-Q{number:02d}" for number in range(1, 15)],
        "A-17 issue inventory drift",
    )
    if value.get("state") == "APPROVED":
        _require(bool(value.get("reviewer_subject_ref")), "approved A-17 requires reviewer")
        _require(bool(value.get("reviewer_attestation")), "approved A-17 requires attestation")
        for issue in issues:
            _require(bool(issue.get("conclusion")), "approved A-17 requires every conclusion")
            _require(bool(issue.get("authority")), "approved A-17 requires supporting authority")
            _require(issue.get("state") != "UNRESOLVED", "approved A-17 has unresolved issue")


def validate_discovery_signature(value: dict[str, Any]) -> None:
    _require(
        value.get("record_type") == "REAL_BUSINESS_DISCOVERY_OWNER_SIGNATURE",
        "wrong discovery signature type",
    )
    _require(
        value.get("research_authorized") is False, "discovery signature cannot authorize research"
    )
    _require(value.get("slot_1_authorized") is False, "discovery signature cannot authorize slot 1")
    _require(
        value.get("person_contact_authorized") is False,
        "discovery signature cannot authorize person/contact",
    )
    _require(
        value.get("browser_authorized") is False, "discovery signature cannot authorize browser"
    )
    _require(
        value.get("communication_authorized") is False,
        "discovery signature cannot authorize communication",
    )


def validate_terraform_package() -> None:
    versions = (TERRAFORM_ROOT / "versions.tf").read_text(encoding="utf-8")
    backend = (TERRAFORM_ROOT / "backend.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "variables.tf").read_text(encoding="utf-8")
    lock = (TERRAFORM_ROOT / ".terraform.lock.hcl").read_text(encoding="utf-8")
    terraform_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TERRAFORM_ROOT.glob("*.tf"))
    )
    _require('required_version = ">= 1.15.9, < 1.16.0"' in versions, "Terraform version drift")
    _require('version = "= 6.53.0"' in versions, "AWS provider version drift")
    _require(
        'version     = "6.53.0"' in lock and 'constraints = "6.53.0"' in lock,
        "AWS provider lock drift",
    )
    _require(lock.count("h1:") >= 2, "provider lock must cover Windows and Linux")
    _require('backend "s3" {}' in backend, "S3 partial backend required")
    _require('default     = "us-east-2"' in variables, "Phase 1 region drift")
    _require("default     = 0" in variables, "worker must default to zero")
    for prohibited in (
        'provisioner "',
        "local-exec",
        "remote-exec",
        "access_key =",
        "secret_key =",
    ):
        _require(prohibited not in terraform_text, f"prohibited Terraform construct: {prohibited}")
    _require(
        "manage_master_user_password         = true" in terraform_text,
        "AWS-managed DB password required",
    )
    _require(not list(TERRAFORM_ROOT.glob("*.tfstate*")), "Terraform state must not be tracked")
    _require(not list(TERRAFORM_ROOT.glob("*.tfplan*")), "Terraform plan must not be tracked")


def deployed_environment_blockers(value: dict[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if value.get("status") != "DEPLOYED_ATTESTED":
        blockers.append("ACTUAL_ENVIRONMENT_NOT_DEPLOYED_OR_ATTESTED")
    if value.get("actual_infrastructure_observed") is not True:
        blockers.append("ACTUAL_INFRASTRUCTURE_OBSERVATION_REQUIRED")
    for field in REQUIRED_DEPLOYMENT_FIELDS:
        item = value.get(field)
        if item is None or item == "" or item == []:
            blockers.append(f"DEPLOYMENT_EVIDENCE_REQUIRED:{field}")
    image = value.get("container_image_digest")
    if image and not re.fullmatch(r"sha256:[a-f0-9]{64}", str(image)):
        blockers.append("IMMUTABLE_CONTAINER_IMAGE_DIGEST_REQUIRED")
    if value.get("evidence_origin") not in {None, "AWS_CONTROL_PLANE_EXPORT"}:
        blockers.append("AWS_CONTROL_PLANE_EVIDENCE_ORIGIN_REQUIRED")
    configuration_hash = value.get("configuration_hash")
    if configuration_hash:
        hash_payload = {key: item for key, item in value.items() if key != "configuration_hash"}
        expected_hash = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if configuration_hash != expected_hash:
            blockers.append("DEPLOYMENT_CONFIGURATION_HASH_MISMATCH")
    return tuple(blockers)


def discovery_readiness_blockers(
    owner: dict[str, Any],
    seed: dict[str, Any],
    deployment: dict[str, Any],
    role_assignments: dict[str, Any],
    a17_review: dict[str, Any],
) -> tuple[str, ...]:
    blockers = list(deployed_environment_blockers(deployment))
    assignments = cast(list[dict[str, Any]], role_assignments["assignments"])
    blockers.extend(
        f"ROLE_SUBJECT_REQUIRED:{item['role']}" for item in assignments if not item["subject_ref"]
    )
    if seed.get("state") != "FROZEN" or not seed.get("candidates"):
        blockers.append("EXACT_PROVENANCE_BACKED_OWNER_SEED_MANIFEST_REQUIRED")
    authority = cast(dict[str, Any], owner["authority"])
    if authority.get("a08") != "APPROVED":
        blockers.append("A08_FINAL_RETENTION_APPROVAL_REQUIRED")
    if authority.get("a09") != "APPROVED":
        blockers.append("A09_EXACT_DISCOVERY_SOURCE_APPROVAL_REQUIRED")
    if authority.get("a17") != "APPROVED" or a17_review.get("state") != "APPROVED":
        blockers.append("A17_QUALIFIED_LEGAL_APPROVAL_REQUIRED")
    blockers.extend(
        (
            "ADR_0071_ACCEPTANCE_REQUIRED",
            "A03_TENANCY_APPROVAL_REQUIRED",
            "A04_CLOUD_REGION_DATA_APPROVAL_REQUIRED",
            "A07_IDENTITY_GOVERNANCE_APPROVAL_REQUIRED",
            "TERRAFORM_BACKEND_RESOURCES_AND_PARTIAL_CONFIG_REQUIRED",
            "AWS_CHARGE_AUTHORIZATION_REQUIRED",
            "AWS_AUTHENTICATED_PLAN_APPLY_AUTHORITY_REQUIRED",
            "REVIEWED_TERRAFORM_PLAN_REQUIRED",
            "OWNER_DISCOVERY_RELEASE_SIGNATURE_REQUIRED",
        )
    )
    return tuple(dict.fromkeys(blockers))


def validate_package() -> dict[str, Any]:
    owner = _load(OWNER_PACKAGE)
    seed = _load(SEED_TEMPLATE)
    provisioning = _load(PROVISIONING_SPEC)
    deployment = _load(DEPLOYMENT_EVIDENCE)
    role_assignments = _load(ROLE_ASSIGNMENTS)
    a17_review = _load(A17_REVIEW)
    discovery_signature = _load(DISCOVERY_SIGNATURE)
    validate_owner_package(owner)
    validate_seed_manifest(seed)
    validate_provisioning_spec(provisioning)
    validate_role_assignments(role_assignments)
    validate_a17_template(a17_review)
    validate_discovery_signature(discovery_signature)
    validate_terraform_package()
    blockers = discovery_readiness_blockers(owner, seed, deployment, role_assignments, a17_review)
    return {
        "state": "NOT_READY_TO_AUTHORIZE_DISCOVERY"
        if blockers
        else "READY_FOR_DISCOVERY_AUTHORIZATION_SIGNATURE",
        "blockers": blockers,
        "real_business_discovery": "NOT_AUTHORIZED",
        "real_public_research": "NOT_AUTHORIZED",
        "real_businesses_accessed": 0,
        "real_people_or_contacts_processed": 0,
        "external_communications": 0,
    }


def main() -> int:
    try:
        report = validate_package()
    except (AuthorizationPackageError, json.JSONDecodeError) as error:
        print(f"M6.7 authorization package invalid: {error}")
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
