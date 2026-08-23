from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def load(name: str) -> dict[str, object]:
    return json.loads((AUTH / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((AUTH / name).read_bytes()).hexdigest()


def test_machine_validator_accepts_fail_closed_package() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m67_primary_a_authentication_package.py")],
        check=True,
    )


def test_authoritative_assignment_is_not_re_designated() -> None:
    statements = load("primary-a-owner-statements-2026-08-23.json")
    approved = statements["already_approved_not_repeated"]
    assert approved["actor_designation"] == "PRIMARY_A_ACTOR"
    assert approved["role"] == "INDEPENDENT_SECOND_REVIEWER"
    assert approved["approval_id"] == "M67_CONSOLIDATED_OWNER_APPROVAL_V1"


def test_human_and_system_values_are_separated() -> None:
    package = load("primary-a-authentication-package-2026-08-23.json")
    ownership = package["value_ownership"]
    assert "AFFIRM_THE_FIXED_NARROW_ATTESTATION" in ownership["primary_a"]
    assert "OPAQUE_SUBJECT_DIGEST" in ownership["idp_and_system"]
    assert "AUTH_EVENT_ID_AND_TIMESTAMP" in ownership["idp_and_system"]
    assert "OWNER_ACTOR_COLLISION_CHECK" in ownership["idp_and_system"]
    assert "OPAQUE_SUBJECT_DIGEST" not in ownership["primary_a"]


def test_challenge_is_not_issued_and_idp_assignment_is_missing() -> None:
    package = load("primary-a-authentication-package-2026-08-23.json")
    assert package["state"] == "BLOCKED_PENDING_PRIMARY_A_AUTHENTICATION_ONLY_IDP_ASSIGNMENT"
    assert package["live_authentication_performed"] is False
    assert package["challenge_issued"] is False
    assert package["missing_external_prerequisite"]["exact_item"] == (
        "APPROVED_AUTHENTICATION_ONLY_IDP_ASSIGNMENT_OR_AUDIENCE_FOR_PRIMARY_A_ACTOR"
    )


def test_state_machine_is_fail_closed() -> None:
    package = load("primary-a-authentication-package-2026-08-23.json")
    failures = set(package["state_machine"]["fail_closed"])
    assert failures == {
        "EXPIRED_CHALLENGE",
        "WRONG_ACTOR",
        "WRONG_ACCOUNT_OR_ENVIRONMENT",
        "MFA_REQUIRED",
        "REPLAYED_CHALLENGE",
        "AMBIGUOUS_SUBJECT",
        "OWNER_PRIMARY_A_IDENTITY_COLLISION",
        "INCOMPLETE_ATTESTATION",
    }
    assert package["state_machine"]["retry_rule"].startswith("NO_RETRY_OR_REUSE")


def test_authentication_does_not_equal_review_or_permission() -> None:
    package = load("primary-a-authentication-package-2026-08-23.json")
    distinction = package["authentication_vs_review"]
    assert distinction["authentication_complete_effect"] == "IDENTITY_PREREQUISITE_ONLY"
    assert distinction["independent_opportunity_review_complete"] is False
    assert (
        distinction["primary_a_separate_discovery_release_signature_required_by_frozen_design"]
        is False
    )
    assert distinction["owner_exact_discovery_release_signature_still_required"] is True
    assert set(package["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_primary_a_form_requests_no_manual_technical_or_secret_values() -> None:
    form = (AUTH / "primary-a-independent-authentication-form-2026-08-23.md").read_text(
        encoding="utf-8"
    )
    assert "What you do not fill in" in form
    assert "Do not manually send your name, email, telephone number, raw IdP subject" in form
    assert "I, the human independently authenticating as PRIMARY_A_ACTOR" in form
    assert "<CHALLENGE_ID>" in form


def test_owner_statements_have_system_fill_rules_and_later_states() -> None:
    statements = load("primary-a-owner-statements-2026-08-23.json")
    assert statements["challenge_issuance_fill_rule"]["emitted_at_state"] == (
        "READY_FOR_PRIMARY_A_CHALLENGE_ISSUANCE_AUTHORIZATION"
    )
    assert statements["reconciliation_fill_rule"]["emitted_at_state"] == (
        "PRIMARY_A_RECONCILED_PENDING_OWNER_ACCEPTANCE"
    )
    assert statements["later_release_fill_rule"]["emitted_at_state"] == (
        "READY_FOR_REAL_BUSINESS_DISCOVERY_OWNER_SIGNATURE"
    )
    assert statements["permissions_changed"] is False


def test_manifest_binds_only_non_secret_preparation_artifacts() -> None:
    manifest = load("primary-a-authentication-preparation-manifest-2026-08-23.json")
    assert manifest["state"] == "BLOCKED_PENDING_PRIMARY_A_AUTHENTICATION_ONLY_IDP_ASSIGNMENT"
    assert manifest["challenge_issued"] is False
    assert manifest["live_authentication_performed"] is False
    assert manifest["permissions_changed"] is False
    paths = {artifact["path"] for artifact in manifest["artifacts"]}
    assert all("local-data" not in path for path in paths)
    assert all("token" not in path.lower() for path in paths)


def test_challenge_issuer_keeps_nonce_private_and_refuses_overwrite(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "issue_m67_primary_a_challenge.py"
    spec = importlib.util.spec_from_file_location("issue_primary_a", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public_path, private_path = module.issue(
        output_dir=tmp_path,
        owner_approval_sha256="a" * 64,
        now=datetime(2026, 8, 23, 12, 0, tzinfo=UTC),
    )
    public = json.loads(public_path.read_text(encoding="utf-8"))
    private = json.loads(private_path.read_text(encoding="utf-8"))
    assert public["state"] == "PRIMARY_A_CHALLENGE_ISSUED"
    assert public["expires_at"] == "2026-08-23T12:15:00Z"
    assert public["permissions_granted"] == []
    assert "raw_nonce" not in public
    assert private["raw_nonce"] not in public_path.read_text(encoding="utf-8")
    try:
        module.issue(
            output_dir=tmp_path,
            owner_approval_sha256="a" * 64,
            now=datetime(2026, 8, 23, 12, 1, tzinfo=UTC),
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("challenge issuer overwrote an existing challenge")


def test_challenge_issuance_readiness_binds_deployed_assignment_and_mechanism() -> None:
    readiness = load("primary-a-challenge-issuance-readiness-2026-08-23.json")
    mechanism = load("primary-a-challenge-mechanism-ready-2026-08-23.json")
    approval = load("primary-a-challenge-issuance-owner-approval-ready-2026-08-23.json")
    assert readiness["state"] == "READY_FOR_PRIMARY_A_CHALLENGE_ISSUANCE_AUTHORIZATION"
    assert readiness["prerequisites"]["challenge_issued"] is False
    assert readiness["prerequisites"]["terraform_post_apply_state"] == "NO_CHANGES"
    assert readiness["hash_bindings"]["assignment_deployed_evidence_sha256"] == sha256(
        "primary-a-authentication-only-assignment-deployed-evidence-2026-08-23.json"
    )
    assert readiness["hash_bindings"]["challenge_mechanism_sha256"] == sha256(
        "primary-a-challenge-mechanism-ready-2026-08-23.json"
    )
    assert approval["authentication_package_sha256"] == sha256(
        "primary-a-challenge-issuance-readiness-2026-08-23.json"
    )
    assert (
        mechanism["implementation"]["issuer_script_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts" / "issue_m67_primary_a_challenge.py").read_bytes()
        ).hexdigest()
    )
    assert approval["challenge_issued"] is False
    assert approval["permissions_changed"] is False
    assert set(readiness["permissions"].values()) == {"NOT_AUTHORIZED"}
