"""Pure-unit tests for the PHASE1_M1_V2_BOUNDED_SITE_CRAWL relevance frontier."""

from __future__ import annotations

from opintel_research.domain import (
    CrawlStopReason,
    DiscoverySource,
    SemanticCategory,
)
from opintel_research.frontier import (
    CandidateScore,
    FrontierStopState,
    PriorityFrontier,
    classify_category,
    evaluate_candidate,
    is_low_value,
    score_candidate,
    should_stop,
)

_HV_NONE: frozenset[SemanticCategory] = frozenset()


def _stop_state(**overrides: object) -> FrontierStopState:
    base: dict[str, object] = dict(
        useful_pages_captured=1,
        max_useful_page_fetches=25,
        total_http_requests=3,
        max_total_http_requests=48,
        discovery_fetches=1,
        max_discovery_fetches=6,
        total_bytes=10_000,
        max_total_bytes=18_000_000,
        elapsed_seconds=1.0,
        max_duration_seconds=300,
        kill_switch_active=False,
        frontier_empty=False,
        high_value_categories_discovered=_HV_NONE,
        high_value_categories_captured=_HV_NONE,
        high_value_candidates_remaining_fit=False,
        best_remaining_score=5,
        low_relevance_floor=20,
        captures_since_new_evidence=0,
        no_progress_window=3,
    )
    base.update(overrides)
    return FrontierStopState(**base)  # type: ignore[arg-type]


def test_seed_always_scores_highest() -> None:
    seed = score_candidate("https://x.example/", "", 0, DiscoverySource.SEED, is_seed=True)
    other = score_candidate(
        "https://x.example/commercial", "Commercial HVAC", 1, DiscoverySource.DECLARED_SITEMAP
    )
    assert seed.score > other.score
    assert seed.category is SemanticCategory.HOMEPAGE


def test_path_hit_and_sitemap_bonus_and_multi_category() -> None:
    anchor = score_candidate(
        "https://x.example/x", "commercial hvac repair", 1, DiscoverySource.ON_PAGE_LINK
    )
    path = score_candidate(
        "https://x.example/commercial-hvac-repair", "", 1, DiscoverySource.ON_PAGE_LINK
    )
    sitemap = score_candidate(
        "https://x.example/commercial-hvac-repair", "", 1, DiscoverySource.DECLARED_SITEMAP
    )
    assert path.score > anchor.score
    assert sitemap.score > path.score
    assert len(path.matched_categories) >= 2


def test_depth_penalty_is_deterministic() -> None:
    shallow = score_candidate("https://x.example/services", "", 1, DiscoverySource.ON_PAGE_LINK)
    deep = score_candidate("https://x.example/services", "", 3, DiscoverySource.ON_PAGE_LINK)
    assert shallow.score - deep.score == 10


def test_classify_category_semantic_not_url_name() -> None:
    primary, _matched, path_hit = classify_category(
        "https://x.example/p/17", "Request Service / Schedule an Appointment"
    )
    assert primary is SemanticCategory.REQUEST_SERVICE_SCHEDULING
    assert path_hit is False


def test_low_value_predicates() -> None:
    assert is_low_value("https://x.example/blog/2019/10/a-post") == "blog_archive"
    assert is_low_value("https://x.example/privacy") == "legal"
    assert is_low_value("https://x.example/search?q=ac") == "search"
    assert is_low_value("https://x.example/wp-login.php") == "auth"
    assert is_low_value("https://x.example/logo.png") == "feed_asset"
    assert is_low_value("https://x.example/commercial") is None


def test_evaluate_excludes_low_value_and_deep_paths() -> None:
    assert not evaluate_candidate(
        "https://x.example/privacy", "Privacy Policy", 1, DiscoverySource.ON_PAGE_LINK
    ).admit
    deep = evaluate_candidate(
        "https://x.example/a/b/c/d/e/f/g", "", 2, DiscoverySource.ON_PAGE_LINK,
        max_path_segments=6,
    )
    assert not deep.admit and deep.disposition_reason == "excluded:path_too_deep"


def test_blog_archive_demoted_when_category_matches() -> None:
    ev = evaluate_candidate(
        "https://x.example/blog/commercial-hvac-maintenance-guide",
        "Commercial HVAC Maintenance", 1, DiscoverySource.ON_PAGE_LINK,
    )
    assert ev.admit and ev.demoted and ev.score.score <= 10


