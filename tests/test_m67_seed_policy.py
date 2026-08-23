from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GEN = runpy.run_path(str(ROOT / "scripts/generate_m67_seed_source_package.py"))
build_package = GEN["build_package"]
freeze_frame = GEN["freeze_frame"]


def observation(index: int) -> dict[str, object]:
    fragment = f"business-{index}"
    host = f"business-{index}.example.test"
    return {
        "public_business_name": f"Synthetic Commercial HVAC {index}",
        "texas_city_or_service_area": "Synthetic, TX",
        "first_party_host_candidate": host,
        "organization_group_hint": f"organization-{index}",
        "lead_flow_unit_hint": f"flow-{index}",
        "eligibility_observations": {
            "identity": [fragment],
            "texas": ["Texas fixture"],
            "commercial_hvac": ["commercial HVAC fixture"],
            "b2b": ["B2B fixture"],
            "operational": ["operational fixture"],
            "first_party_host": [host],
        },
        "provenance": [
            {
                "source_id": f"source-{index}",
                "source_artifact_ref": f"artifact-{index}",
                "source_artifact_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
                "locator": f"fixture:{index}",
                "observed_at": "2026-08-23T00:00:00Z",
            }
        ],
    }


def package(items: list[dict[str, object]], seed: bytes = b"s" * 32) -> dict[str, object]:
    return build_package(
        items,
        created_at="2026-08-23T00:00:00Z",
        created_by_subject_ref="m67-subject-fixture",
        source_policy_revision="a09-seed-fixture",
        selection_seed=seed,
    )


def test_frame_and_order_are_input_order_independent() -> None:
    items = [observation(index) for index in range(30)]
    first = package(items)
    second = package(list(reversed(items)))
    assert first["manifest"]["frozen_frame_hash"] == second["manifest"]["frozen_frame_hash"]
    assert [x["candidate_ref"] for x in first["manifest"]["selected"]] == [
        x["candidate_ref"] for x in second["manifest"]["selected"]
    ]


def test_seed_is_not_part_of_frozen_frame() -> None:
    items = [observation(index) for index in range(30)]
    first = package(items, b"a" * 32)
    second = package(items, b"b" * 32)
    assert first["manifest"]["frozen_frame_hash"] == second["manifest"]["frozen_frame_hash"]
    assert first["manifest"]["seed_commitment"] != second["manifest"]["seed_commitment"]


def test_duplicate_host_is_deterministically_excluded() -> None:
    items = [observation(index) for index in range(25)]
    items[24]["first_party_host_candidate"] = items[0]["first_party_host_candidate"]
    items[24]["eligibility_observations"]["first_party_host"] = [
        items[0]["first_party_host_candidate"]
    ]
    frame = freeze_frame(items, source_policy_revision="a09-seed-fixture")
    assert len(frame.candidates) == 24
    assert any("DUPLICATE_EXACT_HOST" in item["reasons"] for item in frame.decisions)


def test_ambiguous_identity_never_silently_enters_frame() -> None:
    items = [observation(index) for index in range(25)]
    items[24]["identity_ambiguous"] = True
    frame = freeze_frame(items, source_policy_revision="a09-seed-fixture")
    assert len(frame.candidates) == 24
    assert any(item["state"] == "REVIEW_REQUIRED" for item in frame.decisions)


def test_fewer_than_24_after_deduplication_fails_closed() -> None:
    items = [observation(index) for index in range(24)]
    items[23]["first_party_host_candidate"] = items[0]["first_party_host_candidate"]
    items[23]["eligibility_observations"]["first_party_host"] = [
        items[0]["first_party_host_candidate"]
    ]
    with pytest.raises(ValueError, match="fewer than 24"):
        freeze_frame(items, source_policy_revision="a09-seed-fixture")


@pytest.mark.parametrize("prohibited", ["human@example.test", "+1 512-555-0199"])
def test_contact_shaped_values_fail_closed(prohibited: str) -> None:
    items = [observation(index) for index in range(24)]
    items[0]["eligibility_observations"]["identity"] = [prohibited]
    with pytest.raises(ValueError, match="person/contact-shaped"):
        freeze_frame(items, source_policy_revision="a09-seed-fixture")


def test_host_reviews_are_enumerated_and_unapproved() -> None:
    result = package([observation(index) for index in range(24)])
    assert result["state"] == "MANDATORY_STOP_AWAITING_SEED_ARTIFACT_AND_HOST_APPROVALS"
    assert len(result["host_reviews"]) == 24
    for review in result["host_reviews"]:
        assert review["terms_review"] == "NOT_REVIEWED"
        assert review["robots_review"] == "NOT_REVIEWED"
        assert review["access_restrictions_review"] == "NOT_REVIEWED"
        assert review["copyright_contract_review"] == "NOT_REVIEWED"
        assert review["final_state"] == "NOT_APPROVED"
    assert set(result["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_ready_policy_hashes_and_authority_boundary_are_valid() -> None:
    auth = ROOT / "docs" / "readiness" / "m6.7-authorization"
    path = auth / "seed-generator-source-policy-ready-2026-08-23.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    expected_configuration = policy.pop("configuration_hash")
    assert (
        expected_configuration
        == hashlib.sha256(
            json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    for key, relative in {
        "generator_sha256": ROOT / policy["artifact_bindings"]["generator"],
        "schema_sha256": ROOT / policy["artifact_bindings"]["schema"],
        "policy_sha256": ROOT / policy["artifact_bindings"]["policy"],
        "source_policy_sha256": ROOT / policy["artifact_bindings"]["source_policy"],
        "primary_a_step_sha256": ROOT / policy["artifact_bindings"]["primary_a_step"],
        "empty_template_sha256": ROOT / policy["artifact_bindings"]["empty_template"],
    }.items():
        assert policy["artifact_bindings"][key] == hashlib.sha256(relative.read_bytes()).hexdigest()
    assert policy["state"] == "READY_FOR_SEED_POLICY_OWNER_APPROVAL"
    assert policy["real_candidates_present"] == 0
    assert policy["live_source_operations"] == 0
    assert set(policy["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_primary_a_remains_independent_and_owner_approval_grants_policy_only() -> None:
    auth = ROOT / "docs" / "readiness" / "m6.7-authorization"
    primary = json.loads(
        (auth / "primary-a-independent-authentication-step-2026-08-23.json").read_text()
    )
    approval = json.loads((auth / "seed-policy-owner-approval-ready-2026-08-23.json").read_text())
    assert primary["state"] == "PENDING_INDEPENDENT_AUTHENTICATION"
    assert primary["owner_actor_substitution_prohibited"] is True
    assert primary["permissions_granted"] == []
    assert approval["state"] == "READY_FOR_SEED_POLICY_OWNER_APPROVAL"
    assert approval["approval_effect"].endswith("POLICY")
    assert "DOES_NOT_AUTHORIZE_SEED_CONSTRUCTION" in approval["explicit_non_effects"]
