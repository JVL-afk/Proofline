"""Deterministic normalization of a generated candidate.

Subject and body are normalized together and hashed as one unit: the candidate
is the versioned thing, not the body alone (owner refinement, 2026-09-01).
"""

from __future__ import annotations

import re

from opintel_communication.domain import GenerationCandidate, NormalizedCandidate
from opintel_communication.hashing import sha256_text

_TRAILING_WS = re.compile(r"[ \t]+(\n|$)")
_BLANK_RUN = re.compile(r"\n{3,}")


def _normalize_body(text: str) -> str:
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = _TRAILING_WS.sub(r"\1", out)
    out = _BLANK_RUN.sub("\n\n", out)
    return out.strip()


def _normalize_subject(text: str) -> str:
    return " ".join(text.split()).strip()


def normalize_candidate(candidate: GenerationCandidate) -> NormalizedCandidate:
    subj_art = candidate.artifact("subject")
    body_art = candidate.artifact("first_contact_email")
    subject = _normalize_subject(subj_art.text if subj_art else "")
    body = _normalize_body(body_art.text if body_art else "")
    word_count = len(body.split())
    # One content hash over the whole candidate: subject, body, and the
    # provider's declared manifest spans (so a changed manifest is a changed
    # candidate too).
    manifest_spans = "␟".join(
        f"{e.claim_id}␞{e.claim_type}␞{' '.join(e.rendered_span.split())}"
        for e in candidate.claim_manifest.entries
    )
    content_sha = sha256_text(
        "SUBJECT␀" + subject + "␀BODY␀" + body + "␀MANIFEST␀" + manifest_spans
    )
    return NormalizedCandidate(
        candidate_id=candidate.candidate_id,
        normalized_subject=subject,
        normalized_body=body,
        body_word_count=word_count,
        content_sha256=content_sha,
    )
