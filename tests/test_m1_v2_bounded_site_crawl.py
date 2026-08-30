"""Integration tests for PHASE1_M1_V2_BOUNDED_SITE_CRAWL (site_crawl.py).

Synthetic sites are served by an in-memory transport -- no network. Every test
asserts determinism where relevant and that the safety controls (robots, host
equality, minimisation, provenance) still hold.
"""

from __future__ import annotations

import gzip
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_research import ObservationalHtmlExtractor, PublicUrlPolicy, ResearchWorkflowRunner
from opintel_research.domain import (
    Business,
    CrawlPolicy,
    RawHttpResponse,
    ResearchRun,
    ResearchRunStatus,
    RobotsPolicyEvidence,
)
from opintel_research_local import SqlAlchemyResearchRepository
from opintel_research_local.http import SafeHttpFetcher
from opintel_research_worker.minimization import ProductionPhaseOneCaptureMinimizer

PUBLIC_IP = "93.184.216.34"
HOST = "example.com"
BASE = f"https://{HOST}"
V2_PROTOCOL = "phase1-m1@2-bounded-site-crawl"
WORKSPACE = UUID("00000000-0000-4000-8000-000000000001")


@dataclass
class FakeClock:
    value: datetime

    def now(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


@dataclass
class AdvancingSleeper:
    clock: FakeClock
    calls: list[float]

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(timedelta(seconds=seconds))


class StaticResolver:
    def resolve(self, host: str, port: int) -> tuple[str, ...]:
        del host, port
        return (PUBLIC_IP,)


class MapTransport:
    """Serves a fixed URL -> bytes/headers map; unknown URLs 404."""

    def __init__(self, pages: dict[str, tuple[bytes, tuple[tuple[str, str], ...]]]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def request(self, target, timeout_seconds: float, max_bytes: int) -> RawHttpResponse:
        del timeout_seconds, max_bytes
        self.calls.append(target.normalized_url)
        entry = self.pages.get(target.normalized_url)
        if entry is None:
            return RawHttpResponse(404, (("content-type", "text/plain"),), b"not found")
        body, extra = entry
        return RawHttpResponse(200, (("content-type", "text/html; charset=utf-8"), *extra), body)


class RobotsAllowAll:
    def __init__(self, clock: FakeClock, sitemaps: Sequence[str] = ()) -> None:
        self.clock = clock
        self._sitemaps = tuple(sitemaps)

    def evaluate(self, research_run_id, url, permitted_host, policy) -> RobotsPolicyEvidence:
        del policy, url
        return RobotsPolicyEvidence(
            id=UuidFactory().new(), research_run_id=research_run_id, host=permitted_host,
            requested_path="/", captured_at=self.clock.now(), http_status=200,
            body_sha256="0" * 64, body_length=0, decision="ALLOW",
            reason_code="synthetic_robots_allowed", allowed=True,
        )

    def sitemap_directives(self, research_run_id, permitted_host, policy) -> tuple[str, ...]:
        del research_run_id, permitted_host, policy
        return self._sitemaps


class RobotsDenyPaths:
    def __init__(self, clock: FakeClock, denied: Sequence[str]) -> None:
        self.clock = clock
        self._denied = tuple(denied)

    def evaluate(self, research_run_id, url, permitted_host, policy) -> RobotsPolicyEvidence:
        del policy
        from urllib.parse import urlsplit

        path = urlsplit(url).path
        blocked = any(path.startswith(prefix) for prefix in self._denied)
        return RobotsPolicyEvidence(
            id=UuidFactory().new(), research_run_id=research_run_id, host=permitted_host,
            requested_path=path, captured_at=self.clock.now(), http_status=200,
            body_sha256="0" * 64, body_length=0,
            decision="DENY" if blocked else "ALLOW",
            reason_code="robots_denied" if blocked else "robots_allowed",
            allowed=not blocked,
        )

    def sitemap_directives(self, *_a, **_k) -> tuple[str, ...]:
        return ()


class AllowResearch:
    def authorize(self, run, business) -> None:
        assert run.business_id == business.id


class NoBrowser:
    def render(self, url: str, permitted_host: str):
        raise AssertionError("browser fallback must not be used")


_EVIDENCE_FILLER = (
    "Example Heating is a licensed HVAC contractor serving the local service area. "
    "Our technicians handle heating, cooling, air conditioning, furnace repair, system "
    "installation and seasonal maintenance for homes and businesses. Office hours are "
    "Monday through Friday. Ask about our maintenance plans and financing options."
)


def _page(title: str, h1: str, body: str, links: Sequence[str] = ()) -> bytes:
    anchors = "".join(f'<a href="{href}">{href}</a>' for href in links)
    return (
        f"<!doctype html><html><head><title>{title}</title></head>"
        f"<body><h1>{h1}</h1><p>{body}</p><p>{_EVIDENCE_FILLER}</p>{anchors}</body></html>"
    ).encode()


def _urlset(paths: Sequence[str]) -> bytes:
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    body = "".join(f"<url><loc>{BASE}{p}</loc></url>" for p in paths)
    return f'<?xml version="1.0"?><urlset {ns}>{body}</urlset>'.encode()


def _v2_policy(**overrides: object) -> CrawlPolicy:
    base: dict[str, object] = dict(
        max_pages=25, max_depth=3, max_attempts=2, max_total_bytes=18_000_000,
        max_response_bytes=1_000_000, max_compressed_bytes=1_000_000,
        max_duration_seconds=300, per_domain_delay_seconds=0.0, max_redirects=0,
        cache_ttl_seconds=0, max_total_http_requests=48, max_discovery_fetches=6,
        max_sitemap_entries_parsed=2000, max_query_variants_per_path=3,
        max_path_segments=6, max_pages_per_category=4, no_progress_window=3,
        low_relevance_floor=20, crawl_protocol_version=V2_PROTOCOL,
    )
    base.update(overrides)
    return CrawlPolicy(**base)  # type: ignore[arg-type]


def _make_run(repo: SqlAlchemyResearchRepository, clock: FakeClock, policy: CrawlPolicy) -> UUID:
    business = Business(
        id=uuid4(), workspace_id=WORKSPACE, name="Example Heating",
        canonical_url=f"{BASE}/", permitted_host=HOST, created_by="test", created_at=clock.now(),
    )
    repo.create_business(business)
    run = ResearchRun(
        id=uuid4(), workspace_id=WORKSPACE, business_id=business.id, operation_id=uuid4(),
        trace_id=uuid4(), start_url=f"{BASE}/", permitted_host=HOST, policy=policy,
        status=ResearchRunStatus.PENDING, created_by="test", created_at=clock.now(),
        updated_at=clock.now(), crawl_protocol_version=V2_PROTOCOL,
    )
    stored, created = repo.create_or_get_run(run, f"key-{run.id}")
    assert created
    return stored.id


def _runner(repo, clock, transport, robots) -> tuple[ResearchWorkflowRunner, AdvancingSleeper]:
    sleeper = AdvancingSleeper(clock, [])
    return (
        ResearchWorkflowRunner(
            repository=repo,
            fetcher=SafeHttpFetcher(PublicUrlPolicy(StaticResolver()), transport, clock),
            browser=NoBrowser(), extractor=ObservationalHtmlExtractor(), clock=clock,
            identifiers=UuidFactory(), sleeper=sleeper,
            capture_minimizer=ProductionPhaseOneCaptureMinimizer(),
            robots_policy=robots, research_authorization=AllowResearch(),
        ),
        sleeper,
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 30, 12, 0, tzinfo=UTC))


@pytest.fixture
def repo(tmp_path) -> SqlAlchemyResearchRepository:
    value = SqlAlchemyResearchRepository(f"sqlite:///{(tmp_path / 'v2.db').as_posix()}")
    value.initialize()
    return value


# --------------------------------------------------------------------------


def _commercial_site() -> dict[str, tuple[bytes, tuple[tuple[str, str], ...]]]:
    return {
        f"{BASE}/sitemap.xml": (
            _urlset(["/", "/services", "/commercial-hvac", "/request-service", "/about",
                     "/blog/2019/01/old-post", "/privacy"]),
            (),
        ),
        f"{BASE}/": (_page("Home", "Example Heating", "Heating and cooling for your home."), ()),
        f"{BASE}/services": (
            _page("Services", "Our HVAC Services", "We provide repair and installation."),
            (),
        ),
        f"{BASE}/commercial-hvac": (
            _page("Commercial HVAC", "Commercial HVAC",
                  "We serve commercial HVAC and commercial heating clients."), ()),
        f"{BASE}/request-service": (
            _page("Request Service", "Request Service",
                  "Use our request service form to schedule an appointment."), ()),
        f"{BASE}/about": (_page("About", "About Us", "Our story and our team."), ()),
        f"{BASE}/blog/2019/01/old-post": (_page("Old", "Old Post", "unrelated"), ()),
        f"{BASE}/privacy": (_page("Privacy", "Privacy Policy", "cookie policy"), ()),
    }


def test_sitemap_discovery_captures_prioritised_multi_page_corpus(repo, clock) -> None:
    transport = MapTransport(_commercial_site())
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy())

    assert runner.run_once() is True
    run = repo.get_run(WORKSPACE, run_id)
    assert run is not None
    assert run.status is ResearchRunStatus.SUCCEEDED
    pages = repo.list_pages(WORKSPACE, run_id)
    captured = {p.normalized_url for p in pages if p.status.value in {"fetched", "cached"}}
    assert f"{BASE}/commercial-hvac" in captured
    assert f"{BASE}/request-service" in captured
    # low-value pages are excluded from capture
    assert f"{BASE}/privacy" not in captured
    assert f"{BASE}/blog/2019/01/old-post" not in captured
    # provenance: every evidence item resolves to exactly one captured page snapshot
    page_by_snapshot = {p.snapshot_id: p for p in pages if p.snapshot_id}
    for item in repo.list_evidence(WORKSPACE, run_id):
        assert item.snapshot_id in page_by_snapshot


