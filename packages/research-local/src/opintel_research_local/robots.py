"""Fail-closed runtime robots evaluation for bounded M1 research."""

from __future__ import annotations

import hashlib
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from uuid import UUID

from opintel_m0.ports import Clock, IdentifierFactory
from opintel_research.domain import CrawlPolicy, RobotsPolicyEvidence
from opintel_research.ports import HttpTransport
from opintel_research.url_policy import PublicUrlPolicy

_REDIRECTS = {301, 302, 303, 307, 308}
_MAX_ROBOTS_BYTES = 65_536
_USER_AGENT = "OpportunityIntelligenceResearch"


class RuntimeRobotsPolicy:
    """Fetch robots once per run/host and evaluate every candidate path."""

    def __init__(
        self,
        url_policy: PublicUrlPolicy,
        transport: HttpTransport,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._url_policy = url_policy
        self._transport = transport
        self._clock = clock
        self._identifiers = identifiers
        self._cache: dict[tuple[UUID, str], tuple[int | None, bytes | None, str]] = {}

    def evaluate(
        self, research_run_id: UUID, url: str, permitted_host: str, policy: CrawlPolicy
    ) -> RobotsPolicyEvidence:
        cache_key = (research_run_id, permitted_host)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._retrieve(permitted_host, policy)
        status, body, retrieval_reason = self._cache[cache_key]
        path = urlsplit(url).path or "/"
        allowed = False
        reason = retrieval_reason
        if retrieval_reason == "robots_missing":
            allowed, reason = True, "robots_missing_allow"
        elif retrieval_reason == "robots_loaded" and body is not None:
            try:
                text = body.decode("utf-8", errors="strict")
                lines = text.splitlines()
                if not any(line.lower().lstrip().startswith("user-agent:") for line in lines):
                    raise ValueError("no user-agent directive")
                parser = RobotFileParser()
                parser.parse(lines)
                allowed = parser.can_fetch(_USER_AGENT, url)
                reason = "robots_allowed" if allowed else "robots_denied"
            except (UnicodeDecodeError, ValueError):
                reason = "robots_malformed"
        return RobotsPolicyEvidence(
            id=self._identifiers.new(),
            research_run_id=research_run_id,
            host=permitted_host,
            requested_path=path,
            captured_at=self._clock.now(),
            http_status=status,
            body_sha256=hashlib.sha256(body).hexdigest() if body is not None else None,
            body_length=len(body or b""),
            decision="ALLOW" if allowed else "DENY",
            reason_code=reason,
            allowed=allowed,
        )

    def _retrieve(self, host: str, policy: CrawlPolicy) -> tuple[int | None, bytes | None, str]:
        try:
            target = self._url_policy.validate(f"https://{host}/robots.txt", host)
            response = self._transport.request(
                target,
                policy.request_timeout_seconds,
                min(_MAX_ROBOTS_BYTES, policy.max_compressed_bytes),
            )
        except Exception:
            # No raw exception text may escape into evidence.
            return None, None, "robots_transport_failure"
        if response.status_code in _REDIRECTS:
            return response.status_code, response.body, "robots_redirect"
        if response.status_code == 404:
            return response.status_code, b"", "robots_missing"
        if response.status_code != 200:
            return response.status_code, response.body, "robots_http_failure"
        if len(response.body) > _MAX_ROBOTS_BYTES:
            return response.status_code, None, "robots_oversized"
        return response.status_code, response.body, "robots_loaded"
