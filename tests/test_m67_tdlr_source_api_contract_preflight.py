from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_m67_tdlr_source_api_contract_preflight.py"
SPEC = importlib.util.spec_from_file_location("tdlr_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = "application/json;charset=utf-8"
        self.headers["Content-Length"] = str(len(body))
        self.headers["X-SODA2-Fields"] = "content-free-metadata"

    def geturl(self) -> str:
        return MODULE.ENDPOINT

    def read(self, maximum: int) -> bytes:
        return self._body[:maximum]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class Opener:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.requests = []

    def open(self, request, timeout: int):
        self.requests.append((request, timeout))
        return Response(self.body)


def _authorization(path: Path) -> None:
    path.write_text(
        json.dumps({
            "event": MODULE.EVENT,
            "state": "APPROVED",
            "exact_executable_sha256": MODULE.sha256_bytes(SCRIPT.read_bytes()),
        }),
        encoding="utf-8",
    )


def test_request_is_one_post_with_exact_bounded_contract(tmp_path: Path) -> None:
    row = {field: f"safe-{field}" for field in MODULE.FIELDS}
    row["license_type"] = "Air Conditioning Contractor"
    opener = Opener(json.dumps([row]).encode())
    authorization = tmp_path / "authorization.json"
    evidence = tmp_path / "evidence.json"
    _authorization(authorization)

    result = MODULE.run(
        authorization,
        evidence,
        opener=opener,
        now=datetime(2026, 8, 24, 8, tzinfo=UTC),
    )

    assert len(opener.requests) == 1
    request = opener.requests[0][0]
    assert request.method == "POST"
    assert request.full_url == MODULE.ENDPOINT
    assert json.loads(request.data) == MODULE.REQUEST_BODY
    assert result["response"]["row_count"] == 1
    assert result["response"]["raw_body_persisted"] is False
    assert "safe-business_name" not in evidence.read_text(encoding="utf-8")


def test_four_byte_values_cannot_be_treated_as_row_bearing() -> None:
    for value in (b"null", b"[ ]\n"):
        try:
            MODULE.validate_rows(json.loads(value))
        except RuntimeError:
            pass
        else:
            raise AssertionError("non-row-bearing four-byte JSON must fail closed")


def test_contact_shape_fails_closed() -> None:
    row = {field: f"safe-{field}" for field in MODULE.FIELDS}
    row["license_type"] = "Air Conditioning Contractor"
    row["business_name"] = "unsafe@example.com"
    try:
        MODULE.validate_rows([row])
    except RuntimeError as exc:
        assert "contact-shaped" in str(exc)
    else:
        raise AssertionError("contact-shaped content must fail closed")
