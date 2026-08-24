from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_m67_tdlr_taxonomy_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("tdlr_taxonomy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = "application/json;charset=utf-8"
        self.headers["Content-Length"] = str(len(body))

    def geturl(self) -> str:
        return MODULE.ENDPOINT

    def read(self, maximum: int) -> bytes:
        return self.body[:maximum]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class Opener:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def open(self, request, timeout: int):
        self.calls += 1
        assert request.method == "POST"
        assert json.loads(request.data) == MODULE.REQUEST_BODY
        return Response(self.body)


def authorization(path: Path) -> None:
    path.write_text(json.dumps({
        "event": MODULE.EVENT,
        "state": "APPROVED",
        "exact_executable_sha256": MODULE.sha256_bytes(SCRIPT.read_bytes()),
    }), encoding="utf-8")


def test_query_requests_only_classification_and_count() -> None:
    assert MODULE.REQUEST_BODY["page"] == {"pageNumber": 1, "pageSize": 250}
    assert "license_type" in MODULE.QUERY
    assert "count(*)" in MODULE.QUERY
    for prohibited in (
        "business_name", "license_number", "business_county", "business_city_state_zip",
        "owner", "telephone", "email", "license_subtype",
    ):
        assert prohibited not in MODULE.QUERY


def test_classification_values_and_counts_are_the_only_durable_source_values(tmp_path: Path) -> None:
    body = json.dumps([
        {"license_type": "Alpha Classification", "record_count": "3"},
        {"license_type": "Refrigeration Contractor", "record_count": "7"},
    ]).encode()
    auth = tmp_path / "auth.json"
    evidence_path = tmp_path / "evidence.json"
    authorization(auth)
    opener = Opener(body)
    result = MODULE.run(
        auth,
        evidence_path,
        opener=opener,
        now=datetime(2026, 8, 24, 9, tzinfo=UTC),
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert opener.calls == 1
    assert result["state"] == "TDLR_TAXONOMY_DIAGNOSTIC_PASS_PENDING_INTERPRETATION"
    values = evidence["taxonomy_validation"]["classification_values"]
    assert values[1]["observed_dataset_value"] == "Refrigeration Contractor"
    assert values[1]["observed_count"] == 7
    assert values[1]["official_terminology_hits"] == ["refrigeration", "contractor"]
    assert "business_name" not in json.dumps(evidence)


def test_transport_metadata_survives_taxonomy_schema_failure(tmp_path: Path) -> None:
    raw = json.dumps([{"license_type": "Only Type"}]).encode()
    auth = tmp_path / "auth.json"
    evidence_path = tmp_path / "evidence.json"
    authorization(auth)
    result = MODULE.run(
        auth,
        evidence_path,
        opener=Opener(raw),
        now=datetime(2026, 8, 24, 9, tzinfo=UTC),
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result["state"] == "TDLR_TAXONOMY_DIAGNOSTIC_FAIL"
    assert evidence["failure_stage"] == "TAXONOMY_SCHEMA"
    assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
    assert evidence["invariants"]["RESPONSE_METADATA_CAPTURE_BEFORE_SCHEMA_VALIDATION"] == "PASS"


def test_taxonomy_validation_rejects_contact_shape_and_unstable_order() -> None:
    unsafe_cases = (
        [{"license_type": "contact@example.com", "record_count": "1"}],
        [
            {"license_type": "Zulu", "record_count": "1"},
            {"license_type": "Alpha", "record_count": "1"},
        ],
    )
    for rows in unsafe_cases:
        try:
            MODULE.validate_taxonomy(rows)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unsafe taxonomy result must fail closed")


def test_taxonomy_validation_fails_closed_at_page_ceiling() -> None:
    rows = [
        {"license_type": f"Type {index:03d}", "record_count": "1"}
        for index in range(MODULE.PAGE_SIZE)
    ]

    try:
        MODULE.validate_taxonomy(rows)
    except RuntimeError as error:
        assert "completeness is unproven" in str(error)
    else:
        raise AssertionError("a full page cannot prove exhaustive taxonomy")