def test_query_variant_loop_defense_is_caller_owned_but_scoreable() -> None:
    # canonicalisation strips tracking params; the frontier still scores what is left.
    a = score_candidate("https://x.example/cal?d=1", "", 1, DiscoverySource.ON_PAGE_LINK)
    b = score_candidate("https://x.example/cal?d=2", "", 1, DiscoverySource.ON_PAGE_LINK)
    assert a.tie_break_key != b.tie_break_key


def test_priority_frontier_total_order_is_deterministic() -> None:
    def build() -> PriorityFrontier:
        frontier = PriorityFrontier()
        for url, anchor in [
            ("https://x.example/about", "About"),
            ("https://x.example/commercial", "Commercial HVAC"),
            ("https://x.example/contact", "Contact Us"),
            ("https://x.example/random", "random"),
        ]:
            score = score_candidate(url, anchor, 1, DiscoverySource.ON_PAGE_LINK)
            frontier.push(
                canonical_url=url, requested_url=url, depth=1,
                discovery_source=DiscoverySource.ON_PAGE_LINK, anchor_text=anchor,
                from_page_id=None, score=score,
            )
        return frontier

    def drain() -> list[str]:
        frontier = build()
        out: list[str] = []
        while (item := frontier.pop_best()) is not None:
            out.append(item.canonical_url)
        return out

    urls_one = drain()
    urls_two = drain()
    assert urls_one == urls_two
    assert urls_one[0] == "https://x.example/commercial"
    assert urls_one[-1] == "https://x.example/random"


def test_should_stop_hard_ceilings() -> None:
    assert CrawlStopReason.USEFUL_PAGE_BUDGET_EXCEEDED in should_stop(
        _stop_state(useful_pages_captured=25)
    )
    assert CrawlStopReason.BYTE_BUDGET_EXCEEDED in should_stop(
        _stop_state(total_bytes=18_000_000)
    )
    assert CrawlStopReason.CRAWL_DURATION_EXCEEDED in should_stop(
        _stop_state(elapsed_seconds=300.0)
    )
    assert CrawlStopReason.KILL_SWITCH_ACTIVE in should_stop(_stop_state(kill_switch_active=True))
    assert CrawlStopReason.FRONTIER_EXHAUSTED in should_stop(_stop_state(frontier_empty=True))


def test_no_new_evidence_blocked_while_high_value_pending() -> None:
    # 3 stale captures, but a high-value category candidate still fits budget.
    reasons = should_stop(
        _stop_state(
            captures_since_new_evidence=3,
            high_value_candidates_remaining_fit=True,
            high_value_categories_discovered=frozenset({SemanticCategory.COMMERCIAL_HVAC}),
        )
    )
    assert CrawlStopReason.NO_NEW_EVIDENCE not in reasons
    assert CrawlStopReason.HIGH_VALUE_CATEGORIES_SATISFIED not in reasons


def test_no_new_evidence_fires_once_high_value_exhausted() -> None:
    reasons = should_stop(
        _stop_state(
            captures_since_new_evidence=3,
            high_value_candidates_remaining_fit=False,
            best_remaining_score=5,
            high_value_categories_discovered=frozenset({SemanticCategory.COMMERCIAL_HVAC}),
            high_value_categories_captured=frozenset({SemanticCategory.COMMERCIAL_HVAC}),
        )
    )
    assert CrawlStopReason.NO_NEW_EVIDENCE in reasons


def test_high_value_satisfied_when_all_captured_and_only_low_left() -> None:
    reasons = should_stop(
        _stop_state(
            high_value_candidates_remaining_fit=False,
            best_remaining_score=5,
            high_value_categories_discovered=frozenset({SemanticCategory.SERVICES}),
            high_value_categories_captured=frozenset({SemanticCategory.SERVICES}),
        )
    )
    assert CrawlStopReason.HIGH_VALUE_CATEGORIES_SATISFIED in reasons


def test_candidate_score_is_hashable_frozen() -> None:
    score = CandidateScore(SemanticCategory.SERVICES, 100, "k", (SemanticCategory.SERVICES,), True)
    assert hash(score)
