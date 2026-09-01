# ADR-0077: Evidence-Bound Communication Transformer

- **Status:** Proposed
- **Date:** 2026-09-01
- **Decision owners:** Product and architecture owner
- **Related architecture decisions:** ADR-0011 (provider-neutral contracts), ADR-0048
  (provider certification), ADR-0066 / ADR-0067 (rendered-wording / structured-CTA gap),
  ADR-0075 (Phase 1 provisioning), ADR-0076 (controlled research egress)
- **Supersedes:** None

## Context

The deterministic engine (M2–M5) produces the qualified opportunity, the licensed
`CompanyFact` set, the M3 findings, the allowed conditional inferences and
recommendations, the explicit UNKNOWNs, the economics state, and a deterministic
reference email (semantic floor + fallback). Tournament II showed that a provider can
improve *expression* — hook selection, natural combination of permitted facts, tone,
ordering — but must never be trusted with *what may be said*: byte-identical output got
no material credit, and two wording tasks carried adjudicated material defects
(ADR-0066/0067), including a rendered-wording / structured-CTA semantic-consistency gap
that the frozen evaluator could not catch.

M6.8 introduces a provider generation step between deterministic authority and human
review. The decision needed now is the contract and trust model for that step: what the
provider receives, what it is allowed to change, and how its output is independently
re-verified before any human sees it. This must be settled before implementation because
the interface shape (structured semantic envelope vs. email rewrite) and the validator's
fail-closed guarantees are expensive to retrofit.

The provider is assumed compromised: public website text is untrusted inert evidence and
may reach the provider only as quoted data fields, never as executable instructions.

## Decision drivers

- The deterministic engine stays authoritative for every claim; the provider controls
  only expression.
- The interface is a structured semantic envelope, not "rewrite this email".
- Post-generation verification is deterministic, offline, fail-closed, and independent of
  any provider-declared claim mapping.
- The validator must catch semantically equivalent prohibited claims even when the
  literal forbidden words are absent.
- Provider-neutral (ADR-0011); Anthropic Claude may be the first adapter because it
  performed best in Tournament II, but the contract must not depend on Claude-specific
  semantics.
- USD 0 for M6.8-1: no live provider call; synthetic/stub provider outputs only.
- No first real contact before an explicit M6.9 GO.

## Considered options

1. **Email rewrite.** Give the provider the deterministic email and ask for a better
   version. Rejected: the unit of trust becomes free text; the validator would have to
   reverse-engineer intent; strength and provenance are lost.
2. **Envelope in, free text out, provider-declared claim map trusted.** Rejected: a
   compromised provider can declare a false map; trusting it defeats the boundary.
3. **Envelope in, free text + structured claim manifest out, deterministic validator
   re-verifies the manifest and the prose independently.** Selected.
4. **Deterministic templating only, no provider.** Rejected for M6.8: it is the current
   fallback and does not realize the Tournament II expression gain; kept as the semantic
   floor.

## Decision

Adopt option 3. The M6.8 pipeline is:

```
deterministic semantic authority (M2–M5)
  → SemanticEnvelope (comm.semantic_envelope@1, immutable, SHA-256 content-addressed)
  → provider generation (non-authoritative; N=3 default, N=5 hard max)
      returns, per candidate: rendered subject + body (+ later variants) AND a
      structured claim_manifest (comm.claim_manifest@1)
  → deterministic fail-closed validation (comm.output_validator@1 + comm.cta_parser@1)
  → human review
  → independent contact eligibility
  → delivery (not before M6.9 GO)
```

### Semantic envelope (`comm.semantic_envelope@1`)

Immutable, content-addressed. Carries: business identity (display name + exact public
hostname only — no inferred location, size, ownership, tenure, affiliation); **every
eligible `CompanyFact`**, each with category, sanitized phrase, verbatim source phrase,
evidence/provenance IDs, content hash, selector version, `FactStrength`, per-category
usage rule, and `rendered_by_deterministic_m5` status — **including
available-but-not-rendered facts such as A-Plus's RESPONSE_COMMITMENT**; M3 findings;
allowed conditional inferences (with required qualifiers); allowed recommendations;
explicit UNKNOWNs with hard prohibitions; explicit prohibited claims; economics state
(with an external-use flag); the structured CTA (`StructuredCTA` + `CtaSemanticFrame`);
mentionable simulation/demo facts (may-say / must-not-say); required disclosures as
placeholders; deterministic reference artifacts (semantic floor + fallback); the
generation request (candidate count, length bounds, allowed artifact kinds).

