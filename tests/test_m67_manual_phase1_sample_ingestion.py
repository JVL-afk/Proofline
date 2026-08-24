from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "run_m67_manual_phase1_sample_ingestion.py"
SPEC = importlib.util.spec_from_file_location("manual_sample", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample() -> dict[str, object]:
    return {
        "record_type": "M67_MANUAL_PHASE1_SAMPLE_INPUT",
        "schema_version": "1.0.0",
        "sample_source": MODULE.SAMPLE_SOURCE,
        "automated_tdlr_discovery_validated": False,
        "candidates": [
            {
                "submission_index": index,
                "public_business_name": f"Synthetic HVAC Business {index:02d} LLC",
                "texas_city_or_service_area": "Austin, Texas",
                "tdlr_reference": {
                    "dataset_id": "7358-krk7",
                    "license_number": f"TACLA{index:05d}",
                    "source_record_locator": f"TDLR_SYNTHETIC_REFERENCE_{index:02d}",
                },
                "candidate_hostname": f"synthetic-hvac-{index:02d}.example",
            }
            for index in range(1, 25)
        ],
    }


def attestation(input_sha256: str) -> dict[str, object]:
    return {
        "record_type": "M67_MANUAL_PHASE1_SAMPLE_OWNER_ATTESTATION",
        "schema_version": "1.0.0",
        "state": "SIGNED",
        "actor_ref": "OWNER_ACTOR",
        "input_artifact_sha256": input_sha256,
        "candidate_count": 24,
        "selected_before_m1_m5": True,
        "selection_not_based_on_perceived_opportunity": True,
        "selection_not_based_on_website_weakness": True,
        "selection_not_based_on_sales_attractiveness": True,
        "selection_not_based_on_expected_result": True,
        "business_only_confirmed": True,
        "person_contact_data_absent": True,
        "no_outcome_based_exclusion_or_replacement": True,
        "candidate_hostnames_manually_identified": True,
        "automated_tdlr_discovery_validated": False,
        "phase1_sample_source": MODULE.SAMPLE_SOURCE,
        "attested_at": "2026-08-24T12:00:00Z",
        "exact_affirmation": MODULE.AFFIRMATION,
    }


def test_exact_24_are_frozen_and_ordered_without_exclusion() -> None:
    candidates = MODULE.validate_input(sample())
    package, evidence = MODULE.build_package(
        candidates,
        input_sha256="a" * 64,
        attestation_sha256="b" * 64,
        created_at="2026-08-24T12:00:00Z",
        seed=bytes(range(32)),
    )
    assert sorted(row["slot"] for row in package["slots"]) == list(range(1, 25))
    assert {row["submission_index"] for row in package["slots"]} == set(range(1, 25))
    assert package["reserve"] == []
    assert package["AUTOMATED_TDLR_DISCOVERY_VALIDATED"] is False
    assert package["PHASE1_SAMPLE_SOURCE"] == MODULE.SAMPLE_SOURCE
    assert package["outcome_based_replacement_prohibited"] is True
    assert evidence["seed_generated_after_frame_freeze"] is True
    assert set(package["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_duplicate_hostname_is_retained_not_outcome_filtered() -> None:
    value = sample()
    value["candidates"][1]["candidate_hostname"] = value["candidates"][0]["candidate_hostname"]
    candidates = MODULE.validate_input(value)
    package, _ = MODULE.build_package(
        candidates,
        input_sha256="a" * 64,
        attestation_sha256="b" * 64,
        created_at="2026-08-24T12:00:00Z",
        seed=b"x" * 32,
    )
    assert len(package["slots"]) == 24


@pytest.mark.parametrize(
    ("field", "unsafe"),
    (
        ("public_business_name", "person@example.com"),
        ("texas_city_or_service_area", "Call 512-555-1212"),
        ("candidate_hostname", "https://example.com/path"),
    ),
)
def test_contact_shape_or_non_hostname_fails_closed(field: str, unsafe: str) -> None:
    value = sample()
    value["candidates"][0][field] = unsafe
    with pytest.raises(MODULE.ValidationFailure):
        MODULE.validate_input(value)


def test_attestation_must_bind_exact_preparse_hash_and_affirmation() -> None:
    value = attestation("a" * 64)
    MODULE.validate_attestation(value, "a" * 64)
    value["selection_not_based_on_expected_result"] = False
    with pytest.raises(MODULE.ValidationFailure):
        MODULE.validate_attestation(value, "a" * 64)


def test_runner_contains_no_network_client_imports() -> None:
    source = PATH.read_text(encoding="utf-8")
    for forbidden in ("urllib", "requests", "httpx", "socket", "boto3"):
        assert f"import {forbidden}" not in source


def test_owner_input_template_is_exactly_24_and_ingestible_after_replacement() -> None:
    template = MODULE.json.loads(
        (ROOT / "docs/readiness/m6.7-authorization/manual-phase1-sample-input-v1.template.json")
        .read_text(encoding="utf-8")
    )
    assert len(MODULE.validate_input(template)) == 24
