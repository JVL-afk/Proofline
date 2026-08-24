from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_m67_tdlr_response_shape_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("tdlr_shape", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = "application/json;charset=utf-8"
        self.headers["Content-Length"] = str(len(body))
        self.headers["X-Socrata-RequestId"] = "safe-request-id"

    def geturl(self) -> str:
        return MODULE.ENDPOINT

    def read(self, maximum: int) -> bytes:
        return self.body[:maximum]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class Opener:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls = 0

    def open(self, request, timeout: int):
        self.calls += 1
        assert request.method == "POST"
        assert json.loads(request.data) == MODULE.REQUEST_BODY
        return self.response


def authorization(path: Path) -> None:
    path.write_text(json.dumps({
        "event": MODULE.EVENT,
        "state": "APPROVED",
        "exact_executable_sha256": MODULE.sha256_bytes(SCRIPT.read_bytes()),
    }), encoding="utf-8")


def execute(tmp_path: Path, value: object):
    raw = json.dumps(value).encode()
    auth = tmp_path / "auth.json"
    evidence = tmp_path / "evidence.json"
    authorization(auth)
    result = MODULE.run(
        auth,
        evidence,
        opener=Opener(Response(raw)),
        now=datetime(2026, 8, 24, 8, tzinfo=UTC),
    )
    return result, json.loads(evidence.read_text(encoding="utf-8")), raw


def safe_row() -> dict[str, str]:
    row = {field: f"private-value-{field}" for field in MODULE.FIELDS}
    row["license_type"] = "Air Conditioning Contractor"
    return row


def test_array_contract_passes_without_persisting_values(tmp_path: Path) -> None:
    result, evidence, raw = execute(tmp_path, [safe_row()])
    assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_PASS"
    assert evidence["response"]["top_level_json_type"] == "ARRAY"
    assert evidence["response"]["array_length"] == 1
    assert evidence["parser_schema_result"]["row_array_location"] == "$"
    assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
    assert "private-value-business_name" not in json.dumps(evidence)


def test_wrapper_contract_is_identified_content_free(tmp_path: Path) -> None:
    result, evidence, _raw = execute(tmp_path, {"data": [safe_row()], "metadata": {"x": 1}})
    assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_PASS"
    assert evidence["response"]["top_level_json_type"] == "OBJECT"
    assert evidence["response"]["top_level_object_keys"] == ["data", "metadata"]
    assert evidence["response"]["list_valued_top_level_keys"] == ["data"]
    assert evidence["response"]["wrapped_array_lengths"] == {"data": 1}
    assert evidence["response"]["wrapped_array_first_row_field_names"]["data"] == sorted(
        MODULE.FIELDS
    )
    assert evidence["parser_schema_result"]["row_array_location"] == "$.data"


def test_metadata_survives_error_object_schema_failure(tmp_path: Path) -> None:
    result, evidence, raw = execute(tmp_path, {"errorCode": "example", "message": "not retained"})
    assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
    assert evidence["failure_stage"] == "ROW_ARRAY_OR_FIELD_SCHEMA"
    assert evidence["response"]["status"] == 200
    assert evidence["response"]["actual_response_byte_length"] == len(raw)
    assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
    assert evidence["response"]["top_level_object_keys"] == ["errorCode", "message"]
    assert "not retained" not in json.dumps(evidence)


def test_metadata_survives_null_and_string_schema_failures(tmp_path: Path) -> None:
    for index, value in enumerate((None, "unexpected")):
        case = tmp_path / str(index)
        case.mkdir()
        result, evidence, raw = execute(case, value)
        assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
        assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
        assert evidence["response"]["json_parse_success"] is True
        assert evidence["failure_stage"] == "ROW_ARRAY_OR_FIELD_SCHEMA"


def test_metadata_survives_missing_field_schema_failure(tmp_path: Path) -> None:
    row = safe_row()
    del row["license_subtype"]
    result, evidence, _raw = execute(tmp_path, [row])
    assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
    assert evidence["parser_schema_result"]["parser_schema_result"] == "FAIL_EXPECTED_FIELDS_MISSING"
    assert evidence["parser_schema_result"]["first_row_missing_fields"] == ["license_subtype"]
    assert evidence["invariants"]["RESPONSE_METADATA_CAPTURE_BEFORE_SCHEMA_VALIDATION"] == "PASS"


def test_metadata_survives_json_parse_failure(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    evidence_path = tmp_path / "evidence.json"
    authorization(auth)
    raw = b"not-json"
    result = MODULE.run(
        auth,
        evidence_path,
        opener=Opener(Response(raw)),
        now=datetime(2026, 8, 24, 8, tzinfo=UTC),
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result["state"] == "TDLR_RESPONSE_SHAPE_DIAGNOSTIC_FAIL"
    assert evidence["failure_stage"] == "JSON_PARSE"
    assert evidence["response"]["actual_response_byte_length"] == len(raw)
    assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
    assert evidence["response"]["json_parse_success"] is False


def test_pre_schema_seal_survives_unexpected_schema_exception(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    evidence_path = tmp_path / "evidence.json"
    authorization(auth)
    raw = json.dumps([safe_row()]).encode()
    original = MODULE.schema_result

    def explode(_parsed):
        raise RuntimeError("synthetic schema failure")

    MODULE.schema_result = explode
    try:
        try:
            MODULE.run(
                auth,
                evidence_path,
                opener=Opener(Response(raw)),
                now=datetime(2026, 8, 24, 8, tzinfo=UTC),
            )
        except RuntimeError as exc:
            assert str(exc) == "synthetic schema failure"
        else:
            raise AssertionError("schema exception should propagate")
    finally:
        MODULE.schema_result = original

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["state"] == "TDLR_RESPONSE_SHAPE_CAPTURED_PENDING_SCHEMA_VALIDATION"
    assert evidence["response"]["status"] == 200
    assert evidence["response"]["raw_body_sha256"] == MODULE.sha256_bytes(raw)
    assert evidence["parser_schema_result"] == "NOT_RUN_METADATA_ALREADY_SEALED"
