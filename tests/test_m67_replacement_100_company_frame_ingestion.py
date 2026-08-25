from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/run_m67_replacement_100_company_frame_ingestion.py"
SPEC = importlib.util.spec_from_file_location("replacement_frame", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_website_normalization_preserves_www_and_strips_nonhost_components() -> None:
    host, findings = MODULE.normalize_website("HTTPS://www.Example.com/services?q=1#top")
    assert host == "www.example.com"
    assert findings["www_preserved"] is True
    assert findings["path_stripped"] is True
    assert findings["query_stripped"] is True
    assert findings["fragment_stripped"] is True


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com",
        "https://127.0.0.1",
        "https://localhost",
        "https://business.facebook.com",
        "ftp://example.com",
    ],
)
def test_unsafe_website_fails_closed(url: str) -> None:
    with pytest.raises(MODULE.ValidationFailure):
        MODULE.normalize_website(url)


def test_seeded_order_is_deterministic_for_same_frame_and_seed() -> None:
    rows = [
        {
            "submission_index": index,
            "company_name": f"Company {index}",
            "company_website_original": f"https://company-{index}.example",
            "county": "Travis",
            "city": "Austin",
            "normalized_company_name_key": f"company {index}",
            "candidate_hostname": f"company-{index}.example",
            "source_row_sha256": "0" * 64,
        }
        for index in range(1, 101)
    ]
    frame, frame_hash = MODULE.build_frame(rows)
    first, _ = MODULE.build_ordered_package(
        frame,
        frame_hash,
        b"x" * 32,
        input_hash="1" * 64,
        attestation_hash="2" * 64,
        created_at="2026-08-25T00:00:00Z",
    )
    second, _ = MODULE.build_ordered_package(
        frame,
        frame_hash,
        b"x" * 32,
        input_hash="1" * 64,
        attestation_hash="2" * 64,
        created_at="2026-08-25T00:00:00Z",
    )
    assert first["slots"] == second["slots"]
    assert len(first["slots"]) == 24
    assert len(first["frame_remainder"]) == 76
    assert first["reserve_for_outcome_replacement"] == []
