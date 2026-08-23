"""Deterministic, field-limited projection for the proposed M6.7 OSM locator.

This module performs no network access.  A separately authorized acquisition runner may pass a
Nominatim JSON response to :func:`project_response`; the raw response remains ephemeral and only
the returned business-host decision is eligible for durable storage.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

SOURCE_ID = "OSM_NOMINATIM_PUBLIC_SEARCH_V1"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
LEGAL_SUFFIXES = ("co", "company", "corp", "corporation", "inc", "llc", "ltd", "lp", "pllc")
SOCIAL_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "x.com",
    "youtube.com",
}


def build_query(public_business_name: str, texas_city_or_service_area: str) -> str:
    """Return the exact deterministic, business-only Nominatim query URL."""
    if not public_business_name.strip() or not texas_city_or_service_area.strip():
        raise ValueError("business name and Texas location are required")
    params = {
        "addressdetails": "1",
        "countrycodes": "us",
        "extratags": "1",
        "format": "jsonv2",
        "layer": "poi",
        "limit": "3",
        "namedetails": "0",
        "q": f"{public_business_name.strip()}, {texas_city_or_service_area.strip()}, Texas",
    }
    return f"{ENDPOINT}?{urlencode(params)}"


def project_response(
    *,
    public_business_name: str,
    texas_city_or_service_area: str,
    response: object,
    raw_artifact_sha256: str,
    observed_at: str,
) -> dict[str, Any]:
    """Project a raw Nominatim result into a contact-free host decision.

    Only ``extratags.website`` is considered.  Every other extra tag, including phone, email,
    contact and staff-shaped values, is ignored and never copied into the returned object.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", raw_artifact_sha256):
        raise ValueError("raw artifact SHA-256 is invalid")
    if not isinstance(response, list):
        return _decision("QUARANTINED", raw_artifact_sha256, observed_at, reason="INVALID_RESPONSE")

    candidates: list[dict[str, str]] = []
    for item in response:
        if not isinstance(item, dict) or not _is_texas(item):
            continue
        source_name = item.get("name")
        if not isinstance(source_name, str) or not _names_match(public_business_name, source_name):
            continue
        extra = item.get("extratags")
        website = extra.get("website") if isinstance(extra, dict) else None
        if not isinstance(website, str):
            continue
        host = _safe_host(website)
        if host is None:
            continue
        osm_type = item.get("osm_type")
        osm_id = item.get("osm_id")
        if not isinstance(osm_type, str) or not isinstance(osm_id, int | str):
            continue
        candidates.append(
            {
                "first_party_host_candidate": host,
                "locator": f"osm:{osm_type}:{osm_id}",
            }
        )

    unique = {(item["first_party_host_candidate"], item["locator"]): item for item in candidates}
    hosts = {item["first_party_host_candidate"] for item in unique.values()}
    if not hosts:
        return _decision("NOT_FOUND", raw_artifact_sha256, observed_at)
    if len(hosts) != 1:
        return _decision("AMBIGUOUS", raw_artifact_sha256, observed_at)
    selected = sorted(
        unique.values(),
        key=lambda item: (item["first_party_host_candidate"], item["locator"]),
    )[0]
    return {
        "state": "LOCATED_PENDING_EXACT_HOST_A09_REVIEW",
        "public_business_name": public_business_name,
        "texas_city_or_service_area": texas_city_or_service_area,
        **selected,
        "provenance": {
            "source_id": SOURCE_ID,
            "source_artifact_sha256": raw_artifact_sha256,
            "locator": selected["locator"],
            "observed_at": observed_at,
        },
    }


def response_sha256(raw_response: bytes) -> str:
    """Hash an ephemeral response without logging or persisting it."""
    return hashlib.sha256(raw_response).hexdigest()


def _decision(
    state: str,
    artifact_sha256: str,
    observed_at: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "state": state,
        "provenance": {
            "source_id": SOURCE_ID,
            "source_artifact_sha256": artifact_sha256,
            "observed_at": observed_at,
        },
    }
    if reason is not None:
        value["reason"] = reason
    return value


def _normalize_name(value: str, *, strip_suffix: bool = False) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    if strip_suffix and tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _names_match(expected: str, observed: str) -> bool:
    return _normalize_name(expected) == _normalize_name(observed) or _normalize_name(
        expected, strip_suffix=True
    ) == _normalize_name(observed, strip_suffix=True)


def _is_texas(item: dict[str, Any]) -> bool:
    address = item.get("address")
    if not isinstance(address, dict):
        return False
    state = address.get("state")
    code = address.get("ISO3166-2-lvl4") or address.get("state_code")
    return state == "Texas" or (isinstance(code, str) and code.casefold() in {"us-tx", "tx"})


def _safe_host(value: str) -> str | None:
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password:
        return None
    host = parsed.hostname
    if host is None or re.fullmatch(r"\d+(?:\.\d+){3}", host):
        return None
    try:
        normalized = host.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError:
        return None
    if "." not in normalized or any(
        normalized == social or normalized.endswith(f".{social}") for social in SOCIAL_HOSTS
    ):
        return None
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(".local"):
        return None
    return normalized
