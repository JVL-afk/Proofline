"""M6.8-2 stub/provider simulation corpus.

Deterministic pre-written candidates that stand in for a provider's output. They
exercise the full lifecycle (parse -> validate -> rank -> persist -> review)
without any live model. Envelopes come from the M6.8-1 fixtures; the proven-good
A-Plus / Elite bodies are reused from the M6.8-1 validator suite so "valid" here
means the same thing it means there.
"""

from __future__ import annotations

from m68_fixtures import aplus_envelope, elite_envelope, em_envelope  # noqa: F401
from opintel_communication import (
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
)
from test_m68_communication_validator import (
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
    _ELITE_GOOD_BODY,
    _ELITE_GOOD_MANIFEST,
    _entry,
)

_APLUS_SUBJECT = "A note on how A-Plus describes its service response"
_ELITE_SUBJECT = "A question about commercial service-request intake"


def _mk(
    candidate_id: str,
    subject: str,
    body: str,
    manifest: tuple[ClaimManifestEntry, ...],
    lead_source_id: str | None = None,
) -> GenerationCandidate:
    return GenerationCandidate(
        candidate_id=candidate_id,
        artifacts=(
            GeneratedArtifact("subject", subject),
            GeneratedArtifact("first_contact_email", body),
        ),
        claim_manifest=ClaimManifest(entries=manifest),
        lead_source_id=lead_source_id,
    )


def _insert_before_cta(body: str, sentence: str) -> str:
    paras = body.split("\n\n")
    for i, p in enumerate(paras):
        if p.startswith("Would it be useful"):
            paras[i - 1] = paras[i - 1] + " " + sentence
            return "\n\n".join(paras)
    return body + " " + sentence


# ---------------------------------------------------------------------------
# A-Plus - one excellent, two valid-but-weaker (shared skeleton)
# ---------------------------------------------------------------------------

_APLUS_SKELETON = (
    "Hello {{functional_role_or_team}},\n\n"
    "@@OPENING@@\n\n"
    "How inbound commercial requests are actually handled is not something we can see from the "
    "outside.\n\n"
    "We prepared a short deterministic simulation, based only on approved public information, of a "
    "step that acknowledges and sorts a new service request. It is a simulation - not a system "
    "deployed, connected, official, or operated by the business. This is not a claim about how "
    "your team works today.@@HEDGE@@\n\n"
    "Would it be useful to compare that simulation with your actual intake and decide whether the "
    "idea is relevant?\n\n"
    "{{verified_sender_signature}}\n\n{{required_postal_disclosure}}\n\n"
    "{{approved_opt_out_instruction}}"
)


def _aplus_body(opening: str, hedge_tail: str) -> str:
    return _APLUS_SKELETON.replace("@@OPENING@@", opening).replace("@@HEDGE@@", hedge_tail)


_WEAKER_OPENING = (
    "Your site gives homeowners a path to ask about when to schedule an AC replacement, and it "
    "describes commercial air conditioning repairs."
)


def _weaker_manifest(opening: str) -> tuple[ClaimManifestEntry, ...]:
    return (
        _entry(
            "cm1",
            ClaimType.FACT,
            opening,
            ("f-intake", "f-commercial"),
            FactStrength.OBSERVED_PUBLIC_TEXT,
        ),
        *(e for e in _APLUS_GOOD_MANIFEST if e.claim_id != "cm1"),
    )


APLUS_EXCELLENT = _mk(
    "aplus-excellent",
    _APLUS_SUBJECT,
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
    lead_source_id="f-response",
)

APLUS_VALID_MID = _mk(
    "aplus-valid-mid",
    "A note about your commercial service pages",
    _aplus_body(_WEAKER_OPENING, " This may or may not be relevant to your situation."),
    _weaker_manifest(_WEAKER_OPENING),
    lead_source_id="f-intake",
)

APLUS_VALID_WEAK = _mk(
    "aplus-valid-weak",
    "A short note about a simulation idea",
    _aplus_body(
        _WEAKER_OPENING,
        " This may or may not be relevant, and it is only a tentative, early, fairly rough idea.",
    ),
    _weaker_manifest(_WEAKER_OPENING),
    lead_source_id="f-intake",
)