def test_coverage_record_is_deterministic_and_sealed(repo, clock) -> None:
    def run_once() -> dict[str, object]:
        local_repo = SqlAlchemyResearchRepository("sqlite://")
        local_repo.initialize()
        local_clock = FakeClock(datetime(2026, 8, 30, 12, 0, tzinfo=UTC))
        transport = MapTransport(_commercial_site())
        runner, _ = _runner(local_repo, local_clock, transport, RobotsAllowAll(local_clock))
        rid = _make_run(local_repo, local_clock, _v2_policy())
        assert runner.run_once() is True
        record = local_repo.get_coverage_record(WORKSPACE, rid)
        assert record is not None
        assert record.coverage_record_sha256 == record.computed_sha256()
        assert "commercial_hvac" in record.semantic_categories_captured
        payload = record.canonical_payload()
        # run/workspace ids are per-run identity, not crawl behaviour
        payload.pop("research_run_id")
        payload.pop("workspace_id")
        return payload

    assert run_once() == run_once()


def test_m2_relevant_signals_present_across_multi_page_corpus(repo, clock) -> None:
    """The whole-corpus evidence carries BOTH the commercial-HVAC industry signal
    and the public inbound-path signal that the (unchanged) M2 detector requires
    -- which a homepage-only capture did not."""
    transport = MapTransport(_commercial_site())
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy())
    assert runner.run_once() is True
    corpus = " ".join(
        item.extracted_fragment.lower() for item in repo.list_evidence(WORKSPACE, run_id)
    )
    assert "commercial hvac" in corpus or "commercial heating" in corpus
    assert "request service" in corpus
    # homepage-only would have carried neither in this form
    home_only = " ".join(
        item.extracted_fragment.lower()
        for item in repo.list_evidence(WORKSPACE, run_id)
        if item.source_uri == f"{BASE}/"
    )
    assert "request service" not in home_only


