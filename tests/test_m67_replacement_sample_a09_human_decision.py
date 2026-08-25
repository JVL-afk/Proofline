from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/prepare_m67_replacement_sample_a09_human_decision.py"
SPEC = importlib.util.spec_from_file_location("replacement_a09_human", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_clean_exact_host_evidence_is_only_a_non_authoritative_recommendation() -> None:
    decision = {
        "observations": {
            "robots": {"root_allowed_for_review_agent": True},
            "root": {
                "status": 200,
                "identity_signal": "BUSINESS_NAME_TOKENS_PRESENT",
                "redirect_host": None,
            },
        }
    }
    assert MODULE.recommendation(decision) == "APPROVE_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH"


def test_redirect_requires_successor_host_review() -> None:
    decision = {
        "observations": {
            "robots": {"root_allowed_for_review_agent": True},
            "root": {"status": 301, "redirect_host": "www.example.com"},
        }
    }
    assert MODULE.recommendation(decision) == "REQUIRES_SUCCESSOR_HOST_REVIEW"
