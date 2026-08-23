import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs" / "readiness" / "m6.7-authorization"


def test_exact_source_successor_remains_fail_closed() -> None:
    record = json.loads(
        (AUTH / "live-seed-roster-exact-source-review-successor-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["state"] == (
        "BLOCKED_PENDING_QUALIFIED_SOURCE_RIGHTS_REVIEW_AND_LOCATOR_CONTRACT_ACCEPTANCE"
    )
    assert record["primary_a_identity_prerequisite"] == (
        "PRIMARY_A_INDEPENDENT_AUTHENTICATION_ACCEPTED"
    )
    assert record["live_candidate_source_operations_performed"] == 0
    assert record["candidate_records_read"] == 0
    assert record["business_websites_accessed"] == 0
    assert record["owner_live_acquisition_approval_statement"] is None
    assert set(record["permissions"].values()) == {"NOT_AUTHORIZED"}
    assert record["unconsumed_grants"] == {
        "offline_seed_source_acquisition": "0/1",
        "bounded_seed_construction": "0/1",
    }


def test_tdlr_projection_excludes_contact_and_owner_fields() -> None:
    record = json.loads(
        (AUTH / "live-seed-roster-exact-source-review-successor-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    tdlr = record["exact_sources"][0]
    allowed = set(tdlr["safe_query_projection_if_later_approved"])
    prohibited = set(tdlr["never_query_or_durably_project"])
    assert allowed.isdisjoint(prohibited)
    assert {"owner_name", "owner_telephone", "business_telephone"} <= prohibited
    assert "business_name" in allowed


def test_locator_is_non_ai_and_per_host_review_remains_separate() -> None:
    record = json.loads(
        (AUTH / "live-seed-roster-exact-source-review-successor-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    brave = record["exact_sources"][1]
    assert brave["source_id"] == "BRAVE_SEARCH_API_HOST_LOCATOR_V1"
    assert "NO_AI_OR_ANSWER_ENDPOINT" in brave["access_method"]
    assert record["per_host_boundary"]["locator_result_is_not_host_approval"] is True
    assert record["per_host_boundary"]["wildcard_approval"] is False
    assert record["proposed_limits"]["ai_calls"] == 0
    assert record["proposed_limits"]["browser_sessions"] == 0


def test_successor_package_binds_exact_review_artifacts() -> None:
    package = json.loads(
        (AUTH / "live-seed-roster-exact-source-review-successor-package-2026-08-23.json").read_text(
            encoding="utf-8"
        )
    )
    for artifact in package["artifacts"]:
        content = (ROOT / artifact["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
    assert package["candidate_source_requests"] == 0
    assert package["candidate_rows_read"] == 0
    assert package["business_hosts_accessed"] == 0
    assert package["approval_statement_emitted"] is False
    assert package["permissions_changed"] is False
