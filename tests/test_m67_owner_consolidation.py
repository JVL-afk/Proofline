from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"
DEPLOY = ROOT / "docs" / "readiness" / "m6.7-deployment"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_owner_approval_is_immutable_hashed_and_grants_no_live_authority() -> None:
    approval = load(AUTH / "consolidated-owner-approval-2026-08-21.json")
    configuration_hash = approval.pop("configuration_hash")
    expected = hashlib.sha256(
        json.dumps(approval, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert configuration_hash == expected
    assert approval["state"] == "OWNER_APPROVED_RECORDED"
    assert approval["authority"] == {
        "real_business_discovery": "NOT_AUTHORIZED",
        "real_public_research": "NOT_AUTHORIZED",
        "slot_1": "NOT_AUTHORIZED",
    }


def test_generated_actor_bindings_are_opaque_unique_and_require_oidc_reconciliation() -> None:
    roles = load(AUTH / "role-assignments.predeployment.json")
    assignments = roles["assignments"]
    assert isinstance(assignments, list)
    by_role = {item["role"]: item["subject_ref"] for item in assignments}
    assert by_role["PROJECT_OWNER"] == by_role["OPPORTUNITY_REVIEWER"]
    assert by_role["OPPORTUNITY_REVIEWER"] != by_role["INDEPENDENT_SECOND_REVIEWER"]
    assert by_role["PROJECT_OWNER"] != by_role["QUALIFIED_LEGAL_REVIEWER"]
    assert all(str(value).startswith("m67-subject-") for value in by_role.values())
    assert (
        roles["constraints"]["live_operational_actor_oidc_reconciliation_required_before_discovery"]
        is True
    )
    assert "local-data/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_one_account_is_allowed_but_roles_and_apply_events_remain_separate() -> None:
    bootstrap = (ROOT / "infra/terraform/bootstrap/main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "infra/terraform/bootstrap/variables.tf").read_text(encoding="utf-8")
    assert "m67-phase1-tfstate-${var.expected_state_account_id}-${var.aws_region}" in bootstrap
    assert 'variable "state_bucket_name"' not in variables
    assert 'resource "aws_iam_role" "state_plan"' in bootstrap
    assert 'resource "aws_iam_role" "state_apply"' in bootstrap

    consolidation = load(AUTH / "owner-input-consolidation.json")
    assert consolidation["converted_to_system_derived_or_observed"] == 13
    assert consolidation["owner_interactions_before_initial_discovery"] == 6
    assert consolidation["owner_interactions_through_seed_package_approval"] == 7
    assert consolidation["interactions"][1:3] == [
        "APPROVE_BOOTSTRAP_APPLY",
        "APPROVE_PHASE1_APPLY",
    ]


def synthetic_observation(index: int) -> dict[str, object]:
    fragment = f"fixture-{index}"
    artifact_hash = hashlib.sha256(fragment.encode()).hexdigest()
    return {
        "public_business_name": f"Synthetic HVAC {index}",
        "texas_city_or_service_area": "Synthetic, TX",
        "first_party_host_candidate": f"synthetic-{index}.example.test",
        "organization_group_hint": f"group-{index}",
        "lead_flow_unit_hint": f"unit-{index}",
        "eligibility_observations": {
            "identity": [fragment],
            "texas": ["controlled Texas fixture"],
            "commercial_hvac": ["controlled commercial HVAC fixture"],
            "b2b": ["controlled B2B fixture"],
            "operational": ["controlled operating-status fixture"],
            "first_party_host": [f"synthetic-{index}.example.test"],
        },
        "provenance": [
            {
                "source_id": f"fixture-source-{index}",
                "source_artifact_ref": f"fixture-artifact-{index}",
                "locator": f"fixture:{index}",
                "observed_at": "2026-08-21T12:00:00+00:00",
                "source_artifact_sha256": artifact_hash,
            }
        ],
    }


def test_seed_and_source_package_is_generated_without_blanket_host_approval(
    tmp_path: Path,
) -> None:
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps([synthetic_observation(index) for index in range(24)]), encoding="utf-8"
    )
    output = tmp_path / "package.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_m67_seed_source_package.py"),
            "--observations",
            str(observations),
            "--output",
            str(output),
            "--created-at",
            "2026-08-21T12:00:00+00:00",
            "--created-by-subject-ref",
            "m67-subject-" + "a" * 64,
            "--source-policy-revision",
            "synthetic-policy-v1",
            "--private-seed-output",
            str(tmp_path / "seed.secret"),
        ],
        check=True,
    )
    package = load(output)
    manifest = package["manifest"]
    assert manifest["state"] == "FROZEN_AWAITING_OWNER_ARTIFACT_APPROVAL"
    assert len(manifest["selected"]) == 24
    assert manifest["reserve"] == []
    assert len(manifest["manifest_hash"]) == 64
    assert package["wildcard_approval_prohibited"] is True
    assert {item["human_conclusion"] for item in package["host_reviews"]} == {"PENDING"}
    assert {item["final_state"] for item in package["host_reviews"]} == {"NOT_APPROVED"}
    assert set(package["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_seed_generation_rejects_person_contact_fields(tmp_path: Path) -> None:
    observations = [synthetic_observation(index) for index in range(24)]
    observations[0]["contact_email"] = "fixture@example.test"
    source = tmp_path / "observations.json"
    source.write_text(json.dumps(observations), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_m67_seed_source_package.py"),
            "--observations",
            str(source),
            "--output",
            str(tmp_path / "package.json"),
            "--created-at",
            "2026-08-21T12:00:00+00:00",
            "--created-by-subject-ref",
            "m67-subject-" + "a" * 64,
            "--source-policy-revision",
            "synthetic-policy-v1",
            "--private-seed-output",
            str(tmp_path / "seed.secret"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "prohibited seed field" in result.stderr


def test_consolidated_environment_signature_does_not_merge_decision_meanings() -> None:
    acceptance = load(DEPLOY / "consolidated-environment-acceptance.template.json")
    decisions = acceptance["decisions"]
    assert [item["decision"] for item in decisions] == ["A-03", "A-04", "A-07", "A-08", "ADR-0071"]
    assert len({item["meaning"] for item in decisions}) == 5
    assert acceptance["single_signature_binds_every_enumerated_decision"] is True
    assert acceptance["decisions_remain_independently_auditable"] is True


def test_plan_record_derives_hashes_and_blocks_destroy(tmp_path: Path) -> None:
    configuration = tmp_path / "config"
    configuration.mkdir()
    (configuration / "main.tf").write_text('resource "aws_s3_bucket" "x" {}\n', encoding="utf-8")
    (configuration / ".terraform.lock.hcl").write_text("locked\n", encoding="utf-8")
    plan_binary = tmp_path / "plan.tfplan"
    plan_binary.write_bytes(b"synthetic-plan")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "resource_changes": [
                    {
                        "address": "aws_s3_bucket.x",
                        "type": "aws_s3_bucket",
                        "change": {"actions": ["delete"]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/create_m67_terraform_plan_record.py"),
            "--plan-binary",
            str(plan_binary),
            "--plan-json",
            str(plan_json),
            "--configuration-root",
            str(configuration),
            "--plan-kind",
            "BOOTSTRAP",
            "--account-id",
            "123456789012",
            "--authenticated-role",
            "synthetic-role",
            "--output",
            str(output),
        ],
        check=True,
    )
    record = load(output)
    assert record["state"] == "BLOCKED"
    assert record["changes"]["destroy"] == 1
    assert "UNEXPECTED_DESTROY_BLOCKS_APPLY" in record["warnings"]
    assert record["real_business_discovery"] == "NOT_AUTHORIZED"


def test_plan_record_allows_read_only_terraform_data_sources(tmp_path: Path) -> None:
    configuration = tmp_path / "config"
    configuration.mkdir()
    (configuration / "main.tf").write_text('data "aws_partition" "current" {}\n', encoding="utf-8")
    (configuration / ".terraform.lock.hcl").write_text("locked\n", encoding="utf-8")
    plan_binary = tmp_path / "plan.tfplan"
    plan_binary.write_bytes(b"synthetic-plan")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "resource_changes": [
                    {
                        "address": "data.aws_iam_policy_document.example",
                        "mode": "data",
                        "type": "aws_iam_policy_document",
                        "change": {"actions": ["read"]},
                    },
                    {
                        "address": "aws_s3_bucket.example",
                        "mode": "managed",
                        "type": "aws_s3_bucket",
                        "change": {"actions": ["create"]},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/create_m67_terraform_plan_record.py"),
            "--plan-binary",
            str(plan_binary),
            "--plan-json",
            str(plan_json),
            "--configuration-root",
            str(configuration),
            "--plan-kind",
            "PHASE1",
            "--account-id",
            "123456789012",
            "--authenticated-role",
            "synthetic-role",
            "--estimated-cost-usd",
            "1",
            "--output",
            str(output),
        ],
        check=True,
    )
    record = load(output)
    assert record["state"] == "READY_FOR_OWNER_APPLY_DECISION"
    assert record["changes"]["create"] == 1
    assert record["prohibited_resources"] == []
