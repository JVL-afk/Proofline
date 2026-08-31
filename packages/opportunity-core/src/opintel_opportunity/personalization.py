"""Evidence-preserving personalization V2.

Selection and reader-facing rendering are separate concerns.

* ``select_company_facts`` deterministically picks 0-4 ``CompanyFact`` records
  from already-accepted M1 evidence. Each fact carries an exact minimized
  source fragment substring (``phrase``) for provenance.
* The semantic-frame renderers insert supported business / service /
  service-area / intake facts through fixed plain-English frames. They may
  normalize grammatical form. They may not introduce a new factual claim,
  strengthen certainty, infer internal behavior, invent economics, or combine
  facts in a way that changes their meaning.

No AI. No network. Identical inputs produce byte-identical output.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from opintel_m0.ports import IdentifierFactory

from opintel_opportunity.domain import (
    CompanyFact,
    EvidenceReference,
    FactCategory,
    ResearchRunStats,
    ReviewRankHint,
)

SELECTOR_VERSION = "commercial_hvac.company_fact_selector@2"
STATEMENT_FRAME_VERSION = "commercial_hvac.company_statement@2"

# Fixed hypothetical scaffold. Retains every existing UNKNOWN and the "could"
# conditional. Must keep the substrings "response performance", "internal
# routing", and "unknown" for downstream truth assertions.
_HYPOTHETICAL_TAIL = (
    " Given those observed public intake surfaces, a structured acknowledgement "
    "and qualification workflow could be evaluated. Current response performance, "
    "internal routing, lead volume, conversion, feasibility, and economic impact "
    "remain unknown pending business verification."
)

# Legacy statement, used verbatim when no company fact qualifies.
LEGACY_SAFE_STATEMENT = (
    "Public pages show that the business invites commercial HVAC inquiries through observed "
    "digital channels. A structured acknowledgement and qualification workflow could be evaluated "
    "for those channels. Current response performance, internal routing, lead volume, conversion, "
    "feasibility, and economic impact remain unknown pending business verification."
)

_CATEGORY_ORDER: tuple[FactCategory, ...] = (
    FactCategory.INTAKE_SURFACE,
    FactCategory.COMMERCIAL_CONTEXT,
    FactCategory.RESPONSE_COMMITMENT,
    FactCategory.SERVICE_AREA_CONTEXT,
    FactCategory.SERVICE_AVAILABILITY,
)


def company_fact_sort_key(fact: CompanyFact) -> tuple[int, str]:
    """Deterministic canonical ordering for a set of selected CompanyFacts,
    independent of identifier assignment or persistence order."""

    try:
        rank = _CATEGORY_ORDER.index(fact.category)
    except ValueError:
        rank = len(_CATEGORY_ORDER)
    return (rank, fact.phrase)

_PAGE_PURPOSE_PRIORITY: tuple[str, ...] = (
    "request_service_scheduling",
    "estimate_quote",
    "contact_mechanism",
    "commercial_hvac",
    "services",
    "maintenance",
    "heating",
    "cooling_ac",
    "repair",
    "installation",
    "residential_hvac",
    "emergency_service",
    "service_area_location",
    "about",
    "faq",
    "financing",
    "homepage",
    "unclassified",
)

# RESPONSE_COMMITMENT (selector@2): only phrases that inherently describe how an
# inbound contact is acknowledged / answered / returned / responded to. Bare
# service-availability language ("24/7", "24-hour service", "same-day service",
# "emergency service", "fast service") is deliberately NOT here -- it is
# SERVICE_AVAILABILITY.
_RESPONSE_COMMITMENT_CUES: tuple[str, ...] = (
    "phones are answered",
    "phone is answered",
    "phones answered",
    "calls are answered",
    "call is answered",
    "calls answered",
    "we answer your",
    "answered 24",
    "answered around",
    "answered within",
    "answered the same",
    "answered the next",
    "email response",
    "email responses",
    "responses are sent",
    "respond to your",
    "respond to inquiries",
    "respond to inquiry",
    "respond to requests",
    "we respond within",
    "we will respond",
    "respond within",
    "response within",
    "reply to your",
    "reply within",
    "we reply within",
    "we will reply",
    "call you back",
    "call back within",
    "callback within",
    "return your call",
    "returned within",
    "get back to you",
    "we will contact you",
    "contacted after",
    "contacted within",
    "contacted the following",
    "contacted the next",
    "acknowledge your",
    "acknowledged within",
    "by the next business day",
    "next business day",
    "same business day",
    "within one business day",
    "response time",
    "response times",
)
# SERVICE_AVAILABILITY (selector@2): a bare public availability claim. Eligible
# for a supporting availability fact; never upgraded to response behaviour.
_SERVICE_AVAILABILITY_CUES: tuple[str, ...] = (
    "24/7",
    "24-7",
    "24 hour",
    "24-hour",
    "24 hours a day",
    "hours a day, 7 days",
    "around the clock",
    "round-the-clock",
    "same day service",
    "same-day service",
    "emergency service",
    "emergency services",
    "available any time",
    "day or night",
)
_RESPONSE_FACT_CLASSES = frozenset(
    {"public_inbound_path", "public_faq", "public_about", "public_other"}
)
_AVAILABILITY_FACT_CLASSES = frozenset(
    {"public_inbound_path", "public_faq", "public_about", "public_other",
     "public_service_description"}
)
_INTAKE_KEYWORDS: tuple[str, ...] = (
    "request service",
    "request a quote",
    "request an estimate",
    "request estimate",
    "schedule service",
    "book online",
    "free estimate",
    "get a quote",
    "get an estimate",
    "contact us",
    "appointment",
    "schedule",
    "quote",
    "estimate",
    "contact",
)
_COMMERCIAL_KEYWORDS: tuple[str, ...] = (
    "light commercial",
    "commercial maintenance",
    "commercial hvac",
    "commercial heating",
    "commercial cooling",
    "commercial air",
    "commercial and residential",
    "commercial & residential",
    "commercial",
)
_SERVICE_AREA_KEYWORDS: tuple[str, ...] = (
    "service area",
    "areas we serve",
    "cities we serve",
    "serving",
    "proudly serve",
    "locations",
    ", tx",
    ", texas",
    "texas",
)

_SENTENCE_END = re.compile(r"[.!?;]")
_MAX_PHRASE_CHARS = 160
_MIN_PHRASE_CHARS = 8


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _extract_phrase(fragment: str, keywords: tuple[str, ...]) -> str | None:
    """Shortest contiguous verbatim run of ``fragment`` around the first
    matching keyword, snapped to sentence boundaries, capped at 160 chars.
    Returns a whitespace-normalized substring of ``fragment`` (normalized)."""

    norm = _normalize(fragment)
    low = norm.lower()
    hit = -1
    hit_len = 0
    for keyword in keywords:
        index = low.find(keyword)
        if index != -1 and (hit == -1 or index < hit):
            hit = index
            hit_len = len(keyword)
    if hit == -1:
        return None
    start = 0
    for match in _SENTENCE_END.finditer(norm, 0, hit):
        start = match.end()
    end = len(norm)
    tail = _SENTENCE_END.search(norm, hit + hit_len)
    if tail is not None:
        end = tail.end()
    phrase = norm[start:end].strip().strip("\t|-").strip()
    if len(phrase) > _MAX_PHRASE_CHARS:
        phrase = phrase[:_MAX_PHRASE_CHARS].rsplit(" ", 1)[0].strip()
    phrase = _normalize(phrase)
    if len(phrase) < _MIN_PHRASE_CHARS:
        return None
    return phrase


def _bucket(item: EvidenceReference) -> FactCategory | None:
    low = _normalize(item.fragment).lower()
    # RESPONSE_COMMITMENT is the most specific, highest-value signal: a page that
    # actually states how inbound contact is handled is classified as a response
    # commitment even when it is also an intake surface (a contact page usually is
    # both). Checked first so the specific classification wins.
    if item.fact_class in _RESPONSE_FACT_CLASSES and any(
        k in low for k in _RESPONSE_COMMITMENT_CUES
    ):
        return FactCategory.RESPONSE_COMMITMENT
    if item.fact_class == "public_inbound_path" and any(k in low for k in _INTAKE_KEYWORDS):
        return FactCategory.INTAKE_SURFACE
    if item.fact_class == "public_service_area" and any(k in low for k in _SERVICE_AREA_KEYWORDS):
        return FactCategory.SERVICE_AREA_CONTEXT
    if item.fact_class == "public_service_description" and "commercial" in low:
        return FactCategory.COMMERCIAL_CONTEXT
    if item.fact_class in _AVAILABILITY_FACT_CLASSES and any(
        k in low for k in _SERVICE_AVAILABILITY_CUES
    ):
        return FactCategory.SERVICE_AVAILABILITY
    return None


def _rank_key(item: EvidenceReference) -> tuple[int, int, str]:
    try:
        purpose_rank = _PAGE_PURPOSE_PRIORITY.index(item.page_purpose)
    except ValueError:
        purpose_rank = len(_PAGE_PURPOSE_PRIORITY)
    return (purpose_rank, len(_normalize(item.fragment)), str(item.id))


_CATEGORY_KEYWORDS: dict[FactCategory, tuple[str, ...]] = {
    FactCategory.INTAKE_SURFACE: _INTAKE_KEYWORDS,
    FactCategory.COMMERCIAL_CONTEXT: _COMMERCIAL_KEYWORDS,
    FactCategory.RESPONSE_COMMITMENT: _RESPONSE_COMMITMENT_CUES,
    FactCategory.SERVICE_AREA_CONTEXT: _SERVICE_AREA_KEYWORDS,
    FactCategory.SERVICE_AVAILABILITY: _SERVICE_AVAILABILITY_CUES,
}


def select_company_facts(
    hypothesis_logical_id: UUID,
    evidence: tuple[EvidenceReference, ...],
    identifiers: IdentifierFactory,
    now: datetime,
) -> tuple[CompanyFact, ...]:
    """Deterministic ``company_fact_selector@2``. At most one fact per category,
    fixed category order, cap 4. A category with no qualifying evidence is
    simply absent -- public absence is never rendered as a claim."""

    buckets: dict[FactCategory, list[EvidenceReference]] = {c: [] for c in _CATEGORY_ORDER}
    for item in evidence:
        category = _bucket(item)
        if category is not None:
            buckets[category].append(item)
    used_evidence_ids: set[UUID] = set()
    facts: list[CompanyFact] = []
    for category in _CATEGORY_ORDER:
        candidates = sorted(
            (item for item in buckets[category] if item.id not in used_evidence_ids),
            key=_rank_key,
        )
        for candidate in candidates:
            phrase = _extract_phrase(candidate.fragment, _CATEGORY_KEYWORDS[category])
            if phrase is None:
                continue
            facts.append(
                CompanyFact(
                    id=identifiers.new(),
                    hypothesis_id=hypothesis_logical_id,
                    category=category,
                    phrase=phrase,
                    evidence_id=candidate.id,
                    fact_class=candidate.fact_class,
                    page_purpose=candidate.page_purpose,
                    source_uri=candidate.source_uri,
                    content_sha256=candidate.content_sha256,
                    selector_version=SELECTOR_VERSION,
                    created_at=now,
                )
            )
            used_evidence_ids.add(candidate.id)
            break
    return tuple(facts)


# --------------------------------------------------------------------------
# Semantic-frame renderers. Fixed frames; supported facts only.
# --------------------------------------------------------------------------

def _clean_phrase(phrase: str) -> str:
    text = phrase.strip().rstrip(".;:,")
    return text


def statement_clause(category: FactCategory, phrase: str) -> str:
    value = _clean_phrase(phrase)
    if category == FactCategory.INTAKE_SURFACE:
        return f'presents a public request path ("{value}")'
    if category == FactCategory.COMMERCIAL_CONTEXT:
        return f'describes commercial HVAC work ("{value}")'
    if category == FactCategory.RESPONSE_COMMITMENT:
        return (
            "publishes on its contact page how inbound inquiries are answered and "
            "returned"
        )
    if category == FactCategory.SERVICE_AREA_CONTEXT:
        return f'lists a public service area ("{value}")'
    return "references round-the-clock or emergency service availability on its public pages"


def build_statement(business_name: str, facts: tuple[CompanyFact, ...]) -> str:
    """Company-specific hypothetical M2 statement. Falls back to the exact legacy
    statement when no fact qualifies (keeps evidence-poor businesses unchanged)."""

    if not facts:
        return LEGACY_SAFE_STATEMENT
    clauses = [statement_clause(fact.category, fact.phrase) for fact in facts]
    if len(clauses) == 1:
        joined = clauses[0]
    elif len(clauses) == 2:
        joined = f"{clauses[0]} and {clauses[1]}"
    else:
        joined = f"{', '.join(clauses[:-1])}, and {clauses[-1]}"
    return f"{business_name} publicly {joined}.{_HYPOTHETICAL_TAIL}"


# Reader-facing (M5) fact frames -- digit-safe by construction.
_QUOTABLE_CATEGORIES = frozenset(
    {
        FactCategory.INTAKE_SURFACE,
        FactCategory.COMMERCIAL_CONTEXT,
        FactCategory.SERVICE_AREA_CONTEXT,
    }
)
_DIGIT = re.compile(r"\d")


_TRAIL = "-,;:.&/|" + chr(0x2013) + chr(0x2014)  # punct + en/em dash


def short_phrase(phrase: str, max_words: int = 9) -> str:
    words = _clean_phrase(phrase).split()
    if len(words) > max_words:
        words = words[:max_words]
    # drop trailing dangling connector words / punctuation so a truncated quote
    # does not end mid-clause.
    while words and (
        words[-1].strip(_TRAIL) == ""
        or words[-1].lower() in {"and", "or", "the", "a", "for", "to", "of", "with"}
    ):
        words.pop()
    return " ".join(words).rstrip(_TRAIL + " ")


def reader_fact_sentence(business_name: str, category: FactCategory, phrase: str) -> str:
    value = short_phrase(phrase, 7)
    if category in _QUOTABLE_CATEGORIES and not _DIGIT.search(value):
        if category == FactCategory.INTAKE_SURFACE:
            return f'your website has a public request path — "{value}".'
        if category == FactCategory.COMMERCIAL_CONTEXT:
            return f'your site describes commercial HVAC work — "{value}".'
        return f'your site lists a public service area — "{value}".'
    if category == FactCategory.SERVICE_AVAILABILITY:
        return "your site also references round-the-clock or emergency service availability."
    return "your contact page describes how inbound inquiries are answered and returned."


def is_reader_specific(category: FactCategory, phrase: str) -> bool:
    """Whether this fact renders a materially company-specific reader sentence
    (a quotable, digit-free phrase). Response-commitment facts are supported but
    render as a fixed frame, so they do not by themselves satisfy the gate."""

    return category in _QUOTABLE_CATEGORIES and not _DIGIT.search(_clean_phrase(phrase))


def review_rank_hint(
    priority_band: str,
    facts: tuple[CompanyFact, ...],
    run_stats: ResearchRunStats | None,
) -> ReviewRankHint:
    return ReviewRankHint(
        priority_band=priority_band,
        evidence_fact_count=len(facts),
        distinct_fact_classes=len({fact.fact_class for fact in facts}),
        partial_crawl=bool(run_stats and run_stats.partial),
    )
