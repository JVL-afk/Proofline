"""Deterministic URL normalization and public-network policy."""

from __future__ import annotations

import ipaddress
import socket
import unicodedata
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from opintel_research.domain import (
    UrlPolicyError,
    ValidatedUrl,
    contains_prohibited_contact_value,
)
from opintel_research.ports import Resolver

_ALLOWED_PORTS = {"http": 80, "https": 443}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}

# Frozen crawl-dedup tracking-parameter set for PHASE1_M1_V2_BOUNDED_SITE_CRAWL.
# These are stripped ONLY for crawl canonicalisation / dedup -- never from the
# URL that safety validation or provenance sees.
TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
        "_ga",
        "_gl",
        "msclkid",
        "igshid",
        "si",
        "yclid",
        "dclid",
    }
)


def canonical_crawl_url(normalized_url: str) -> str:
    """Additive crawl-dedup canonicalisation on top of ``normalize_public_url``.

    Pure and deterministic. Does NOT replace ``normalize_public_url`` or any
    safety check; the input MUST already be a normalised public URL.
    - strip a trailing slash except on the site root
    - drop ``TRACKING_PARAMS`` and any ``utm_*`` key
    - sort remaining query keys; collapse a repeated key to its first value
    """
    parsed = urlsplit(normalized_url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    kept: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_PARAMS or lowered.startswith("utm_"):
            continue
        if key not in kept:
            kept[key] = value
    query = urlencode(sorted(kept.items()), doseq=False)
    canonical = urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))
    if contains_prohibited_contact_value(canonical):
        raise UrlPolicyError("URL contains prohibited contact data")
    return canonical


def normalize_public_url(value: str) -> str:
    if not value or len(value) > 2048 or any(ord(character) < 32 for character in value):
        raise UrlPolicyError("invalid URL")
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_PORTS:
        raise UrlPolicyError("scheme is not permitted")
    if parsed.username is not None or parsed.password is not None:
        raise UrlPolicyError("URL credentials are prohibited")
    if not parsed.hostname:
        raise UrlPolicyError("URL host is required")
    try:
        host = unicodedata.normalize("NFC", parsed.hostname).encode("idna").decode("ascii").lower()
        port = parsed.port
    except (UnicodeError, ValueError) as error:
        raise UrlPolicyError("invalid URL host or port") from error
    effective_port = port or _ALLOWED_PORTS[scheme]
    if effective_port != _ALLOWED_PORTS[scheme]:
        raise UrlPolicyError("nonstandard ports are prohibited")
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise UrlPolicyError("local hosts are prohibited")
    path = parsed.path or "/"
    path = quote(path, safe="/%:@!$&'()*+,;=-._~")
    netloc = host
    query = quote(parsed.query, safe="=&;%:@!$'()*+,/?-._~")
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    if contains_prohibited_contact_value(normalized):
        raise UrlPolicyError("URL contains prohibited contact data")
    return normalized


class SocketResolver:
    def resolve(self, host: str, port: int) -> tuple[str, ...]:
        try:
            records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise UrlPolicyError("host resolution failed") from error
        return tuple(sorted({str(record[4][0]) for record in records}))


class PublicUrlPolicy:
    def __init__(self, resolver: Resolver) -> None:
        self._resolver = resolver

    def validate(self, value: str, permitted_host: str) -> ValidatedUrl:
        normalized = normalize_public_url(value)
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
        normalized_permit = permitted_host.encode("idna").decode("ascii").lower().rstrip(".")
        if host.rstrip(".") != normalized_permit:
            raise UrlPolicyError("host is outside the explicit research permit")
        port = _ALLOWED_PORTS[parsed.scheme]
        addresses = self._resolver.resolve(host, port)
        if not addresses:
            raise UrlPolicyError("host has no usable addresses")
        for address in addresses:
            try:
                candidate = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as error:
                raise UrlPolicyError("resolver returned an invalid address") from error
            if not candidate.is_global:
                raise UrlPolicyError("host resolves to a non-public address")
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        return ValidatedUrl(
            normalized_url=normalized,
            scheme=parsed.scheme,
            host=host,
            port=port,
            request_target=target,
            addresses=addresses,
        )
