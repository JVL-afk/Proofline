from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "infra" / "terraform" / "bootstrap"


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