def test_cross_host_links_are_never_fetched(repo, clock) -> None:
    pages = _commercial_site()
    pages[f"{BASE}/"] = (
        _page("Home", "Example Heating", "welcome",
              links=["https://facebook.com/us", "https://supplier.example.net/x", "/services"]),
        (),
    )
    transport = MapTransport(pages)
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    _make_run(repo, clock, _v2_policy())
    assert runner.run_once() is True
    offsite = [c for c in transport.calls if "facebook.com" in c or "supplier.example.net" in c]
    assert not offsite


def test_robots_excluded_paths_are_not_fetched_but_siblings_are(repo, clock) -> None:
    transport = MapTransport(_commercial_site())
    robots = RobotsDenyPaths(clock, denied=["/request-service"])
    runner, _ = _runner(repo, clock, transport, robots)
    run_id = _make_run(repo, clock, _v2_policy())
    assert runner.run_once() is True
    pages = repo.list_pages(WORKSPACE, run_id)
    captured = {p.normalized_url for p in pages if p.status.value in {"fetched", "cached"}}
    assert f"{BASE}/request-service" not in captured
    assert f"{BASE}/commercial-hvac" in captured
    record = repo.get_coverage_record(WORKSPACE, run_id)
    assert record is not None and record.pages_denied_by_robots >= 1


