from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def load(name: str) -> dict[str, object]:
    return json.loads((AUTH / name).read_text(encoding="utf-8"))


def test_machine_validator_accepts_offline_acquisition_gate() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m67_seed_source_acquisition.py")],
        check=True,
    )


def test_source_set_is_one_offline_class_with_no_network_wildcard() -> None:
    value = load("seed-source-acquisition-authorization-ready-2026-08-23.json")
    source = value["source_set"][0]
    assert source["source_class"] == "OWNER_CONTROLLED_FIELD_LIMITED_OFFLINE_BUSINESS_ROSTER_V1"
    assert source["exact_instances_allowed"] == 1
    assert source["network_hosts"] == []
    assert source["wildcard_hosts"] is False
    assert source["robots_state"] == "NOT_APPLICABLE_NO_NETWORK"


def test_limits_are_zero_cost_network_browser_and_ai() -> None:
    limits = load("seed-source-acquisition-authorization-ready-2026-08-23.json")["limits"]
    assert limits["input_artifacts"] == 1
    assert limits["input_bytes"] == 5_000_000
    assert limits["external_requests"] == 0
    assert limits["dns_queries"] == 0
    assert limits["http_attempts"] == 0
    assert limits["retries"] == 0
    assert limits["ai_calls"] == 0
    assert limits["browser_sessions"] == 0
    assert limits["monetary_cost_usd"] == 0


def test_minimization_and_anticherry_picking_fail_closed() -> None:
    value = load("seed-source-acquisition-authorization-ready-2026-08-23.json")
    assert value["minimization"]["raw_input_durable_copy"] is False
    assert value["minimization"]["unsafe_or_unprovable_projection"].startswith("FAIL_CLOSED")
    assert value["anti_cherry_picking"]["complete_predeclared_source_frame_required"] is True
    assert value["anti_cherry_picking"]["frame_cap_before_filtering"] == 100
    assert value["anti_cherry_picking"]["outcome_or_opportunity_observation"] == "PROHIBITED"


def test_permissions_and_primary_a_gate_remain_separate() -> None:
    value = load("seed-source-acquisition-authorization-ready-2026-08-23.json")
    assert set(value["permissions_before_during_after"].values()) == {"NOT_AUTHORIZED"}
    assert value["primary_a"]["required_for_this_gate"] is False
    assert value["primary_a"]["required_for_candidate_package_owner_review"] is False
    assert value["primary_a"]["mandatory_gate"] == "LATER_REAL_BUSINESS_DISCOVERY_ROLE_RELEASE"
    assert value["primary_a"]["owner_actor_substitution_prohibited"] is True
