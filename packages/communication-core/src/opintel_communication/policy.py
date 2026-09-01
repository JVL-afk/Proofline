"""Deterministic policy for the M6.8 communication validator.

Concept-level prohibited-claim detection: the validator must catch a *semantically
equivalent* prohibited claim even when it is phrased without the literal forbidden
words. Each concept below is a family of patterns plus the set of source kinds (if
any) that could legitimately license that meaning. A concept with an empty
``licensable_by`` set can never be licensed - it is always a hard failure when the
pattern matches an OBSERVATION / INFERENCE / RECOMMENDATION clause.

No provider, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProhibitedConcept:
    code: str
    description: str
    patterns: tuple[re.Pattern[str], ...]
    # Envelope source kinds that could license this meaning. Empty = never.
    licensable_by: frozenset[str]


def _p(*expressions: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(expr, re.IGNORECASE) for expr in expressions)


# `RESPONSE_COMMITMENT` is the only source kind that may license availability ->
# response phrasing, and even then only as the business's own self-claim.
_SRC_RESPONSE_COMMITMENT = frozenset({"RESPONSE_COMMITMENT"})


PROHIBITED_CONCEPTS: tuple[ProhibitedConcept, ...] = (
    ProhibitedConcept(
        code="MISSED_LEADS",
        description="any implication that inbound leads/inquiries are lost, missed, or unhandled",
        patterns=_p(
            r"\bslip(?:s|ping|ped)?\b[^.]{0,40}\b(?:through|cracks|by|away)\b",
            r"\bfall(?:s|ing|en)?\b[^.]{0,20}\bthrough the cracks\b",
            r"\b(?:lead|leads|inquir\w+|request\w*|call\w*|customer\w*)\b[^.]{0,40}"
            r"\b(?:get|got|getting|can get|could get|may get|might get|are)\b[^.]{0,15}"
            r"\b(?:missed|lost|overlooked|dropped|forgotten|unattended)\b",
            r"\b(?:missed|lost|dropped|overlooked|unanswered|forgotten)\b[^.]{0,20}"
            r"\b(?:lead|leads|inquir\w+|request\w*|call\w*|opportunit\w+)\b",
            r"\bgo(?:es|ing)?\b[^.]{0,15}\bunanswered\b",
            r"\bleft\b[^.]{0,15}\b(?:unanswered|unattended|hanging|waiting)\b",
            r"\bno(?:\s?one|body)\b[^.]{0,25}\b(?:responds?|gets? back|picks? up|follows? up)\b",
            r"\bnot\b[^.]{0,10}\b(?:get|getting)\b[^.]{0,10}\bback to\b",
            r"\bdrop(?:s|ping|ped)?\b[^.]{0,10}\bthe ball\b",
            r"\bfall(?:s|ing)?\b[^.]{0,10}\boff (?:the )?(?:radar|list)\b",
            r"\b(?:never|not|won'?t|can'?t)\b[^.]{0,20}"
            r"\b(?:leave|leaving|let)\b[^.]{0,25}"
            r"\b(?:waiting|unanswered|hanging|without a (?:reply|response))\b",
            r"\bnothing\b[^.]{0,15}\b(?:slips|falls|gets missed|is missed)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="RESPONSE_PERFORMANCE_ASSERTED",
        description=(
            "asserting how or how fast the business answers, returns, or handles inbound "
            "contacts as fact (RESPONSE_PERFORMANCE is an explicit UNKNOWN)"
        ),
        patterns=_p(
            r"\byou\b[^.]{0,12}"
            r"\b(?:respond|answer|reply|get back|acknowledge|return|handle|attend to)\b"
            r"[^.]{0,45}"
            r"\b(?:within|in|every|all|each|always|immediately|instantly|minutes|hours|"
            r"quickly|fast|same[-\s]?day|promptly|right away|around the clock|24/7)\b",
            r"\bevery (?:inbound |new )?(?:inquiry|request|call|lead|message)\b[^.]{0,25}"
            r"\b(?:is|are|gets?)\b[^.]{0,20}"
            r"\b(?:answered|handled|returned|acknowledged|responded to|picked up)\b",
            r"\byour (?:response|reply|callback|turnaround) (?:time|times|is|are)\b"
            r"[^.]{0,25}\b(?:fast|quick|prompt|minutes|hours|same[-\s]?day|excellent|strong)\b",
            r"\bnever leav\w+\b[^.]{0,25}\b(?:waiting|hanging|without)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="SLOW_RESPONSE",
        description="any implication that the business responds slowly, late, or inconsistently",
        patterns=_p(
            r"\bslow(?:er|ly)?\b[^.]{0,25}"
            r"\b(?:respond\w*|response|repl\w+|get\w* back|turnaround)\b",
            r"\b(?:respond\w*|response|repl\w+|callback|turnaround)\b[^.]{0,30}"
            r"\b(?:slow\w*|late\w*|lag\w*|delay\w*|suffer\w*|slip\w*|inconsist\w*|"
            r"vary|varies|drop\w*|struggl\w*)\b",
            r"\bdelay(?:s|ed|ing)?\b[^.]{0,25}\b(?:respond\w*|response|repl\w+|getting back)\b",
            r"\btake(?:s|n)?\b[^.]{0,20}\b(?:a while|too long|days|hours|longer)\b[^.]{0,20}"
            r"\b(?:respond\w*|repl\w+|get\w* back)\b",
            r"\b(?:hard|difficult|challeng\w+|tough|tricky)\b[^.]{0,40}"
            r"\b(?:respond\w*|repl\w+|keep up|stay on top|turnaround|response consistency)\b",
            r"\bresponse consistency\b",
            r"\bstruggl\w+\b[^.]{0,20}\b(?:respond\w*|keep up|turnaround)\b",
            r"\bbacklog\b",
            r"\bbehind\b[^.]{0,20}\b(?:on )?(?:inquir\w+|request\w*|repl\w+|response\w*)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="UNDERSTAFFED_OR_BUSY",
        description="any implication of understaffing or that busy periods degrade handling",
        patterns=_p(
            r"\b(?:short[-\s]?staffed|understaffed|overwhelmed|swamped|stretched thin|"
            r"spread too thin)\b",
            r"\bnot enough\b[^.]{0,15}\b(?:hands|staff|people|time)\b",
            r"\bbusy\b[^.]{0,15}\b(?:period\w*|season\w*|time\w*|day\w*|stretch\w*)\b[^.]{0,40}"
            r"\b(?:hard|difficult|challeng\w+|miss\w*|slip\w*|behind|consisten\w*|keep up)\b",
            r"\bwhen\b[^.]{0,10}\b(?:things get|you'?re|it'?s|volume)\b[^.]{0,10}"
            r"\b(?:busy|high|spike\w*|surge\w*)\b",
            r"\bduring\b[^.]{0,10}\b(?:peak|the rush|high season|a rush)\b",
            r"\bjuggl(?:e|es|ing)\b[^.]{0,25}\b(?:inquir\w+|request\w*|call\w*|lead\w*)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="NO_CRM_OR_MANUAL",
        description="any claim the business lacks a CRM / automation / system, or works manually",
        patterns=_p(
            r"\bwithout a\b[^.]{0,15}\b(?:crm|system|tool|process|way to track)\b",
            r"\bno\b[^.]{0,10}\b(?:crm|automation|central system|way to track|single view)\b",
            r"\bmanual(?:ly)?\b[^.]{0,20}\b(?:track\w*|log\w*|handle\w*|process\w*|route\w*|"
            r"enter\w*|copy\w*)\b",
            r"\b(?:spreadsheet\w*|sticky note\w*|pen and paper|whiteboard\w*)\b",
            r"\bfalls?\b[^.]{0,10}\b(?:to|on)\b[^.]{0,15}\bone person\b",
            r"\ball in\b[^.]{0,15}\b(?:someone'?s|one person'?s) head\b",
            r"\bad[-\s]?hoc\b[^.]{0,20}\b(?:process|handling|routing|intake)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="AVAILABILITY_TO_RESPONSE",
        description=(
            "a bare availability signal rendered as inbound response / acknowledgement behaviour"
        ),
        patterns=_p(
            r"\b(?:24/7|24-7|24\s?hour\w*|around the clock|round-the-clock|same[-\s]?day|"
            r"any\s?time|day or night|after[-\s]?hours)\b[^.]{0,60}"
            r"\b(?:answer\w*|respond\w*|repl\w+|get\w* back|reach\w*|someone picks? up|"
            r"call\w* back|acknowledg\w+|handled|attended|covered|monitored)\b",
            r"\b(?:answer\w*|respond\w*|repl\w+|get\w* back|reach\w*|acknowledg\w+|handled|"
            r"attended|covered)\b[^.]{0,60}"
            r"\b(?:24/7|24-7|24\s?hour\w*|around the clock|round-the-clock|any\s?time|"
            r"day or night|after[-\s]?hours)\b",
        ),
        # Never licensable-by-presence: the existence of a RESPONSE_COMMITMENT
        # fact does not license turning a *different* fact's availability
        # language into response behaviour. The response-commitment self-claim
        # ("your site highlights fast response times") does not match these
        # patterns (no 24/7 trigger) and so is unaffected.
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="QUANTIFIED_BENEFIT",
        description="any quantified or implied-quantified economic / volume benefit",
        patterns=_p(
            r"\b(?:recover\w*|save\w*|gain\w*|add\w*|capture\w*|win\w*|gener\w*|grow\w*)\b"
            r"[^.]{0,30}\d",
            r"\d+\s?(?:%|percent|x\b|leads?|inquir\w+|hours?|minutes?|days?|dollars?|"
            r"customers?|calls?|jobs?)\b",
            r"\b(?:roi|revenue|profit\w*|savings?|bottom line|payback|top line)\b"
            r"[^.]{0,25}\b(?:\d|significant\w*|meaningful\w*|substantial\w*|worth|material\w*)\b",
            r"\bpays? for itself\b",
            r"\b(?:meaningful|significant|substantial|material|real|serious)\b[^.]{0,20}"
            r"\b(?:revenue|savings?|profit\w*|lost \w+|money|value|roi|jobs?|work|growth)\b",
            r"\b(?:thousands|hundreds|tens) of (?:dollars|leads|inquiries|jobs)\b",
            r"\b(?:more|extra|additional)\b[^.]{0,15}\b(?:booked|won|closed)\b[^.]{0,15}"
            r"\b(?:jobs|work|revenue)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="PROBLEM_PRESUMPTION",
        description="presuming the business has a deficiency, gap, or loss",
        patterns=_p(
            r"\b(?:your|the)\b[^.]{0,15}\b(?:current|existing)\b[^.]{0,15}"
            r"\b(?:process|system|setup|approach|intake)\b[^.]{0,30}"
            r"\b(?:is|isn'?t|might be|may be|could be|seems?)\b[^.]{0,20}"
            r"\b(?:broken|inefficient|slow\w*|leak\w*|costing|losing|lacking|missing|weak)\b",
            r"\b(?:fix|solve|address|close|plug|stop|prevent)\b[^.]{0,15}"
            r"\b(?:the )?(?:gap|leak\w*|problem|issue|hole|bleeding)\b",
            r"\byou'?re\b[^.]{0,15}\b(?:losing|missing|leaving\b[^.]{0,10}\b(?:money|revenue|jobs))\b",
            r"\bfall(?:s|ing|en)?\b[^.]{0,10}\bshort\b",
            r"\bwhat you'?re\b[^.]{0,10}\b(?:missing|losing)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="DEMO_DEPLOYED",
        description="stating the simulation/demo is deployed, connected, live, or official",
        patterns=_p(
            r"\b(?:demo|simulation|workflow|system|tool|assistant)\b[^.]{0,25}"
            r"\b(?:is|has been|was|now)\b[^.]{0,15}"
            r"\b(?:deployed|live|connected|running|integrated|set up|active|in place|official)\b"
            r"[^.]{0,25}\b(?:for|at|with|in)\b[^.]{0,10}\b(?:you|your|the business|the company)\b",
            r"\bwe'?ve?\b[^.]{0,15}\b(?:deployed|connected|integrated|set up|built|launched)\b"
            r"[^.]{0,25}\b(?:for you|your (?:system|intake|site|business))\b",
            r"\byour\b[^.]{0,10}\b(?:new|live)\b[^.]{0,10}\b(?:intake|workflow|system|assistant)\b",
            r"\b(?:connected|linked|hooked up|integrated|wired)\b[^.]{0,20}\b(?:to|with|into)\b"
            r"[^.]{0,15}\byour\b[^.]{0,15}"
            r"\b(?:crm|scheduling|dispatch|systems?|website|phone|intake|workflow|process)\b",
            r"\bwe (?:have|'ve) (?:connected|integrated|set up|built|deployed|linked)\b"
            r"[^.]{0,25}\b(?:the |a |your )?(?:workflow|system|intake|assistant|simulation)\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="TESTIMONIAL_OR_ENDORSEMENT",
        description="customer testimonial, case study, referral, or third-party endorsement",
        patterns=_p(
            r"\b(?:other|similar|our)\b[^.]{0,20}\b(?:businesses|companies|contractors|clients|"
            r"customers)\b[^.]{0,25}\b(?:have|report\w*|saw|see\b|found|say|love\w*|switch\w*)\b",
            r"\bcase stud(?:y|ies)\b",
            r"\b(?:rave|glowing|five[-\s]?star)\b[^.]{0,10}\breview\w*\b",
            r"\btestimonial\w*\b",
            r"\bas featured in\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="URGENCY_OR_SCARCITY",
        description="urgency, scarcity, or pressure tactics",
        patterns=_p(
            r"\bact now\b",
            r"\blimited[-\s]time\b",
            r"\bdon'?t (?:wait|miss|delay|hesitate)\b",
            r"\bbefore it'?s too late\b",
            r"\brunning out\b",
            r"\bonly \d+ (?:spots?|slots?|left)\b",
            r"\b(?:today|this week) only\b",
            r"\bhurry\b",
        ),
        licensable_by=frozenset(),
    ),
    ProhibitedConcept(
        code="IDENTITY_OVERREACH",
        description=(
            "claims about size, ownership, tenure, revenue, or affiliation beyond name + hostname"
        ),
        patterns=_p(
            r"\b(?:family[-\s]?owned|locally owned|veteran[-\s]?owned|woman[-\s]?owned)\b",
            r"\b(?:since|established|founded|serving .* since)\b[^.]{0,6}\b(?:19|20)\d{2}\b",
            r"\b(?:\d+\+?\s?years?|decades?)\b[^.]{0,15}\b(?:in business|of experience|serving)\b",
            r"\b(?:largest|leading|top|#1|number one|premier|award[-\s]?winning|biggest)\b"
            r"[^.]{0,20}\b(?:contractor|company|provider|hvac|business)\b",
            r"\b(?:franchise|subsidiary|division|part of)\b",
        ),
        licensable_by=frozenset(),
    ),
)


# Place-like token detection for the unsupported-geography check. Deliberately
# small and conservative: a proper gazetteer is a later concern, but any
# city/county/state reference that is not present in a licensed SERVICE_AREA
# phrase fails closed now.
_TX_PLACE_HINTS: frozenset[str] = frozenset(
    {
        "texas",
        "tx",
        "austin",
        "houston",
        "dallas",
        "san antonio",
        "fort worth",
        "el paso",
        "arlington",
        "plano",
        "colleyville",
        "hill country",
        "central texas",
        "north texas",
        "gulf coast",
        "travis county",
        "tarrant county",
        "harris county",
        "dallas county",
        "bexar county",
        "colleyville tx",
        "marshall",
        "wascom",
        "carthage",
        "jefferson",
        "hallsville",
    }
)
_PLACE_SHAPE = re.compile(
    r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),?\s+(?:TX|Texas)\b|\b([A-Z][a-z]+\s+County)\b"
)


def place_like_tokens(text: str) -> set[str]:
    found: set[str] = set()
    low = text.lower()
    for hint in _TX_PLACE_HINTS:
        if re.search(r"\b" + re.escape(hint) + r"\b", low):
            found.add(hint)
    for match in _PLACE_SHAPE.finditer(text):
        token = (match.group(1) or match.group(2) or "").strip().lower()
        if token:
            found.add(token)
    return found


# Instruction-shaped substrings that must never appear in provider output and
# must never be reproduced from a quoted evidence phrase.
_INJECTION_MARKERS: tuple[re.Pattern[str], ...] = _p(
    r"\bignore (?:all |any |the )?(?:previous|prior|above|earlier) "
    r"(?:instructions?|prompts?|context)\b",
    r"\bdisregard (?:all |the )?(?:above|previous|prior)\b",
    r"\byou are (?:now |a )?(?:an? )?(?:assistant|ai|model|system|chatbot)\b",
    r"\bsystem\s*:\s*",
    r"\bassistant\s*:\s*",
    r"\buser\s*:\s*",
    r"\b(?:as|per) (?:instructed|directed|the instructions?)\b[^.]{0,20}"
    r"\b(?:on|in) (?:the|this) (?:page|site|website)\b",
    r"\bfollow the instructions? (?:below|above|on the page)\b",
    r"```",
    r"<\s*/?\s*(?:system|prompt|instructions?)\s*>",
    r"\[/?INST\]",
    r"\bplease output\b[^.]{0,20}\bexactly\b",
)


def injection_markers(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in _INJECTION_MARKERS:
        m = pattern.search(text)
        if m:
            hits.append(m.group(0)[:60])
    return hits


# Conditional / hedge cues used to check that licensed inferences and
# recommendations keep their conditionality.
CONDITIONAL_CUES: frozenset[str] = frozenset(
    {
        "may",
        "might",
        "could",
        "would",
        "appears",
        "appear",
        "seems",
        "seem",
        "suggests",
        "suggest",
        "possibly",
        "potentially",
        "perhaps",
        "if",
        "whether",
        "consider",
        "explore",
        "evaluate",
        "worth",
        "curious",
    }
)

# Words that turn a conditional into an assertion of certainty.
CERTAINTY_CUES: frozenset[str] = frozenset(
    {
        "will",
        "does",
        "is",
        "are",
        "definitely",
        "certainly",
        "clearly",
        "obviously",
        "proven",
        "guaranteed",
        "always",
        "every time",
        "ensures",
        "means that",
        "so you",
        "which means",
    }
)
