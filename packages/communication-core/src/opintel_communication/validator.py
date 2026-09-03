"""``comm.output_validator@1`` - deterministic, offline, fail-closed validation of
one generated candidate against its immutable semantic envelope.

Shares no code path with any generator and makes no provider call. A PASS never
adds authority - it only removes the ADR-0067 block for one rendered artifact,
which then still needs human review and the independently gated contact / send
stages.

Provider-declared claim manifests are treated as advisory hints, never as proof.
"""

from __future__ import annotations

import re

from opintel_outreach.composition import (
    _PLACEHOLDER,
    _SCORE_LEAK,
    FINANCIAL_EXTERNAL,
    PERSONAL_CONTACT,
)

from opintel_communication.cta_parser import cta_semantic_consistency
from opintel_communication.domain import (
    CTA_PARSER_V2_VERSION,
    CTA_PARSER_V3_VERSION,
    CTA_PARSER_VERSION,
    OUTPUT_VALIDATOR_V2_VERSION,
    OUTPUT_VALIDATOR_V3_VERSION,
    OUTPUT_VALIDATOR_VERSION,
    ClaimManifestEntry,
    ClaimType,
    EnvelopeFact,
    FactStrength,
    GenerationCandidate,
    M3FindingRef,
    SemanticEnvelope,
    ValidationResult,
    ValidatorFinding,
    ValidatorSeverity,
    strength_at_most,
)
from opintel_communication.policy import (
    CERTAINTY_CUES,
    CONDITIONAL_CUES,
    PROHIBITED_CONCEPTS,
    injection_markers,
    place_like_tokens,
)

_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_QUOTED = re.compile(r'"([^"]{2,})"')
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "you",
        "your",
        "our",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "not",
        "but",
        "any",
        "all",
        "can",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "one",
        "two",
        "who",
        "how",
        "what",
        "when",
        "which",
        "into",
        "than",
        "then",
        "them",
        "they",
        "its",
        "his",
        "her",
        "their",
        "about",
        "from",
        "out",
        "off",
        "over",
        "some",
        "such",
        "only",
        "also",
        "more",
        "most",
        "very",
        "just",
        "like",
    }
)


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


# (Attempt-6 remediation, section B.2) v2 tokenization: an ``n't`` negation is
# licensed everywhere (the negation itself carries no new business fact), and a
# possessive / contraction tail is grammar, not evidence -- "Bayline Systems'",
# "Meridian HVAC's", "what's", "don't" must not each read as an unlicensed
# content word. Strip those, then apply the identical v1 stopword filter.
_APOS = "['’]"  # straight-or-curly apostrophe class  # noqa: RUF001
_V2_NT_RE = re.compile("n" + _APOS + r"t\b")
# an apostrophe (with an optional contraction/possessive tail) that is NOT
# followed by another word character: "systems'", "hvac's", "what's", "we're".
_V2_POSSESSIVE_RE = re.compile(_APOS + r"(?:s|re|ve|ll|d|m)?(?![\w'’])")  # noqa: RUF001


def _content_words_v2(text: str) -> set[str]:
    t = _V2_NT_RE.sub(" ", text.lower())
    t = _V2_POSSESSIVE_RE.sub("", t)
    return {w for w in _WORD.findall(t) if w not in _STOPWORDS}


def _norm(text: str) -> str:
    return " ".join(text.split()).strip()


# --------------------------------------------------------------------------
# Attempt-6 preparation (owner authorization 2026-09-02, section 3). All of the
# following are consulted ONLY under contract="v2". @1 behaviour is unchanged.
# --------------------------------------------------------------------------

# (3a) prohibited/demo concepts whose meaning is inverted by an explicit
# negation - "nothing in it is connected", "not a system deployed". An
# UNSUPPORTED positive claim (no negation) still fails.
_V2_NEGATION_SUPPRESSIBLE: frozenset[str] = frozenset(
    {"AVAILABILITY_TO_RESPONSE", "DEMO_DEPLOYED", "RESPONSE_PERFORMANCE_ASSERTED"}
)
_V2_DISCOVERY_ADVERBS: frozenset[str] = frozenset(
    {"monthly", "weekly", "daily", "annually", "yearly", "know", "learn"}
)
_STRONG_NEG = re.compile(
    r"\b(?:not|no|nothing|never|isn'?t|aren'?t|wasn'?t|weren'?t|doesn'?t|don'?t|"
    r"didn'?t|won'?t|cannot|can'?t|without|nor|non-)\b",
    re.IGNORECASE,
)
_POSITIVE_DEPLOY = re.compile(
    r"\b(?:is|are|has|have|been|now|currently)\s+"
    r"(?:been\s+)?(?:deployed|connected|live|running|integrated|active|in place)\b",
    re.IGNORECASE,
)


def _negation_governs(clause: str, start: int) -> bool:
    """True when the concept trigger at ``start`` sits inside an explicit
    negation and no intervening positive-deployment assertion cancels it."""
    window = clause[max(0, start - 55) : start]
    if not _STRONG_NEG.search(window):
        return False
    return not _POSITIVE_DEPLOY.search(window)


class _AuthorizedVocab:
    """Content-word views of the meanings THIS exact envelope explicitly
    licenses: its required disclosures, its canonical discovery questions, its
    ``may_say`` demo phrases, and its structured-CTA ``asks_for`` frame. Not a
    generic 'prompt text is safe' bypass - only this envelope's own text."""

    __slots__ = ("phrases", "union")

    def __init__(self, env: SemanticEnvelope) -> None:
        phrases: list[set[str]] = []
        for disc in env.required_disclosures:
            if disc.canonical_text:
                phrases.append(_content_words(disc.canonical_text))
        for question in env.structured_cta.canonical_discovery_questions:
            phrases.append(_content_words(question))
        for phrase in env.mentionable_demo_facts.may_say:
            phrases.append(_content_words(phrase))
        phrases.append(_content_words(env.structured_cta.semantic_frame.asks_for))
        self.phrases = [w for w in phrases if len(w) >= 4]
        self.union: set[str] = set().union(*self.phrases) if self.phrases else set()


def _matches_authorized(
    clause: str, authorized: _AuthorizedVocab, *, allow_fold: bool = False
) -> bool:
    cw = _content_words(clause)
    if len(cw) < 4:
        return False
    # (a) the clause is (near-)equivalent to one single authorized phrase.
    for phrase in authorized.phrases:
        if len(phrase & cw) / min(len(phrase), len(cw)) >= 0.70:
            return True
    # (b) discovery-question territory only: the clause folds in two authorized
    #     phrases (e.g. both canonical discovery questions in one CTA sentence,
    #     which @6 encourages) - >= 5 words from the authorized union and at most
    #     two words beyond that union + safe framing + discovery adverbs. NOT
    #     applied to demo-deployment concepts, where a genuine positive claim
    #     shares its content words with the negated disclosure.
    if not allow_fold:
        return False
    beyond = cw - authorized.union - _SAFE_FRAMING_VOCAB - _V2_DISCOVERY_ADVERBS
    return len(cw & authorized.union) >= 5 and len(beyond) <= 2


# (3e) disclosure negation grammar: accept explicitly-tested contractions.
_V2_DISCLOSURE_NOT_DEPLOYED = re.compile(
    r"\b(?:not|isn'?t|aren'?t|wasn'?t|weren'?t|doesn'?t|don'?t|never|no)\b"
    r"[^.]{0,45}\b(?:deployed|connected|official|operated|a system|implemented|"
    r"live|integrated|in production)\b",
    re.IGNORECASE,
)

# Round 2 (owner authorization 2026-09-02). All consulted ONLY under v2.

# (section 5/6) findings that affect COMMUNICATION_QUALITY but are NOT a
# safety/validation failure - they do not by themselves fail a candidate or
# force NOT_CERTIFIED.
_V2_ADVISORY_CODES: frozenset[str] = frozenset(
    {"no_company_specific_evidence", "provider_manifest_type_mismatch"}
)

# (section 5) ubiquitous category words that appear in almost every fixture's
# fact vocabulary AND in the business display name - overlap with these alone is
# name-only personalization, not substantive company-specific evidence.
_GENERIC_FACT_WORDS: frozenset[str] = frozenset(
    {
        "commercial",
        "hvac",
        "service",
        "services",
        "business",
        "company",
        "work",
        "system",
        "systems",
    }
)


def _licensed_numeric_strings(env: SemanticEnvelope) -> set[str]:
    """Numeric tokens/strings that appear verbatim in an eligible licensed
    fact - e.g. '24/7' from a '24/7 Emergency Service' fact."""
    out: set[str] = set()
    for fact in env.eligible_company_facts:
        if fact.injection_suspected:
            continue
        for text in (fact.sanitized_phrase, fact.verbatim_source_phrase):
            out |= set(re.findall(r"\d[\d/:.\-]*\d|\d", text))
    return out


