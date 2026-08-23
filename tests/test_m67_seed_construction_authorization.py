from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def load(name: str) -> dict[str, object]:
    return json.loads((AUTH / name).read_text(encoding="utf-8"))


def test_machine_validator_accepts_reviewed_package() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m67_seed_construction_authorization.py")],
        check=True,
    )


def test_construction_is_offline_one_shot_and_below_discovery_permission() -> None:
    value = load("seed-construction-authorization-ready-2026-08-23.json")
    assert value["grant_type"] == "ONE_SHOT_EXECUTION_GRANT_NOT_A_SUCCESSOR_PERMISSION"
    assert value["scope"]["maximum_terminal_attempts"] == 1
    assert value["input_source"]["acquisition_by_this_grant"] == "PROHIBITED"
    assert value["input_source"]["network_source_access"] == "PROHIBITED"
    assert value["operation_caps"]["dns_queries"] == 0
    assert value["operation_caps"]["http_requests"] == 0
    assert value["operation_caps"]["candidate_observations"] == 100
    assert set(value["permissions_before_during_after"].values()) == {"NOT_AUTHORIZED"}
    assert value["terminal_behavior"]["automatic_next_stage"] is False


def test_input_schema_is_closed_business_only_and_bounded() -> None:
    schema = load("phase1-seed-construction-input-v1.schema.json")
    assert schema["minItems"] == 24
    assert schema["maxItems"] == 100
    item = schema["items"]
    assert item["additionalProperties"] is False
    properties = set(item["properties"])
    prohibited_fragments = {
        "person",
        "contact",
        "email",
        "phone",
        "revenue",
        "headcount",
        "opportunity",
        "crm",
    }
    assert all(
        not any(fragment in field for fragment in prohibited_fragments) for field in properties
    )


def test_host_stubs_cannot_inherit_or_wildcard_approval() -> None:
    template = load("generated-seed-source-package.template.json")
    requirements = template["host_review_requirements"]
    assert requirements["separate_result_per_exact_host"] is True
    assert requirements["wildcard_approval_prohibited"] is True
    assert requirements["blocked_or_uncertain_host_remains_visible"] is True
    assert template["host_reviews"] == []


def test_primary_a_preparation_requires_independent_session_and_grants_nothing() -> None:
    challenge = load("primary-a-independent-authentication-challenge.template.json")
    assert challenge["state"] == "NOT_ISSUED"
    assert challenge["required_independent_session"] is True
    assert challenge["owner_session_prohibited"] is True
    assert challenge["permissions_granted"] == []
