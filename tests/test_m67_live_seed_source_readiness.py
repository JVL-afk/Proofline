from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def load(name: str) -> dict[str, object]:
    return json.loads((AUTH / name).read_text(encoding="utf-8"))


def test_live_seed_source_gate_validator() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m67_live_seed_source_readiness.py")],
        check=True,
    )


def test_tdlr_is_not_inferred_to_support_uncaptured_fields() -> None:
    value = load("live-seed-roster-source-review-blocker-2026-08-23.json")
    support = value["tdlr_field_support"]
    assert support["public_business_name"].startswith("NOT_VERIFIED")
    assert support["first_party_host_candidate"].startswith("NOT_SUPPORTED")
    assert support["b2b_evidence"] == "NOT_SUPPORTED"
    assert support["organization_grouping_or_franchise_hint"] == "NOT_SUPPORTED"
    assert support["business_entity_vs_natural_person_discriminator"] == (
        "NOT_VERIFIED_CRITICAL_PRIVACY_BLOCKER"
    )


def test_no_wildcard_source_or_live_authority_exists() -> None:
    value = load("live-seed-roster-source-review-blocker-2026-08-23.json")
    assert value["live_source_operations_performed"] == 0
    assert value["owner_approval_statement"] is None
    assert set(value["permissions"].values()) == {"NOT_AUTHORIZED"}
    assert set(value["unconsumed_grants"].values()) == {"0/1"}
    for source in value["source_candidates"]:
        assert source["a09_state"] not in {"APPROVED", "AUTHORIZED"}
        assert "WILDCARD" not in source["source_id"]


def test_minimization_and_anticherry_picking_remain_fail_closed() -> None:
    value = load("live-seed-roster-source-review-blocker-2026-08-23.json")
    minimization = value["minimization"]
    anti = value["anti_cherry_picking"]
    assert minimization["unsafe_or_unprovable_result"].startswith("QUARANTINE")
    assert "PERSON_NAMES" in minimization["durable_prohibited"]
    assert "INDIVIDUAL_LICENSE_RECORDS" in minimization["durable_prohibited"]
    assert anti["source_snapshot_and_cutoff_frozen_before_content_classification"] is True
    assert anti["opportunity_site_quality_contactability_and_value_signals_prohibited"] is True
    assert anti["outcome_based_replacement_prohibited"] is True


def test_primary_a_is_required_at_the_live_discovery_release() -> None:
    value = load("live-seed-roster-source-review-blocker-2026-08-23.json")
    role = load("primary-a-live-discovery-role-gate-2026-08-23.json")
    gate = value["role_and_permission_gate"]
    assert gate["operation_semantics"] == "REAL_BUSINESS_DISCOVERY"
    assert gate["temporary_permission_bypass_allowed"] is False
    assert gate["primary_a_required_before_live_acquisition_authorization"] is True
    assert role["state"] == "REQUIRED_PENDING_INDEPENDENT_AUTHENTICATION"
    assert role["owner_actor_substitution_prohibited"] is True
    assert role["permissions_granted"] == []


def test_proposed_bounds_fit_frozen_capacity_and_cost_zero() -> None:
    limits = load("live-seed-roster-source-review-blocker-2026-08-23.json")[
        "proposed_limits_after_source_approval"
    ]
    assert limits["source_records_considered"] == 500
    assert limits["roster_observations_max"] == 100
    assert limits["logical_http_requests"] == 120
    assert limits["total_attempts"] == 360
    assert limits["aggregate_response_bytes"] == 36_000_000
    assert limits["concurrency"] == 1
    assert limits["ai_calls"] == 0
    assert limits["browser_sessions"] == 0
    assert limits["monetary_cost_usd"] == 0


def test_review_package_is_blocked_and_non_authorizing() -> None:
    package = load("live-seed-roster-source-review-package-2026-08-23.json")
    assert package["state"].startswith("BLOCKED_PENDING_TDLR")
    assert package["live_source_operations"] == 0
    assert package["approval_statement_emitted"] is False
    assert package["offline_acquisition_grant_consumed"] is False
    assert package["bounded_seed_construction_grant_consumed"] is False
    assert package["permissions_changed"] is False
