from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/prepare_m67_manual_exact_host_a09_review.py"
SPEC = importlib.util.spec_from_file_location("a09", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def package(host: str = "example-hvac.com") -> dict[str, object]:
    return {
        "package_sha256": MODULE.EXPECTED_PACKAGE_SEMANTIC_SHA256,
        "slots": [
            {"slot": index, "public_business_name": f"Business {index}", "candidate_hostname": host if index == 1 else f"business-{index}.example"}
            for index in range(1, 25)
        ],
    }


def test_offline_review_never_silently_approves_unknown_host() -> None:
    review, summary = MODULE.prepare(package())
    assert len(review["decisions"]) == 24
    assert {row["decision"] for row in review["decisions"]} == {"REQUIRES_HUMAN_REVIEW"}
    assert summary["approved_for_bounded_first_party_public_research"] == 0
    assert summary["network_operations"] == 0


def test_prohibited_third_party_host_is_rejected() -> None:
    review, summary = MODULE.prepare(package("business.facebook.com"))
    assert review["decisions"][0]["decision"] == "REJECTED"
    assert "PROHIBITED_THIRD_PARTY_HOST_CATEGORY" in review["decisions"][0]["reasons"]
    assert summary["rejected"] == 1


def test_ip_local_and_malformed_hosts_are_rejected() -> None:
    for host in ("127.0.0.1", "localhost.local", "https://example.com/path"):
        safe, reasons = MODULE.structurally_safe(host)
        assert not safe
        assert reasons


def test_slot_mapping_must_remain_exactly_1_through_24() -> None:
    value = package()
    value["slots"][0]["slot"] = 2
    try:
        MODULE.prepare(value)
    except ValueError as error:
        assert "slot mapping" in str(error)
    else:
        raise AssertionError("reordered slots must fail closed")