def test_gzip_sitemap_is_decoded(repo, clock) -> None:
    pages = _commercial_site()
    del pages[f"{BASE}/sitemap.xml"]
    pages[f"{BASE}/sitemap.xml.gz"] = (
        gzip.compress(_urlset(["/", "/commercial-hvac", "/request-service"])),
        (("content-encoding", "gzip"),),
    )
    transport = MapTransport(pages)
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy(max_discovery_fetches=6))
    assert runner.run_once() is True
    captured = {
        p.normalized_url for p in repo.list_pages(WORKSPACE, run_id)
        if p.status.value in {"fetched", "cached"}
    }
    assert f"{BASE}/commercial-hvac" in captured


def test_query_variant_loop_is_bounded(repo, clock) -> None:
    loop_links = [f"/calendar?day={n}" for n in range(1, 12)]
    pages = {
        f"{BASE}/sitemap.xml": (_urlset(["/"]), ()),
        f"{BASE}/": (
            _page("Home", "Example Heating", "schedule an appointment", links=loop_links),
            (),
        ),
    }
    for n in range(1, 12):
        pages[f"{BASE}/calendar?day={n}"] = (_page("Cal", "Schedule", "appointment slot"), ())
    transport = MapTransport(pages)
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy())
    assert runner.run_once() is True
    record = repo.get_coverage_record(WORKSPACE, run_id)
    assert record is not None
    loop_excls = [
        u for u, reason in record.duplicate_or_excluded_urls
        if reason == "excluded:query_variant_loop"
    ]
    assert loop_excls, "query-variant loop defence did not fire"
    calendar_fetches = [c for c in transport.calls if "/calendar?day=" in c]
    assert len(calendar_fetches) <= 3


def test_useful_page_ceiling_is_a_hard_cap(repo, clock) -> None:
    many = [f"/services/{cat}-{n}" for cat in ("repair", "install") for n in range(20)]
    site = {f"{BASE}/sitemap.xml": (_urlset(["/", *many]), ()),
            f"{BASE}/": (_page("Home", "Example Heating", "hvac"), ())}
    for path in many:
        site[f"{BASE}{path}"] = (
            _page("S", "Repair and installation", "commercial hvac service"), (),
        )
    transport = MapTransport(site)
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy(max_pages=5, max_total_http_requests=48))
    assert runner.run_once() is True
    run = repo.get_run(WORKSPACE, run_id)
    assert run is not None and run.pages_succeeded <= 5
    record = repo.get_coverage_record(WORKSPACE, run_id)
    assert record is not None
    assert "useful_page_budget_exceeded" in record.stop_reasons


def test_no_sitemap_falls_back_to_on_page_links(repo, clock) -> None:
    pages = {
        f"{BASE}/": (
            _page("Home", "Example Heating", "welcome",
                  links=["/commercial-hvac", "/request-service"]),
            (),
        ),
        f"{BASE}/commercial-hvac": (
            _page("Commercial", "Commercial HVAC", "commercial heating and cooling"), ()),
        f"{BASE}/request-service": (
            _page("Request", "Request Service", "schedule an appointment now"), ()),
    }
    transport = MapTransport(pages)  # all /sitemap* -> 404
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    run_id = _make_run(repo, clock, _v2_policy())
    assert runner.run_once() is True
    captured = {
        p.normalized_url for p in repo.list_pages(WORKSPACE, run_id)
        if p.status.value in {"fetched", "cached"}
    }
    assert {f"{BASE}/commercial-hvac", f"{BASE}/request-service"} <= captured


def test_v1_protocol_runs_still_use_homepage_only_path(repo, clock) -> None:
    """A run WITHOUT the v2 protocol tag must not probe sitemaps."""
    transport = MapTransport({f"{BASE}/": (_page("Home", "Example Heating", "hvac"), ())})
    runner, _ = _runner(repo, clock, transport, RobotsAllowAll(clock))
    business = Business(
        id=uuid4(), workspace_id=WORKSPACE, name="Example Heating", canonical_url=f"{BASE}/",
        permitted_host=HOST, created_by="test", created_at=clock.now(),
    )
    repo.create_business(business)
    run = ResearchRun(
        id=uuid4(), workspace_id=WORKSPACE, business_id=business.id, operation_id=uuid4(),
        trace_id=uuid4(), start_url=f"{BASE}/", permitted_host=HOST,
        policy=CrawlPolicy(per_domain_delay_seconds=0.0, max_redirects=0),
        status=ResearchRunStatus.PENDING, created_by="test",
        created_at=clock.now(), updated_at=clock.now(),
    )
    repo.create_or_get_run(run, f"key-{run.id}")
    assert runner.run_once() is True
    assert not any("sitemap" in call for call in transport.calls)