### FactStrength lattice

`OBSERVED_PUBLIC_TEXT` (1), `OBSERVED_AVAILABILITY_SIGNAL` (1), `PUBLISHED_SELF_CLAIM`
(2), `LICENSED_INFERENCE` (2), `LICENSED_RECOMMENDATION` (2), `VERIFIED_FACT` (3 —
ceiling nothing in Phase 1 reaches). A rendered clause must never assert more certainty
than the strongest source it cites, and never more than its declared strength.

### Provider authority

**May:** choose the strongest permitted hook; combine permitted facts into natural
observations; vary structure, tone, ordering; generate subject and body as one validated
artifact; generate follow-up / call-opener / voicemail / LinkedIn variants when later
authorized; shorten or omit weak permitted facts.

**May not:** invent facts; infer internal processes as facts; turn an UNKNOWN into a
known; invent economics; claim missed leads; claim slow response; claim absence of
CRM / automation / staffing; strengthen SERVICE_AVAILABILITY into a RESPONSE_COMMITMENT;
claim the demo is deployed or connected; introduce unsupported customer, operational, or
financial claims; emit any number, range, percentage, or monetary benefit; leak internal
HIGH/LOW scores; personalize by business-name substitution only; carry prompt-injection-
derived instructions or source-content directives into the output.

### Structured claim manifest (`comm.claim_manifest@1`)

Every candidate returns the rendered communication **and** a manifest. Each substantive
rendered clause (FACT / INFERENCE / RECOMMENDATION / QUESTION-CTA) declares: claim ID;
claim type; rendered span; licensed semantic-envelope source ID(s); asserted strength;
qualifiers; CTA intent where applicable. **Provider-declared mappings are not
authoritative.** The deterministic validator independently verifies: every substantive
rendered clause is represented; every cited source actually licenses the meaning; the
rendered wording does not exceed the declared or source strength; no undeclared
substantive claim exists; no fact is materially altered by paraphrase; conditional
language stays conditional; UNKNOWN stays UNKNOWN.

### Deterministic output validator (`comm.output_validator@1`)

Pure, offline, fail-closed. Segments subject + body into clauses, classifies each,
licenses substantive clauses against `(fact phrases) ∪ (deterministic engine wording) ∪
(safe framing vocabulary)`, checks the FactStrength lattice, and runs a **semantic**
prohibited-concept scan (concept patterns in `policy.py`, not literal strings) so that
unsupported paraphrases fail — e.g. "leads may be slipping through the cracks", "busy
periods can make response consistency difficult", "after-hours requests can easily get
missed" all fail when unsupported even though "missed leads" / "slow response" never
appear. It also checks disclosure meaning + placeholder retention + no-person; CTA
semantics against the structured CTA (ADR-0067, via `comm.cta_parser@1`); an economics /
number scan reusing the deployed `outreach.qc@3` regexes; the name-only personalization
gate; a prompt-injection scan; structure bounds; subject independence (the subject must
independently obey the envelope and may not imply a claim stronger than the body or its
licensed sources); and the claim-manifest cross-checks above.

Fail-closed findings include at least: `undeclared_rendered_claim`,
`claim_manifest_source_mismatch`, `claim_manifest_strength_mismatch`,
`rendered_claim_exceeds_manifest`, `prohibited_claim`, `availability_upgraded_to_response`,
`unknown_asserted`, `fact_strength_escalation`, `unsupported_number`,
`financial_implication`, `score_leak`, `demo_misrepresented`, `disclosure_weakened`,
`placeholder_resolved_early`, `personalization_name_only`, `prompt_injection_echo`,
`unsupported_geography`, `cta_semantic_inconsistency`, `subject_exceeds_body_or_source`,
`material_paraphrase_alteration`, `conditional_language_lost`, `structure_violation`,
`person_or_contact_present`.

### CTA parser (`comm.cta_parser@1`)

