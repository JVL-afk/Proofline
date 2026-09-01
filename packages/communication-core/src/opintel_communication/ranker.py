"""``comm.candidate_ranker@1`` - deterministic ordering of candidates that have
ALREADY PASSED validation.

The ranker never sees a FAILED candidate, never overrides a validator finding,
and never decides send eligibility. It produces a stable order plus a full,
auditable breakdown of every bounded feature it considered. Given the same
inputs it always returns the same order and the same scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opintel_communication.domain import (
    CANDIDATE_RANKER_VERSION,
    ClaimType,
    EnvelopeFact,
    GenerationCandidate,
    M3FindingRef,
    RankComponent,
    RankedCandidate,
    RankScore,
    SemanticEnvelope,
    ValidationResult,
    strength_rank,
)
from opintel_communication.normalize import normalize_candidate

_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_QUOTED = re.compile(r'"([^"]{2,})"')

_GENERIC_TOKENS: frozenset[str] = frozenset(
    {
        "service",
        "services",
        "quality",
        "professional",
        "trusted",
        "reliable",
        "expert",
        "experts",
        "solution",
        "solutions",
        "needs",
        "team",
        "company",
        "business",
        "customer",
        "customers",
        "commercial",
        "value",
        "help",
        "provide",
        "offer",
    }
)

_HEDGE_TOKENS: frozenset[str] = frozenset(
    {
        "might",
        "maybe",
        "perhaps",
        "possibly",
        "potentially",
        "somewhat",
        "fairly",
        "rather",
        "arguably",
        "presumably",
        "seemingly",
        "roughly",
        "sort",
        "kind",
        "guess",
    }
)

# Fixed, documented weights. They sum to 1.0.
_WEIGHTS: dict[str, float] = {
    "distinguishing_fact_strength": 0.25,
    "company_specific_content": 0.20,
    "evidence_class_diversity": 0.15,
    "brevity": 0.10,
    "generic_phrase_ratio": 0.10,
    "hedge_density": 0.08,
    "quoted_fragment_count": 0.07,
    "disclosure_opening_dominance": 0.05,
}
_PENALTY_FEATURES = frozenset(
    {
        "generic_phrase_ratio",
        "hedge_density",
        "quoted_fragment_count",
        "disclosure_opening_dominance",
    }
)


@dataclass(frozen=True, slots=True)
class _Feat:
    raw: str
    normalized: float  # [0, 1], higher is always better


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _cited_sources(
    env: SemanticEnvelope, candidate: GenerationCandidate
) -> tuple[list[EnvelopeFact], list[M3FindingRef], int]:
    facts: list[EnvelopeFact] = []
    findings: list[M3FindingRef] = []
    substantive = 0
    for entry in candidate.claim_manifest.entries:
        if entry.claim_type in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION):
            substantive += 1
        for sid in entry.licensed_source_ids:
            src = env.source_by_id(sid)
            if isinstance(src, EnvelopeFact):
                facts.append(src)
            elif isinstance(src, M3FindingRef):
                findings.append(src)
    return facts, findings, substantive


def _distinguishing_fact_strength(facts: list[EnvelopeFact]) -> _Feat:
    if not facts:
        return _Feat("no licensed fact cited", 0.0)
    best = max(facts, key=lambda f: strength_rank(f.strength))
    # rank is 1..3; a distinguishing lead is rank >= 2.
    norm = _clamp01((strength_rank(best.strength) - 1) / 2.0)
    return _Feat(f"{best.category}:{best.strength}", norm)


def _company_specific_content(
    facts: list[EnvelopeFact], findings: list[M3FindingRef], substantive: int
) -> _Feat:
    if substantive == 0:
        return _Feat("0 substantive manifest entries", 0.0)
    grounded = len(facts) + len(findings)
    return _Feat(
        f"{grounded} grounded / {substantive} substantive", _clamp01(grounded / substantive)
    )


def _evidence_class_diversity(env: SemanticEnvelope, facts: list[EnvelopeFact]) -> _Feat:
    available = {f.category for f in env.eligible_company_facts if not f.injection_suspected}
    used = {f.category for f in facts}
    if not available:
        return _Feat("no eligible categories", 0.0)
    return _Feat(f"{len(used)}/{len(available)} categories", _clamp01(len(used) / len(available)))


def _brevity(env: SemanticEnvelope, body_words: int) -> _Feat:
    cap = max(1, env.generation_request.max_body_words)
    # reward staying comfortably under the cap; 60% of cap or less scores 1.0
    ratio = body_words / cap
    norm = _clamp01((1.0 - ratio) / 0.4)
    return _Feat(f"{body_words}/{cap} words", norm)


def _generic_phrase_ratio(body: str) -> _Feat:
    words = _WORD.findall(body.lower())
    if not words:
        return _Feat("empty body", 0.0)
    hits = sum(1 for w in words if w in _GENERIC_TOKENS)
    ratio = hits / len(words)
    return _Feat(f"{hits}/{len(words)} generic ({ratio:.3f})", _clamp01(1.0 - ratio / 0.15))


def _hedge_density(body: str) -> _Feat:
    words = _WORD.findall(body.lower())
    sentences = max(1, body.count(".") + body.count("?"))
    hits = sum(1 for w in words if w in _HEDGE_TOKENS)
    density = hits / sentences
    return _Feat(f"{hits} hedges / {sentences} sentences ({density:.2f})", _clamp01(1.0 - density))


def _quoted_fragment_count(body: str) -> _Feat:
    n = len(_QUOTED.findall(body))
    over = max(0, n - 2)
    return _Feat(f"{n} quoted fragments", _clamp01(1.0 - over / 3.0))


def _disclosure_opening_dominance(env: SemanticEnvelope, body: str) -> _Feat:
    opening = body.split("\n\n", 1)[0]
    open_words = _WORD.findall(opening.lower())
    if not open_words:
        return _Feat("empty opening", 0.0)
    disc_tokens: set[str] = set()
    for disc in env.required_disclosures:
        text = disc.canonical_text or disc.placeholder or ""
        disc_tokens |= set(_WORD.findall(text.lower()))
    if not disc_tokens:
        return _Feat("no disclosure tokens", 1.0)
    hits = sum(1 for w in open_words if w in disc_tokens)
    ratio = hits / len(open_words)
    return _Feat(
        f"{hits}/{len(open_words)} opening words are disclosure ({ratio:.2f})",
        _clamp01(1.0 - ratio / 0.5),
    )


def _score_candidate(env: SemanticEnvelope, candidate: GenerationCandidate) -> RankScore:
    norm = normalize_candidate(candidate)
    facts, findings, substantive = _cited_sources(env, candidate)
    feats: dict[str, _Feat] = {
        "distinguishing_fact_strength": _distinguishing_fact_strength(facts),
        "company_specific_content": _company_specific_content(facts, findings, substantive),
        "evidence_class_diversity": _evidence_class_diversity(env, facts),
        "brevity": _brevity(env, norm.body_word_count),
        "generic_phrase_ratio": _generic_phrase_ratio(norm.normalized_body),
        "hedge_density": _hedge_density(norm.normalized_body),
        "quoted_fragment_count": _quoted_fragment_count(norm.normalized_body),
        "disclosure_opening_dominance": _disclosure_opening_dominance(env, norm.normalized_body),
    }
    components: list[RankComponent] = []
    total = 0.0
    for name, weight in _WEIGHTS.items():
        feat = feats[name]
        contribution = round(feat.normalized * weight, 6)
        total += contribution
        components.append(
            RankComponent(
                name=name,
                raw_value=feat.raw,
                normalized=round(feat.normalized, 6),
                weight=weight,
                contribution=contribution,
                penalty=name in _PENALTY_FEATURES,
            )
        )
    return RankScore(
        candidate_id=candidate.candidate_id,
        components=tuple(components),
        total=round(total, 6),
    )


class CandidateRanker:
    version = CANDIDATE_RANKER_VERSION

    def rank(
        self,
        envelope: SemanticEnvelope,
        passing: tuple[tuple[GenerationCandidate, ValidationResult], ...],
    ) -> tuple[RankedCandidate, ...]:
        """Order the PASS-validation candidates. A candidate whose validation
        did not pass is a programming error here and is rejected."""

        for cand, result in passing:
            if not result.passed:
                raise ValueError(
                    f"ranker received candidate {cand.candidate_id} with a FAILED validation; "
                    "the ranker must never rank a candidate the validator rejected"
                )
        scored = [(_score_candidate(envelope, cand), cand) for cand, _ in passing]
        # Deterministic order: higher total, then shorter body, then candidate_id.
        scored.sort(
            key=lambda pair: (
                -pair[0].total,
                normalize_candidate(pair[1]).body_word_count,
                pair[1].candidate_id,
            )
        )
        return tuple(
            RankedCandidate(rank=i + 1, candidate_id=score.candidate_id, score=score)
            for i, (score, _cand) in enumerate(scored)
        )
