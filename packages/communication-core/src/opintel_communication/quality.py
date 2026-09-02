"""``comm.communication_quality@1`` - deterministic, offline reader-facing quality
assessment for one generated candidate (owner authorization 2026-09-02,
section G).

Quality is a FIRST-CLASS requirement but strictly separate from safety: it never
rescues unsafe prose, and a WEAK candidate is technically safe but not
commercially ready. A good candidate reads like a human looked at *this*
company's public evidence, understood something relevant, and wrote a concise
note around it - not "I noticed your company provides HVAC services and thought
automation might help."

Classifications: STRONG | ACCEPTABLE | WEAK | NOT_DISTINCTIVE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opintel_communication.compactor import split_sentences, strongest_usable_hook_words
from opintel_communication.domain import (
    ClaimType,
    GenerationCandidate,
    SemanticEnvelope,
)
from opintel_communication.validator import _classify, _content_words_v2

QUALITY_ASSESSOR_VERSION = "comm.communication_quality@1"

_GENERIC_PRAISE = re.compile(
    r"\b(impressive|excellent|amazing|fantastic|outstanding|great\s+work|"
    r"love\s+what\s+you|really\s+admire|top[- ]notch|world[- ]class|"
    r"leading\s+provider|industry\s+leader)\b",
    re.IGNORECASE,
)
_FAKE_FAMILIARITY = re.compile(
    r"\b(as\s+you\s+know|i'?m\s+sure\s+you|we\s+both\s+know|like\s+you,\s+we|"
    r"i\s+know\s+how\s+busy|you'?re\s+probably\s+(?:swamped|slammed|drowning)|"
    r"i\s+get\s+it)\b",
    re.IGNORECASE,
)
_BOILERPLATE = re.compile(
    r"\b(automation\s+might\s+help|thought\s+(?:this|that|it)\s+might|"
    r"wanted\s+to\s+reach\s+out|touching\s+base|circle\s+back|"
    r"quick\s+question\s+for\s+you|hope\s+(?:this|you'?re)\s+well|"
    r"streamline\s+your\s+(?:operations|workflow|business)|"
    r"take\s+your\s+business\s+to\s+the\s+next\s+level)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    version: str
    classification: str  # STRONG | ACCEPTABLE | WEAK | NOT_DISTINCTIVE
    score: float  # 0..1, advisory
    uses_company_specific_evidence: bool
    uses_strongest_hook: bool
    boilerplate_hits: int
    generic_praise: bool
    fake_familiarity: bool
    body_word_count: int
    observations: tuple[str, ...]


def assess_quality(candidate: GenerationCandidate, envelope: SemanticEnvelope) -> QualityAssessment:
    email = candidate.artifact("first_contact_email")
    body = email.text if email else ""
    subject = candidate.artifact("subject")
    subj = subject.text if subject else ""
    wc = len(body.split())
    low = body.lower()
    obs: list[str] = []

    fact_words: set[str] = set()
    for fact in envelope.eligible_company_facts:
        if not fact.injection_suspected:
            fact_words |= _content_words_v2(fact.sanitized_phrase)
    generic = {
        "commercial",
        "hvac",
        "service",
        "services",
        "business",
        "company",
        "work",
        "system",
        "systems",
        "area",
    }
    hook_words, has_hook = strongest_usable_hook_words(envelope)

    sentences: list[str] = []
    for line in re.split(r"\n{2,}|\n", body):
        line = line.strip()
        if line and not re.match(r"^\{\{[^}]+\}\}$", line):
            sentences.extend(split_sentences(line))
    substantive = [
        c
        for c in sentences
        if _classify(c, contract="v2")
        in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
    ]
    company_specific = 0
    for c in substantive:
        w = _content_words_v2(c)
        if (w & fact_words) - generic:
            company_specific += 1
    uses_specific = company_specific >= 1
    body_words = _content_words_v2(body)
    uses_hook = has_hook and len(hook_words & body_words) >= 2

    boiler = len(_BOILERPLATE.findall(low))
    praise = bool(_GENERIC_PRAISE.search(body)) or bool(_GENERIC_PRAISE.search(subj))
    fake = bool(_FAKE_FAMILIARITY.search(body))

    if not uses_specific:
        obs.append("no substantive clause is specific to this company beyond category words")
    if has_hook and not uses_hook:
        obs.append("did not use the strongest available evidence hook")
    if boiler:
        obs.append(f"{boiler} boilerplate phrase(s) present")
    if praise:
        obs.append("contains generic praise")
    if fake:
        obs.append("contains fake familiarity")
    if wc > 130:
        obs.append(f"body is {wc} words (over the 130 hard cap)")
    elif wc < 60:
        obs.append(f"body is only {wc} words (thin)")

    # Deterministic score - advisory.
    score = 0.0
    score += 0.34 if uses_specific else 0.0
    score += 0.22 if uses_hook else (0.10 if not has_hook else 0.0)
    score += 0.14 if company_specific >= 2 else 0.0
    score += 0.10 if 60 <= wc <= 125 else 0.0
    score += 0.10 if not boiler else 0.0
    score += 0.05 if not praise else 0.0
    score += 0.05 if not fake else 0.0
    score = round(min(1.0, score), 4)

    if not envelope.has_distinctive_fact():
        cls = "NOT_DISTINCTIVE"
    elif not uses_specific or (praise and boiler):
        cls = "NOT_DISTINCTIVE" if not uses_specific else "WEAK"
    elif boiler >= 2 or (has_hook and not uses_hook) or fake or praise:
        cls = "WEAK"
    elif uses_specific and uses_hook and company_specific >= 2 and not boiler:
        cls = "STRONG"
    else:
        cls = "ACCEPTABLE"

    return QualityAssessment(
        version=QUALITY_ASSESSOR_VERSION,
        classification=cls,
        score=score,
        uses_company_specific_evidence=uses_specific,
        uses_strongest_hook=uses_hook,
        boilerplate_hits=boiler,
        generic_praise=praise,
        fake_familiarity=fake,
        body_word_count=wc,
        observations=tuple(obs),
    )
