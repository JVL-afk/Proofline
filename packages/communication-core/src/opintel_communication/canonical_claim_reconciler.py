"""``comm.canonical_claim_reconciler@2`` - the deterministic canonical claim map.

Owner authorization 2026-09-02 "FINAL M6.8-3 ARCHITECTURAL CORRECTION": the
provider-authored claim manifest is no longer authoritative. This component
independently discovers, classifies, and licenses every materially substantive
span of the *rendered* prose against the semantic envelope. Its output
(``comm.canonical_claim_map@2``) is what deterministic validation reasons about.

``@2`` (M6.8-3 FINAL CLOSEOUT ITERATION, owner authorization 2026-09-02): the
bounded attribution/framing verb family gained "labeled" / "titled" / "named" /
"termed" / ... (generalised, not a per-sentence exception), and "either" /
"neither" inside a recognised coordinating construction are grammatical glue.
Neither change licenses a substantive object/predicate - each is still
independently discovered, classified, source-licensed and strength-checked.

The provider manifest, if supplied, is used ONLY as non-authoritative diagnostic
hints - never to decide what claims exist, which are licensed, source authority,
strength, UNKNOWN state, or CTA legality. An omitted or wrong provider-manifest
row can never route a substantive claim around licensing (section 4, fail-closed).

No LLM. No second-provider call. All logic is the bounded deterministic
machinery already validated for this communication domain, reused: clause
segmentation, ``_classify``, the fact / framing / usage-rule vocabularies, light
morphology, negation awareness, the strength lattice, ``_detected_strength``, and
the prohibited-concept detectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from opintel_outreach.composition import _PLACEHOLDER

from opintel_communication.domain import (
    ClaimManifest,
    ClaimType,
    ConditionalInference,
    EnvelopeFact,
    FactStrength,
    M3FindingRef,
    Recommendation,
    RequiredDisclosure,
    SemanticEnvelope,
    StructuredCTA,
    ValidatorFinding,
)
from opintel_communication.policy import CONDITIONAL_CUES
from opintel_communication.validator import (
    _SAFE_FRAMING_VOCAB,
    _V2_FRAMING_VOCAB,
    _classify,
    _content_words,
    _content_words_v2,
    _detected_strength,
    _f,
    _fact_vocab,
    _is_framing_leadin,
    _licensed_framing_vocab,
    _licensed_numeric_strings,
    _norm,
    _only_in_negation,
    _rank,
    _split_clauses,
    _stem_covered,
)

_QUOTED = re.compile(r'"([^"]{2,})"')

CANONICAL_CLAIM_RECONCILER_VERSION = "comm.canonical_claim_reconciler@2"
CANONICAL_CLAIM_MAP_VERSION = "comm.canonical_claim_map@2"

# M6.8-3 FINAL CLOSEOUT ITERATION (owner authorization 2026-09-02, sections 1-2).
#
# (1) The bounded attribution / framing verb family. A verb in this set only
# FRAMES a public-page observation ("the site lists X", "a path labeled Y", "a
# section titled Z") - it introduces no substantive meaning of its own and is
# consistent with the family the reconciler already treats as glue ("listed",
# "described", "referenced", "mentioned", "noted"). Adding "labeled" (and
# "titled" / "named" / "termed" / ...) generalises that family; it is NOT a
# per-sentence string exception. A framing verb licenses NOTHING by itself: the
# object / predicate that follows ("'24/7 Emergency Service'", "responding in
# five minutes") is still independently discovered, classified, source-licensed
# and strength-checked below, so an unsupported claim attached to one of these
# verbs still fails closed.
_ATTRIBUTION_FRAMING_VOCAB: frozenset[str] = frozenset(
    {
        "label",
        "labels",
        "labeled",
        "labelled",
        "labeling",
        "labelling",
        "title",
        "titles",
        "titled",
        "titling",
        "name",
        "names",
        "named",
        "naming",
        "call",
        "calls",
        "called",
        "calling",
        "term",
        "terms",
        "termed",
        "terming",
        "dub",
        "dubs",
        "dubbed",
        "caption",
        "captions",
        "captioned",
        "headlined",
        "styled",
        "denote",
        "denotes",
        "denoted",
        "designate",
        "designates",
        "designated",
    }
)

# (2) "either" / "neither" are grammatical function words with no substantive
# proposition of their own. They are treated as glue ONLY inside a recognised
# coordinating / determiner construction (see ``_grammatical_function_word``);
# a bare unexplained occurrence stays UNRESOLVED and fails closed (section 2:
# "do not simply globally ignore the token without context").
_FUNCTION_WORD_CONSTRUCTS: dict[str, re.Pattern[str]] = {
    "either": re.compile(
        r"\beither\s+(?:way|ways|side|end|one|option|options|of\s+(?:those|these|them|the\s+two)|"
        r"direction|case|scenario|approach|kind|sort)\b"
        r"|\bon\s+either\b|\bin\s+either\b|\beither\b[^.?!]{0,60}\bor\b",
        re.IGNORECASE,
    ),
    "neither": re.compile(
        r"\bneither\b[^.?!]{0,60}\bnor\b|\bneither\s+(?:way|one|of\s+(?:those|these|them))\b",
        re.IGNORECASE,
    ),
}


def _grammatical_function_word(word: str, span: str) -> bool:
    pat = _FUNCTION_WORD_CONSTRUCTS.get(word)
    return bool(pat and pat.search(span))


_FACT_BEARING = (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
_NON_SUBSTANTIVE_TYPES = (
    ClaimType.SALUTATION,
    ClaimType.SIGNATURE_SLOT,
    ClaimType.TRANSITION,
    ClaimType.NON_SUBSTANTIVE,
    ClaimType.DISCLOSURE,
    ClaimType.QUESTION,
    ClaimType.CTA,
)

# A residual content word (present in the rendered clause, not covered by any
# matched source and not covered by the licensed framing vocabulary) is treated
# as harmless connective / light-verb / discourse glue ONLY if it is in this
# closed, curated set. Anything else is either a new claim (>_MAX_RESIDUAL of
# them, or a concept/number word => REJECTED) or, for 1-2 words, an unresolved
# span that fails closed (section 12: no "probably harmless but unclassified").
_RESIDUAL_GLUE: set[str] = {
    # discourse / connectives
    "also",
    "then",
    "so",
    "though",
    "however",
    "meanwhile",
    "separately",
    "additionally",
    "alongside",
    "besides",
    "overall",
    "briefly",
    "simply",
    "just",
    "here",
    "there",
    "now",
    "today",
    "currently",
    "recently",
    "again",
    # light verbs / auxiliaries that carry no domain content
    "put",
    "putting",
    "together",
    "prepared",
    "prepare",
    "preparing",
    "built",
    "build",
    "building",
    "made",
    "make",
    "making",
    "created",
    "create",
    "creating",
    "included",
    "include",
    "includes",
    "including",
    "shows",
    "showing",
    "shown",
    "presents",
    "presenting",
    "presented",
    "features",
    "featuring",
    "featured",
    "references",
    "referencing",
    "referenced",
    "highlights",
    "highlighting",
    "highlighted",
    "lists",
    "listing",
    "listed",
    "describes",
    "describing",
    "described",
    "mentions",
    "mentioning",
    "mentioned",
    "notes",
    "noting",
    "noted",
    "publishes",
    "publishing",
    "published",
    "offers",
    "offering",
    "offered",
    "invites",
    "inviting",
    "invited",
    "provides",
    "providing",
    "provided",
    "maintains",
    "maintaining",
    "maintained",
    "advertises",
    "advertising",
    "advertised",
    "states",
    "stating",
    "stated",
    # generic reader/visitor/domain scaffolding (non-distinctive)
    "visitors",
    "visitor",
    "reader",
    "readers",
    "customer",
    "customers",
    "client",
    "clients",
    "prospective",
    "team",
    "teams",
    "staff",
    "office",
    "business",
    "company",
    "companies",
    "commercial",
    "hvac",
    "service",
    "services",
    "work",
    "works",
    "system",
    "systems",
    "process",
    "processes",
    "step",
    "steps",
    "path",
    "paths",
    "way",
    "ways",
    "point",
    "points",
    "part",
    "parts",
    "piece",
    "pieces",
    "kind",
    "sort",
    "line",
    "lines",
    "form",
    "forms",
    "page",
    "pages",
    "site",
    "website",
    "web",
    "online",
    "public",
    "publicly",
    "presence",
    "material",
    "materials",
    "content",
    "detail",
    "details",
    "description",
    "descriptions",
    "reference",
    "request",
    "requests",
    "inquiry",
    "inquiries",
    "quote",
    "quotes",
    "visit",
    "visits",
    "call",
    "calls",
    "assessment",
    "consultation",
    "booking",
    "scheduling",
    "intake",
    "inbound",
    "incoming",
    "new",
    "actual",
    "real",
    "typical",
    "current",
    "existing",
    "relevant",
    "useful",
    "worth",
    "specific",
    "particular",
    "certain",
    "given",
    "based",
    "only",
    "purely",
    "solely",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "channel",
    "channels",
    "small",
    "short",
    "brief",
    "quick",
    "concise",
    "simple",
    "clear",
    # simulation vocabulary (also handled by DISCLOSURE cues, kept for safety)
    "simulation",
    "simulated",
    "deterministic",
    "synthetic",
    "example",
    "examples",
    "sample",
    "hypothetical",
    "illustrative",
    "human",
    "review",
    "reviewed",
    "reviewing",
    "checked",
    "compare",
    "comparison",
    "comparing",
    "compared",
    "against",
    "acknowledge",
    "acknowledges",
    "acknowledging",
    "acknowledgement",
    "sorts",
    "sorting",
    "sorted",
    "route",
    "routes",
    "routing",
    "routed",
    "handle",
    "handles",
    "handling",
    "handled",
    "models",
    "model",
    "modeled",
    "modelled",
    "modeling",
    "modelling",
    "share",
    "shares",
    "shared",
    "sharing",
    "closer",
    "close",
    "closely",
    "separate",
    "having",
    "alright",
    "okay",
    "purpose",
    "purposes",
    "limit",
    "limits",
    "mind",
    "general",
    "generally",
    "reasonable",
    "reasonably",
    "anywhere",
    "since",
    "look",
    "looks",
    "looked",
    "glance",
    "sense",
    "idea",
    "approach",
    "approaches",
    "one",
    "single",
    "first",
    "next",
    "before",
    "after",
    "later",
    "beyond",
    "matter",
    "context",
    "regard",
    "regarding",
    "note-that",
    "meaning",
    "meant",
    "means",
    "help",
    "helpful",
    "helps",
    "input",
    "inputs",
    "output",
    "outputs",
    "data",
    "info",
    "information",
    "acknowledgements",
    "acknowledgment",
}

_DIGIT_OR_CURRENCY = re.compile(r"[\d$£€%]")

# more than this many residual content words the reconciler cannot place is a
# fabricated / over-reaching claim, not a single unresolved span.
_MAX_AMBIGUOUS = 2

# Domain nouns / verbs that, appearing UN-licensed in a rendered clause, are a
# genuine new claim rather than harmless glue - a superset of the concept-scan
# vocabulary, kept explicit here so a fabricated claim word is rejected even when
# it slips a concept regex.
_CLAIM_MATERIAL: set[str] = {
    "respond",
    "responds",
    "response",
    "responding",
    "reply",
    "replies",
    "replying",
    "answer",
    "answers",
    "answering",
    "minute",
    "minutes",
    "hour",
    "hours",
    "day",
    "days",
    "immediately",
    "instantly",
    "promptly",
    "fast",
    "quickly",
    "guarantee",
    "guaranteed",
    "guarantees",
    "always",
    "never",
    "every",
    "revenue",
    "profit",
    "cost",
    "costs",
    "savings",
    "roi",
    "lead",
    "leads",
    "conversion",
    "pipeline",
    "value",
    "money",
    "dollars",
    "lose",
    "loses",
    "losing",
    "lost",
    "missed",
    "missing",
    "unanswered",
    "integrate",
    "integrates",
    "integration",
    "integrated",
    "connects",
    "connected",
    "sync",
    "syncs",
    "api",
    "servicetitan",
    "housecall",
    "jobber",
    "salesforce",
    "hubspot",
    "crm",
    "deployed",
    "live",
    "running",
    "operational",
    "installed",
    "active",
    "proactive",
    "automated",
    "automation",
    "automatic",
    "cadence",
    "nurture",
    "campaign",
    "proves",
    "proven",
    "demonstrates",
    "verifies",
    "understaffed",
    "overwhelmed",
    "busy",
    "backlog",
    "slow",
    "delay",
    "delays",
    "delayed",
}

# Disposition of a rendered clause after canonical reconciliation.
NON_SUBSTANTIVE = "NON_SUBSTANTIVE"
LICENSED = "LICENSED"
REJECTED = "REJECTED"
UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class CanonicalClaim:
    clause_index: int
    span: str
    rendered_class: ClaimType
    substantive: bool
    candidate_source_ids: tuple[str, ...]
    authorized_strength: FactStrength | None
    rendered_strength: FactStrength | None
    residual_words: tuple[str, ...]
    introduces_new_content: bool
    fully_licensed: bool
    disposition: str
    findings: tuple[ValidatorFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class ManifestDisagreement:
    kind: str  # PROVIDER_OMITTED_CLAIM | PROVIDER_ADDED_REDUNDANT_WRAPPER
    # | PROVIDER_MISTYPED_CLAIM | PROVIDER_WRONG_SOURCE | PROVIDER_MISSTATED_STRENGTH
    detail: str
    span: str = ""


@dataclass(frozen=True, slots=True)
class CanonicalClaimMap:
    version: str = CANONICAL_CLAIM_MAP_VERSION
    reconciler_version: str = CANONICAL_CLAIM_RECONCILER_VERSION
    claims: tuple[CanonicalClaim, ...] = ()
    substantive_count: int = 0
    licensed_count: int = 0
    rejected_count: int = 0
    unresolved_count: int = 0
    coverage: float = 1.0
    findings: tuple[ValidatorFinding, ...] = ()
    manifest_disagreements: tuple[ManifestDisagreement, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# source vocabulary + strength
# --------------------------------------------------------------------------


def _source_profile(src: object) -> tuple[set[str], FactStrength] | None:
    """(content words that a source licenses, its evidentiary strength). The
    source's own ``usage_rule`` text is part of what it licenses (a faithful
    paraphrase that stays within the rule is covered) - identical to validator
    rule 15c."""

    if isinstance(src, EnvelopeFact):
        words = _split_hyphens(
            _content_words(src.sanitized_phrase)
            | _content_words(src.verbatim_source_phrase)
            | _content_words(getattr(src, "usage_rule", "") or "")
        )
        return words, src.strength
    if isinstance(src, M3FindingRef):
        words = _content_words(src.rendered_text) | _content_words(
            getattr(src, "usage_rule", "") or ""
        )
        if src.supporting_excerpt:
            words |= _content_words(src.supporting_excerpt)
        return _split_hyphens(words), FactStrength.OBSERVED_PUBLIC_TEXT
    if isinstance(src, ConditionalInference):
        words = _content_words(src.text) | _content_words(getattr(src, "usage_rule", "") or "")
        return _split_hyphens(words), FactStrength.LICENSED_INFERENCE
    if isinstance(src, Recommendation):
        words = _content_words(src.text) | _content_words(getattr(src, "usage_rule", "") or "")
        return _split_hyphens(words), FactStrength.LICENSED_RECOMMENDATION
    return None


def _all_sources(env: SemanticEnvelope) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for fact in env.eligible_company_facts:
        if fact.injection_suspected:
            # an injection-suspected fact never licenses rendered prose
            continue
        out.append((fact.fact_id, fact))
    for finding in env.m3_findings:
        out.append((finding.finding_id, finding))
    for inf in env.allowed_conditional_inferences:
        out.append((inf.inference_id, inf))
    for rec in env.allowed_recommendations:
        out.append((rec.recommendation_id, rec))
    return out


def _split_hyphens(words: set[str]) -> set[str]:
    """Add the parts of every hyphenated compound (vocab side - keep both)."""
    out = set(words)
    for w in list(words):
        if "-" in w:
            out |= {p for p in w.split("-") if len(p) >= 3}
    return out


def _explode_hyphens(words: set[str]) -> set[str]:
    """Replace every hyphenated compound with its parts (clause side - a
    compound token is analysed only through its components)."""
    out: set[str] = set()
    for w in words:
        if "-" in w:
            out |= {p for p in w.split("-") if len(p) >= 3}
        else:
            out.add(w)
    return out


def _covered(word: str, vocab: set[str]) -> bool:
    """Word is licensed by ``vocab`` under light morphology: exact match, ``_stem``
    equivalence, or naive singular/plural (upgrade~upgrades)."""

    if word in vocab or _stem_covered(word, vocab):
        return True
    if word.endswith("s") and len(word) > 3 and word[:-1] in vocab:
        return True
    return (word + "s") in vocab or (word + "es") in vocab


def _claim_words(span: str, name_tokens: set[str]) -> set[str]:
    """Content words of the rendered clause that could carry claim meaning:
    everything except stopwords, the business name, pure framing / epistemic
    connectives, and words that occur only inside a negation."""

    out: set[str] = set()
    for w in _explode_hyphens(set(_content_words_v2(span))):
        if w in name_tokens:
            continue
        if w in _V2_FRAMING_VOCAB or w in _SAFE_FRAMING_VOCAB:
            continue
        if w in _ATTRIBUTION_FRAMING_VOCAB or _grammatical_function_word(w, span):
            continue
        if _only_in_negation(w, span):
            continue
        out.add(w)
    return out


def _residual_kind(word: str, span: str) -> str:
    """'glue' | 'new_claim' | 'ambiguous' for a residual content word (present in
    the rendered clause, covered by neither a matched source nor engine wording
    nor the fact vocabulary)."""

    # a word that only ever appears inside an explicit negation ("not deployed,
    # live, or official"; "it proves nothing") is not an asserted new claim.
    low = span.lower()
    if _only_in_negation(word, span) or re.search(
        rf"\b{re.escape(word)}\s+(?:nothing|no|none)\b", low
    ):
        return "glue"
    if _DIGIT_OR_CURRENCY.search(word):
        return "new_claim"
    if word in _CLAIM_MATERIAL or _stem_covered(word, _CLAIM_MATERIAL):
        return "new_claim"
    # a bounded attribution / framing verb ("labeled", "titled", "named", ...)
    # frames the observation; the object it introduces is checked independently.
    if word in _ATTRIBUTION_FRAMING_VOCAB:
        return "glue"
    # "either" / "neither" inside a recognised coordinating construction.
    if _grammatical_function_word(word, span):
        return "glue"
    if word in _RESIDUAL_GLUE or _covered(word, set(_RESIDUAL_GLUE)):
        return "glue"
    cap = word[:1].upper() + word[1:]
    if re.search(rf"(?<!^)\b{re.escape(cap)}\b", span):
        # a proper noun the reconciler could not license
        return "new_claim"
    return "ambiguous"


# --------------------------------------------------------------------------
# the reconciler
# --------------------------------------------------------------------------


def reconcile(
    *,
    subject: str,
    body: str,
    envelope: SemanticEnvelope,
    structured_cta: StructuredCTA | None = None,
    required_disclosures: tuple[RequiredDisclosure, ...] = (),
    provider_manifest: ClaimManifest | None = None,
) -> CanonicalClaimMap:
    _ = (subject, structured_cta, required_disclosures)  # reserved; CTA/disclosure
    # legality is validated by the unchanged prose rules 6 and 9.
    clauses = _split_clauses(body)
    # identical to validator rule 12's `allowed_vocab | _V2_FRAMING_VOCAB`: the
    # deterministic engine's OWN wording (reference artifacts, m3-finding /
    # inference / recommendation text, disclosure canonical text, CTA questions,
    # may_say, display name, hostname, every usage_rule) plus the fact phrases
    # plus epistemic connectives. Language inside this is not a new claim.
    engine_vocab = _split_hyphens(_licensed_framing_vocab(envelope, v2=True) | _SAFE_FRAMING_VOCAB)
    fact_vocab = _split_hyphens(_fact_vocab(envelope))
    v2_framing = (
        engine_vocab | fact_vocab | set(_V2_FRAMING_VOCAB) | set(_ATTRIBUTION_FRAMING_VOCAB)
    )
    name_tokens = _content_words_v2(envelope.business_identity.display_name)
    sources = _all_sources(envelope)
    licensed_numeric = _licensed_numeric_strings(envelope)

    claims: list[CanonicalClaim] = []
    findings: list[ValidatorFinding] = []

    for i, clause in enumerate(clauses):
        rc = _classify(clause, contract="v2")
        cw = _claim_words(clause, name_tokens)

        # licensing gate - the same logic validator rule 12 uses to license the
        # historical corpus: a substantive word is unlicensed if it is in neither
        # the framing vocab nor any fact/finding/inference/rec wording, under
        # light morphology (hyphenated compounds split, plural/prefix coverage).
        words_v2 = _explode_hyphens(set(_content_words_v2(clause)))
        unlicensed = {w for w in (words_v2 - v2_framing) if not _covered(w, v2_framing)}

        # a bare digit in the rendered clause that is not part of a licensed
        # numeric string, a placeholder, or a quoted fact phrase is an invented
        # number (mirrors validator rule 4). Detected directly - digits are not
        # word tokens.
        clause_for_num = clause
        for n in licensed_numeric:
            clause_for_num = re.sub(re.escape(n), " ", clause_for_num)
        clause_for_num = _QUOTED.sub(" ", _PLACEHOLDER.sub(" ", clause_for_num))
        has_bare_number = bool(re.search(r"(?<!\d)\d+(?!\d)", clause_for_num))

        residual_kinds0 = {w: _residual_kind(w, clause) for w in unlicensed}
        new_claim_words0 = {w for w, k in residual_kinds0.items() if k == "new_claim"}
        if has_bare_number:
            new_claim_words0 = new_claim_words0 | {"<number>"}

        bare_leadin = _is_framing_leadin(_norm(clause), envelope)
        # a bare evidentiary lead-in ("While reviewing X's public pages, I
        # noticed"), or a structural clause (DISCLOSURE / QUESTION / CTA /
        # SALUTATION / SIGNATURE_SLOT / TRANSITION) whose legality is checked by
        # rules 6 and 9, is non-substantive UNLESS it smuggles a genuine new fact
        # or number - which is the "provider falsely labels an unsupported fact
        # as DISCLOSURE" case (section 10) and fails closed below.
        structural = rc in (
            ClaimType.DISCLOSURE,
            ClaimType.QUESTION,
            ClaimType.CTA,
            ClaimType.SALUTATION,
            ClaimType.SIGNATURE_SLOT,
            ClaimType.TRANSITION,
        )
        if bare_leadin or (structural and not new_claim_words0):
            claims.append(
                CanonicalClaim(
                    clause_index=i,
                    span=_norm(clause),
                    rendered_class=rc,
                    substantive=False,
                    candidate_source_ids=(),
                    authorized_strength=None,
                    rendered_strength=None,
                    residual_words=(),
                    introduces_new_content=False,
                    fully_licensed=True,
                    disposition=NON_SUBSTANTIVE,
                )
            )
            continue
        if rc == ClaimType.NON_SUBSTANTIVE and not unlicensed:
            claims.append(
                CanonicalClaim(
                    clause_index=i,
                    span=_norm(clause),
                    rendered_class=rc,
                    substantive=False,
                    candidate_source_ids=(),
                    authorized_strength=None,
                    rendered_strength=None,
                    residual_words=(),
                    introduces_new_content=False,
                    fully_licensed=True,
                    disposition=NON_SUBSTANTIVE,
                )
            )
            continue

        # substantive: independently attribute source(s) and evidence strength.
        # The provider's declared class / sources / strength are never consulted.
        matched_ids: list[str] = []
        matched_strengths: list[FactStrength] = []
        for sid, src in sources:
            prof = _source_profile(src)
            if prof is None:
                continue
            sw, sstr = prof
            if any(w in sw or _stem_covered(w, sw) for w in (cw - _V2_FRAMING_VOCAB)):
                matched_ids.append(sid)
                matched_strengths.append(sstr)

        new_claim_words = set(new_claim_words0)
        ambiguous_words = {w for w, k in residual_kinds0.items() if k == "ambiguous"}
        residual = unlicensed

        clause_findings: list[ValidatorFinding] = []
        if has_bare_number:
            clause_findings.append(
                _f(
                    "unsupported_number",
                    "canonical reconciler: rendered clause states a number licensed by no "
                    "eligible fact",
                    "first_contact_email",
                    span=_norm(clause),
                )
            )

        rendered_strength = _detected_strength(_norm(clause), v2=True)
        if matched_strengths:
            best_strength: FactStrength | None = max(matched_strengths, key=_rank)
        elif rc == ClaimType.INFERENCE:
            best_strength = FactStrength.LICENSED_INFERENCE
        elif rc == ClaimType.RECOMMENDATION:
            best_strength = FactStrength.LICENSED_RECOMMENDATION
        else:
            best_strength = None
        auth_strength = best_strength
        disposition: str
        word_claims = new_claim_words - {"<number>"}

        if has_bare_number:
            disposition = REJECTED
        elif word_claims or len(residual) > _MAX_AMBIGUOUS:
            disposition = REJECTED
            clause_findings.append(
                _f(
                    "unlicensed_claim",
                    "canonical reconciler: rendered claim asserts content licensed by no "
                    f"envelope source or engine wording: {sorted(word_claims or residual)[:6]}",
                    "first_contact_email",
                    span=_norm(clause),
                )
            )
        elif best_strength is not None and _rank(rendered_strength) > _rank(best_strength):
            disposition = REJECTED
            clause_findings.append(
                _f(
                    "strength_increase",
                    "canonical reconciler: rendered wording sounds like "
                    f"{rendered_strength.value}, matched source licenses only "
                    f"{best_strength.value}",
                    "first_contact_email",
                    span=_norm(clause),
                )
            )
        elif ambiguous_words:
            disposition = UNRESOLVED
            clause_findings.append(
                _f(
                    "unresolved_substantive_claim",
                    "canonical reconciler: substantive rendered content could not be "
                    f"confidently licensed or rejected: {sorted(ambiguous_words)[:6]}",
                    "first_contact_email",
                    span=_norm(clause),
                )
            )
        else:
            disposition = LICENSED

        # conditional preservation for inference / recommendation wording
        if disposition == LICENSED and rc in (ClaimType.INFERENCE, ClaimType.RECOMMENDATION):
            low = _norm(clause).lower()
            if not any(cue in low for cue in CONDITIONAL_CUES):
                clause_findings.append(
                    _f(
                        "conditional_language_lost",
                        "canonical reconciler: inference/recommendation lost its conditional "
                        "qualifier",
                        "first_contact_email",
                        span=_norm(clause),
                    )
                )

        findings.extend(clause_findings)
        claims.append(
            CanonicalClaim(
                clause_index=i,
                span=_norm(clause),
                rendered_class=rc,
                substantive=True,
                candidate_source_ids=tuple(sorted(set(matched_ids))),
                authorized_strength=auth_strength,
                rendered_strength=rendered_strength,
                residual_words=tuple(sorted(residual)),
                introduces_new_content=bool(new_claim_words),
                fully_licensed=(disposition == LICENSED),
                disposition=disposition,
                findings=tuple(clause_findings),
            )
        )

    substantive = [c for c in claims if c.substantive]
    licensed_n = sum(1 for c in substantive if c.disposition == LICENSED)
    rejected_n = sum(1 for c in substantive if c.disposition == REJECTED)
    unresolved_n = sum(1 for c in substantive if c.disposition == UNRESOLVED)
    total = len(substantive)
    coverage = 1.0 if total == 0 else (total - unresolved_n) / total

    disagreements = _compare_provider_manifest(claims, provider_manifest, envelope)

    return CanonicalClaimMap(
        claims=tuple(claims),
        substantive_count=total,
        licensed_count=licensed_n,
        rejected_count=rejected_n,
        unresolved_count=unresolved_n,
        coverage=coverage,
        findings=tuple(findings),
        manifest_disagreements=tuple(disagreements),
    )


# --------------------------------------------------------------------------
# provider manifest: diagnostic comparison only (section 3) - advisory
# --------------------------------------------------------------------------


def _compare_provider_manifest(
    claims: list[CanonicalClaim],
    provider_manifest: ClaimManifest | None,
    env: SemanticEnvelope,
) -> list[ManifestDisagreement]:
    if provider_manifest is None:
        return []
    out: list[ManifestDisagreement] = []
    entries = list(provider_manifest.entries)
    entry_spans = [(_norm(e.rendered_span).lower(), e) for e in entries]
    substantive = [c for c in claims if c.substantive]

    for c in substantive:
        cl = c.span.lower()
        hit = next(
            (e for s, e in entry_spans if s and (s in cl or cl in s) and len(s) > 3),
            None,
        )
        if hit is None:
            out.append(
                ManifestDisagreement(
                    "PROVIDER_OMITTED_CLAIM",
                    f"substantive rendered claim has no provider-manifest entry "
                    f"(canonical: {c.disposition}, sources {list(c.candidate_source_ids)})",
                    c.span,
                )
            )
            continue
        # mis-type: provider labelled it non-fact-bearing but it renders substantive
        if hit.claim_type not in _FACT_BEARING and c.disposition in (LICENSED, REJECTED):
            out.append(
                ManifestDisagreement(
                    "PROVIDER_MISTYPED_CLAIM",
                    f"provider declared {hit.claim_type} for a span the reconciler licenses "
                    f"as a substantive claim",
                    c.span,
                )
            )
        # wrong source
        declared = {sid for sid in hit.licensed_source_ids}
        if declared and c.candidate_source_ids and not (declared & set(c.candidate_source_ids)):
            out.append(
                ManifestDisagreement(
                    "PROVIDER_WRONG_SOURCE",
                    f"provider cited {sorted(declared)}, reconciler matched "
                    f"{list(c.candidate_source_ids)}",
                    c.span,
                )
            )
        # misstated strength
        if (
            hit.asserted_strength is not None
            and c.authorized_strength is not None
            and _rank(hit.asserted_strength) > _rank(c.authorized_strength)
        ):
            out.append(
                ManifestDisagreement(
                    "PROVIDER_MISSTATED_STRENGTH",
                    f"provider asserted {hit.asserted_strength.value}, reconciler-matched "
                    f"source licenses {c.authorized_strength.value}",
                    c.span,
                )
            )

    # redundant source-less wrapper the provider added over granular entries
    canon_spans = [c.span.lower() for c in substantive]
    for s, e in entry_spans:
        if not e.licensed_source_ids and e.claim_type in _FACT_BEARING:
            covered_parts = [cs for cs in canon_spans if cs and cs in s and cs != s]
            if len(covered_parts) >= 1:
                out.append(
                    ManifestDisagreement(
                        "PROVIDER_ADDED_REDUNDANT_WRAPPER",
                        "provider added a source-less wrapper entry spanning finer claims the "
                        "reconciler validates independently",
                        _norm(e.rendered_span),
                    )
                )
    _ = env
    return out
