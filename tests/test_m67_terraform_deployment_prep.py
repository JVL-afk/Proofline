from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "infra" / "terraform" / "bootstrap"
PHASE1 = ROOT / "infra" / "terraform" / "phase1"
IDENTIFIERS = ROOT / "infra" / "terraform" / "modules" / "phase1-identifiers"


def test_bootstrap_is_separate_and_protects_remote_state() -> None:
    main = (BOOTSTRAP / "main.tf").read_text(encoding="utf-8")
    assert 'resource "aws_s3_bucket" "state"' in main
    assert 'resource "aws_kms_key" "state"' in main
    assert 'resource "aws_cloudtrail" "state"' in main
    assert "prevent_destroy = true" in main
    assert 'object_ownership = "BucketOwnerEnforced"' in main
    assert "enable_key_rotation     = true" in main
    assert 'type   = "AWS::S3::Object"' in main
    assert '"s3:PutObject", "s3:DeleteObject"' in main


def test_bootstrap_and_review_artifact_grant_no_live_authority() -> None:
    files = [
        path
        for path in BOOTSTRAP.iterdir()
        if path.is_file() and (path.suffix in {".tf", ".md"} or path.name == ".terraform.lock.hcl")
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for forbidden in (
        "aws_ecs_service",
        "aws_db_instance",
        "openai",
        "anthropic",
        "gemini",
        "sendgrid",
        "twilio",
        "playwright",
    ):
        assert forbidden not in combined.lower()

    review = json.loads(
        (
            ROOT / "docs" / "readiness" / "m6.7-deployment" / "terraform-plan-review.template.json"
        ).read_text(encoding="utf-8")
    )
    assert review["state"] == "BLOCKED_PENDING_AUTHENTICATED_PLAN"
    assert review["apply_readiness"] == "NOT_READY"
    assert set(review["live_permissions"].values()) == {"NOT_AUTHORIZED"}


def test_local_plan_and_backend_values_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("*.tfplan", "*.tfplan.json", "backend.hcl", "terraform.tfvars"):
        assert pattern in ignore


def test_workload_plan_and_apply_identities_are_separate_and_bounded() -> None:
    access = (BOOTSTRAP / "workload_access.tf").read_text(encoding="utf-8")
    assert 'resource "aws_iam_role" "workload_plan"' in access
    assert 'resource "aws_iam_role" "workload_apply"' in access
    assert "m67-phase1-terraform-state-plan" in access
    assert "m67-phase1-terraform-state-apply" in access
    assert "max_session_duration = 14400" in access
    assert "max_session_duration = 3600" in access
    assert "AdministratorAccess" not in access
    assert "PowerUserAccess" not in access
    assert 'actions   = ["sts:AssumeRole"]' in access

    read_document = access.split('data "aws_iam_policy_document" "workload_read"', maxsplit=1)[
        1
    ].split('resource "aws_iam_role_policy" "workload_plan"', maxsplit=1)[0]
    for mutating_action in (
        "CreateBucket",
        "CreateDBInstance",
        "CreateService",
        "CreateVpc",
        "PutRolePolicy",
        "RegisterTaskDefinition",
    ):
        assert mutating_action not in read_document

    assert "role/m67-phase1-*" in access
    assert "REAL_BUSINESS_DISCOVERY" not in access
    assert "REAL_PUBLIC_RESEARCH" not in access


def test_phase1_bucket_names_and_workload_iam_share_one_identifier_module() -> None:
    identifiers = (IDENTIFIERS / "main.tf").read_text(encoding="utf-8")
    outputs = (IDENTIFIERS / "outputs.tf").read_text(encoding="utf-8")
    phase1_provider = (PHASE1 / "providers.tf").read_text(encoding="utf-8")
    storage = (PHASE1 / "storage.tf").read_text(encoding="utf-8")
    workload_access = (BOOTSTRAP / "workload_access.tf").read_text(encoding="utf-8")

    assert "restricted-captures" in identifiers
    assert 'sha256("${var.account_id}:${var.aws_region}:${var.name_prefix}' in identifiers
    assert 'output "capture_bucket_arn"' in outputs
    assert 'output "audit_bucket_arn"' in outputs
    assert 'source = "../modules/phase1-identifiers"' in phase1_provider
    assert 'source = "../modules/phase1-identifiers"' in workload_access
    assert "bucket = module.phase1_identifiers.capture_bucket_name" in storage
    assert "bucket = module.phase1_identifiers.audit_bucket_name" in storage
    assert "module.phase1_identifiers.capture_bucket_arn" in workload_access
    assert "module.phase1_identifiers.audit_bucket_arn" in workload_access
    assert "IAM_CAPTURE_BUCKET_ARN must equal PLANNED_CAPTURE_BUCKET_ARN" in storage
    assert "IAM_AUDIT_BUCKET_ARN must equal PLANNED_AUDIT_BUCKET_ARN" in storage
    assert "bucket_prefix" not in storage


def test_partial_apply_provider_permissions_remain_exact_and_cloud_map_has_no_fake_role() -> None:
    access = (BOOTSTRAP / "workload_access.tf").read_text(encoding="utf-8")
    compute = (PHASE1 / "compute.tf").read_text(encoding="utf-8")

    assert 'actions   = ["budgets:TagResource"]' in access
    assert "budget/${local.workload_name_prefix}-monthly-hard-ceiling" in access
    assert 'actions = ["iam:TagRole"]' in access
    assert "role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS" in access
    assert "role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS" in access
    assert "servicediscovery.amazonaws.com" not in access
    assert 'resource "aws_iam_service_linked_role" "service_discovery"' not in compute
    assert "aws_iam_service_linked_role.service_discovery" not in compute
    assert "health_check_custom_config" in compute
    assert "failure_threshold = 1" in compute


def test_research_worker_image_revision_cannot_replace_controlled_egress_image() -> None:
    variables = (PHASE1 / "variables.tf").read_text(encoding="utf-8")
    compute = (PHASE1 / "compute.tf").read_text(encoding="utf-8")

    assert 'variable "worker_image_uri"' in variables
    assert 'variable "controlled_egress_image_uri"' in variables
    worker_definition = compute.split('resource "aws_ecs_task_definition" "worker"', maxsplit=1)[
        1
    ].split('resource "aws_ecs_service" "worker"', maxsplit=1)[0]
    egress_definition = compute.split('resource "aws_ecs_task_definition" "egress"', maxsplit=1)[
        1
    ].split('resource "aws_ecs_service" "egress"', maxsplit=1)[0]
    assert "image     = var.worker_image_uri" in worker_definition
    assert "controlled_egress_image_uri" not in worker_definition
    assert "image                  = var.controlled_egress_image_uri" in egress_definition
    assert "var.worker_image_uri" not in egress_definition


def test_kill_switch_policy_is_stable_across_worker_task_revisions() -> None:
    observability = (PHASE1 / "observability.tf").read_text(encoding="utf-8")

    kill_policy = observability.split('data "aws_iam_policy_document" "kill_operator"', maxsplit=1)[
        1
    ].split('resource "aws_iam_role_policy" "kill_operator"', maxsplit=1)[0]
    assert "aws_ecs_service.worker.id" not in kill_policy
    assert "service/${var.name_prefix}-research/${var.name_prefix}-research-worker" in kill_policy
    assert 'actions = ["ecs:UpdateService", "ecs:DescribeServices"]' in kill_policy


def test_final_iam_remediation_is_exact_and_bounded() -> None:
    access = (BOOTSTRAP / "workload_access.tf").read_text(encoding="utf-8")
    variables = (BOOTSTRAP / "variables.tf").read_text(encoding="utf-8")

    assert 'actions   = ["route53:CreateHostedZone"]' in access
    # CreateHostedZone has no resource-level ARN before creation and the
    # route53:VPCs condition is not honored for this Cloud Map call path.
    assert 'variable = "route53:VPCs"' not in access
    assert 'actions   = ["kms:CreateGrant"]' in access
    assert "resources = [var.phase1_database_kms_key_arn]" in access
    assert 'variable = "kms:GrantIsForAWSResource"' in access
    assert 'variable = "kms:ViaService"' in access
    assert 'values   = ["rds.${var.aws_region}.amazonaws.com"]' in access
    assert 'actions   = ["budgets:ListTagsForResource"]' in access
    assert '"secretsmanager:CreateSecret"' in access
    assert '"secretsmanager:TagResource"' in access
    assert "secret:rds!db-*" in access
    assert 'actions   = ["cloudtrail:PutEventSelectors"]' in access
    assert 'actions   = ["cloudtrail:GetEventSelectors"]' in access
    assert "trail/${local.workload_name_prefix}-audit" in access
    assert '"kms:Decrypt"' in access
    assert '"kms:GenerateDataKey"' in access
    assert 'values   = ["secretsmanager.${var.aws_region}.amazonaws.com"]' in access
    assert '"s3:GetAccelerateConfiguration"' in access
    assert '"s3:GetReplicationConfiguration"' in access
    assert "module.phase1_identifiers.capture_bucket_arn" in access
    assert "module.phase1_identifiers.audit_bucket_arn" in access
    assert 'variable "phase1_vpc_id"' in variables
    assert 'variable "phase1_database_kms_key_arn"' in variables
    assert '"route53:*"' not in access
    assert '"kms:*"' not in access
    assert '"s3:*"' not in access
    assert '"budgets:*"' not in access
