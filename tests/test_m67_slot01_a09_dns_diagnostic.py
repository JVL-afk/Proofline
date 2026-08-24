from __future__ import annotations

import importlib.util
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/run_m67_slot01_a09_dns_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("slot01_dns", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_answers_are_content_free() -> None:
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 0)),
    ]
    evidence = MODULE.public_answer_evidence(answers)
    assert evidence["answer_count"] == 2
    assert evidence["address_families"] == ["IPv4", "IPv6"]
    assert "8.8.8.8" not in str(evidence)


def test_private_answer_fails_closed() -> None:
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with pytest.raises(RuntimeError, match="non-public"):
        MODULE.public_answer_evidence(answers)
