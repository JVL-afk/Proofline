"""PHASE1_M1_V2_BOUNDED_SITE_CRAWL execution.

A deterministic, bounded, same-host multi-page evidence crawl. Every safety
branch of the homepage-only protocol is preserved verbatim and reused here
(``ResearchWorkflowRunner._snapshot`` / ``_minimize`` / ``_durable_snapshot`` /
``_durable_material`` / ``_evidence``): per-URL runtime robots (fail-closed,
gzip-aware), host equality on normalise + discovery + enqueue + dequeue,
``normalize_public_url`` + ``PublicUrlPolicy`` (SSRF / public-IP / DNS-rebinding),
zero followed redirects, ephemeral raw body, deterministic block-level
minimisation or quarantine, one-evidence-item-to-one-page-snapshot provenance.
The only additions are discovery, a deterministic relevance frontier, per-page
purpose classification, discovery-edge records, a deterministic coverage record,
and deterministic early stopping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import UUID

from opintel_research.domain import (
    HIGH_VALUE_CATEGORIES,
    Business,
    CaptureQuarantine,
    CrawlPolicy,
    CrawlStopReason,
    DiscoveryEdge,
    DiscoverySource,
    DurablePageBundle,
    ExtractedMaterial,
    FetchAttempt,
    FetchError,
    M1CoverageRecord,
    MinimizedPageSnapshot,
    PageStatus,
    ResearchPage,
    ResearchRun,
    ResearchRunStatus,
    SemanticCategory,
    UrlPolicyError,
)
from opintel_research.frontier import (
    FrontierStopState,
    PriorityFrontier,
    QueuedCandidate,
    classify_category,
    evaluate_candidate,
    m2_relevance_hits,
    score_candidate,
    should_stop,
)
from opintel_research.sitemap import SitemapKind, SitemapParseResult, parse_sitemap
from opintel_research.url_policy import canonical_crawl_url, normalize_public_url

if TYPE_CHECKING:
    from opintel_research.workflow import ResearchWorkflowRunner

_CONVENTIONAL_SITEMAPS: tuple[str, ...] = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap.xml.gz",
)
_PROTOCOL = "phase1-m1@2-bounded-site-crawl"


@dataclass(slots=True)
class _Counters:
    useful_pages: int = 0
    pages_attempted: int = 0
    pages_quarantined: int = 0
    pages_denied_by_robots: int = 0
    transport_failures: int = 0
    total_http_requests: int = 0
    discovery_fetches: int = 0
    total_bytes: int = 0
    attempts_used: int = 0


@dataclass(slots=True)
class _State:
    frontier: PriorityFrontier = field(default_factory=PriorityFrontier)
    counters: _Counters = field(default_factory=_Counters)
    edges: list[DiscoveryEdge] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)
    captured_pages: list[tuple[str, str]] = field(default_factory=list)
    quarantined_pages: list[tuple[str, str]] = field(default_factory=list)
    robots_denied_pages: list[tuple[str, str]] = field(default_factory=list)
    transport_failed_pages: list[tuple[str, str]] = field(default_factory=list)
    category_captures: dict[SemanticCategory, int] = field(default_factory=dict)
    captured_categories: set[SemanticCategory] = field(default_factory=set)
    discovered_categories: set[SemanticCategory] = field(default_factory=set)
    candidate_source_counts: dict[str, int] = field(default_factory=dict)
    candidate_urls_discovered: int = 0
    m2_hits: set[str] = field(default_factory=set)
    captures_since_new_evidence: int = 0
    stop_reasons: list[CrawlStopReason] = field(default_factory=list)
    sitemap_docs: int = 0
    robots_directives_seen: int = 0
    first_error: str | None = None


class BoundedSiteCrawlRunner:
    def __init__(self, wf: ResearchWorkflowRunner) -> None:
        self._wf = wf
        self._repo = wf._repository
        self._fetcher = wf._fetcher
        self._robots = wf._robots_policy
        self._clock = wf._clock
        self._ids = wf._identifiers
        self._sleeper = wf._sleeper
        self._stop_signal = wf._stop_signal

    # -- entry point -------------------------------------------------------

    def execute(self, run: ResearchRun, business: Business) -> None:
        policy = run.policy
        started = self._clock.now()
        state = _State()

        self._discover(run, policy, state)

        while True:
            elapsed = (self._clock.now() - started).total_seconds()
            kill = self._stop_signal is not None and self._stop_signal.is_active()
            room = (
                state.counters.useful_pages < policy.max_pages
                and state.counters.total_http_requests < policy.max_total_http_requests
                and state.counters.total_bytes < policy.max_total_bytes
                and elapsed < policy.max_duration_seconds
            )
            reasons = should_stop(
                FrontierStopState(
                    useful_pages_captured=state.counters.useful_pages,
                    max_useful_page_fetches=policy.max_pages,
                    total_http_requests=state.counters.total_http_requests,
                    max_total_http_requests=policy.max_total_http_requests,
                    discovery_fetches=state.counters.discovery_fetches,
                    max_discovery_fetches=policy.max_discovery_fetches,
                    total_bytes=state.counters.total_bytes,
                    max_total_bytes=policy.max_total_bytes,
                    elapsed_seconds=elapsed,
                    max_duration_seconds=policy.max_duration_seconds,
                    kill_switch_active=kill,
                    frontier_empty=len(state.frontier) == 0,
                    high_value_categories_discovered=frozenset(
                        state.discovered_categories & HIGH_VALUE_CATEGORIES
                    ),
                    high_value_categories_captured=frozenset(
                        state.captured_categories & HIGH_VALUE_CATEGORIES
                    ),
                    high_value_candidates_remaining_fit=room
                    and state.frontier.remaining_high_value_fits(lambda _item: True),
                    best_remaining_score=state.frontier.best_score(),
                    low_relevance_floor=policy.low_relevance_floor,
                    captures_since_new_evidence=state.captures_since_new_evidence,
                    no_progress_window=policy.no_progress_window,
                )
            )
            if reasons:
                for reason in reasons:
                    if reason not in state.stop_reasons:
                        state.stop_reasons.append(reason)
                if kill:
                    state.first_error = state.first_error or "kill_switch_active"
                break

            queued = state.frontier.pop_best()
            if queued is None:
                if CrawlStopReason.FRONTIER_EXHAUSTED not in state.stop_reasons:
                    state.stop_reasons.append(CrawlStopReason.FRONTIER_EXHAUSTED)
                break

            category = queued.score.category
            if (
                category is not None
                and state.category_captures.get(category, 0) >= policy.max_pages_per_category
            ):
                state.excluded.append((queued.canonical_url, "excluded:category_cap"))
                self._edge(run, state, queued.from_page_id, queued.canonical_url,
                           queued.discovery_source, category, queued.score.score, "budget_skipped")
                continue

            self._process(run, business, state, queued, policy)

        elapsed_final = int((self._clock.now() - started).total_seconds())
        coverage = self._coverage(run, state, elapsed_final)
        self._repo.save_coverage_record(coverage)
        if state.edges:
            self._repo.save_discovery_edges(tuple(state.edges))

        if state.counters.useful_pages == 0:
            status = ResearchRunStatus.FAILED
        elif state.first_error:
            status = ResearchRunStatus.PARTIAL
        else:
            status = ResearchRunStatus.SUCCEEDED
        self._repo.complete_run(
            run.id,
            status,
            state.counters.pages_attempted,
            state.counters.useful_pages,
            state.counters.total_bytes,
            self._clock.now(),
            state.first_error,
            "bounded site crawl completed with failures" if state.first_error else None,
            coverage.coverage_record_sha256,
        )

    # -- per-URL processing (mirrors the homepage protocol) ---------------

    def _process(
        self,
        run: ResearchRun,
        business: Business,
        state: _State,
        queued: QueuedCandidate,
        policy: CrawlPolicy,
    ) -> None:
        requested_url = queued.requested_url
        depth = queued.depth
        try:
            normalized = normalize_public_url(requested_url)
            if (urlsplit(normalized).hostname or "") != run.permitted_host:
                raise UrlPolicyError("link host is outside permit")
        except UrlPolicyError:
            state.excluded.append((queued.canonical_url, "excluded:offsite"))
            return
        state.counters.pages_attempted += 1

        robots = self._robots.evaluate(run.id, normalized, run.permitted_host, policy)
        self._repo.record_robots_evidence(robots)
        if not robots.allowed:
            state.first_error = state.first_error or robots.reason_code
            state.counters.pages_denied_by_robots += 1
            state.robots_denied_pages.append((queued.canonical_url, robots.reason_code))
            self._edge(run, state, queued.from_page_id, queued.canonical_url,
                       queued.discovery_source, queued.score.category, queued.score.score,
                       "robots_denied")
            now = self._clock.now()
            self._repo.save_failed_page(
                self._page(run, requested_url, normalized, depth, PageStatus.FAILED,
                           error_code=robots.reason_code, fetched_at=now),
                FetchAttempt(
                    id=self._ids.new(), research_run_id=run.id, normalized_url=normalized,
                    attempt_number=0, started_at=now, completed_at=now,
                    outcome="robots_blocked", error_code=robots.reason_code,
                ),
            )
            return

        cached = self._repo.find_cached_snapshot(
            run.workspace_id, run.business_id, normalized,
            self._clock.now() - timedelta(seconds=policy.cache_ttl_seconds),
        )
        if cached is not None:
            snapshot, material = cached
            if state.counters.total_bytes + snapshot.content_length > policy.max_total_bytes:
                state.first_error = state.first_error or "crawl_byte_budget_exceeded"
                state.stop_reasons.append(CrawlStopReason.BYTE_BUDGET_EXCEEDED)
                return
            purpose = self._purpose(normalized, material)
            page = self._page(run, requested_url, normalized, depth, PageStatus.CACHED,
                              snapshot_id=snapshot.id, material_id=material.id,
                              fetched_at=self._clock.now(), page_purpose=purpose.value)
            evidence = self._wf._evidence(run, page, snapshot, material)
            self._repo.save_page_bundle(
                page, DurablePageBundle(snapshot, material, tuple(evidence))
            )
            state.counters.total_bytes += snapshot.content_length
            self._on_capture(run, state, queued, page, snapshot, material, purpose)
            return

        document = None
        final_error: FetchError | UrlPolicyError | None = None
        for attempt_number in range(1, policy.max_attempts + 1):
            if self._stop_signal is not None and self._stop_signal.is_active():
                final_error = FetchError("kill_switch_active", "research is suspended")
                break
            attempt_started = self._clock.now()
            if policy.per_domain_delay_seconds and (
                state.counters.total_http_requests > 0 or attempt_number > 1
            ):
                self._sleeper.sleep(policy.per_domain_delay_seconds)
            state.counters.total_http_requests += 1
            state.counters.attempts_used += 1
            try:
                document = self._fetcher.fetch(
                    normalized, run.permitted_host, policy, attempt_number
                )
                self._repo.record_attempt(FetchAttempt(
                    id=self._ids.new(), research_run_id=run.id, normalized_url=normalized,
                    attempt_number=attempt_number, started_at=attempt_started,
                    completed_at=self._clock.now(), outcome="succeeded",
                ))
                break
            except (FetchError, UrlPolicyError) as error:
                final_error = error
                self._repo.record_attempt(FetchAttempt(
                    id=self._ids.new(), research_run_id=run.id, normalized_url=normalized,
                    attempt_number=attempt_number, started_at=attempt_started,
                    completed_at=self._clock.now(),
                    outcome="retryable_failure" if error.retryable else "permanent_failure",
                    error_code=error.code,
                ))
                if not error.retryable or attempt_number >= policy.max_attempts:
                    break
                self._sleeper.sleep(min(2 ** (attempt_number - 1), 4))

        if document is None:
            error_code = final_error.code if final_error else "fetch_failed"
            state.first_error = state.first_error or error_code
            state.counters.transport_failures += 1
            state.transport_failed_pages.append((queued.canonical_url, error_code))
            self._edge(run, state, queued.from_page_id, queued.canonical_url,
                       queued.discovery_source, queued.score.category, queued.score.score,
                       "transport_failed")
            now = self._clock.now()
            self._repo.save_failed_page(
                self._page(run, requested_url, normalized, depth, PageStatus.FAILED,
                           error_code=error_code, fetched_at=now),
                FetchAttempt(
                    id=self._ids.new(), research_run_id=run.id, normalized_url=normalized,
                    attempt_number=0, started_at=now, completed_at=now,
                    outcome="page_failed", error_code=error_code,
                ),
            )
            return

        state.counters.total_bytes += len(document.content)
        if state.counters.total_bytes > policy.max_total_bytes:
            state.first_error = state.first_error or "crawl_byte_budget_exceeded"
            state.stop_reasons.append(CrawlStopReason.BYTE_BUDGET_EXCEEDED)
            return

        raw_snapshot = self._wf._snapshot(run, document)
        raw_material = self._wf._extractor.extract(
            raw_snapshot, self._ids.new(), self._clock.now()
        )
        minimized = self._wf._minimize(raw_snapshot, business.name, raw_material.visible_text)
        if isinstance(minimized, CaptureQuarantine):
            now = self._clock.now()
            state.first_error = state.first_error or "minimization_quarantine"
            state.counters.pages_quarantined += 1
            state.quarantined_pages.append((queued.canonical_url, minimized.quarantine_reasons[0]))
            self._edge(run, state, queued.from_page_id, queued.canonical_url,
                       queued.discovery_source, queued.score.category, queued.score.score,
                       "quarantined")
            self._repo.save_quarantined_page(
                self._page(run, requested_url, normalized, depth, PageStatus.FAILED,
                           error_code="minimization_quarantine", fetched_at=now),
                minimized,
                FetchAttempt(
                    id=self._ids.new(), research_run_id=run.id, normalized_url=normalized,
                    attempt_number=0, started_at=now, completed_at=now,
                    outcome="quarantined", error_code="minimization_quarantine",
                ),
            )
            return

        snapshot = self._wf._durable_snapshot(raw_snapshot, minimized)
        page_id = self._ids.new()
        material = self._wf._durable_material(raw_material, snapshot)
        purpose = self._purpose(normalized, material)
        evidence = self._wf._evidence(run, page_id, snapshot, material)
        page = ResearchPage(
            id=page_id, workspace_id=run.workspace_id, business_id=run.business_id,
            research_run_id=run.id, requested_url=requested_url, normalized_url=normalized,
            depth=depth, status=PageStatus.FETCHED, snapshot_id=snapshot.id,
            material_id=material.id, fetched_at=snapshot.captured_at, page_purpose=purpose.value,
        )
        self._repo.save_page_bundle(page, DurablePageBundle(snapshot, material, tuple(evidence)))
        self._on_capture(run, state, queued, page, snapshot, raw_material, purpose)

    # -- discovery -------------------------------------------------------

    def _discover(self, run: ResearchRun, policy: CrawlPolicy, state: _State) -> None:
        seed_norm = normalize_public_url(run.start_url)
        seed_canon = canonical_crawl_url(seed_norm)
        seed_score = score_candidate(seed_canon, "", 0, DiscoverySource.SEED, is_seed=True)
        state.frontier.push(
            canonical_url=seed_canon, requested_url=seed_norm, depth=0,
            discovery_source=DiscoverySource.SEED, anchor_text="", from_page_id=None,
            score=seed_score,
        )
        state.candidate_urls_discovered += 1
        state.candidate_source_counts["seed"] = 1
        state.discovered_categories.add(SemanticCategory.HOMEPAGE)
        self._edge(run, state, None, seed_canon, DiscoverySource.SEED,
                   SemanticCategory.HOMEPAGE, seed_score.score, "queued")

        # Discovery honours the kill switch just like page fetches: if research is
        # suspended, no sitemap probe is made at all.
        if self._stop_signal is not None and self._stop_signal.is_active():
            return

        directives: tuple[str, ...] = ()
        getter = getattr(self._robots, "sitemap_directives", None)
        if callable(getter):
            try:
                directives = tuple(getter(run.id, run.permitted_host, policy))
            except Exception:
                directives = ()
        state.robots_directives_seen = len(directives)

        if directives:
            sources = [(url, DiscoverySource.ROBOTS_SITEMAP) for url in directives]
        else:
            sources = [
                (f"https://{run.permitted_host}{path}", DiscoverySource.CONVENTIONAL_SITEMAP)
                for path in _CONVENTIONAL_SITEMAPS
            ]

        index_recursions_left = 1
        for raw_url, source in sources:
            if state.counters.discovery_fetches >= policy.max_discovery_fetches:
                break
            if state.counters.total_http_requests >= policy.max_total_http_requests:
                break
            parsed = self._fetch_sitemap(run, raw_url, policy, state)
            if parsed is None:
                continue
            state.sitemap_docs += 1
            for child_url in parsed.child_sitemap_locs:
                if index_recursions_left <= 0:
                    break
                if state.counters.discovery_fetches >= policy.max_discovery_fetches:
                    break
                child = self._fetch_sitemap(run, child_url, policy, state)
                if child is None:
                    continue
                state.sitemap_docs += 1
                index_recursions_left -= 1
                self._ingest(run, state, child.page_locs, source, policy)
            self._ingest(run, state, parsed.page_locs, source, policy)
            conventional = source is DiscoverySource.CONVENTIONAL_SITEMAP
            if conventional and parsed.kind is not SitemapKind.UNKNOWN:
                break

    def _fetch_sitemap(
        self, run: ResearchRun, raw_url: str, policy: CrawlPolicy, state: _State
    ) -> SitemapParseResult | None:
        if self._stop_signal is not None and self._stop_signal.is_active():
            return None
        try:
            normalized = normalize_public_url(raw_url)
            if (urlsplit(normalized).hostname or "") != run.permitted_host:
                return None
        except UrlPolicyError:
            return None
        robots = self._robots.evaluate(run.id, normalized, run.permitted_host, policy)
        self._repo.record_robots_evidence(robots)
        if not robots.allowed:
            return None
        state.counters.discovery_fetches += 1
        state.counters.total_http_requests += 1
        state.counters.attempts_used += 1
        try:
            document = self._fetcher.fetch(normalized, run.permitted_host, policy, 1)
        except Exception:
            return None
        state.counters.total_bytes += len(document.content)
        encoding = ""
        for name, value in document.headers:
            if name.lower() == "content-encoding":
                encoding = value
                break
        return parse_sitemap(document.content, encoding, policy.max_sitemap_entries_parsed)

    def _ingest(
        self,
        run: ResearchRun,
        state: _State,
        locs: tuple[str, ...],
        source: DiscoverySource,
        policy: CrawlPolicy,
    ) -> None:
        for loc in locs:
            try:
                normalized = normalize_public_url(loc)
                if (urlsplit(normalized).hostname or "") != run.permitted_host:
                    state.excluded.append((loc, "excluded:offsite"))
                    continue
                canonical = canonical_crawl_url(normalized)
            except UrlPolicyError:
                state.excluded.append((loc, "excluded:url_policy"))
                continue
            self._consider(run, state, normalized, canonical, "", source, 1, None, policy)

    # -- frontier admission --------------------------------------------

    def _consider(
        self,
        run: ResearchRun,
        state: _State,
        normalized: str,
        canonical: str,
        anchor: str,
        source: DiscoverySource,
        depth: int,
        from_page_id: UUID | None,
        policy: CrawlPolicy,
    ) -> None:
        if state.frontier.has_seen(canonical):
            return
        state.candidate_urls_discovered += 1
        state.candidate_source_counts[source.value] = (
            state.candidate_source_counts.get(source.value, 0) + 1
        )
        if "?" in canonical:
            base = canonical.split("?", 1)[0]
            variants = sum(
                1 for seen in state.frontier.known_urls()
                if "?" in seen and seen.split("?", 1)[0] == base
            )
            if variants >= policy.max_query_variants_per_path:
                state.frontier.mark_seen(canonical)
                state.excluded.append((canonical, "excluded:query_variant_loop"))
                return
        evaluation = evaluate_candidate(
            canonical, anchor, depth, source, max_path_segments=policy.max_path_segments
        )
        primary = evaluation.score.category
        if primary is not None:
            state.discovered_categories.add(primary)
        for matched in evaluation.score.matched_categories:
            state.discovered_categories.add(matched)
        if not evaluation.admit:
            state.frontier.mark_seen(canonical)
            reason = evaluation.disposition_reason or "excluded:unknown"
            state.excluded.append((canonical, reason))
            self._edge(run, state, from_page_id, canonical, source, primary,
                       evaluation.score.score, reason)
            return
        state.frontier.push(
            canonical_url=canonical, requested_url=normalized, depth=depth,
            discovery_source=source, anchor_text=anchor, from_page_id=from_page_id,
            score=evaluation.score,
        )
        self._edge(run, state, from_page_id, canonical, source, primary,
                   evaluation.score.score, "queued")

    # -- capture bookkeeping ------------------------------------------

    def _on_capture(
        self,
        run: ResearchRun,
        state: _State,
        queued: QueuedCandidate,
        page: ResearchPage,
        snapshot: MinimizedPageSnapshot,
        material: object,
        purpose: SemanticCategory,
    ) -> None:
        self._edge(run, state, queued.from_page_id, queued.canonical_url,
                   queued.discovery_source, queued.score.category, queued.score.score, "captured")
        state.counters.useful_pages += 1
        state.captured_pages.append((queued.canonical_url, purpose.value))
        if queued.score.category is not None:
            state.category_captures[queued.score.category] = (
                state.category_captures.get(queued.score.category, 0) + 1
            )
        new_categories = {purpose} - {SemanticCategory.UNCLASSIFIED}
        if queued.score.category is not None:
            new_categories.add(queued.score.category)
        progressed = bool(new_categories - state.captured_categories)
        state.captured_categories |= new_categories
        state.discovered_categories |= new_categories

        hits = m2_relevance_hits(snapshot.minimized_text)
        fresh = hits - state.m2_hits
        state.m2_hits |= set(hits)
        if progressed or fresh:
            state.captures_since_new_evidence = 0
        else:
            state.captures_since_new_evidence += 1

        if isinstance(material, ExtractedMaterial) and page.depth < run.policy.max_depth:
            for href, anchor_text, _rel in material.links:
                try:
                    link_norm = normalize_public_url(href)
                    if (urlsplit(link_norm).hostname or "") != run.permitted_host:
                        continue
                    link_canon = canonical_crawl_url(link_norm)
                except UrlPolicyError:
                    continue
                self._consider(run, state, link_norm, link_canon, anchor_text,
                               DiscoverySource.ON_PAGE_LINK, page.depth + 1, page.id, run.policy)

    # -- helpers ----------------------------------------------------

    def _purpose(self, normalized_url: str, material: object) -> SemanticCategory:
        title = material.title if isinstance(material, ExtractedMaterial) else None
        h1 = None
        if isinstance(material, ExtractedMaterial):
            for level, text, _ in material.headings:
                if level == 1:
                    h1 = text
                    break
        primary, _matched, _path = classify_category(
            canonical_crawl_url(normalized_url), "", title=title, h1=h1
        )
        return primary or SemanticCategory.UNCLASSIFIED

    def _page(
        self,
        run: ResearchRun,
        requested_url: str,
        normalized: str,
        depth: int,
        status: PageStatus,
        *,
        snapshot_id: UUID | None = None,
        material_id: UUID | None = None,
        fetched_at: datetime | None = None,
        error_code: str | None = None,
        page_purpose: str = "unclassified",
    ) -> ResearchPage:
        return ResearchPage(
            id=self._ids.new(), workspace_id=run.workspace_id, business_id=run.business_id,
            research_run_id=run.id, requested_url=requested_url, normalized_url=normalized,
            depth=depth, status=status, snapshot_id=snapshot_id, material_id=material_id,
            fetched_at=fetched_at, error_code=error_code, page_purpose=page_purpose,
        )

    def _edge(
        self,
        run: ResearchRun,
        state: _State,
        from_page_id: UUID | None,
        canonical: str,
        source: DiscoverySource,
        category: SemanticCategory | None,
        score: int,
        disposition: str,
    ) -> None:
        state.edges.append(DiscoveryEdge(
            id=self._ids.new(), workspace_id=run.workspace_id, research_run_id=run.id,
            from_page_id=from_page_id if isinstance(from_page_id, UUID) else None,
            discovered_url_canonical=canonical, discovery_source=source, category=category,
            score=score, disposition=disposition, recorded_at=self._clock.now(),
        ))

    def _coverage(
        self, run: ResearchRun, state: _State, elapsed_seconds: int
    ) -> M1CoverageRecord:
        searched = tuple(sorted(category.value for category in SemanticCategory))
        record = M1CoverageRecord(
            research_run_id=run.id,
            workspace_id=run.workspace_id,
            crawl_protocol_version=run.crawl_protocol_version or _PROTOCOL,
            candidate_urls_discovered=state.candidate_urls_discovered,
            candidate_source_breakdown=tuple(sorted(state.candidate_source_counts.items())),
            eligible_urls=max(0, len(state.frontier.known_urls()) - len(state.excluded)),
            duplicate_or_excluded_urls=tuple(state.excluded),
            pages_attempted=state.counters.pages_attempted,
            pages_successfully_captured=state.counters.useful_pages,
            captured_pages=tuple(state.captured_pages),
            pages_quarantined=state.counters.pages_quarantined,
            quarantined_pages=tuple(state.quarantined_pages),
            pages_denied_by_robots=state.counters.pages_denied_by_robots,
            robots_denied_pages=tuple(state.robots_denied_pages),
            transport_failures=state.counters.transport_failures,
            transport_failed_pages=tuple(state.transport_failed_pages),
            semantic_categories_searched=searched,
            semantic_categories_found=tuple(
                sorted(category.value for category in state.discovered_categories)
            ),
            semantic_categories_captured=tuple(
                sorted(category.value for category in state.captured_categories)
            ),
            sitemap_documents_fetched=state.sitemap_docs,
            robots_sitemap_directives_seen=state.robots_directives_seen,
            stop_reasons=tuple(reason.value for reason in state.stop_reasons),
            byte_budget_used=state.counters.total_bytes,
            time_budget_used_seconds=elapsed_seconds,
            attempts_used=state.counters.attempts_used,
            total_http_requests_used=state.counters.total_http_requests,
        )
        return record.sealed()