Rule-based (closed vocabularies + regex, no ML). Classifies a rendered CTA clause
(interrogative / imperative, ask-object from a closed vocabulary, deficiency
presumption) and implements the ADR-0066/0067
`RENDERED_CTA_SEMANTIC_CONSISTENCY_GAP` invariant. Regression case id
`51ee87af09907a072639e7b6`.

### Terminal states

`GENERATED_AND_VALIDATED`, `REJECTED_BY_VALIDATOR`, `NO_CANDIDATE_PASSED`,
`COMMUNICATION_NOT_DISTINCTIVE_ENOUGH`, `PROVIDER_ERROR`, `HUMAN_REJECTED`,
`HUMAN_APPROVED`. `COMMUNICATION_NOT_DISTINCTIVE_ENOUGH` is a first-class valid non-error
terminal: no automatic regeneration, no forced human override. For a weak envelope like
E+M ("Request Service", "Commercial AC", service-area context, all generic) the system
prefers modest outreach or declares this terminal rather than inventing specificity.

### Retention

Proposed technical maximum, **not legally approved**: raw provider response and rejected
provider output encrypted, access-controlled, hard-deleted at 30 days; immutable
hash / metadata / validator result / normalized artifact / claim map / cost record
retained under the future `ai_communication_generation` policy. Encoded as
`legally_approved=False` pending privacy/legal confirmation.

### Milestone placement

New milestone **M6.8 — Evidence-Bound Communication Transformer**. The subsequent
pre-contact decision milestone is **M6.9 — Launch Review**. No first real contact before
an explicit M6.9 GO. Provider/model certification stays governed by ADR-0048 and may
reference this ADR rather than creating a separate architecture ADR.

## Consequences

### Positive

- The provider can realize the Tournament II expression gain without holding any claim
  authority.
- Every rendered claim is independently traceable to a licensed source and a strength.
- Semantic prohibited-concept detection closes the paraphrase gap the frozen Tournament
  II evaluator could not.
- The ADR-0066/0067 CTA gap has an executable regression.
- Provider-neutral; a compromised provider cannot smuggle claims past the validator.

### Negative

- Two artifacts per candidate (prose + manifest) and a large curated safe-framing
  vocabulary raise maintenance cost.
- A conservative validator will reject some genuinely safe phrasings; the safe-framing
  vocabulary and licensed-source expansion need ongoing tuning against the certification
  corpus.
- `COMMUNICATION_NOT_DISTINCTIVE_ENOUGH` will fire on thin envelopes; that is intended,
  not a defect.

### Risks and mitigations

- **Validator false-negative (unsupported claim passes).** Mitigation: fail-closed
  default, semantic concept scan, independent manifest re-verification, adversarial
  corpus (~20 categories) in CI, human review as the next gate.
- **Validator false-positive (safe claim rejected).** Mitigation: deterministic
  certification corpus of frozen good candidates that must always pass; tune vocabulary,
  never weaken a fail-closed check to make a candidate pass.
- **Prompt injection from website text.** Mitigation: website text appears only as quoted
  data fields; system/developer instructions separate source content from control
  instructions; injection scan on provider output; injection-suspected fact phrases must
  not be reproduced.
- **Provider-declared manifest gaming.** Mitigation: manifest is re-verified, never
  trusted; unsafe prose with a correct manifest still fails; a safe-looking prose with an
  unsafe manifest is flagged.

## Validation

- M6.8-1: `comm.output_validator@1` reliably distinguishes permitted from semantically
  unsupported communication on the frozen A-Plus / Elite / E+M envelopes with **no live
  provider call**, proven by the deterministic certification corpus + adversarial corpus.
- ADR-0067 regression (`51ee87af09907a072639e7b6`) is green.
- Full repository test suite green.
- M6.8-2/3 (real provider adapter, cost accounting, human-review UI) proceed only on
  explicit owner authorization.

## Revisit triggers

- The adversarial corpus finds a class of unsupported claim the validator cannot catch.
- The certification corpus cannot be made to pass without weakening a fail-closed check.
- Privacy/legal sets a retention maximum other than 30 days.
- A second provider adapter reveals a Claude-specific assumption in the contract.
- Owner authorizes M6.9 and the launch-review criteria need this ADR amended.