APLUS_VALID_SET = (APLUS_EXCELLENT, APLUS_VALID_MID, APLUS_VALID_WEAK)


# ---------------------------------------------------------------------------
# A-Plus - failing candidates
# ---------------------------------------------------------------------------

APLUS_STRONG_PROSE_ONE_UNSUPPORTED = _mk(
    "aplus-one-unsupported",
    _APLUS_SUBJECT,
    _APLUS_GOOD_BODY.replace(
        "How inbound commercial requests are actually handled is not something we can see from "
        "the outside.",
        "The point is to make sure you never leave a commercial request waiting.",
    ),
    _APLUS_GOOD_MANIFEST,
)

APLUS_CORRECT_BODY_UNSAFE_SUBJECT = _mk(
    "aplus-unsafe-subject",
    "Every missed call is lost revenue",
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
)

APLUS_SENSATIONAL_SUBJECT = _mk(
    "aplus-sensational-subject",
    "Act now before you lose more commercial work",
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
)

APLUS_FINANCIAL_SUBJECT = _mk(
    "aplus-financial-subject",
    "A 30 percent lift in booked commercial work",
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
)

APLUS_IMPLIED_PROBLEM_SUBJECT = _mk(
    "aplus-implied-problem-subject",
    "Fixing your slow commercial response",
    _APLUS_GOOD_BODY,
    _APLUS_GOOD_MANIFEST,
)

APLUS_UNSAFE_SUBJECT_SET = (
    APLUS_CORRECT_BODY_UNSAFE_SUBJECT,
    APLUS_SENSATIONAL_SUBJECT,
    APLUS_FINANCIAL_SUBJECT,
    APLUS_IMPLIED_PROBLEM_SUBJECT,
)

# Manifest lies about the prose: the opening FACT clause is dropped from the
# manifest entirely, so the rendered claim is undeclared.
APLUS_MANIFEST_LYING = _mk(
    "aplus-manifest-lying",
    _APLUS_SUBJECT,
    _APLUS_GOOD_BODY,
    tuple(e for e in _APLUS_GOOD_MANIFEST if e.claim_id != "cm1"),
)

APLUS_FABRICATED_NUMBER = _mk(
    "aplus-fabricated-number",
    _APLUS_SUBJECT,
    _APLUS_GOOD_BODY.replace(
        "How inbound commercial requests are actually handled is not something we can see from "
        "the outside.",
        "Most contractors in this position see about 40 commercial inquiries a month.",
    ),
    _APLUS_GOOD_MANIFEST,
)

APLUS_AVAILABILITY_TO_RESPONSE = _mk(
    "aplus-availability-to-response",
    _APLUS_SUBJECT,
    _APLUS_GOOD_BODY.replace(
        "How inbound commercial requests are actually handled is not something we can see from "
        "the outside.",
        "Your 24-hour service means every after-hours commercial call is answered right away.",
    ),
    _APLUS_GOOD_MANIFEST,
)

# Three candidates, each independently invalid.
APLUS_ALL_INVALID_SET = (
    APLUS_STRONG_PROSE_ONE_UNSUPPORTED,
    APLUS_FABRICATED_NUMBER,
    APLUS_AVAILABILITY_TO_RESPONSE,
)


# ---------------------------------------------------------------------------
# Elite - one safe, one availability->response violation
# ---------------------------------------------------------------------------

ELITE_SAFE = _mk(
    "elite-safe",
    _ELITE_SUBJECT,
    _ELITE_GOOD_BODY,
    _ELITE_GOOD_MANIFEST,
    lead_source_id="e-avail",
)

ELITE_AVAILABILITY_TO_RESPONSE = _mk(
    "elite-availability-to-response",
    _ELITE_SUBJECT,
    _ELITE_GOOD_BODY.replace(
        "what happens to one before a person takes it is not visible publicly.",
        "round-the-clock availability means every after-hours commercial call is answered "
        "immediately.",
    ),
    _ELITE_GOOD_MANIFEST,
)
