from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
TF = ROOT / "infra" / "terraform" / "bootstrap" / "primary_a_authentication.tf"
PLAN_REVIEW = AUTH / "primary-a-authentication-only-assignment-plan-review-2026-08-23.json"


def test_readonly_evidence_requires_a_new_assignment_without_claiming_mfa() -> None:
    evidence = json.loads(
        (AUTH / "primary-a-identity-center-readonly-evidence-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["screenshot_used_as_authoritative_evidence"] is False
    assert evidence["primary_a"]["matching_user_count"] == 1
    assert evidence["primary_a"]["user_status"] == "ENABLED"
    assert evidence["primary_a"]["distinct_from_owner_actor_observed_user"] is True
    assert evidence["assignments"]["aws_account_assignments"] == 0
    assert evidence["assignments"]["application_assignments"] == 0
    assert evidence["assignments"]["authentication_only_assignment_exists"] is False
    assert evidence["mfa"]["conclusion"] == "MFA_DEVICE_COUNT_NOT_SYSTEM_VERIFIED_PRE_CHALLENGE"
    assert evidence["conclusion"]["mfa_enrollment_authoritatively_verified"] is False
    assert evidence["conclusion"]["aws_mutation_required"] is True
    assert set(evidence["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_assignment_is_one_user_one_account_and_no_policy_attachment() -> None:
    config = TF.read_text(encoding="utf-8")
    assert 'resource "aws_ssoadmin_permission_set" "primary_a_authentication_only"' in config
    assert 'resource "aws_ssoadmin_account_assignment" "primary_a_authentication_only"' in config
    assert 'name             = "m67-primary-a-auth-only"' in config
    assert 'principal_type     = "USER"' in config
    assert 'target_type        = "AWS_ACCOUNT"' in config
    assert 'session_duration = "PT1H"' in config
    assert "aws_ssoadmin_managed_policy_attachment" not in config
    assert "aws_ssoadmin_customer_managed_policy_attachment" not in config
    assert "aws_ssoadmin_permissions_boundary_attachment" not in config
    assert "inline_policy" not in config


def test_raw_primary_a_identity_is_not_committed() -> None:
    config = TF.read_text(encoding="utf-8")
    evidence = (AUTH / "primary-a-identity-center-readonly-evidence-2026-08-23.json").read_text(
        encoding="utf-8"
    )
    assert "primary_a_identity_store_user_id" in config
    assert "sensitive   = true" in config
    assert "@" not in evidence
    assert '"username":' not in evidence.lower()
    assert '"email":' not in evidence.lower()


def test_assignment_plan_review_is_exact_and_fail_closed() -> None:
    review = json.loads(PLAN_REVIEW.read_text(encoding="utf-8"))
    assert review["state"] == (
        "READY_FOR_PRIMARY_A_AUTHENTICATION_ONLY_ASSIGNMENT_APPLY_AUTHORIZATION"
    )
    assert review["changes"] == {
        "create": 2,
        "change": 0,
        "replace": 0,
        "destroy": 0,
        "unexpected_change": 0,
    }
    assert {item["address"] for item in review["planned_resources"]} == {
        "aws_ssoadmin_permission_set.primary_a_authentication_only",
        "aws_ssoadmin_account_assignment.primary_a_authentication_only",
    }
    permission_set = review["planned_resources"][0]
    assert permission_set["service_permissions"] == "NONE"
    assert permission_set["inline_policies"] == 0
    assert permission_set["managed_policy_attachments"] == 0
    assert review["resulting_access"]["challenge_issuance_authorized"] is False
    assert set(review["permissions"].values()) == {"NOT_AUTHORIZED"}
