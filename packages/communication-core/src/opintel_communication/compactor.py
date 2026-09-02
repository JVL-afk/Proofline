"""``comm.candidate_compactor@1`` - deterministic, offline, sentence-level body
compaction (owner authorization 2026-09-02, section D2).

Purpose: a smaller/faster provider model cannot reliably obey the <= 130-word
body limit. Rather than teach the model to count perfectly, this compactor
removes *complete optional sentences* - never rewriting, paraphrasing,
truncating, splicing, adding words, strengthening claims, altering quotations,
altering the CTA, removing a required disclosure, or removing a
signature/placeholder line.

Every surviving rendered span is byte-identical to the provider output. The raw
provider response / candidate / manifest are untouched; this produces a
separately hashed *revision*. Compaction never launders unsafe prose: the caller
still validates the ORIGINAL candidate and any zero-tolerance safety finding on
the original remains run-visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opintel_communication.domain import (
    ClaimManifest,
    ClaimType,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
    SemanticEnvelope,
)
from opintel_communication.hashing import sha256_text
from opintel_communication.validator import (
    _DISCLOSURE_CUES,
    _classify,
    _content_words_v2,
    _norm,
)

COMPACTOR_VERSION = "comm.candidate_compactor@1"

_HARD_BODY_WORD_CAP = 130
_PLACEHOLDER_LINE = re.compile(r"^\s*\{\{[^}]+\}\}\s*$")
# a sentence boundary is [.!?], then an optional closing quote, then whitespace -
# so `Repair." This is ...` splits into two sentences (the closing quote travels
# with the whitespace separator, so rebuild stays byte-identical).
_QUOTE_CHARS = "\"'" + chr(0x2019) + chr(0x201D)
_SENTENCE_END = re.compile("(?<=[.!?])([" + re.escape(_QUOTE_CHARS) + r"]?\s+)")


def split_sentences(text: str) -> list[str]:
    """Quote-aware sentence split of a single line/paragraph of prose."""
    parts = _SENTENCE_END.split(text)
    return [p.strip().strip(_QUOTE_CHARS) for p in parts if p and p.strip()]


# Retention tiers - lower number = keep harder. Sentences are removed starting
# from the highest tier number, last-in-document first within a tier.
_TIER_NEVER = 0  # disclosure / sole CTA / salutation / placeholder / signature
_TIER_EVIDENCE_HOOK = 1  # the sentence carrying the strongest company-specific fact
_TIER_VALUE_CORE = 2  # the simulation / comparison / recommendation sentence
_TIER_SECONDARY_EVIDENCE = 3  # other fact / inference sentences
_TIER_TRANSITION = 4  # transitions, redundant framing, generic explanation

_TIER_NAME = {
    _TIER_NEVER: "protected",
    _TIER_EVIDENCE_HOOK: "evidence_hook",
    _TIER_VALUE_CORE: "value_core",
    _TIER_SECONDARY_EVIDENCE: "secondary_evidence",
    _TIER_TRANSITION: "transition_or_redundant",
}

_VALUE_CUES = re.compile(
    r"\b(simulation|simulated|compare|comparing|comparison|deterministic|"
    r"acknowledg\w*|sorts?|routing|intake step|reference point)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RemovedSentence:
    sentence_id: int
    text: str
    tier: str
    reason: str
    words: int


@dataclass(frozen=True, slots=True)
class CompactionAudit:
    version: str
    applied: bool
    reached_target: bool
    words_before: int
    words_after: int
    hard_word_cap: int
    removed_sentences: tuple[RemovedSentence, ...]
    manifest_entries_removed: tuple[str, ...]
    original_body_sha256: str
    compacted_body_sha256: str
    protected_sentence_ids: tuple[int, ...]

    @property
    def any_change(self) -> bool:
        return self.applied and bool(self.removed_sentences)


@dataclass(frozen=True, slots=True)
class _Unit:
    """One rebuildable body piece: the exact text plus the exact trailing
    whitespace that followed it in the original body."""

    unit_id: int
    text: str
    trailing_ws: str
    is_placeholder: bool
    tier: int
    reason: str

    @property
    def words(self) -> int:
        return 0 if self.is_placeholder else len(self.text.split())


def _word_count(body: str) -> int:
    total = 0
    for line in body.splitlines():
        if _PLACEHOLDER_LINE.match(line):
            continue
        total += len(line.split())
    return total


def _split_units(body: str) -> list[tuple[str, str, bool]]:
    """(text, trailing_whitespace, is_placeholder) preserving every character."""
    out: list[tuple[str, str, bool]] = []
    # Split into blocks on blank lines, keeping the separators.
    parts = re.split(r"(\n{2,}|\n)", body)
    buf_text = ""
    for i, part in enumerate(parts):
        if i % 2 == 0:
            buf_text = part
        else:
            sep = part
            if buf_text.strip():
                if _PLACEHOLDER_LINE.match(buf_text):
                    out.append((buf_text.strip(), sep, True))
                else:
                    _emit_sentences(buf_text, sep, out)
            elif out:
                # attach a stray separator to the previous unit
                ptxt, pws, pph = out[-1]
                out[-1] = (ptxt, pws + sep, pph)
            buf_text = ""
    if buf_text.strip():
        if _PLACEHOLDER_LINE.match(buf_text):
            out.append((buf_text.strip(), "", True))
        else:
            _emit_sentences(buf_text, "", out)
    return out


def _emit_sentences(block: str, block_sep: str, out: list[tuple[str, str, bool]]) -> None:
    pieces = _SENTENCE_END.split(block)
    # pieces = [sent, ws, sent, ws, ..., sent]
    idx = 0
    while idx < len(pieces):
        sent = pieces[idx]
        ws = pieces[idx + 1] if idx + 1 < len(pieces) else ""
        idx += 2
        stripped = sent.strip()
        if not stripped:
            if out:
                out[-1] = (out[-1][0], out[-1][1] + sent + ws, out[-1][2])
            continue
        lead = sent[: len(sent) - len(sent.lstrip())]
        trail = sent[len(sent.rstrip()) :]
        if lead and out:
            out[-1] = (out[-1][0], out[-1][1] + lead, out[-1][2])
        out.append((stripped, trail + ws, False))
    if block_sep and out:
        out[-1] = (out[-1][0], out[-1][1] + block_sep, out[-1][2])


_GENERIC_HOOK_WORDS: frozenset[str] = frozenset(
    {"commercial", "hvac", "service", "services", "area", "areas", "serve", "work"}
)
_FACT_STRENGTH_RANK = {
    FactStrength.PUBLISHED_SELF_CLAIM: 3,
    FactStrength.OBSERVED_AVAILABILITY_SIGNAL: 2,
    FactStrength.OBSERVED_PUBLIC_TEXT: 1,
}


def strongest_usable_hook_words(env: SemanticEnvelope) -> tuple[set[str], bool]:
    """Content words of the strongest USABLE evidence hook. RESPONSE_COMMITMENT
    facts are excluded (the communication policy prohibits restating them), and a
    fact whose only words are ubiquitous category labels is not a hook."""
    best: tuple[int, set[str]] | None = None
    for fact in env.eligible_company_facts:
        if fact.injection_suspected or fact.category == "response_commitment":
            continue
        w = _content_words_v2(fact.sanitized_phrase)
        if not (w - _GENERIC_HOOK_WORDS):
            continue
        r = _FACT_STRENGTH_RANK.get(fact.strength, 1)
        if best is None or r > best[0]:
            best = (r, w)
    if best is None:
        return set(), False
    return best[1], True


def _strongest_fact_words(env: SemanticEnvelope) -> set[str]:
    return strongest_usable_hook_words(env)[0]


def _disclosure_word_sets(env: SemanticEnvelope) -> list[set[str]]:
    sets: list[set[str]] = []
    for disc in env.required_disclosures:
        if disc.canonical_text:
            sets.append(_content_words_v2(disc.canonical_text))
    return sets


def _tier_for(
    sentence: str,
    *,
    hook_words: set[str],
    disclosure_word_sets: list[set[str]],
    has_cta_already: bool,
) -> tuple[int, str]:
    ctype = _classify(sentence, contract="v2")
    if ctype in (ClaimType.SALUTATION, ClaimType.SIGNATURE_SLOT):
        return _TIER_NEVER, "salutation/signature"
    if ctype in (ClaimType.CTA, ClaimType.QUESTION) or sentence.strip().endswith("?"):
        return _TIER_NEVER, "call-to-action / permission question"
    if ctype == ClaimType.DISCLOSURE or _DISCLOSURE_CUES.search(sentence):
        return _TIER_NEVER, "required disclosure / simulation status"
    sw = _content_words_v2(sentence)
    for dset in disclosure_word_sets:
        if dset and len(dset & sw) / max(1, len(dset)) >= 0.6:
            return _TIER_NEVER, "required disclosure (canonical overlap)"
    if hook_words and len(hook_words & sw) >= 2 and ctype == ClaimType.FACT:
        return _TIER_EVIDENCE_HOOK, "strongest company-specific evidence hook"
    if _VALUE_CUES.search(sentence):
        return _TIER_VALUE_CORE, "core simulation / value sentence"
    if ctype in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION):
        return _TIER_SECONDARY_EVIDENCE, "secondary evidence / inference"
    return _TIER_TRANSITION, "transition / redundant framing"


def compact_candidate(
    candidate: GenerationCandidate,
    envelope: SemanticEnvelope,
    *,
    hard_word_cap: int = _HARD_BODY_WORD_CAP,
) -> tuple[GenerationCandidate, CompactionAudit]:
    """Return (possibly-compacted candidate, audit). If the body is already
    within the cap, the candidate is returned unchanged with applied=False."""

    email = candidate.artifact("first_contact_email")
    body = email.text if email else ""
    words_before = _word_count(body)
    original_sha = sha256_text(body)

    raw_units = _split_units(body)
    hook_words = _strongest_fact_words(envelope)
    dsets = _disclosure_word_sets(envelope)

    units: list[_Unit] = []
    seen_cta = False
    for i, (text, ws, is_ph) in enumerate(raw_units):
        if is_ph:
            units.append(_Unit(i, text, ws, True, _TIER_NEVER, "placeholder line"))
            continue
        tier, reason = _tier_for(
            text, hook_words=hook_words, disclosure_word_sets=dsets, has_cta_already=seen_cta
        )
        if tier == _TIER_NEVER and "call-to-action" in reason:
            seen_cta = True
        units.append(_Unit(i, text, ws, False, tier, reason))

    protected_ids = tuple(u.unit_id for u in units if u.tier == _TIER_NEVER)

    if words_before <= hard_word_cap:
        return candidate, CompactionAudit(
            version=COMPACTOR_VERSION,
            applied=False,
            reached_target=True,
            words_before=words_before,
            words_after=words_before,
            hard_word_cap=hard_word_cap,
            removed_sentences=(),
            manifest_entries_removed=(),
            original_body_sha256=original_sha,
            compacted_body_sha256=original_sha,
            protected_sentence_ids=protected_ids,
        )

    kept = {u.unit_id: u for u in units}
    removed: list[RemovedSentence] = []
    current = words_before
    for tier in (_TIER_TRANSITION, _TIER_SECONDARY_EVIDENCE, _TIER_VALUE_CORE):
        if current <= hard_word_cap:
            break
        # last-in-document first, so the opening hook survives longest.
        for u in sorted(
            (x for x in units if x.tier == tier and x.unit_id in kept),
            key=lambda x: x.unit_id,
            reverse=True,
        ):
            if current <= hard_word_cap:
                break
            del kept[u.unit_id]
            current -= u.words
            removed.append(
                RemovedSentence(
                    sentence_id=u.unit_id,
                    text=u.text,
                    tier=_TIER_NAME[tier],
                    reason=f"removed to satisfy <= {hard_word_cap}-word body cap ({u.reason})",
                    words=u.words,
                )
            )

    reached = current <= hard_word_cap
    new_body = _rebuild(units, kept)
    words_after = _word_count(new_body)

    surviving_spans = new_body
    entries_removed: list[str] = []
    kept_entries = []
    for entry in candidate.claim_manifest.entries:
        if entry.rendered_artifact == "first_contact_email":
            span = _norm(entry.rendered_span)
            if span and span not in _norm(surviving_spans):
                entries_removed.append(entry.claim_id)
                continue
        kept_entries.append(entry)

    new_artifacts = tuple(
        GeneratedArtifact("first_contact_email", new_body) if a.kind == "first_contact_email" else a
        for a in candidate.artifacts
    )
    compacted = GenerationCandidate(
        candidate_id=candidate.candidate_id,
        artifacts=new_artifacts,
        claim_manifest=ClaimManifest(
            entries=tuple(kept_entries), schema_version=candidate.claim_manifest.schema_version
        ),
        lead_source_id=candidate.lead_source_id,
        self_report=candidate.self_report,
    )
    audit = CompactionAudit(
        version=COMPACTOR_VERSION,
        applied=True,
        reached_target=reached,
        words_before=words_before,
        words_after=words_after,
        hard_word_cap=hard_word_cap,
        removed_sentences=tuple(removed),
        manifest_entries_removed=tuple(entries_removed),
        original_body_sha256=original_sha,
        compacted_body_sha256=sha256_text(new_body),
        protected_sentence_ids=protected_ids,
    )
    return compacted, audit


def _rebuild(units: list[_Unit], kept: dict[int, _Unit]) -> str:
    out: list[str] = []
    for u in units:
        if u.unit_id in kept:
            out.append(u.text)
            out.append(u.trailing_ws)
    return "".join(out).rstrip() + "\n" if out else ""


def laundered_safety_codes(
    original_codes: set[str], compacted_codes: set[str], safety_codes: frozenset[str]
) -> set[str]:
    """Zero-tolerance safety findings present in the ORIGINAL provider output but
    absent from the compacted candidate - i.e. compaction removed the offending
    sentence. These MUST remain certification-invalidating (section D2)."""
    return (original_codes & safety_codes) - compacted_codes
