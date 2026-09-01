"""Deterministic canonical serialization + SHA-256 for the M6.8-2 audit chain.

Every hash in the generation record chain is computed here so replay is exact:
the same inputs always produce the same bytes and therefore the same digest.
No randomness, no wall-clock, no dict-ordering dependence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any


def _plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace, str() fallback."""

    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chain_hash(previous_record_hash: str, record_body: Any) -> str:
    """Hash of one audit record, binding it to its predecessor."""

    return hashlib.sha256(
        (previous_record_hash + "\n" + canonical_json(record_body)).encode("utf-8")
    ).hexdigest()


GENESIS_HASH = "0" * 64
