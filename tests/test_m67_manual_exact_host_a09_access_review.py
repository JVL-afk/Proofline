from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/run_m67_manual_exact_host_a09_access_review.py"
SPEC = importlib.util.spec_from_file_location("a09_access", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_legal_path_must_remain_same_host_https_and_query_free() -> None:
    links = [
        ("https://other.example/terms", "Terms"),
        ("/terms?tracking=1", "Terms"),
        ("/legal", "Legal"),
    ]
    assert MODULE.safe_legal_path("example.com", links) == "/legal"


def test_identity_signal_persists_only_a_classification() -> None:
    result = MODULE.identity_signal("Bob Smith Air Conditioning", "Welcome to Bob Smith")
    assert result == "BUSINESS_NAME_TOKENS_PRESENT"
    assert "Bob" not in result


def test_restriction_flags_do_not_return_source_text() -> None:
    source = "Automated scraping and commercial robots are restricted."
    flags = MODULE.restriction_flags(source)
    assert flags == ["AUTOMATED", "SCRAP", "ROBOT", "COMMERCIAL"]
    assert source not in flags


def test_no_redirect_handler_never_creates_followup_request() -> None:
    assert MODULE.NoRedirect().redirect_request() is None
