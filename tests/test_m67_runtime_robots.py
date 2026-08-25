from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_research.domain import CrawlPolicy, RawHttpResponse, TransientFetchError
from opintel_research.url_policy import PublicUrlPolicy
from opintel_research_local.robots import RuntimeRobotsPolicy


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 25, 12, tzinfo=UTC)


class Resolver:
    def resolve(self, host: str, port: int) -> tuple[str, ...]:
        del host, port
        return ("93.184.216.34",)


class Transport:
    def __init__(self, response: RawHttpResponse | Exception) -> None:
        self.response = response
        self.calls = 0

    def request(self, target, timeout_seconds: float, max_bytes: int) -> RawHttpResponse:
        del target, timeout_seconds, max_bytes
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def decision(response: RawHttpResponse | Exception, path: str = "/services"):
    transport = Transport(response)
    policy = RuntimeRobotsPolicy(PublicUrlPolicy(Resolver()), transport, Clock(), UuidFactory())
    result = policy.evaluate(uuid4(), f"https://example.com{path}", "example.com", CrawlPolicy())
    return result, transport


@pytest.mark.parametrize(
    "response,allowed,reason",
    [
        (RawHttpResponse(200, (), b"User-agent: *\nAllow: /\n"), True, "robots_allowed"),
        (RawHttpResponse(200, (), b"User-agent: *\nDisallow: /services\n"), False, "robots_denied"),
        (RawHttpResponse(404, (), b""), True, "robots_missing_allow"),
        (RawHttpResponse(200, (), b"not-a-robots-file"), False, "robots_malformed"),
        (RawHttpResponse(200, (), b"x" * 65537), False, "robots_oversized"),
        (
            RawHttpResponse(302, (("location", "https://other.invalid/robots.txt"),), b""),
            False,
            "robots_redirect",
        ),
        (TransientFetchError(), False, "robots_transport_failure"),
    ],
)
def test_runtime_robots_policy_is_deterministic_and_fail_closed(response, allowed, reason):
    result, transport = decision(response)
    assert result.allowed is allowed
    assert result.reason_code == reason
    assert transport.calls == 1
    assert not hasattr(result, "body")


def test_runtime_robots_is_retrieved_once_and_applied_before_each_path() -> None:
    response = RawHttpResponse(200, (), b"User-agent: *\nDisallow: /private\n")
    transport = Transport(response)
    checker = RuntimeRobotsPolicy(PublicUrlPolicy(Resolver()), transport, Clock(), UuidFactory())
    run_id = uuid4()
    assert checker.evaluate(
        run_id, "https://example.com/services", "example.com", CrawlPolicy()
    ).allowed
    assert not checker.evaluate(
        run_id, "https://example.com/private", "example.com", CrawlPolicy()
    ).allowed
    assert transport.calls == 1


def test_current_m1_robots_deny_overrides_any_prior_a09_observation() -> None:
    current, _ = decision(RawHttpResponse(200, (), b"User-agent: *\nDisallow: /\n"), "/")
    assert current.reason_code == "robots_denied"
    assert current.allowed is False