def _stem(word: str) -> str:
    """Crude, deterministic light morphology for source-licensing checks only."""
    for suf in ("ies", "ied", "ing", "ers", "er", "ed", "es", "s"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            base = word[: -len(suf)]
            return base + "y" if suf in ("ies", "ied") else base
    return word


def _stem_covered(word: str, vocab: set[str]) -> bool:
    s = _stem(word)
    return s in vocab or any(_stem(v) == s for v in vocab)


def _is_identity_grammar(span: str, env: SemanticEnvelope) -> bool:
    """(Attempt-6 remediation B.2/B.3) True when ``span`` is just the business
    display name (possibly a prefix / possessive of it) - identity grammar, not a
    business fact that needs an evidentiary source."""
    name = _norm(env.business_identity.display_name).lower()
    s = _norm(span).lower().strip(" .,\"'" + "’")  # noqa: RUF001
    if not s or not name or len(s) > len(name) + 4:
        return False
    if s in name or name in s:
        return True
    sw, nw = _content_words_v2(s), _content_words_v2(name)
    return bool(sw) and sw <= nw


# (Haiku track, section D1) a bare evidentiary lead-in: a framing verb whose
# object is the business's own public presence, with NO substantive business
# predicate. "While reviewing Acme's public pages, I noticed" - source-free.
# "While reviewing Acme's public pages, I noticed you respond in five minutes" -
# the trailing predicate is substantive, so this is NOT a bare lead-in.
_FRAMING_VERB = re.compile(
    r"\b(?:review(?:ed|ing)?|notic(?:ed|ing|e)|noted|noting|saw|see(?:n|ing)?|"
    r"came\s+across|come\s+across|coming\s+across|read(?:ing)?|brows(?:ed|ing)|"
    r"look(?:ed|ing)?\s+(?:at|over|through)|glanc(?:ed|ing))\b",
    re.IGNORECASE,
)
_FRAMING_LEADIN_STOP: frozenset[str] = frozenset(
    {
        "while",
        "when",
        "after",
        "during",
        "reviewing",
        "reviewed",
        "review",
        "browsing",
        "reading",
        "looking",
        "glancing",
        "noticing",
        "noticed",
        "notice",
        "noted",
        "noting",
        "saw",
        "seen",
        "seeing",
        "came",
        "come",
        "coming",
        "across",
        "over",
        "through",
        "public",
        "publicly",
        "site",
        "website",
        "pages",
        "page",
        "web",
        "online",
        "presence",
        "homepage",
    }
)


def _is_framing_leadin(span: str, env: SemanticEnvelope) -> bool:
    if not _FRAMING_VERB.search(span):
        return False
    name_tokens = _content_words_v2(env.business_identity.display_name)
    residual = (
        _content_words_v2(span)
        - _SAFE_FRAMING_VOCAB
        - _V2_FRAMING_VOCAB
        - name_tokens
        - _FRAMING_LEADIN_STOP
    )
    return not residual


def _only_in_negation(word: str, span: str) -> bool:
    """True when every occurrence of ``word`` in ``span`` is governed by an
    explicit negation - it cannot be evidence that an AFFIRMATIVE claim is
    licensed by the cited source."""
    low = span.lower()
    positions = [m.start() for m in re.finditer(rf"\b{re.escape(word)}\b", low)]
    if not positions:
        return False
    return all(_STRONG_NEG.search(low[max(0, p - 42) : p]) for p in positions)


# --------------------------------------------------------------------------
# Bounded redundant-manifest-wrapper reconciliation (return-to-Sonnet-5, owner
# authorization 2026-09-02 "AUTHORIZE BOUNDED REDUNDANT-MANIFEST RECONCILIATION",
# sections 2-3). Consulted ONLY under contract="v2".
#
# Observed failing pattern: the provider renders a sentence like "While reviewing
# Acme's public pages, I noticed X alongside Y." and the manifest carries granular
# FACT entries for X and Y (each correctly source-licensed) PLUS a broader
# source-less wrapper entry spanning the same sentence. The wrapper adds no
# independently unsupported meaning - it is a manifest-granularity artefact.
#
# A source-less entry escapes ``claim_manifest_source_mismatch`` ONLY when every
# condition below is deterministically true. The provider's declared claim_type
# is NEVER trusted - a factual claim must not be hideable inside a wrapper the
# provider labels DISCLOSURE / TRANSITION.
# --------------------------------------------------------------------------


def _wrapper_residual_framing() -> frozenset[str]:
    # built lazily: _SAFE_FRAMING_VOCAB / _V2_FRAMING_VOCAB are defined later in
    # the module. Non-substantive framing / attribution / transition / glue that
    # may remain in a redundant wrapper after its sibling-covered facts are
    # removed.
    return frozenset(
        _SAFE_FRAMING_VOCAB | _V2_FRAMING_VOCAB | _FRAMING_LEADIN_STOP | _V2_DISCOVERY_ADVERBS
    )


def _source_strength(src: object, claim_type: ClaimType) -> FactStrength | None:
    if src is None:
        return None
    if isinstance(src, EnvelopeFact):
        return src.strength
    if isinstance(src, M3FindingRef):
        return FactStrength.OBSERVED_PUBLIC_TEXT
    return (
        FactStrength.LICENSED_INFERENCE
        if claim_type == ClaimType.INFERENCE
        else FactStrength.LICENSED_RECOMMENDATION
    )


def _wrapper_covering_siblings(
    entry: ClaimManifestEntry, cand: GenerationCandidate
) -> list[ClaimManifestEntry]:
    """Other manifest entries whose rendered span is a strictly finer part of
    this entry's span (every content word inside it, shorter text)."""
    w_words = _content_words_v2(entry.rendered_span)
    w_len = len(_norm(entry.rendered_span))
    out: list[ClaimManifestEntry] = []
    for sib in cand.claim_manifest.entries:
        if sib is entry:
            continue
        s_norm = _norm(sib.rendered_span)
        s_words = _content_words_v2(s_norm)
        if not s_words or len(s_norm) >= w_len:
            continue
        if s_words <= w_words:
            out.append(sib)
    return out


def _redundant_wrapper_reconciled(
    entry: ClaimManifestEntry,
    cand: GenerationCandidate,
    env: SemanticEnvelope,
) -> bool:
    span = _norm(entry.rendered_span)
    siblings = _wrapper_covering_siblings(entry, cand)
    if not siblings:  # (2) must overlap >= 1 sibling
        return False

    name_tokens = _content_words_v2(env.business_identity.display_name)
    sib_words: set[str] = set()
    residual_text = span
    for sib in siblings:
        sw = _content_words_v2(sib.rendered_span)
        sib_words |= sw
        for w in sw:
            residual_text = re.sub(rf"\b{re.escape(w)}\b", " ", residual_text, flags=re.IGNORECASE)
        # remove the sibling's exact rendered phrase too, so a licensed numeric /
        # short-token string it carries ("24/7", "AC") leaves no residue.
        residual_text = re.sub(
            re.escape(_norm(sib.rendered_span)), " ", residual_text, flags=re.IGNORECASE
        )
    # a numeric string that appears verbatim in an eligible licensed fact is
    # supported (rule 4, section 3) - strip those before the digit check.
    for n in _licensed_numeric_strings(env):
        residual_text = re.sub(re.escape(n), " ", residual_text)
    residual_text = _norm(residual_text)

    # (2) every substantive word of the wrapper is covered by a sibling or is
    #     non-substantive framing / attribution / glue.
    residual_substantive = (
        _content_words_v2(span) - sib_words - _wrapper_residual_framing() - name_tokens
    )
    if residual_substantive:
        return False
    # (5) the wrapper-only residual introduces no number / currency / percent.
    if re.search(r"[\d$£€%]", residual_text):
        return False
    # (5) the residual is not itself fact / inference / recommendation bearing.
    #     A bare framing shell ("While reviewing <name>'s public pages, I
    #     noticed") is not a claim even though _classify types the possessive
    #     site phrase as FACT - _is_framing_leadin recognises it.
    if (
        residual_text
        and not _is_framing_leadin(residual_text, env)
        and _classify(residual_text, contract="v2")
        in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
    ):
        return False
    # (5) the residual trips no prohibited / availability / demo / response
    #     concept (an explicit negation still suppresses the negation-suppressible
    #     ones, matching rule 8).
    for concept in PROHIBITED_CONCEPTS:
        for pat in concept.patterns:
            m = pat.search(residual_text)
            if m is None:
                continue
            if concept.code in _V2_NEGATION_SUPPRESSIBLE and _negation_governs(
                residual_text, m.start()
            ):
                continue
            return False
    # (5) no economic / contact language in the residual.
    if FINANCIAL_EXTERNAL.search(residual_text) or PERSONAL_CONTACT.search(residual_text):
        return False

    # (3) every covering sibling that renders fact-bearing wording must itself be
    #     validly licensed - resolvable, non-empty sources at an evidentiary
    #     strength - regardless of how the provider typed it. (4) sibling
    #     licensing must be at least as strong as the wrapper claim requires, and
    #     no sibling may over-assert vs its own source.
    wrapper_cap = _rank(entry.asserted_strength) if entry.asserted_strength is not None else None
    saw_factual_sibling = False
    for sib in siblings:
        rendered = _classify(_norm(sib.rendered_span), contract="v2")
        factual = rendered in (
            ClaimType.FACT,
            ClaimType.INFERENCE,
            ClaimType.RECOMMENDATION,
        ) or sib.claim_type in (
            ClaimType.FACT,
            ClaimType.INFERENCE,
            ClaimType.RECOMMENDATION,
        )
        if not factual:
            continue
        saw_factual_sibling = True
        resolved = [env.source_by_id(s) for s in sib.licensed_source_ids]
        if not sib.licensed_source_ids or any(r is None for r in resolved):
            return False
        strengths = [
            s for s in (_source_strength(r, sib.claim_type) for r in resolved) if s is not None
        ]
        if not strengths:
            return False
        sib_rank = max(_rank(s) for s in strengths)
        if sib_rank < _rank(FactStrength.OBSERVED_PUBLIC_TEXT):
            return False
        if wrapper_cap is not None and wrapper_cap > sib_rank:
            return False
        if sib.asserted_strength is not None and _rank(sib.asserted_strength) > sib_rank:
            return False
    return saw_factual_sibling


# (3c) attribution cues: a clause that explicitly frames a statement as the
# business's own published words is a PUBLISHED_SELF_CLAIM, not a VERIFIED_FACT,
# even when it contains a response verb.
_ATTRIBUTION_CUES = re.compile(
    r"\b(?:your\s+(?:site|page|pages|website|contact page)\s+(?:also\s+)?"
    r"(?:state|states|say|says|publish|publishes|note|notes|list|lists|read|reads)|"
    r"this is what you (?:publish|state|say)|that'?s (?:your own )?published claim|"
    r"what'?s (?:publicly )?(?:published|posted|stated)|a published (?:note|statement|claim)|"
    r"you publicly state|according to your (?:site|page)|as published on your)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Clause segmentation and classification
# --------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_OBSERVATION_SUBJECTS = re.compile(
    r"\b(your (?:site|website|page|pages|contact page|public pages|homepage)|"
    r"you (?:publish|publicly|say|state|describe|list|offer|present|mention|"
    r"reference|highlight|note|feature|invite|have|give|respond|answer|reply|handle|"
    r"never|always|are|do)|"
    r"the captured public pages|the public (?:site|pages|website))\b",
    re.IGNORECASE,
)
# (section 5) "<Business Name>'s public site / pages" - a legitimate observation
# whose subject is the business's own web presence, not the pronoun "your".
_POSSESSIVE_SITE = re.compile(
    r"\b[a-z][\w&.'\- ]{1,45}(?:'s|\u2019s|s')\s+"
    r"(?:public\s+|company\s+|own\s+)?"
    r"(?:site|website|web\s?site|pages?|homepage|home\s?page|contact\s?page|online\s+presence)\b",
    re.IGNORECASE,
)
# Any clause that makes an assertion whose grammatical subject is the business.
_BUSINESS_ASSERTION = re.compile(
    r"^(?:your\s+\w+|you\s+\w+|that\s+is\b|those\s+\w+|it\s+(?:means|is|routes|uses|shows))"
    r"|(?:\bmeans (?:that )?you\b|\bso you\b|\bwhich means\b|\byou never\b|\byou always\b)",
    re.IGNORECASE,
)
# (Haiku track) "<Business Name> publishes / lists / describes / offers ... X" -
# a public-text observation whose subject is the named business. A leading
# capitalised multi-word proper name (the business) followed by an observation
# verb. Consulted ONLY under v2.
_NAME_TOK = "[A-Z][\\w&.'" + chr(0x2019) + "-]+"
_BUSINESS_NAME_ASSERTION = re.compile(
    r"^(?:(?i:(?:while\s+\w+ing\s+[\w' ,-]{0,40}?,?\s*)?(?:i|we)\s+"
    r"(?:noticed|noted|saw|see|seen|reviewed)\s+))?"
    + _NAME_TOK
    + r"(?:\s+(?:&\s+)?"
    + _NAME_TOK
    + r"){0,4}\s+"
    r"(?:publish(?:es)?|list(?:s)?|describ(?:es)?|offer(?:s)?|show(?:s)?|"
    r"highlight(?:s)?|feature(?:s)?|reference(?:s)?|include(?:s)?|present(?:s)?|"
    r"invite(?:s)?|maintain(?:s)?|advertis(?:es)?|note(?:s)?|state(?:s)?)\b"
)
# The primary permission CTA vs. a folded-in discovery question.
_DISCOVERY_QUESTION = re.compile(
    r"\b(how many\b|how are (?:new )?inquir|through which channels|"
    r"what response times|acknowledged today|arrive in a typical month)\b",
    re.IGNORECASE,
)
_PRIMARY_CTA_CUES = re.compile(
    r"\b(compare|useful|relevant|curious|make sense|open to|move forward|"
    r"confirm|walk through|next step|worth (?:a|your))\b",
    re.IGNORECASE,
)
_IMPERATIVE_CTA_START = re.compile(
    r"^(?:book|call|schedule|reply|respond|click|sign\s?up|register|reserve|buy|"
    r"grab|claim|download|visit|check out|get\s+started|join|contact us|email us|"
    r"text us|hit reply|pick a time|set up a)\b",
    re.IGNORECASE,
)
# Map a prohibited-concept code to the specific fail-closed finding it raises.
_CONCEPT_FINDING_CODE: dict[str, str] = {
    "AVAILABILITY_TO_RESPONSE": "availability_upgraded_to_response",
    "DEMO_DEPLOYED": "demo_misrepresented",
}
_RECOMMENDATION_CUES = re.compile(
    r"\b(a step that|could be evaluated|workflow could be|acknowledges and sorts|"
    r"acknowledge and sort|structured acknowledgement)\b",
    re.IGNORECASE,
)
_INFERENCE_CUES = re.compile(
    r"\b(may support|could support|might support|opportunity (?:to|could|may)|"
    r"appears to|seems to|suggests)\b",
    re.IGNORECASE,
)
_DISCLOSURE_CUES = re.compile(
    r"\b(simulation|not a system deployed|not (?:a system )?(?:deployed|connected|"
    r"official|operated)|deterministic simulation|based only on (?:approved )?public|"
    r"not a claim about how your team|we have no visibility|synthetic|"
    # (Attempt-6 remediation B.3) simulation-mechanics / status sentences: a
    # "routes every case to a human review step" / "nothing in it is connected
    # to your systems" sentence is a DISCLOSURE about the simulation pipeline,
    # never a business FACT (the "it routes" prefix otherwise matches
    # _BUSINESS_ASSERTION and mis-types it FACT).
    r"routes? (?:every|each) (?:case|request|inquiry|one)|human review step|"
    r"nothing in it (?:is |)?(?:connected|touches)|before any action)\b",
    re.IGNORECASE,
)
_TRANSITION_CUES = re.compile(
    r"\b(we prepared|we put together|we built|it routes|before (?:a|any) (?:person|"
    r"human)|hello|hi there|dear)\b",
    re.IGNORECASE,
)


def _split_clauses(text: str) -> list[str]:
    clauses: list[str] = []
    for block in re.split(r"\n{2,}|\n", text):
        block = _norm(block)
        if not block:
            continue
        for sentence in _SENTENCE_SPLIT.split(block):
            sentence = _norm(sentence)
            if sentence:
                clauses.append(sentence)
    return clauses


def _classify(clause: str, *, contract: str = "v1") -> ClaimType:
    low = clause.lower()
    if _PLACEHOLDER.fullmatch(clause.strip()):
        return ClaimType.SIGNATURE_SLOT
    if low.startswith(("hello", "hi ", "hi,", "dear ")) or "{{functional_role_or_team}}" in low:
        return ClaimType.SALUTATION
    if clause.strip().endswith("?"):
        if _DISCOVERY_QUESTION.search(clause) and not _PRIMARY_CTA_CUES.search(clause):
            return ClaimType.QUESTION
        return ClaimType.CTA
    if _IMPERATIVE_CTA_START.search(clause.strip()):
        return ClaimType.CTA
    if _DISCLOSURE_CUES.search(clause):
        return ClaimType.DISCLOSURE
    if _RECOMMENDATION_CUES.search(clause):
        return ClaimType.RECOMMENDATION
    if _INFERENCE_CUES.search(clause):
        return ClaimType.INFERENCE
    if _OBSERVATION_SUBJECTS.search(clause) or _BUSINESS_ASSERTION.search(clause):
        return ClaimType.FACT
    if contract == "v2" and (
        _POSSESSIVE_SITE.search(clause) or _BUSINESS_NAME_ASSERTION.match(clause.strip())
    ):
        # (section 5 / Haiku track) "<Business Name>'s public site describes X" or
        # "<Business Name> publishes X" is a public-text observation, not filler.
        return ClaimType.FACT
    if _TRANSITION_CUES.search(clause):
        return ClaimType.TRANSITION
    return ClaimType.NON_SUBSTANTIVE


# --------------------------------------------------------------------------
# Licensed vocabulary: the exact wording the deterministic engine itself uses.
# A rewrite that stays within (fact phrases) plus (this framing vocabulary) is
# not inventing a claim.
# --------------------------------------------------------------------------


def _licensed_framing_vocab(env: SemanticEnvelope, *, v2: bool = False) -> set[str]:
    words: set[str] = set()
    ref = env.deterministic_reference_artifacts
    for piece in (
        ref.first_contact_email,
        ref.subject,
        ref.follow_up_draft,
        ref.call_opening_script,
    ):
        words |= _content_words(piece)
    for finding in env.m3_findings:
        words |= _content_words(finding.rendered_text)
        if finding.supporting_excerpt:
            words |= _content_words(finding.supporting_excerpt)
    for inference in env.allowed_conditional_inferences:
        words |= _content_words(inference.text)
    for rec in env.allowed_recommendations:
        words |= _content_words(rec.text)
    for disc in env.required_disclosures:
        if disc.canonical_text:
            words |= _content_words(disc.canonical_text)
    for unknown in env.explicit_unknowns:
        words |= _content_words(unknown.text)
    words |= _content_words(env.structured_cta.usage_rule)
    for question in env.structured_cta.canonical_discovery_questions:
        words |= _content_words(question)
    for fact in env.mentionable_demo_facts.may_say:
        words |= _content_words(fact)
    words |= _content_words(env.business_identity.display_name)
    if v2:
        # (3d) the synthetic business's own envelope-authorized display identity
        # and hostname. No arbitrary external hostname - only this envelope's.
        # Both the hyphenated token as it tokenises ("bayline-air-demo") and the
        # split components ("bayline", "air", "demo").
        host = env.business_identity.exact_public_hostname.lower()
        words |= _content_words(host)
        words |= _content_words(host.replace(".", " ").replace("-", " "))
        words |= _content_words(host.rsplit(".", 1)[0])
        words |= {"www", "http", "https"}
        for token in env.business_identity.name_tokens:
            words |= _content_words(token)
        # (section 1) the deterministic engine's OWN usage_rule fields are
        # authoritative about how a finding / inference / recommendation MAY be
        # phrased. Language the rule explicitly permits ("compare a simulated
        # intake step with the real process") is licensed. This is bounded to
        # the envelope's own rule text - it is not a free-paraphrase bypass.
        for finding in env.m3_findings:
            words |= _content_words(getattr(finding, "usage_rule", "") or "")
        for inference in env.allowed_conditional_inferences:
            words |= _content_words(getattr(inference, "usage_rule", "") or "")
        for rec in env.allowed_recommendations:
            words |= _content_words(getattr(rec, "usage_rule", "") or "")
    return words


def _fact_vocab(env: SemanticEnvelope) -> set[str]:
    words: set[str] = set()
    for fact in env.eligible_company_facts:
        if fact.injection_suspected:
            continue
        words |= _content_words(fact.sanitized_phrase)
        words |= _content_words(fact.verbatim_source_phrase)
    return words


# Rhetorical scaffolding a faithful rewrite may add without inventing a claim:
# observation verbs, hedges, connectives, and the fixed simulation vocabulary.
# Anything outside (this set) plus (the deterministic engine's own wording) plus
# (the licensed fact phrases) is treated as potentially claim-bearing.
_SAFE_FRAMING_VOCAB: frozenset[str] = frozenset(
    {
        "site",
        "website",
        "web",
        "page",
        "pages",
        "public",
        "publicly",
        "publish",
        "publishes",
        "published",
        "shows",
        "show",
        "showing",
        "says",
        "say",
        "states",
        "state",
        "describes",
        "describe",
        "description",
        "lists",
        "list",
        "offers",
        "offer",
        "presents",
        "present",
        "mentions",
        "mention",
        "references",
        "reference",
        "highlights",
        "highlight",
        "notes",
        "note",
        "features",
        "feature",
        "includes",
        "include",
        "invites",
        "invite",
        "gives",
        "give",
        "provides",
        "provide",
        "positions",
        "position",
        "positioned",
        "calls",
        "call",
        "way",
        "path",
        "how",
        "what",
        "about",
        "alongside",
        "together",
        "both",
        "and",
        "also",
        "that",
        "those",
        "this",
        "these",
        "there",
        "here",
        "which",
        "whether",
        "if",
        "so",
        "then",
        "actually",
        "today",
        "currently",
        "internally",
        "internal",
        "outside",
        "externally",
        "visible",
        "visibility",
        "see",
        "seen",
        "seeing",
        "observe",
        "observed",
        "captured",
        "approved",
        "information",
        "based",
        "only",
        "public-facing",
        "step",
        "steps",
        "structured",
        "structure",
        "acknowledges",
        "acknowledge",
        "acknowledged",
        "acknowledgement",
        "sorts",
        "sort",
        "sorting",
        "route",
        "routes",
        "routed",
        "routing",
        "new",
        "inbound",
        "incoming",
        "request",
        "requests",
        "inquiry",
        "inquiries",
        "service",
        "services",
        "commercial",
        "hvac",
        "work",
        "business",
        "team",
        "person",
        "human",
        "review",
        "reviewed",
        "before",
        "after",
        "hours",
        "typical",
        "month",
        "channels",
        "handled",
        "handle",
        "handling",
        "comes",
        "come",
        "coming",
        "takes",
        "take",
        "taking",
        "picks",
        "pick",
        "picked",
        "could",
        "would",
        "may",
        "might",
        "appears",
        "appear",
        "seems",
        "seem",
        "suggests",
        "suggest",
        "possibly",
        "potentially",
        "perhaps",
        "curious",
        "wondering",
        "wonder",
        "consider",
        "explore",
        "evaluate",
        "evaluated",
        "compare",
        "comparing",
        "comparison",
        "relevant",
        "relevance",
        "useful",
        "helpful",
        "help",
        "helps",
        "idea",
        "sense",
        "worth",
        "open",
        "short",
        "quick",
        "brief",
        "small",
        "simple",
        "deterministic",
        "simulation",
        "simulated",
        "synthetic",
        "example",
        "examples",
        "prepared",
        "put",
        "built",
        "made",
        "created",
        "connected",
        "deployed",
        "official",
        "operated",
        "system",
        "systems",
        "claim",
        "claims",
        "claiming",
        "not",
        "no",
        "nothing",
        "any",
        "every",
        "each",
        "one",
        "some",
        "roughly",
        "approximately",
        "around",
        "typically",
        "generally",
        "kind",
        "sort-of",
        "part",
        "piece",
        "matter",
        "thing",
        "point",
        "note-that",
        "positioning",
        "front",
        "first",
        "contact",
        "reach",
        "reaching",
        "reachable",
        "especially",
        "something",
        "someone",
        "anything",
        "everything",
        "actual",
        "decide",
        "decision",
        "direct",
        "directly",
        "real",
        "own",
        "yourself",
        "yourselves",
        "us",
        "we",
        "our",
        "me",
        "myself",
        "reading",
        "read",
        "looking",
        "look",
        "noticed",
        "notice",
        "wanted",
        "want",
        "reason",
        "reasons",
        "hand",
        "hands",
        "front-door",
        "door",
        "line",
        "make",
        "makes",
        "making",
        "let",
        "lets",
        "letting",
        "keep",
        "keeping",
        "given",
        "giving",
        "get",
        "gets",
        "getting",
        "providing",
        "set",
        "setup",
        "putting",
        "run",
        "runs",
        "running",
        "use",
        "uses",
        "using",
        "used",
        "case",
        "cases",
        "next",
        "when",
        "where",
        "while",
        "under",
        "above",
        "along",
        "across",
        "within",
        "outside-view",
        "external-view",
    }
)

# (Attempt-6 remediation, section B.2) evidentiary-framing / epistemic connective
# vocabulary. These words perform NON-SUBSTANTIVE framing of an observation ("I
# noticed / while reviewing / listed / describing ...") or mark epistemic status
# ("though / rather / remains / we don't know ..."). They are consulted ONLY under
# v2 and ONLY as tense/aspect variants of words the safe-framing set already
# licenses, or as pure connectives - a framing verb never licenses a new business
# fact; the substantive remainder of the clause is still checked against the
# envelope vocabulary independently.
_V2_FRAMING_VOCAB: frozenset[str] = frozenset(
    {
        "reviewing",
        "noted",
        "noting",
        "listed",
        "listing",
        "describing",
        "referencing",
        "mentioning",
        "including",
        "showing",
        "available",
        "availability",
        "came",
        "browsing",
        "spotted",
        "though",
        "rather",
        "against",
        "simply",
        "now",
        "things",
        "stays",
        "stay",
        "remains",
        "remain",
        "remaining",
        "know",
        "knowing",
        "knew",
        "assumption",
        "assumptions",
        "question",
        "questions",
        "prospective",
        "customer",
        "customers",
    }
)

# --------------------------------------------------------------------------
# The validator
# --------------------------------------------------------------------------

# A substantive clause may carry at most this many content words that come from
# neither the fact phrases, the deterministic engine's own wording, nor the safe
# framing vocabulary.
_MAX_UNLICENSED_WORDS = 2
_MAX_UNLICENSED_RATIO = 0.5

# A clause that explicitly preserves an UNKNOWN is describing what is *not*
# known, not asserting it - the response/availability/missed-lead concepts are
# suppressed for that clause.
_PRESERVES_UNKNOWN = re.compile(
    r"\b(not (?:something|visible|publicly|clear)|isn'?t (?:visible|clear|something)|"
    r"no visibility|can(?:'?t| not) (?:see|tell|know)|not (?:visible|observable) "
    r"(?:from|to)|remains? unknown|we don'?t know|not for us to (?:say|know)|"
    r"from the outside|publicly (?:visible|observable))\b",
    re.IGNORECASE,
)
_UNKNOWN_SUPPRESSIBLE_CONCEPTS: frozenset[str] = frozenset(
    {
        "MISSED_LEADS",
        "SLOW_RESPONSE",
        "UNDERSTAFFED_OR_BUSY",
        "AVAILABILITY_TO_RESPONSE",
        "RESPONSE_PERFORMANCE_ASSERTED",
    }
)


class OutputValidator:
    version = OUTPUT_VALIDATOR_VERSION

    def __init__(self, *, contract: str = "v1") -> None:
        if contract not in ("v1", "v2", "v3"):
            raise ValueError(f"unknown validator contract {contract!r}")
        # v3 reuses every v2 prose rule; it only replaces rule 15 (the
        # provider-manifest cross-checks) with canonical claim reconciliation.
        self._v2 = contract in ("v2", "v3")
        self._v3 = contract == "v3"
        if self._v3:
            self.version = OUTPUT_VALIDATOR_V3_VERSION
        elif self._v2:
            self.version = OUTPUT_VALIDATOR_V2_VERSION
        else:
            self.version = OUTPUT_VALIDATOR_VERSION
        self.cta_parser_version = (
            CTA_PARSER_V3_VERSION
            if self._v3
            else CTA_PARSER_V2_VERSION
            if self._v2
            else CTA_PARSER_VERSION
        )
        self.contract = contract

    def validate(
        self, envelope: SemanticEnvelope, candidate: GenerationCandidate
    ) -> ValidationResult:
        findings: list[ValidatorFinding] = []
        cc = "v2" if self._v2 else "v1"  # (section 5) contract for _classify
        framing = _licensed_framing_vocab(envelope, v2=self._v2) | _SAFE_FRAMING_VOCAB
        fact_words = _fact_vocab(envelope)
        allowed_vocab = framing | fact_words
        # Built unconditionally (cheap); only consulted when self._v2.
        authorized = _AuthorizedVocab(envelope)

        email = candidate.artifact("first_contact_email")
        subject = candidate.artifact("subject")
        body = email.text if email else ""
        clauses = _split_clauses(body)
        manifest_by_span = {(_norm(e.rendered_span)): e for e in candidate.claim_manifest.entries}

        # 1. structure -----------------------------------------------------
        gr = envelope.generation_request
        if email is None:
            findings.append(_f("structure_violation", "no first_contact_email artifact"))
        else:
            wc = len(body.split())
            if wc > gr.max_body_words:
                findings.append(
                    _f(
                        "structure_violation",
                        f"body {wc} words > {gr.max_body_words}",
                        "first_contact_email",
                    )
                )
            cta_clauses = [c for c in clauses if _classify(c, contract=cc) == ClaimType.CTA]
            if len(cta_clauses) != 1:
                findings.append(
                    _f(
                        "structure_violation",
                        f"expected exactly one CTA clause, found {len(cta_clauses)}",
                        "first_contact_email",
                    )
                )
        if subject is not None:
            st = _norm(subject.text)
            if len(st) > gr.max_subject_chars:
                findings.append(
                    _f(
                        "structure_violation",
                        f"subject {len(st)} chars > {gr.max_subject_chars}",
                        "subject",
                    )
                )
            if re.match(r"^(re|fwd)\s*:", st, re.IGNORECASE):
                findings.append(
                    _f("structure_violation", "subject uses a fake-thread prefix", "subject")
                )

        # 2. required disclosure placeholders retained -------------------
        for disc in envelope.required_disclosures:
            if disc.placeholder and disc.placeholder not in body:
                findings.append(
                    _f(
                        "placeholder_resolved_early",
                        f"required placeholder {disc.placeholder} missing from body",
                        "first_contact_email",
                    )
                )
        for token in _PLACEHOLDER.findall(body):
            # a placeholder that is not one of the envelope's required ones is
            # fine, but a *resolved* required slot (token replaced by real text)
            # is caught above by the missing-placeholder check.
            _ = token

        # 3. no person / no contact -------------------------------------
        full_external = "\n".join(
            a.text for a in candidate.artifacts if a.kind in ("subject", "first_contact_email")
        )
        if PERSONAL_CONTACT.search(full_external):
            findings.append(
                _f("person_or_contact_present", "external text contains contact-shaped data")
            )

        # 4. numbers / financial values -------------------------------
        stripped = _PLACEHOLDER.sub(" ", full_external)
        stripped = _QUOTED.sub(" ", stripped)  # digits inside a quoted fact phrase are that fact's
        if self._v2:
            # (section 3) a numeric string that appears verbatim in an eligible
            # licensed fact is supported - e.g. "24/7" from a "24/7 Emergency
            # Service" SERVICE_AVAILABILITY fact. It supports availability
            # language only; "respond 24/7" is still caught by the
            # AVAILABILITY_TO_RESPONSE concept scan (rule 8), unchanged.
            licensed_nums = _licensed_numeric_strings(envelope)
            for n in licensed_nums:
                stripped = re.sub(re.escape(n), " ", stripped)
            fin = FINANCIAL_EXTERNAL.search(stripped)
            # a FINANCIAL_EXTERNAL hit is an unsupported NUMBER only when it
            # actually carries a digit / currency / percent; bare economic
            # vocabulary ("lead volume") is an economic-CLAIM concern handled by
            # the QUANTIFIED_BENEFIT concept scan, not by this number rule.
            if fin and re.search(r"[\d$£€%]", fin.group(0)):
                findings.append(
                    _f("unsupported_number", "external text contains a financial value or quantity")
                )
            elif re.search(r"(?<!\d)\d+(?!\d)", stripped):
                findings.append(
                    _f("unsupported_number", "external text contains an unsupported number")
                )
        else:
            if FINANCIAL_EXTERNAL.search(stripped):
                findings.append(
                    _f("unsupported_number", "external text contains a financial value or quantity")
                )
            elif re.search(r"(?<!\d)\d+(?!\d)", stripped):
                # bare digits outside placeholders and quoted fact phrases
                findings.append(
                    _f("unsupported_number", "external text contains an unsupported number")
                )

        # 5. internal score leak -------------------------------------
        if _SCORE_LEAK.search(full_external) or re.search(
            r"\b(high|low)\b[^.]{0,40}\b(priority|confidence|band|tier|match|fit)\b",
            full_external,
            re.I,
        ):
            findings.append(
                _f("internal_score_leak", "external text contains internal ranking language")
            )

        # 6. simulation disclosure meaning present -----------------
        _not_deployed = (
            _V2_DISCLOSURE_NOT_DEPLOYED.search(body)
            if self._v2
            else re.search(
                r"\bnot\b[^.]{0,40}\b(deployed|connected|official|operated|a system)\b",
                body,
                re.IGNORECASE,
            )
        )
        if (
            not _DISCLOSURE_CUES.search(body)
            or not re.search(r"\bsimulation\b", body, re.IGNORECASE)
            or not _not_deployed
        ):
            findings.append(
                _f(
                    "disclosure_lost",
                    "simulation / not-deployed disclosure meaning is missing or weakened",
                    "first_contact_email",
                )
            )

        # 7. injection markers -------------------------------------
        for hit in injection_markers(full_external):
            findings.append(
                _f("injection_derived_instruction", f"instruction-shaped text: {hit!r}")
            )
        for fact in envelope.eligible_company_facts:
            if (
                fact.injection_suspected
                and _norm(fact.verbatim_source_phrase).lower() in body.lower()
            ):
                findings.append(
                    _f(
                        "injection_derived_instruction",
                        f"reproduced an injection-suspected phrase for fact {fact.fact_id}",
                    )
                )

        # 8. semantic prohibited-concept scan. Runs on every prose clause (not
        #    just the ones the classifier could type as substantive) so an
        #    implication phrased with a vague subject - "some inquiries may go
        #    unanswered" - is still caught. Fail-closed.
        licensed_source_kinds = _licensed_source_kinds_for(envelope, candidate)
        prose_clauses = [
            c
            for c in clauses
            if _classify(c, contract=cc) not in (ClaimType.SALUTATION, ClaimType.SIGNATURE_SLOT)
        ]
        _fold_ok = {"AVAILABILITY_TO_RESPONSE", "RESPONSE_PERFORMANCE_ASSERTED"}
        for clause in prose_clauses:
            preserves_unknown = bool(_PRESERVES_UNKNOWN.search(clause))
            for concept in PROHIBITED_CONCEPTS:
                match = next(
                    (m for p in concept.patterns if (m := p.search(clause)) is not None), None
                )
                if match is None:
                    continue
                if preserves_unknown and concept.code in _UNKNOWN_SUPPRESSIBLE_CONCEPTS:
                    continue
                if concept.licensable_by and (concept.licensable_by & licensed_source_kinds):
                    # e.g. AVAILABILITY_TO_RESPONSE licensed by a RESPONSE_COMMITMENT
                    # fact - still only as a self-claim, checked by strength below.
                    continue
                # (3a) the trigger sits inside an explicit negation, or (3b) the
                # clause is (near-)equivalent to text this envelope itself
                # licenses (its disclosure / discovery question / may_say). An
                # unsupported POSITIVE claim still fails.
                if (
                    self._v2
                    and concept.code in _V2_NEGATION_SUPPRESSIBLE
                    and (
                        _negation_governs(clause, match.start())
                        or _matches_authorized(
                            clause, authorized, allow_fold=concept.code in _fold_ok
                        )
                    )
                ):
                    continue
                code = _CONCEPT_FINDING_CODE.get(concept.code, "prohibited_claim")
                findings.append(
                    _f(
                        code,
                        concept.description,
                        "first_contact_email",
                        span=clause,
                        concept=concept.code,
                    )
                )

        # 9. CTA semantic consistency (ADR-0067) ------------------
        _cta_contract = "v3" if self._v3 else "v2" if self._v2 else "v1"
        for clause in clauses:
            if _classify(clause, contract=cc) != ClaimType.CTA:
                continue
            for reason in cta_semantic_consistency(
                clause, envelope.structured_cta, contract=_cta_contract
            ):
                findings.append(
                    _f("cta_semantic_conflict", reason, "first_contact_email", span=clause)
                )

        # 10. unsupported geography -----------------------------
        allowed_places: set[str] = set()
        for fact in envelope.eligible_company_facts:
            if fact.category == "service_area_context" or "service_area" in fact.fact_class:
                allowed_places |= place_like_tokens(fact.verbatim_source_phrase)
                allowed_places |= place_like_tokens(fact.sanitized_phrase)
        allowed_places |= {envelope.business_identity.exact_public_hostname.lower()}
        for place in place_like_tokens(full_external):
            if place not in allowed_places and place not in {"tx", "texas"}:
                findings.append(
                    _f(
                        "unsupported_geography",
                        f"names a place not in a licensed service-area fact: {place!r}",
                    )
                )
            elif place in {"tx", "texas"} and not any(
                "tx" in p or "texas" in p for p in allowed_places
            ):
                findings.append(
                    _f(
                        "unsupported_geography",
                        "references Texas without a licensed service-area fact",
                    )
                )

        # 11. demo not misrepresented -------------------------
        for phrase in envelope.mentionable_demo_facts.must_not_say:
            pw = _content_words(phrase)
            if not pw:
                continue
            if not self._v2:
                if pw <= _content_words(body):
                    findings.append(
                        _f(
                            "demo_misrepresented",
                            f"asserts a prohibited demo statement: {phrase!r}",
                            "first_contact_email",
                        )
                    )
                continue
            # (3a) v2: the prohibited demo statement must actually be ASSERTED -
            # its content words co-occur inside one clause that is neither an
            # explicit negation/disclaimer nor a rendering of the envelope's own
            # authorized may_say / disclosure text.
            for clause in prose_clauses:
                if not pw <= _content_words(clause):
                    continue
                if _matches_authorized(clause, authorized):
                    continue
                triggers = [
                    m.start()
                    for w in ("deployed", "connected", "live", "official", "operated")
                    for m in re.finditer(rf"\b{w}\b", clause, re.IGNORECASE)
                ]
                if triggers and all(_negation_governs(clause, t) for t in triggers):
                    continue
                findings.append(
                    _f(
                        "demo_misrepresented",
                        f"asserts a prohibited demo statement: {phrase!r}",
                        "first_contact_email",
                        span=clause,
                    )
                )
                break

        # 12. licensing every substantive clause against the envelope vocab
        substantive = [
            c
            for c in clauses
            if _classify(c, contract=cc)
            in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
        ]
        company_specific_clauses = 0
        v2_framing = allowed_vocab | _V2_FRAMING_VOCAB
        for clause in substantive:
            if self._v2:
                # (Attempt-6 remediation B.2) drop possessive/contraction tails,
                # allow tense/aspect variants of licensed words (_stem_covered),
                # and treat evidentiary-framing / epistemic connectives as
                # licensed. A genuinely new business fact still leaves > 2
                # uncovered content words and still fails.
                words = _content_words_v2(clause)
                if not words:
                    continue
                unlicensed = {w for w in (words - v2_framing) if not _stem_covered(w, v2_framing)}
            else:
                words = _content_words(clause)
                if not words:
                    continue
                unlicensed = words - allowed_vocab
            if (
                len(unlicensed) > _MAX_UNLICENSED_WORDS
                or len(unlicensed) / len(words) > _MAX_UNLICENSED_RATIO
            ):
                findings.append(
                    _f(
                        "unlicensed_claim",
                        "clause introduces content not licensed by any fact/finding/inference: "
                        f"{sorted(unlicensed)[:6]}",
                        "first_contact_email",
                        span=clause,
                    )
                )
            # (section 5) under v2 a clause counts as company-specific only when
            # it shares a NON-GENERIC fact word with the envelope; a clause whose
            # only overlap is "commercial"/"hvac"/"service"/... is commercially
            # generic, not personalized.
            fact_hits = words & fact_words
            if self._v2:
                fact_hits = fact_hits - _GENERIC_FACT_WORDS
            if fact_hits:
                company_specific_clauses += 1
            # conditional preservation for inference/recommendation clauses
            if _classify(clause, contract=cc) in (ClaimType.INFERENCE, ClaimType.RECOMMENDATION):
                low = clause.lower()
                if not any(cue in low for cue in CONDITIONAL_CUES):
                    findings.append(
                        _f(
                            "conditional_language_lost",
                            "inference/recommendation lost its conditional qualifier",
                            "first_contact_email",
                            span=clause,
                        )
                    )

        # 13. name-only personalization ----------------------
        # (section 5, owner decision 2026-09-02) safe-but-generic prose is a
        # COMMUNICATION_QUALITY concern, not a safety failure: under v2 this is
        # ADVISORY and never by itself fails a candidate or the run. Human review
        # and M6.8-4 may still reject WEAK / NOT_DISTINCTIVE output.
        if company_specific_clauses == 0:
            findings.append(
                _f(
                    "no_company_specific_evidence",
                    "no substantive clause is company-specific beyond the display name",
                    severity=(
                        ValidatorSeverity.ADVISORY if self._v2 else ValidatorSeverity.HARD_FAILURE
                    ),
                )
            )

        # 14. paraphrase fidelity: any quoted fragment must be a verbatim
        #     substring of a licensed source phrase --------------------
        licensed_verbatim = [
            _norm(f.verbatim_source_phrase).lower() for f in envelope.eligible_company_facts
        ] + [
            _norm(f.supporting_excerpt).lower()
            for f in envelope.m3_findings
            if f.supporting_excerpt
        ]
        for match in _QUOTED.finditer(full_external):
            quoted = _norm(match.group(1)).lower()
            if not any(quoted in src or src in quoted for src in licensed_verbatim):
                findings.append(
                    _f(
                        "material_paraphrase_alteration",
                        "quoted fragment is not a verbatim licensed source phrase: "
                        f"{match.group(1)!r}",
                    )
                )

        # 15. claim reconciliation -------------------------------
        canonical_meta: dict[str, object] = {}
        if self._v3:
            # (final M6.8-3 architectural correction) the provider manifest is
            # NON-AUTHORITATIVE. Every substantive rendered clause is
            # independently discovered, classified, source-licensed and
            # strength-checked from the prose + envelope. 100% substantive
            # coverage is required; an unresolved substantive span fails closed.
            from opintel_communication.canonical_claim_reconciler import reconcile

            cmap = reconcile(
                subject=subject.text if subject else "",
                body=body,
                envelope=envelope,
                structured_cta=envelope.structured_cta,
                required_disclosures=envelope.required_disclosures,
                provider_manifest=candidate.claim_manifest,
            )
            findings.extend(cmap.findings)
            if cmap.coverage < 1.0:
                findings.append(
                    _f(
                        "canonical_reconciliation_incomplete",
                        f"substantive-prose reconciliation coverage {cmap.coverage:.3f} < 1.0 "
                        f"({cmap.unresolved_count} unresolved span(s))",
                        "first_contact_email",
                    )
                )
            for dg in cmap.manifest_disagreements:
                findings.append(
                    _f(
                        "provider_manifest_disagreement",
                        f"{dg.kind}: {dg.detail}",
                        span=dg.span or None,
                        severity=ValidatorSeverity.ADVISORY,
                    )
                )
            canonical_meta = {
                "canonical_reconciliation_coverage": cmap.coverage,
                "unresolved_substantive_claims": cmap.unresolved_count,
                "canonical_substantive_claims": cmap.substantive_count,
                "canonical_licensed_claims": cmap.licensed_count,
                "canonical_rejected_claims": cmap.rejected_count,
                "provider_manifest_disagreements": tuple(
                    d.kind for d in cmap.manifest_disagreements
                ),
                "canonical_claim_map": cmap,
            }
        else:
            findings.extend(
                self._check_manifest(
                    envelope,
                    candidate,
                    clauses,
                    manifest_by_span,
                    allowed_vocab,
                    licensed_source_kinds,
                )
            )

        # 16. subject <= body / source strength ------------------
        if subject is not None:
            findings.extend(
                self._check_subject(envelope, subject.text, body, allowed_vocab, fact_words)
            )

        # 17. UNKNOWN hard prohibitions (belt-and-braces on top of concept scan)
        for unknown in envelope.explicit_unknowns:
            if not unknown.hard_prohibition:
                continue
            # crude: if a clause asserts a certainty verb near the unknown's
            # component keyword, flag it.
            comp_words = _content_words(unknown.component.replace("_", " "))
            for clause in substantive:
                low = clause.lower()
                if self._v2 and (
                    _matches_authorized(clause, authorized, allow_fold=True)
                    or _PRESERVES_UNKNOWN.search(clause)
                ):
                    continue
                if (
                    comp_words & _content_words(clause)
                    and any(cue in low for cue in CERTAINTY_CUES)
                    and not any(cue in low for cue in CONDITIONAL_CUES)
                ):
                    findings.append(
                        _f(
                            "unknown_asserted",
                            f"asserts the {unknown.component} UNKNOWN as known",
                            "first_contact_email",
                            span=clause,
                        )
                    )

        # (sections 5/6) under v2, an ADVISORY finding records a
        # COMMUNICATION_QUALITY concern but never by itself fails the candidate
        # or the run. Under v1 every finding is a hard failure (byte-identical
        # legacy behaviour). All findings are retained on the result either way.
        if self._v2:
            passed = not any(f.severity != ValidatorSeverity.ADVISORY for f in findings)
        else:
            passed = not findings
        if self._v3:
            return ValidationResult(
                candidate_id=candidate.candidate_id,
                passed=passed,
                findings=tuple(findings),
                validator_version=OUTPUT_VALIDATOR_V3_VERSION,
                cta_parser_version=self.cta_parser_version,
                **canonical_meta,  # type: ignore[arg-type]
            )
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            passed=passed,
            findings=tuple(findings),
        )

    # ------------------------------------------------------------------

    def _check_manifest(
        self,
        env: SemanticEnvelope,
        cand: GenerationCandidate,
        clauses: list[str],
        manifest_by_span: dict[str, ClaimManifestEntry],
        allowed_vocab: set[str],
        licensed_source_kinds: set[str],
    ) -> list[ValidatorFinding]:
        out: list[ValidatorFinding] = []
        cc = "v2" if self._v2 else "v1"
        _FACT_BEARING = (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
        substantive = [c for c in clauses if _classify(c, contract=cc) in _FACT_BEARING]

        # 15a. every substantive rendered clause is represented in the manifest
        for clause in substantive:
            covered = any(
                _norm(clause).lower() in span.lower() or span.lower() in _norm(clause).lower()
                for span in manifest_by_span
            )
            if not covered:
                out.append(
                    _f(
                        "undeclared_rendered_claim",
                        f"substantive clause absent from claim_manifest: {clause!r}",
                        "first_contact_email",
                        span=clause,
                    )
                )

        # (section 2) non-fact-bearing entry types may legitimately carry
        # licensed_source_ids = []; their legality is validated by the CTA
        # contract (rule 9), the disclosure contract (rule 6), artifact
        # structure (rule 1) and placeholder/signature rules (rule 2), not by
        # evidentiary source-word overlap. Under v2 the CTA type joins the set
        # already skipped here. Factual / inferential / recommendation entries
        # still MUST cite an evidentiary source.
        _checked_types = (
            (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
            if self._v2
            else (
                ClaimType.FACT,
                ClaimType.INFERENCE,
                ClaimType.RECOMMENDATION,
                ClaimType.CTA,
            )
        )
        for entry in cand.claim_manifest.entries:
            span = _norm(entry.rendered_span)
            span_words = _content_words_v2(span) if self._v2 else _content_words(span)

            # (section 4) reconcile the provider's declared claim_type with the
            # deterministic classification of the wording it actually rendered.
            if self._v2:
                rendered_type = _classify(span, contract=cc)
                declared_fact_bearing = entry.claim_type in _FACT_BEARING
                rendered_fact_bearing = rendered_type in _FACT_BEARING
                if _is_framing_leadin(span, env):
                    # (Haiku track D1) a bare evidentiary lead-in with no
                    # substantive business predicate - source-free regardless of
                    # how the provider typed it. The sibling factual clause
                    # carries its own manifest entry and stays source-bound.
                    if entry.claim_type != ClaimType.TRANSITION:
                        out.append(
                            _f(
                                "provider_manifest_type_mismatch",
                                f"claim {entry.claim_id}: {entry.claim_type} lead-in fragment "
                                f"with no substantive predicate ({span!r})",
                                claim_id=entry.claim_id,
                                span=span,
                                severity=ValidatorSeverity.ADVISORY,
                            )
                        )
                    continue
                if declared_fact_bearing and _is_identity_grammar(span, env):
                    # (Attempt-6 remediation B.2) the span is just the business
                    # display name - identity grammar, not a business fact.
                    # Record the mis-type; no evidentiary source is required.
                    out.append(
                        _f(
                            "provider_manifest_type_mismatch",
                            f"claim {entry.claim_id}: declared {entry.claim_type} for a "
                            f"span that is only the business identity ({span!r})",
                            claim_id=entry.claim_id,
                            span=span,
                            severity=ValidatorSeverity.ADVISORY,
                        )
                    )
                    continue
                if declared_fact_bearing and rendered_type in (
                    ClaimType.DISCLOSURE,
                    ClaimType.QUESTION,
                    ClaimType.CTA,
                    ClaimType.SALUTATION,
                    ClaimType.SIGNATURE_SLOT,
                ):
                    # Provider over-typed a disclosure / question / CTA /
                    # structural sentence as a fact. The deterministic classifier
                    # affirmatively recognises it as non-fact-bearing, so it
                    # needs no evidentiary licensing - the mis-type is recorded
                    # as an advisory manifest/schema finding. (A span the
                    # classifier is merely UNSURE about - NON_SUBSTANTIVE /
                    # TRANSITION - is NOT waived: it still runs the checks below.)
                    out.append(
                        _f(
                            "provider_manifest_type_mismatch",
                            f"claim {entry.claim_id}: declared {entry.claim_type} but "
                            f"wording classifies as {rendered_type}",
                            claim_id=entry.claim_id,
                            span=span,
                            severity=ValidatorSeverity.ADVISORY,
                        )
                    )
                    continue
                if not declared_fact_bearing and rendered_fact_bearing:
                    # Provider under-typed a fact-bearing span (e.g. labelled it
                    # DISCLOSURE). It still requires evidence: fall through into
                    # the evidentiary checks below and record the mis-type -
                    # unless the source-less redundant-wrapper reconciliation at
                    # 15b will account for it (avoid a duplicate advisory).
                    if not (
                        not entry.licensed_source_ids
                        and _redundant_wrapper_reconciled(entry, cand, env)
                    ):
                        out.append(
                            _f(
                                "provider_manifest_type_mismatch",
                                f"claim {entry.claim_id}: declared {entry.claim_type} but "
                                f"wording classifies as fact-bearing {rendered_type}",
                                claim_id=entry.claim_id,
                                span=span,
                                severity=ValidatorSeverity.ADVISORY,
                            )
                        )
                elif entry.claim_type not in _checked_types:
                    continue
            elif entry.claim_type not in _checked_types:
                continue

            # 15b. declared sources exist
            resolved = [env.source_by_id(sid) for sid in entry.licensed_source_ids]
            if not entry.licensed_source_ids:
                # (owner authorization 2026-09-02 "AUTHORIZE BOUNDED
                # REDUNDANT-MANIFEST RECONCILIATION") a source-less entry is
                # exempt ONLY as a redundant wrapper whose every substantive unit
                # is independently and validly licensed by finer-grained sibling
                # entries and which itself adds nothing. Deterministic; the
                # provider's declared claim_type is not trusted.
                if self._v2 and _redundant_wrapper_reconciled(entry, cand, env):
                    out.append(
                        _f(
                            "provider_manifest_type_mismatch",
                            f"claim {entry.claim_id}: source-less wrapper span fully "
                            f"reconciled by sibling entries; adds no independent "
                            f"unsupported claim",
                            claim_id=entry.claim_id,
                            span=span,
                            severity=ValidatorSeverity.ADVISORY,
                        )
                    )
                    continue
                out.append(
                    _f(
                        "claim_manifest_source_mismatch",
                        f"claim {entry.claim_id} cites an unknown or empty source",
                        claim_id=entry.claim_id,
                    )
                )
                continue
            if any(r is None for r in resolved):
                out.append(
                    _f(
                        "claim_manifest_source_mismatch",
                        f"claim {entry.claim_id} cites an unknown or empty source",
                        claim_id=entry.claim_id,
                    )
                )
                continue

            # 15c. the cited sources actually license the meaning of the span
            source_words: set[str] = set()
            source_strengths: list[FactStrength] = []
            for src in resolved:
                if isinstance(src, EnvelopeFact):
                    source_words |= _content_words(src.sanitized_phrase)
                    source_words |= _content_words(src.verbatim_source_phrase)
                    source_strengths.append(src.strength)
                elif isinstance(src, M3FindingRef):
                    source_words |= _content_words(src.rendered_text)
                    if src.supporting_excerpt:
                        source_words |= _content_words(src.supporting_excerpt)
                    source_strengths.append(FactStrength.OBSERVED_PUBLIC_TEXT)
                else:  # inference / recommendation
                    text = getattr(src, "text", "")
                    source_words |= _content_words(text)
                    source_strengths.append(
                        FactStrength.LICENSED_INFERENCE
                        if entry.claim_type == ClaimType.INFERENCE
                        else FactStrength.LICENSED_RECOMMENDATION
                    )
                # (section 2) a source's usage_rule is part of what it licenses:
                # a faithful paraphrase that stays within the usage rule is
                # covered. Only consulted under v2.
                if self._v2:
                    source_words |= _content_words(getattr(src, "usage_rule", "") or "")
            # A CTA entry's meaning is checked by cta_semantic_consistency, not by
            # source-word overlap - skip 15c/15e for it.
            if entry.claim_type != ClaimType.CTA:
                _15c_allowed = allowed_vocab
                if self._v2:
                    # (Attempt-6 remediation B.2) evidentiary-framing / epistemic
                    # connectives ("though", "rather", "remains", "we don't
                    # know", "assumption") are not new business facts.
                    _15c_allowed = _15c_allowed | _V2_FRAMING_VOCAB
                span_specific = span_words - _15c_allowed - source_words
                if self._v2 and span_specific:
                    # (section 2) bounded semantic licensing: light morphology
                    # (confirm/confirms) counts as covered, and a word that
                    # occurs in the span ONLY inside a semantic negation is not
                    # evidence of an added claim. A fluent paraphrase that adds
                    # >_MAX_UNLICENSED_WORDS genuinely-new content words still
                    # fails.
                    span_specific = {
                        w
                        for w in span_specific
                        if not _stem_covered(w, source_words | _15c_allowed)
                        and not _only_in_negation(w, span)
                    }
                if span_words and len(span_specific) > _MAX_UNLICENSED_WORDS:
                    out.append(
                        _f(
                            "claim_manifest_source_mismatch",
                            f"claim {entry.claim_id}: span content not covered by the cited "
                            f"source(s): {sorted(span_specific)[:6]}",
                            claim_id=entry.claim_id,
                            span=span,
                        )
                    )

            # 15d. asserted strength <= strongest cited source strength
            if entry.asserted_strength is not None and source_strengths:
                strongest = max(source_strengths, key=lambda s: _rank(s))
                if not strength_at_most(entry.asserted_strength, strongest):
                    out.append(
                        _f(
                            "claim_manifest_strength_mismatch",
                            f"claim {entry.claim_id}: asserted "
                            f"{entry.asserted_strength} > source {strongest}",
                            claim_id=entry.claim_id,
                        )
                    )

            if entry.claim_type == ClaimType.CTA:
                continue

            source_ceiling = (
                max(source_strengths, key=lambda s: _rank(s)) if source_strengths else None
            )
            # (3c) when the manifest declaration is consistent with the cited
            # source, trust it - do not let a lexical strength guess override a
            # declaration that already matches its licensed source. A GENUINE
            # strengthening ABOVE the source is still caught by 15d
            # (claim_manifest_strength_mismatch) and the prohibited-concept scan.
            if (
                self._v2
                and entry.asserted_strength is not None
                and source_ceiling is not None
                and entry.asserted_strength == source_ceiling
            ):
                continue

            # 15e. rendered wording does not exceed the licensed strength
            detected = _detected_strength(span, v2=self._v2)
            ceiling = entry.asserted_strength or source_ceiling
            if ceiling is not None and not strength_at_most(detected, ceiling):
                out.append(
                    _f(
                        "rendered_claim_exceeds_manifest",
                        f"claim {entry.claim_id}: wording sounds like "
                        f"{detected}, licensed ceiling {ceiling}",
                        claim_id=entry.claim_id,
                        span=span,
                    )
                )
        _ = licensed_source_kinds
        return out

    def _check_subject(
        self,
        env: SemanticEnvelope,
        subject_text: str,
        body: str,
        allowed_vocab: set[str],
        fact_words: set[str],
    ) -> list[ValidatorFinding]:
        out: list[ValidatorFinding] = []
        subj = _norm(subject_text)
        subj_words = _content_words(subj)
        unlicensed = subj_words - allowed_vocab
        if subj_words and len(unlicensed) / len(subj_words) > _MAX_UNLICENSED_RATIO:
            out.append(
                _f(
                    "subject_exceeds_body_or_source",
                    f"subject introduces content not in the envelope: {sorted(unlicensed)[:6]}",
                    "subject",
                )
            )
        # subject may not sound stronger than the body: its detected strength
        # must not exceed the strongest strength present in the body.
        body_strength = _detected_strength(body, v2=self._v2)
        subj_strength = _detected_strength(subj, v2=self._v2)
        if not strength_at_most(subj_strength, body_strength):
            out.append(
                _f(
                    "subject_exceeds_body_or_source",
                    f"subject strength {subj_strength} exceeds body strength {body_strength}",
                    "subject",
                )
            )
        # subject must also independently pass the concept scan
        for concept in PROHIBITED_CONCEPTS:
            if any(p.search(subj) for p in concept.patterns) and not concept.licensable_by:
                out.append(
                    _f(
                        "prohibited_claim",
                        f"subject: {concept.description}",
                        "subject",
                        concept=concept.code,
                    )
                )
        _ = (env, fact_words)
        return out


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_CERTAINTY_STRENGTH = re.compile(
    r"\b(you (?:respond|answer|reply|handle|are|do)|responds?|answers?|handles?|"
    r"ensures?|guarantees?|means (?:that )?you|so you (?:never|always)|"
    r"every (?:call|request|inquiry) (?:is|gets))\b",
    re.IGNORECASE,
)
_SELF_CLAIM_STRENGTH = re.compile(
    r"\b(you (?:publicly )?(?:describe|highlight|position|market|present) yourself|"
    r"your site (?:highlights|describes|positions|calls)|you say|you claim|"
    r"publicly (?:describe|highlight|present)|your public (?:pages|site) (?:say|state))\b",
    re.IGNORECASE,
)


def _detected_strength(text: str, *, v2: bool = False) -> FactStrength:
    # (3c) under v2, an explicitly-attributed statement ("your site states X",
    # "a published note that…") is a PUBLISHED_SELF_CLAIM even if it contains a
    # response verb - it is not being asserted as verified fact.
    attributed = v2 and bool(_ATTRIBUTION_CUES.search(text))
    if _CERTAINTY_STRENGTH.search(text) and not attributed:
        return FactStrength.VERIFIED_FACT
    if _SELF_CLAIM_STRENGTH.search(text) or attributed:
        return FactStrength.PUBLISHED_SELF_CLAIM
    low = text.lower()
    if any(cue in low for cue in CONDITIONAL_CUES):
        return FactStrength.LICENSED_INFERENCE
    return FactStrength.OBSERVED_PUBLIC_TEXT


_RANK = {
    FactStrength.OBSERVED_PUBLIC_TEXT: 1,
    FactStrength.OBSERVED_AVAILABILITY_SIGNAL: 1,
    FactStrength.PUBLISHED_SELF_CLAIM: 2,
    FactStrength.LICENSED_INFERENCE: 2,
    FactStrength.LICENSED_RECOMMENDATION: 2,
    FactStrength.VERIFIED_FACT: 3,
}


def _rank(value: FactStrength) -> int:
    return _RANK[value]


def _licensed_source_kinds_for(env: SemanticEnvelope, cand: GenerationCandidate) -> set[str]:
    """Fact categories present in the envelope that a candidate could draw on."""

    kinds: set[str] = set()
    for fact in env.eligible_company_facts:
        if not fact.injection_suspected:
            kinds.add(fact.category.upper())
    return kinds


def _f(
    code: str,
    message: str,
    artifact_kind: str | None = None,
    span: str | None = None,
    concept: str | None = None,
    claim_id: str | None = None,
    *,
    severity: ValidatorSeverity = ValidatorSeverity.HARD_FAILURE,
) -> ValidatorFinding:
    return ValidatorFinding(
        code=code,
        message=message,
        severity=severity,
        artifact_kind=artifact_kind,
        span=span[:200] if span else None,
        concept=concept,
        claim_id=claim_id,
    )
