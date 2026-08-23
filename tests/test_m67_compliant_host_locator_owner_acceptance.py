import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def test_owner_acceptance_package_is_ready_but_grants_no_live_authority() -> None:
    value = json.loads(
        (AUTH / "compliant-host-locator-owner-acceptance-ready-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["state"] == "READY_FOR_COMPLIANT_HOST_LOCATOR_OWNER_ACCEPTANCE"
    assert value["locator"]["source_id"] == "OSM_NOMINATIM_PUBLIC_SEARCH_V1"
    assert value["locator"]["persistent_hostname_storage"].startswith("PERMITTED")
    assert value["locator"]["credential_requirements"] == "NONE"
    assert value["locator"]["cost_ceiling_usd"] == 0
    assert value["locator"]["qualified_source_review_required"] is False
    assert value["live_source_operations_performed"] == 0
    assert value["candidate_records_processed"] == 0
    assert set(value["one_shot_grants"].values()) == {"0/1"}
    assert set(value["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_exact_statement_binds_controls_and_preserves_next_gate() -> None:
    value = json.loads(
        (AUTH / "compliant-host-locator-owner-acceptance-ready-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    statement = value["exact_owner_approval_statement"]
    assert "APPROVE_OSM_NOMINATIM_PHASE1_HOST_LOCATOR_SOURCE" in statement
    assert "100-request and 5,000,000-byte aggregate ceilings" in statement
    assert "USD 0 source cost" in statement
    assert "does not authorize any live Nominatim" in statement
    assert "all seven M6.7 permissions remain NOT_AUTHORIZED" in statement
    assert value["next_state_after_acceptance"] == (
        "PREPARE_READY_FOR_LIVE_SEED_ROSTER_ACQUISITION_AUTHORIZATION"
    )
