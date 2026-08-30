"""Deterministic, pure relevance frontier for PHASE1_M1_V2_BOUNDED_SITE_CRAWL.

No I/O, no clock, no randomness. Everything the frontier needs (visited set,
per-category counts, captured-evidence signal, remaining budget) is passed in by
``workflow.py``. Given identical site bytes the crawl order and stop decision are
byte-for-byte reproducible.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from opintel_research.domain import (
    _SITEMAP_DISCOVERY_SOURCES,
    HIGH_VALUE_CATEGORIES,
    SEMANTIC_CATEGORIES,
    CrawlStopReason,
    DiscoverySource,
    SemanticCategory,
)

_UNCLASSIFIED_BASE = 20
_HIGH_VALUE_BASE = 100
_PATH_HIT_BONUS = 15
_SITEMAP_BONUS = 10
_EXTRA_CATEGORY_BONUS = 5
_DEPTH_PENALTY = 5
_BLOG_ARCHIVE_BASE = 10
_SEED_SCORE = 10_000

# Deterministic tie-break priority when a URL matches several high-value
# categories: the dict insertion order of SEMANTIC_CATEGORIES.
_CATEGORY_PRIORITY: dict[SemanticCategory, int] = {
    category: index for index, category in enumerate(SEMANTIC_CATEGORIES)
}

_LOW_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("blog_archive", re.compile(r"(?:^|/)(?:blog|news|articles|posts|press)(?:/|$)")),
    (
        "pagination",
        re.compile(r"(?:^|/)page/\d+|[?&]paged?=|/category/|/tag/|/author/|/\d{4}/\d{2}/"),
    ),
    ("search", re.compile(r"(?:^|/)search(?:/|$)|[?&]s=|[?&]q=")),
    (
        "auth",
        re.compile(
            r"(?:^|/)(?:login|logout|register|signin|sign-in|account|my-account"
            r"|wp-admin|wp-login|cart|checkout)(?:/|$|\.)"
        ),
    ),
    (
        "legal",
        re.compile(
            r"(?:^|/)(?:privacy|cookie|cookies|terms|terms-of-service|legal"
            r"|disclaimer|accessibility|sitemap-page|gdpr)(?:/|$)"
        ),
    ),
    (
        "feed_asset",
        re.compile(
            r"(?:^|/)feed(?:/|$)|\.(?:rss|atom|pdf|jpe?g|png|gif|svg|webp|css|js"
            r"|zip|gz|mp4|mov|woff2?|ico)(?:$|\?)"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class CandidateScore:
    category: SemanticCategory | None
    score: int
    tie_break_key: str
    matched_categories: tuple[SemanticCategory, ...]
    path_hit: bool


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    admit: bool
    disposition_reason: str | None
    demoted: bool
    score: CandidateScore


def _tokens(canonical_url: str) -> tuple[str, bool]:
    parsed = urlsplit(canonical_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    query_keys = [pair.split("=", 1)[0] for pair in parsed.query.split("&") if pair]
    haystack = " ".join(segments + query_keys).replace("-", " ").replace("_", " ").lower()
    return f" {haystack} ", bool(segments)


def _text_haystack(*parts: str | None) -> str:
    joined = " ".join(part for part in parts if part)
    return f" {joined.replace('-', ' ').replace('_', ' ').lower()} "


def classify_category(
    canonical_url: str,
    anchor_text: str = "",
    *,
    title: str | None = None,
    h1: str | None = None,
) -> tuple[SemanticCategory | None, tuple[SemanticCategory, ...], bool]:
    """Return (primary_category, all_matched_categories, primary_is_path_hit)."""
    path_haystack, _has_segments = _tokens(canonical_url)
    text_haystack = _text_haystack(anchor_text, title, h1)
    matched: dict[SemanticCategory, bool] = {}
    for category, keywords in SEMANTIC_CATEGORIES.items():
        in_path = any(keyword in path_haystack for keyword in keywords)
        in_text = in_path or any(keyword in text_haystack for keyword in keywords)
        if in_text:
            matched[category] = in_path
    if not matched:
        return None, (), False
    ordered = sorted(
        matched, key=lambda category: (not matched[category], _CATEGORY_PRIORITY[category])
    )
    primary = ordered[0]
    return primary, tuple(ordered), matched[primary]


def is_low_value(canonical_url: str, anchor_text: str = "") -> str | None:
    parsed = urlsplit(canonical_url)
    probe = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
    probe = probe.lower()
    for reason, pattern in _LOW_VALUE_PATTERNS:
        if pattern.search(probe):
            return reason
    return None


def score_candidate(
    canonical_url: str,
    anchor_text: str,
    depth: int,
    discovery_source: DiscoverySource,
    *,
    is_seed: bool = False,
    title: str | None = None,
    h1: str | None = None,
) -> CandidateScore:
    if is_seed:
        return CandidateScore(
            SemanticCategory.HOMEPAGE, _SEED_SCORE, "", (SemanticCategory.HOMEPAGE,), True
        )
    primary, matched, path_hit = classify_category(
        canonical_url, anchor_text, title=title, h1=h1
    )
    if primary is None:
        score = _UNCLASSIFIED_BASE - _DEPTH_PENALTY * depth
        return CandidateScore(None, score, f"~\x1f{canonical_url}", (), False)
    score = _HIGH_VALUE_BASE
    if path_hit:
        score += _PATH_HIT_BONUS
    if discovery_source in _SITEMAP_DISCOVERY_SOURCES:
        score += _SITEMAP_BONUS
    score += _EXTRA_CATEGORY_BONUS * max(0, len(matched) - 1)
    score -= _DEPTH_PENALTY * depth
    return CandidateScore(
        primary, score, f"{primary.value}\x1f{canonical_url}", matched, path_hit
    )


def evaluate_candidate(
    canonical_url: str,
    anchor_text: str,
    depth: int,
    discovery_source: DiscoverySource,
    *,
    is_seed: bool = False,
    max_path_segments: int = 6,
    title: str | None = None,
    h1: str | None = None,
) -> CandidateEvaluation:
    score = score_candidate(
        canonical_url, anchor_text, depth, discovery_source,
        is_seed=is_seed, title=title, h1=h1,
    )
    if is_seed:
        return CandidateEvaluation(True, None, False, score)
    segments = [segment for segment in urlsplit(canonical_url).path.split("/") if segment]
    if len(segments) > max_path_segments:
        return CandidateEvaluation(False, "excluded:path_too_deep", False, score)
    low = is_low_value(canonical_url, anchor_text)
    if low is None:
        return CandidateEvaluation(True, None, False, score)
    high_value_path_hit = score.category is not None and score.path_hit
    if low == "blog_archive":
        if high_value_path_hit or score.category is not None:
            demoted = CandidateScore(
                score.category, min(score.score, _BLOG_ARCHIVE_BASE),
                score.tie_break_key, score.matched_categories, score.path_hit,
            )
            return CandidateEvaluation(True, None, True, demoted)
        return CandidateEvaluation(False, "excluded:blog_archive", False, score)
    if high_value_path_hit:
        demoted = CandidateScore(
            score.category, min(score.score, _BLOG_ARCHIVE_BASE),
            score.tie_break_key, score.matched_categories, score.path_hit,
        )
        return CandidateEvaluation(True, None, True, demoted)
    return CandidateEvaluation(False, f"excluded:{low}", False, score)


@dataclass(frozen=True, slots=True)
class FrontierStopState:
    useful_pages_captured: int
    max_useful_page_fetches: int
    total_http_requests: int
    max_total_http_requests: int
    discovery_fetches: int
    max_discovery_fetches: int
    total_bytes: int
    max_total_bytes: int
    elapsed_seconds: float
    max_duration_seconds: int
    kill_switch_active: bool
    frontier_empty: bool
    high_value_categories_discovered: frozenset[SemanticCategory]
    high_value_categories_captured: frozenset[SemanticCategory]
    high_value_candidates_remaining_fit: bool
    best_remaining_score: int
    low_relevance_floor: int
    captures_since_new_evidence: int
    no_progress_window: int


def should_stop(state: FrontierStopState) -> tuple[CrawlStopReason, ...]:
    reasons: list[CrawlStopReason] = []
    if state.kill_switch_active:
        reasons.append(CrawlStopReason.KILL_SWITCH_ACTIVE)
    if state.useful_pages_captured >= state.max_useful_page_fetches:
        reasons.append(CrawlStopReason.USEFUL_PAGE_BUDGET_EXCEEDED)
    if state.total_http_requests >= state.max_total_http_requests:
        reasons.append(CrawlStopReason.TOTAL_REQUEST_BUDGET_EXCEEDED)
    if state.discovery_fetches >= state.max_discovery_fetches and state.frontier_empty:
        # discovery budget alone does not stop page capture; only relevant when
        # combined with an empty frontier (nothing left to try).
        pass
    if state.total_bytes >= state.max_total_bytes:
        reasons.append(CrawlStopReason.BYTE_BUDGET_EXCEEDED)
    if state.elapsed_seconds >= state.max_duration_seconds:
        reasons.append(CrawlStopReason.CRAWL_DURATION_EXCEEDED)
    if state.frontier_empty:
        reasons.append(CrawlStopReason.FRONTIER_EXHAUSTED)

    # Owner refinement: neither saturation rule may fire while a discovered
    # high-priority category is still unattempted AND fits the remaining budget.
    high_value_coverage_pending = state.high_value_candidates_remaining_fit
    if not high_value_coverage_pending and not state.frontier_empty:
        uncaptured = state.high_value_categories_discovered - state.high_value_categories_captured
        if not uncaptured and state.best_remaining_score < state.low_relevance_floor:
            reasons.append(CrawlStopReason.HIGH_VALUE_CATEGORIES_SATISFIED)
        elif uncaptured and state.best_remaining_score < state.low_relevance_floor:
            # remaining high-value categories cannot be reached within budget
            reasons.append(CrawlStopReason.HIGH_VALUE_CATEGORIES_SATISFIED)
        if state.captures_since_new_evidence >= state.no_progress_window:
            reasons.append(CrawlStopReason.NO_NEW_EVIDENCE)

    # Deduplicate preserving first-seen order.
    seen: set[CrawlStopReason] = set()
    ordered: list[CrawlStopReason] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return tuple(ordered)


@dataclass(slots=True)
class _Queued:
    canonical_url: str
    requested_url: str
    depth: int
    discovery_source: DiscoverySource
    anchor_text: str
    from_page_id: object
    score: CandidateScore


@dataclass(slots=True)
class PriorityFrontier:
    """Deterministic priority queue keyed by (-score, category_name, canonical_url)."""

    _queued: dict[str, _Queued] = field(default_factory=dict)
    _known: set[str] = field(default_factory=set)

    def has_seen(self, canonical_url: str) -> bool:
        return canonical_url in self._known

    def mark_seen(self, canonical_url: str) -> None:
        self._known.add(canonical_url)

    def push(
        self,
        *,
        canonical_url: str,
        requested_url: str,
        depth: int,
        discovery_source: DiscoverySource,
        anchor_text: str,
        from_page_id: object,
        score: CandidateScore,
    ) -> bool:
        if canonical_url in self._known:
            return False
        self._known.add(canonical_url)
        self._queued[canonical_url] = _Queued(
            canonical_url, requested_url, depth, discovery_source, anchor_text,
            from_page_id, score,
        )
        return True

    def __len__(self) -> int:
        return len(self._queued)

    @staticmethod
    def _order_key(item: _Queued) -> tuple[int, int, str]:
        rank = (
            _CATEGORY_PRIORITY[item.score.category]
            if item.score.category is not None
            else len(_CATEGORY_PRIORITY)
        )
        return (-item.score.score, rank, item.canonical_url)

    def best_score(self) -> int:
        if not self._queued:
            return -(10**9)
        return max(item.score.score for item in self._queued.values())

    def pop_best(self) -> _Queued | None:
        if not self._queued:
            return None
        best = min(self._queued.values(), key=self._order_key)
        del self._queued[best.canonical_url]
        return best

    def remaining_high_value_fits(self, fits: Callable[[_Queued], bool]) -> bool:
        for item in self._queued.values():
            category = item.score.category
            if category not in HIGH_VALUE_CATEGORIES or category is SemanticCategory.HOMEPAGE:
                continue
            if fits(item):
                return True
        return False

    def queued_high_value_categories(self) -> frozenset[SemanticCategory]:
        return frozenset(
            item.score.category
            for item in self._queued.values()
            if item.score.category in HIGH_VALUE_CATEGORIES
        )
