"""Create a bounded, hash-linked M6.7 Terraform plan approval record."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

ALLOWED_RESOURCE_TYPES = frozenset(
    {
        "aws_budgets_budget",
        "aws_cloudtrail",
        "aws_cloudwatch_log_group",
        "aws_cloudwatch_metric_alarm",
        "aws_db_instance",
        "aws_db_subnet_group",
        "aws_ecs_cluster",
        "aws_ecs_service",
        "aws_ecs_task_definition",
        "aws_eip",
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_internet_gateway",
        "aws_kms_alias",
        "aws_kms_key",
        "aws_nat_gateway",
        "aws_route_table",
        "aws_route_table_association",
        "aws_s3_bucket",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_ownership_controls",
        "aws_s3_bucket_policy",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_s3_bucket_versioning",
        "aws_security_group",
        "aws_sns_topic",
        "aws_sns_topic_policy",
        "aws_ssm_parameter",
        "aws_subnet",
        "aws_vpc",
        "aws_vpc_security_group_egress_rule",
        "aws_vpc_security_group_ingress_rule",
    }
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.tf")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_record(
    *,
    plan_binary: Path,
    plan_json: Path,
    configuration_root: Path,
    plan_kind: str,
    account_id: str,
    organization_id: str | None,
    authenticated_role: str,
    estimated_cost_usd: Decimal | None,
) -> dict[str, Any]:
    if plan_kind not in {"BOOTSTRAP", "PHASE1"}:
        raise ValueError("plan kind must be BOOTSTRAP or PHASE1")
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    changes = cast(list[dict[str, Any]], plan.get("resource_changes", []))
    counts = {"create": 0, "update": 0, "replace": 0, "destroy": 0, "no_op": 0}
    resources: list[dict[str, object]] = []
    prohibited: list[str] = []
    for item in changes:
        resource_type = str(item.get("type"))
        actions = cast(list[str], cast(dict[str, Any], item.get("change", {})).get("actions", []))
        action_set = set(actions)
        if action_set == {"create"}:
            counts["create"] += 1
        elif action_set == {"update"}:
            counts["update"] += 1
        elif action_set == {"delete"}:
            counts["destroy"] += 1
        elif action_set == {"create", "delete"}:
            counts["replace"] += 1
        elif action_set == {"no-op"}:
            counts["no_op"] += 1
        if resource_type not in ALLOWED_RESOURCE_TYPES:
            prohibited.append(str(item.get("address")))
        resources.append(
            {
                "address": item.get("address"),
                "type": resource_type,
                "actions": actions,
            }
        )
    lock = configuration_root / ".terraform.lock.hcl"
    warnings: list[str] = []
    if estimated_cost_usd is None:
        warnings.append("COST_EVIDENCE_REQUIRED")
    elif estimated_cost_usd > Decimal("250"):
        warnings.append("COST_EXCEEDS_OWNER_CEILING")
    if counts["destroy"]:
        warnings.append("UNEXPECTED_DESTROY_BLOCKS_APPLY")
    if counts["replace"]:
        warnings.append("UNEXPECTED_REPLACE_BLOCKS_APPLY")
    if prohibited:
        warnings.append("PROHIBITED_OR_UNREVIEWED_RESOURCE_TYPE")
    record: dict[str, Any] = {
        "record_type": "M67_TERRAFORM_PLAN_REVIEW",
        "version": "1.0.0",
        "state": "READY_FOR_OWNER_APPLY_DECISION" if not warnings else "BLOCKED",
        "plan_kind": plan_kind,
        "required_owner_event": f"APPROVE_{plan_kind}_APPLY",
        "target": {
            "account_id": account_id,
            "organization_id": organization_id,
            "region": "us-east-2",
            "authenticated_role": authenticated_role,
        },
        "hashes": {
            "plan_sha256": file_hash(plan_binary),
            "plan_json_sha256": file_hash(plan_json),
            "configuration_sha256": configuration_hash(configuration_root),
            "provider_lock_sha256": file_hash(lock),
        },
        "changes": counts,
        "resources": resources,
        "prohibited_resources": prohibited,
        "cost": {
            "estimated_usd": str(estimated_cost_usd) if estimated_cost_usd is not None else None,
            "ceiling_usd": "250.00",
        },
        "warnings": warnings,
        "real_business_discovery": "NOT_AUTHORIZED",
        "real_public_research": "NOT_AUTHORIZED",
        "owner_signature": None,
    }
    record["configuration_hash"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-binary", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--configuration-root", type=Path, required=True)
    parser.add_argument("--plan-kind", choices=("BOOTSTRAP", "PHASE1"), required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--organization-id")
    parser.add_argument("--authenticated-role", required=True)
    parser.add_argument("--estimated-cost-usd", type=Decimal)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = build_record(
        plan_binary=args.plan_binary,
        plan_json=args.plan_json,
        configuration_root=args.configuration_root,
        plan_kind=args.plan_kind,
        account_id=args.account_id,
        organization_id=args.organization_id,
        authenticated_role=args.authenticated_role,
        estimated_cost_usd=args.estimated_cost_usd,
    )
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
