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


def _norm(text: str) -> str:
    return " ".join(text.split()).strip()


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
# Any clause that makes an assertion whose grammatical subject is the business.
_BUSINESS_ASSERTION = re.compile(
    r"^(?:your\s+\w+|you\s+\w+|that\s+is\b|those\s+\w+|it\s+(?:means|is|routes|uses|shows))"
    r"|(?:\bmeans (?:that )?you\b|\bso you\b|\bwhich means\b|\byou never\b|\byou always\b)",
    re.IGNORECASE,
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
    r"not a claim about how your team|we have no visibility|synthetic)\b",
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


def _classify(clause: str) -> ClaimType:
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
    if _TRANSITION_CUES.search(clause):
        return ClaimType.TRANSITION
    return ClaimType.NON_SUBSTANTIVE


# --------------------------------------------------------------------------
# Licensed vocabulary: the exact wording the deterministic engine itself uses.
# A rewrite that stays within (fact phrases) plus (this framing vocabulary) is
# not inventing a claim.
# --------------------------------------------------------------------------


def _licensed_framing_vocab(env: SemanticEnvelope) -> set[str]:
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

    def validate(
        self, envelope: SemanticEnvelope, candidate: GenerationCandidate
    ) -> ValidationResult:
        findings: list[ValidatorFinding] = []
        framing = _licensed_framing_vocab(envelope) | _SAFE_FRAMING_VOCAB
        fact_words = _fact_vocab(envelope)
        allowed_vocab = framing | fact_words

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
            cta_clauses = [c for c in clauses if _classify(c) == ClaimType.CTA]
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
        if (
            not _DISCLOSURE_CUES.search(body)
            or not re.search(r"\bsimulation\b", body, re.IGNORECASE)
            or not re.search(
                r"\bnot\b[^.]{0,40}\b(deployed|connected|official|operated|a system)\b",
                body,
                re.IGNORECASE,
            )
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
            if _classify(c) not in (ClaimType.SALUTATION, ClaimType.SIGNATURE_SLOT)
        ]
        for clause in prose_clauses:
            preserves_unknown = bool(_PRESERVES_UNKNOWN.search(clause))
            for concept in PROHIBITED_CONCEPTS:
                if not any(p.search(clause) for p in concept.patterns):
                    continue
                if preserves_unknown and concept.code in _UNKNOWN_SUPPRESSIBLE_CONCEPTS:
                    continue
                if concept.licensable_by and (concept.licensable_by & licensed_source_kinds):
                    # e.g. AVAILABILITY_TO_RESPONSE licensed by a RESPONSE_COMMITMENT
                    # fact - still only as a self-claim, checked by strength below.
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
        for clause in clauses:
            if _classify(clause) != ClaimType.CTA:
                continue
            for reason in cta_semantic_consistency(clause, envelope.structured_cta):
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
            if _content_words(phrase) and _content_words(phrase) <= _content_words(body):
                findings.append(
                    _f(
                        "demo_misrepresented",
                        f"asserts a prohibited demo statement: {phrase!r}",
                        "first_contact_email",
                    )
                )

        # 12. licensing every substantive clause against the envelope vocab
        substantive = [
            c
            for c in clauses
            if _classify(c) in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
        ]
        company_specific_clauses = 0
        for clause in substantive:
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
            if words & fact_words:
                company_specific_clauses += 1
            # conditional preservation for inference/recommendation clauses
            if _classify(clause) in (ClaimType.INFERENCE, ClaimType.RECOMMENDATION):
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
        if company_specific_clauses == 0:
            findings.append(
                _f(
                    "no_company_specific_evidence",
                    "no substantive clause is company-specific beyond the display name",
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

        # 15. claim-manifest cross-checks (owner refinement) -------
        findings.extend(
            self._check_manifest(
                envelope, candidate, clauses, manifest_by_span, allowed_vocab, licensed_source_kinds
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

        passed = not findings
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
        substantive = [
            c
            for c in clauses
            if _classify(c) in (ClaimType.FACT, ClaimType.INFERENCE, ClaimType.RECOMMENDATION)
        ]

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

        for entry in cand.claim_manifest.entries:
            if entry.claim_type not in (
                ClaimType.FACT,
                ClaimType.INFERENCE,
                ClaimType.RECOMMENDATION,
                ClaimType.CTA,
            ):
                continue
            span = _norm(entry.rendered_span)
            span_words = _content_words(span)

            # 15b. declared sources exist
            resolved = [env.source_by_id(sid) for sid in entry.licensed_source_ids]
            if any(r is None for r in resolved) or not entry.licensed_source_ids:
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
            # A CTA entry's meaning is checked by cta_semantic_consistency, not by
            # source-word overlap - skip 15c/15e for it.
            if entry.claim_type != ClaimType.CTA:
                span_specific = span_words - allowed_vocab - source_words
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

            # 15e. rendered wording does not exceed the declared strength
            detected = _detected_strength(span)
            declared = entry.asserted_strength or (
                max(source_strengths, key=lambda s: _rank(s)) if source_strengths else None
            )
            if declared is not None and not strength_at_most(detected, declared):
                out.append(
                    _f(
                        "rendered_claim_exceeds_manifest",
                        f"claim {entry.claim_id}: wording sounds like "
                        f"{detected}, declared {declared}",
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
        body_strength = _detected_strength(body)
        subj_strength = _detected_strength(subj)
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


def _detected_strength(text: str) -> FactStrength:
    if _CERTAINTY_STRENGTH.search(text):
        return FactStrength.VERIFIED_FACT
    if _SELF_CLAIM_STRENGTH.search(text):
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
) -> ValidatorFinding:
    return ValidatorFinding(
        code=code,
        message=message,
        artifact_kind=artifact_kind,
        span=span[:200] if span else None,
        concept=concept,
        claim_id=claim_id,
    )
