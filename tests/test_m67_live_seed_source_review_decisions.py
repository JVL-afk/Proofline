import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def test_reviewer_decisions_are_preserved_without_permission_change() -> None:
    record = json.loads(
        (AUTH / "live-seed-source-review-decisions-accepted-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["review_kind"] == "SOURCE_GOVERNANCE_NOT_LEGAL_OPINION"
    assert record["decisions"][0]["state"] == "APPROVED_WITH_CONTROLS"
    assert record["decisions"][0]["unconditional_license_grant"] is False
    assert record["decisions"][1]["state"] == "REJECTED"
    assert record["decisions"][1]["persistent_hostname_allowed"] is False
    assert record["live_acquisition_readiness"] == (
        "BLOCKED_PENDING_COMPLIANT_FIRST_PARTY_HOST_LOCATOR"
    )
    assert record["live_operations_performed"] == 0
    assert record["grants_consumed"] is False
    assert set(record["permissions"].values()) == {"NOT_AUTHORIZED"}


def test_tdlr_allowed_fields_are_exact_and_contact_free() -> None:
    record = json.loads(
        (AUTH / "live-seed-source-review-decisions-accepted-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    allowed = record["decisions"][0]["allowed_fields"]
    assert allowed == [
        "license_type",
        "license_number",
        "business_county",
        "business_name",
        "business_city_state_zip",
        "license_expiration_date_mmddccyy",
        "license_subtype",
    ]
    assert all("owner" not in field and "telephone" not in field for field in allowed)
