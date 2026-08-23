"""Fail-closed third-party-host guard for the accepted M6.7 Nominatim projector.

The accepted projector emits an in-memory candidate.  This successor guard must approve that
candidate before any roster write.  It performs no DNS or network access.
"""

from __future__ import annotations

from typing import Any

ALLOWED_OSM_HOST_TAGS = ("website",)
DENIED_THIRD_PARTY_DOMAINS = frozenset(
    {
        # Social and video platforms.
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "tiktok.com",
        "x.com",
        "youtube.com",
        # Directories, review sites, lead marketplaces and maps.
        "angi.com",
        "bbb.org",
        "buildzoom.com",
        "chamberofcommerce.com",
        "google.com",
        "homeadvisor.com",
        "houzz.com",
        "manta.com",
        "mapquest.com",
        "nextdoor.com",
        "porch.com",
        "thumbtack.com",
        "yellowpages.com",
        "yelp.com",
        # URL shorteners and profile/link aggregators.
        "bit.ly",
        "goo.gl",
        "linktr.ee",
        "tinyurl.com",
    }
)


def guard_projection(projection: object) -> dict[str, Any]:
    """Return a durable-safe decision without introducing a fallback source."""
    if not isinstance(projection, dict):
        return {"state": "AMBIGUOUS", "reason": "INVALID_PROJECTOR_OUTPUT"}
    state = projection.get("state")
    if state in {"NOT_FOUND", "AMBIGUOUS", "QUARANTINED"}:
        return _content_free_failure(str(state), projection)
    if state != "LOCATED_PENDING_EXACT_HOST_A09_REVIEW":
        return {"state": "AMBIGUOUS", "reason": "UNRECOGNIZED_PROJECTOR_STATE"}
    host = projection.get("first_party_host_candidate")
    if not isinstance(host, str) or _is_denied_third_party(host):
        return _content_free_failure("AMBIGUOUS", projection, "THIRD_PARTY_HOST_REJECTED")
    allowed = {
        "state",
        "public_business_name",
        "texas_city_or_service_area",
        "first_party_host_candidate",
        "locator",
        "provenance",
    }
    if set(projection) != allowed:
        return _content_free_failure("AMBIGUOUS", projection, "UNEXPECTED_PROJECTOR_FIELD")
    return dict(projection)


def _is_denied_third_party(host: str) -> bool:
    normalized = host.casefold().rstrip(".")
    return any(
        normalized == denied or normalized.endswith(f".{denied}")
        for denied in DENIED_THIRD_PARTY_DOMAINS
    )


def _content_free_failure(
    state: str,
    projection: dict[str, Any],
    reason: str | None = None,
) -> dict[str, Any]:
    provenance = projection.get("provenance")
    safe_provenance: dict[str, Any] = {}
    if isinstance(provenance, dict):
        for key in ("source_id", "source_artifact_sha256", "observed_at"):
            value = provenance.get(key)
            if isinstance(value, str):
                safe_provenance[key] = value
    result: dict[str, Any] = {"state": state, "provenance": safe_provenance}
    if reason is not None:
        result["reason"] = reason
    return result
