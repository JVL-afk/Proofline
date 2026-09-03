"""``comm.cta_parser@1`` - deterministic, rule-based classification of a rendered
call-to-action clause, and the ADR-0067 rendered-wording / structured-CTA
semantic-consistency check.

This is the artefact ADR-0066/0067 named as missing from the frozen Tournament II
evaluator (the ``RENDERED_CTA_SEMANTIC_CONSISTENCY_GAP`` /
``BLOCKED_PENDING_VALIDATOR_FIX``). No ML, no provider - closed vocabularies and
regex only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opintel_communication.domain import (
    CTA_PARSER_V2_VERSION,
    CTA_PARSER_V3_VERSION,
    CTA_PARSER_VERSION,
    StructuredCTA,
)

# Attempt-6 preparation (owner authorization 2026-09-02, section 4): recognise the
# forensic-confirmed permitted construction
#   "would it be worth / useful / helpful comparing ... with/against your
#    actual/current/real ... process/intake/workflow?"
# as PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS, but only when the clause
# stays interrogative, non-presumptive, non-purchase, and non-meeting-demand
# (those guards are the existing branch conditions, unchanged). Consulted ONLY
# under contract="v2".
_COMPARE_PERMISSION_V2 = re.compile(
    r"\b(?:would it be (?:worth|useful|helpful)|is it worth|worth)\b[^.?!]{0,45}"
    r"\bcompar(?:e|ing)\b[^.?!]{0,45}"
    r"\b(?:with|against|to|and)\b[^.?!]{0,30}"
    r"\byour\b[^.?!]{0,25}\b(?:actual|current|real|existing|own)\b[^.?!]{0,20}"
    r"\b(?:process|intake|workflow|setup|approach|way|operations?)\b",
    re.IGNORECASE,
)

# M6.8-3 FINAL CLOSEOUT ITERATION (owner authorization 2026-09-02, section 3):
# recognise the semantically-equivalent permission surface form
#   "would / might / could it be alright / ok / acceptable / fine if I
#    shared / sent / showed / forwarded ... <the comparison/simulation/summary>
#    for your review / for your input / so you can review it?"
# as PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS - it is interrogative,
# permission-seeking, non-presumptive, non-purchase, non-meeting-demand and
# non-urgent. This does NOT broaden CTA authority: it only improves recognition
# of an already-allowed intent. It must NOT match "I'll send it over.",
# "Let's review it tomorrow.", "Can we book 30 minutes?" or "I'll show you how
# much you're losing." (none are a permission question about sharing a review
# artefact). Consulted ONLY under contract="v3".
_SHARE_PERMISSION_V3 = re.compile(
    r"\b(?:would|might|could)\s+it\s+be\s+"
    r"(?:alright|all\s+right|ok|okay|acceptable|fine|reasonable|worthwhile|helpful|useful)\b"
    r"[^.?!]{0,25}\bif\s+i\b[^.?!]{0,20}"
    r"\b(?:shared?|sent|send|show(?:ed)?|forward(?:ed)?|pass(?:ed)?\s+along|"
    r"put\s+together|walk(?:ed)?\s+you\s+through)\b[^.?!]{0,55}"
    r"\b(?:for\s+your\s+(?:review|input|consideration)|for\s+you\s+to\s+review|"
    r"so\s+you\s+can\s+(?:review|take\s+a\s+look|see)\b|to\s+review\b)",
    re.IGNORECASE,
)

_INTERROGATIVE_STARTS = (
    "would ",
    "could ",
    "is ",
    "are ",
    "do ",
    "does ",
    "did ",
    "have ",
    "has ",
    "can ",
    "may ",
    "might ",
    "how ",
    "what ",
    "when ",
    "which ",
    "who ",
    "shall ",
    "should ",
    "will ",
)
_QUESTION_FRAMES = (
    "would it be useful",
    "would it be helpful",
    "would you be open",
    "are you open to",
    "are you interested",
    "could we",
    "would you like",
    "does it make sense",
    "worth",
    "curious",
)
_IMPERATIVE_VERBS = frozenset(
    {
        "book",
        "call",
        "schedule",
        "reply",
        "respond",
        "click",
        "sign",
        "get",
        "grab",
        "claim",
        "download",
        "visit",
        "check",
        "register",
        "confirm",
        "reserve",
        "buy",
        "start",
        "join",
        "contact",
        "email",
        "text",
        "hit",
        "pick",
        "choose",
        "tap",
        "follow",
        "share",
    }
)

# Ask objects, closed vocabulary. Each maps to a family of surface cues.
_ASK_OBJECT_CUES: dict[str, tuple[str, ...]] = {
    "compare_simulation": (
        "compare",
        "compare the simulation",
        "compare that simulation",
        "look at the simulation",
        "look at a simulation",
        "review the simulation",
        "walk through the simulation",
        "see the simulation",
        "see how it compares",
        "see how that compares",
        "put it next to",
        "hold it up against",
        "decide whether the idea is relevant",
        "decide if the idea is relevant",
    ),
    "meeting_time": (
        "book a call",
        "book a time",
        "book 15",
        "book fifteen",
        "schedule a call",
        "schedule a time",
        "schedule a meeting",
        "set up a call",
        "set up a time",
        "hop on a call",
        "jump on a call",
        "quick call",
        "brief call",
        "grab time",
        "grab 15",
        "find a time",
        "calendar",
        "meeting",
        "demo call",
        "get on a call",
        "call this week",
        "call next week",
        "chat for 15",
    ),
    "purchase": (
        "sign up",
        "get started",
        "pricing",
        "get a quote from us",
        "buy",
        "purchase",
        "subscribe",
        "start a trial",
        "our plans",
        "checkout",
    ),
    "contact_details": (
        "your number",
        "your phone number",
        "your email",
        "best way to reach you",
        "best number",
        "your direct line",
        "share your",
        "send your",
    ),
    "commitment": (
        "commit to",
        "decide today",
        "agree to",
        "confirm you'll",
        "confirm that you",
        "lock in",
        "say yes",
    ),
    "confirmation_of_problem": (
        "confirm that you",
        "acknowledge you have",
        "admit",
        "agree there's a problem",
        "agree you're losing",
        "confirm you're missing",
    ),
    "discovery_question": (
        "how many",
        "how are new inquiries",
        "through which channels",
        "what response times",
        "acknowledged today",
    ),
}

_DEFICIENCY_CUES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(expr, re.IGNORECASE)
    for expr in (
        r"\bsince you'?re\b[^.?!]{0,30}\b(?:missing|losing|slow|behind|short)\b",
        r"\bto (?:stop|avoid|prevent) (?:losing|missing)\b",
        r"\bfix your\b",
        r"\bbefore (?:you|more) (?:lose|miss)\b",
        r"\bclose the gap\b",
        r"\byour (?:current|existing) (?:process|setup|system)\b[^.?!]{0,25}"
        r"\b(?:isn'?t|is not|falls short|struggles|leaks)\b",
        r"\bwhat you'?re (?:missing|losing)\b",
    )
)

_PERMISSION_CUES = (
    "would it be useful",
    "would it be helpful",
    "would you be open",
    "are you open to",
    "if it helps",
    "no pressure",
    "only if",
    "happy to",
    "if that's useful",
    "if useful",
)


@dataclass(frozen=True, slots=True)
class ParsedCta:
    is_question: bool
    is_imperative: bool
    presumes_deficiency: bool
    ask_objects: frozenset[str]
    intent_class: str
    parser_version: str = CTA_PARSER_VERSION


def _norm(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_cta(clause: str, *, contract: str = "v1") -> ParsedCta:
    text = _norm(clause)
    low = text.lower()

    is_question = (
        text.endswith("?")
        or low.startswith(_INTERROGATIVE_STARTS)
        or any(frame in low for frame in _QUESTION_FRAMES)
    )
    first_word = re.sub(r"[^a-z]", "", low.split(" ", 1)[0]) if low else ""
    is_imperative = (not is_question) and first_word in _IMPERATIVE_VERBS

    ask_objects: set[str] = set()
    for obj, cues in _ASK_OBJECT_CUES.items():
        if any(cue in low for cue in cues):
            ask_objects.add(obj)
    if contract in ("v2", "v3") and _COMPARE_PERMISSION_V2.search(text):
        ask_objects.add("compare_simulation")
    if contract == "v3" and _SHARE_PERMISSION_V3.search(text):
        # a permission question about sharing the review artefact IS the
        # already-authorized compare/permission intent (section 3).
        ask_objects.add("compare_simulation")

    presumes_deficiency = any(p.search(text) for p in _DEFICIENCY_CUES)

    # Intent classification.
    if is_imperative or {"purchase", "commitment", "meeting_time"} & ask_objects:
        intent = "DIRECT_ACTION_OR_COMMITMENT"
    elif "confirmation_of_problem" in ask_objects or presumes_deficiency:
        intent = "PRESUMES_DEFICIENCY"
    elif is_question and (
        "compare_simulation" in ask_objects
        or "discovery_question" in ask_objects
        or any(cue in low for cue in _PERMISSION_CUES)
        or "relevant" in low
        or "compare" in low
    ):
        intent = "PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS"
    elif is_question:
        intent = "OPEN_QUESTION_UNCLASSIFIED"
    else:
        intent = "STATEMENT_NOT_A_QUESTION"

    return ParsedCta(
        is_question=is_question,
        is_imperative=is_imperative,
        presumes_deficiency=presumes_deficiency,
        ask_objects=frozenset(ask_objects),
        intent_class=intent,
        parser_version=(
            CTA_PARSER_V3_VERSION
            if contract == "v3"
            else CTA_PARSER_V2_VERSION
            if contract == "v2"
            else CTA_PARSER_VERSION
        ),
    )


# Ask objects that the permission CTA must never request.
_FORBIDDEN_ASK_MAP: dict[str, str] = {
    "purchase": "a purchase",
    "meeting_time": "a meeting time",
    "contact_details": "contact details",
    "commitment": "a commitment",
    "confirmation_of_problem": "confirmation that something is wrong",
}


def cta_semantic_consistency(
    rendered_cta_clause: str, structured_cta: StructuredCTA, *, contract: str = "v1"
) -> list[str]:
    """Return a list of sub-reason strings; empty means consistent (ADR-0067)."""

    parsed = parse_cta(rendered_cta_clause, contract=contract)
    frame = structured_cta.semantic_frame
    reasons: list[str] = []

    if frame.must_remain_a_question and not parsed.is_question:
        reasons.append("rendered CTA is not a question")
    if parsed.is_imperative:
        reasons.append("rendered CTA is an imperative, not a permission question")
    if frame.must_not_presume_a_problem and parsed.presumes_deficiency:
        reasons.append("rendered CTA presumes a deficiency")

    forbidden = {v.lower() for v in frame.does_not_ask_for}
    for obj in parsed.ask_objects:
        label = _FORBIDDEN_ASK_MAP.get(obj)
        if label and label.lower() in forbidden:
            reasons.append(f"rendered CTA asks for {label}")

    if parsed.intent_class not in (
        structured_cta.cta_intent,
        "PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS",
    ):
        reasons.append(
            f"rendered CTA intent '{parsed.intent_class}' != structured intent "
            f"'{structured_cta.cta_intent}'"
        )

    # A permission CTA may fold in AT MOST the canonical discovery questions and
    # the compare-simulation ask; nothing else new.
    allowed_objects = {"compare_simulation", "discovery_question"}
    extra = parsed.ask_objects - allowed_objects
    extra_unforbidden = {o for o in extra if o not in _FORBIDDEN_ASK_MAP}
    if extra_unforbidden:
        reasons.append(f"rendered CTA introduces an unlicensed ask: {sorted(extra_unforbidden)}")

    return reasons
