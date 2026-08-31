# M2–M5 Evidence-Preserving Personalization V2 — Design (2026-08-31)

**Status:** DESIGN ONLY. No code changed. No slot regenerated. No research run.
No truth threshold lowered. No AI introduced. No external benchmark or economic
assumption introduced.

**Design corpus / regression fixtures:** the sealed Slots 02–04 outputs and evidence
(Webb Air `15ea883c…` / webbair.com; BNCAIR `491df72b…` / www.bncair.net;
All Elements `6e8a8f8e…` / allelementshvac.com), as surfaced in
`slots02-04-m5-product-quality-review-2026-08-30.md` and the two RDS diagnostic
evidence docs.

**Problem restated:** M1 acquisition and the M2–M5 truth-calibration layers work.
But every reader-facing M2/M3/M4/M5 surface for the three companies is the same
template with a name swapped in. The pipeline captured company-specific,
commercially-relevant public FACTs (Webb Air's published response commitment;
All Elements' Marshall, TX coverage and About page; BNCAIR's "Free Estimate" CTA)
and rendered **none** of them. This design makes personalization *deterministic
from already-accepted evidence* while preserving every existing truth rule.

---

## 1. Root-cause analysis — where company-specific evidence is lost today

The loss is not in acquisition. M1 stores rich, classified evidence:
`research_evidence.fact_class` (`public_inbound_path`, `public_service_area`,
`public_about`, `public_service_description`, `public_faq`, `public_other`) and
`research_pages.page_purpose`. Slot 02 alone stored 161 evidence rows across 24
pages. The loss happens at four deterministic chokepoints downstream.

### RC-1 — M2 evidence adapter drops the classification
`packages/opportunity-local/src/opintel_opportunity_local/adapters.py::ResearchEvidenceCatalog.list_evidence`
maps `ResearchEvidence → EvidenceReference` **without copying `fact_class` or
`page_purpose`** (`EvidenceReference` in `opportunity-core/domain.py` has no such
fields). M2 rules therefore cannot see that a fragment is an inbound-path,
service-area, or about-page fact — it only sees `fragment` (raw text) plus
provenance. Every subsequent stage inherits this blindness because they consume
M3 claims, which consume M2 observations.

### RC-2 — M2 statement and observation values are hard-coded constants
`packages/opportunity-core/src/opintel_opportunity/rules.py`:
- `SAFE_STATEMENT` is a module constant. `hypothesis.statement = SAFE_STATEMENT`
  verbatim for every business. No evidence text is ever interpolated.
- `detect()` builds `Observation.value` from a fixed literal per predicate
  (`"commercial HVAC publicly described"`, `"public inbound service path
  observed"`, `"public structured intake details observed"`). The matched
  evidence row's own text is discarded — only `Observation.evidence_id` (a
  pointer) survives.
- `_matching(evidence, terms)` keeps `matches[:1]` — exactly one evidence row per
  predicate, chosen by iteration order, not by informativeness.
- The inference `statement` is also a constant.

Net: M2 emits at most 3 observations, each a constant string + one evidence
pointer, and a constant hypothesis statement. That is the entire company-specific
signal it forwards — a set of UUIDs.

### RC-3 — M3 "facts" are raw excerpt dumps, capped at the observation count
`packages/audit-core/src/opintel_audit/composition.py::DeterministicAuditComposer.compose`:
for each of the ≤3 observations it emits one `ClaimType.FACT` claim with text
`f"The captured public surface states or exposes: {item.bounded_excerpt}"`. There
is no finding taxonomy, no synthesis, no grouping by fact class, and no use of the
other ~158 evidence rows. The 11-section schema has a `facts` section but it is
populated only from observations. **Crawl quality/coverage is never rendered** —
`source.run` carries `research_run_id` but `pages_attempted` / `pages_succeeded` /
`status` are not surfaced, so All Elements' 7 failed pages are invisible in the
audit.

### RC-4 — M4 and M5 reader text is keyed by predicate, not by evidence
- M4 `demo-core/composition.py::_specification`: `questions`, `personas`,
  `SCENARIO_ID`, option value-sets (`office/retail/warehouse/...`,
  `north_texas/central_texas/...`) are all hard-coded tuples. The only
  company-specific field threaded is `source.business_name` (the
  `DemoSpecification.business_name` slot). `statements` binds only FACT claims
  whose predicate ∈ `ALLOWED_FACT_PREDICATES` (the 3 generic predicates) — so the
  "personalization" is a restatement of the same 3 generic claims.
- M5 `outreach-core/composition.py`: `FACT_WORDING` is a 3-entry dict keyed by
  predicate. `_projections` selects audit FACT claims whose predicate is in that
  dict, sorts by `FACT_PRIORITY`, and takes `[:1]` (`select_second_fact=False` by
  default). The rendered bound-claim text is `FACT_WORDING[item.predicate]` — a
  **constant**. `subject`, `CTA`, `SIMULATION_DISCLOSURE` are constants.
  Consequence: because all three companies produced the predicate
  `inbound_path.observed`, all three emails render the identical
  `content_hash 217bc695…`.

### RC-5 — no personalization gate; completeness not modelled in state
`OutreachQualityPolicy.evaluate` checks fact **count** (1–2 projections) and
lineage, but never checks that any rendered sentence is *specific to this
business*. A name substitution — or, as today, not even that — passes. Separately,
the three unresolved slots (`{{verified_sender_signature}}`,
`{{required_postal_disclosure}}`, `{{approved_opt_out_instruction}}`) do not
affect `OutreachRevisionState`; the composer emits `READY_FOR_REVIEW` and the
Phase-1 runtime review then stamps `content_approved` on a skeleton.

### RC-6 — internal score signal is computed then discarded for ranking
`score_snapshot()` produces `review_priority_band` HIGH/LOW (Webb Air HIGH; the
other two LOW) and per-factor bands. Nothing downstream *orders* review work by
it, and it is not exposed as an internal ranking artifact. It is also correctly
never leaked externally — that part must be preserved.

---

## 2. Exact proposed changes by stage

Design principle for all four: **selection and phrasing are pure functions of
already-accepted M1/M2 evidence** (fact class, page purpose, verified substrings
of minimized snapshots) plus fixed version-pinned scaffolds. No free text
generation. Identical inputs ⇒ byte-identical output.

### 2.1 M2 — `opportunity-core/rules.py`, `opportunity-local/adapters.py`

1. **Propagate classification (RC-1).** Add `fact_class: str` and
   `page_purpose: str` to `EvidenceReference`; populate them in
   `ResearchEvidenceCatalog.list_evidence` from `ResearchEvidence.fact_class` and
   the owning `ResearchPage.page_purpose`. Backfill-safe: default
   `"public_other"` / `"unclassified"`.

2. **Extract `CompanyFact` records (new type, §3.1).** After the existing
   predicate detection, run a deterministic selector (§4) over the full evidence
   tuple that produces 0–4 `CompanyFact`s in these categories:
   `INTAKE_SURFACE`, `COMMERCIAL_CONTEXT`, `RESPONSE_COMMITMENT`,
   `SERVICE_AREA_CONTEXT`. Each `CompanyFact` carries the source `evidence_id`,
   `fact_class`, `page_purpose`, `content_sha256`, `source_uri`, and a
   `phrase` (a whitespace-normalized **verbatim substring** of the evidence
   fragment, ≤160 chars, chosen by the §4 rule). No paraphrase at M2.

3. **Compose the statement deterministically.** Replace the `SAFE_STATEMENT`
   constant with `build_statement(company_facts) -> str`:
   - Fixed opening scaffold: `"{Business} publicly "` + a deterministic
     conjunction of 1–3 selected `CompanyFact.phrase` clauses (ordered by
     category priority), each rendered through a fixed per-category frame
     (e.g. `INTAKE_SURFACE → "offers {phrase}"`,
     `RESPONSE_COMMITMENT → "publishes response expectations, including
     \"{phrase}\""`).
   - Fixed hypothetical scaffold, unchanged in meaning:
     `" Given those observed public intake surfaces, a structured
     acknowledgement and qualification workflow could be evaluated. Actual
     internal response performance, routing, lead volume, conversion,
     feasibility, and economic impact remain unknown pending business
     verification."`
   - If `company_facts` is empty → fall back to today's exact `SAFE_STATEMENT`
     (guarantees non-regression for evidence-poor businesses and keeps
     `M2_INSUFFICIENT_EVIDENCE` behavior untouched).
   The number-safety constraint from M3/M5 QC is respected because the phrase is a
   verified substring of a cited evidence fragment (see §6).

4. **Statement stays explicitly hypothetical.** The word `could`, the
   `remain unknown` clause, all 7 alternative explanations, all 10 information
   gaps, all 4 UNKNOWN assumptions, and the `INSUFFICIENT_DATA` economics path are
   **unchanged**. `HypothesisStatus` logic unchanged.

5. **Score (RC-6).** Keep `score_snapshot()` factor logic. Add an internal-only
   `ReviewRankHint` (§3.4): `{priority_band, evidence_fact_count,
   distinct_fact_classes, partial_crawl}` persisted with the snapshot and used by
   the review queue ordering only. Never rendered into M3/M4/M5 external text
   (enforced by QC, §5.3).

`RULE_VERSION` / `FACTOR_CONFIG_VERSION` → `@2`. `DEFINITION_VERSION` unchanged
(the opportunity definition is the same; only rendering changes).

### 2.2 M3 — `audit-core/composition.py`

1. **Finding taxonomy replaces raw dumps as the primary `facts` content.**
   Introduce `AuditFinding` (§3.2) with `FindingKind`:
   `OBSERVED_INTAKE_SURFACE`, `OBSERVED_COMMERCIAL_CONTEXT`,
   `OBSERVED_RESPONSE_COMMITMENT`, `OBSERVED_SERVICE_AREA`,
   `WHAT_REMAINS_UNKNOWN`, `CRAWL_COVERAGE`. Each finding is one concise
   sentence built from a fixed per-kind frame + the bound `CompanyFact.phrase`
   (or, for `WHAT_REMAINS_UNKNOWN`, a fixed summary of the gap set). Every finding
   retains `evidence_ids` + `observation_ids` + `fact_class` and is emitted as a
   `ClaimType.FACT` (kinds 1–4) bound to its exact evidence, or `ClaimType.INFERENCE`
   is untouched (still the single M2 inference). The raw
   `bounded_excerpt` is kept, but demoted to a per-finding `supporting_excerpt`
   structured item, not the headline claim text.

2. **Crawl coverage is surfaced.** New structured items in a `coverage`
   sub-block of the `facts` section (or a dedicated 12th slot inside the existing
   `methodology` section to avoid changing the 11-section count — see §7):
   `pages_attempted`, `pages_succeeded`, `pages_failed`, `partial: bool`,
   `fact_class_histogram`, `captured_page_purposes`. Sourced from a new
   `source.run_stats` field on `OpportunityBundle` (§3.3). When `partial` is true
   the audit scope sentence gains a fixed clause: `"Coverage was partial
   (N of M pages captured); absence of a fact may reflect incomplete capture."`

3. **Provenance unchanged and mandatory.** `_manifest`, `evidence_fingerprints`,
   per-claim `evidence_ids`/`observation_ids`/`inference_revision_ids`, the
   `AuditQualityPolicy` (all HARD_FAILURE checks incl. `fact_without_evidence`,
   `unsupported_precision`, `content_outside_manifest`, `prohibited_hvac_claim`,
   `inference_as_fact`) stay exactly as they are. New findings pass through the
   same policy; `unsupported_precision` (every number token must be a substring of
   the cited evidence excerpt) is what keeps `RESPONSE_COMMITMENT` findings
   honest.

`COMPOSITION_POLICY_VERSION` → `audit.commercial_hvac.deterministic@2`.

### 2.3 M4 — `demo-core/composition.py`

1. **Company-configured scenario, synthetic mechanics preserved.**
   - `DemoSpecification` gains `service_categories: tuple[ServiceCategoryOption,…]`
     and `service_area_context: tuple[ServiceAreaOption,…]` (§3.5), each option
     carrying `label` + `evidence_id` + `fact_class`. Derived deterministically
     from M2 `CompanyFact`s of category `COMMERCIAL_CONTEXT` /
     `SERVICE_AREA_CONTEXT` (e.g. Webb Air → `["Light Commercial HVAC",
     "Commercial Maintenance Programs"]`; All Elements → area
     `["Marshall, TX"]`).
   - The `service_need` and `service_location` `SingleChoiceQuestion` option sets
     become `company_derived_options + ("other", "unknown")` when ≥1 evidence-bound
     option exists; otherwise the current synthetic set verbatim (fallback for
     BNCAIR-style thin evidence).
   - The scenario introduction copy references `{business_name}` + the top
     `COMMERCIAL_CONTEXT` phrase: fixed frame, bound phrase.
   - `SCENARIO_ID` unchanged (`commercial_hvac.inbound_lead_response`);
     `STATE_MACHINE_VERSION`, states, transitions, `maximum_transitions`,
     terminals **unchanged**.

2. **All safety controls preserved verbatim.** `SimulationNotice`,
   `deployment_status = "PROPOSED SIMULATION — NOT IMPLEMENTED FOR THE TARGET
   BUSINESS"`, `MockClassification.MOCK_ONLY` on every action,
   `SafetyHandoffPanel` + `SAFETY_HANDOFF_MESSAGE`, `human_handoff` state,
   `NOT_CONNECTED / MOCK_ONLY` integrations, persistent anti-impersonation
   disclosure, `collects_contact_destination = false`, synthetic personas
   ("Avery Example" / "Jordan Example"), `PERSONAL_DATA` / `ACTIVE_CONTENT`
   guards — **no change**.

3. **New QC** in `DemoQualityPolicy`: every company-derived option label must
   resolve to an `evidence_id` in `manifest.evidence_ids` whose `fact_class` is in
   the allowed set for that field; otherwise HARD_FAILURE
   `unsupported_option_personalization`. Personas must remain `synthetic=True`
   (existing check retained).

`COMPOSITION_POLICY_VERSION` → `demo.commercial_hvac.lead_response@2`;
`QUESTION_SET_VERSION` → `@2`.

### 2.4 M5 — `outreach-core/composition.py`

1. **Evidence-derived facts replace predicate-keyed constants.** New
   `ProjectionMode.EVIDENCE_DERIVED_FACT`. `_projections` selects, from the M3
   `AuditFinding` FACT claims of kinds 1–4, up to **2** (prefer 2 when ≥2 distinct
   `fact_class`), ordered by the §4 category priority. `rendered_text` is built
   from a fixed per-kind plain-English frame + a **reader-safe rendering** of the
   `CompanyFact.phrase`:
   - numerals stripped/relabelled to satisfy `FINANCIAL_EXTERNAL`
     (which rejects `\d+\s*(hours?|minutes?|leads?|%|…)`): e.g. Webb Air's
     `"Email responses are sent the next business day … after 8:00am the
     following day"` renders as `"your contact page publishes response
     expectations, including next-business-day email replies and an after-hours
     callback window"` — no digits, meaning preserved.
   - URLs, `@`, phone-shaped strings never included (`PERSONAL_CONTACT`,
     `ACTIVE_OR_EXTERNAL`).
   The projection keeps `source_claim_id`, `evidence_ids`, `observation_ids`.

2. **Plain-English CTA derived from safe gaps.** Replace the abstract constant CTA
   with a deterministic build from the two `safe_for_first_contact` gaps
   (`DEMAND_VOLUME`, `RESPONSE_PERFORMANCE` — already the first two in
   `GAP_DEFINITIONS`): fixed frame
   `"I noticed {fact_clause}. I'm curious — {gap_question_1_shortened} and
   {gap_question_2_shortened}?"`. The gap questions are existing approved strings;
   only a fixed truncation/join rule is applied. `CTA_POLICY_VERSION` → `@2`.
   The phrase "structured acknowledgement and qualification workflow" is replaced
   in reader text by `"a step that acknowledges and sorts new service requests"`
   (semantics preserved; the internal recommendation claim text is unchanged).

3. **Message answers the four required questions** by fixed structure:
   *What we noticed* (1–2 `EVIDENCE_DERIVED_FACT` segments) → *why it might be
   worth a conversation* (the `could be evaluated` conditional, qualifiers
   retained) → *what we are not claiming* (fixed:
   `"This is not a claim about how your team handles requests today — we have no
   visibility into that."`) → *smallest next step* (the derived CTA). Simulation
   disclosure retained verbatim. Body word cap 130 retained.

4. **Personalization quality gate (§5) + completeness state (§3.6).**

`TEMPLATE_VERSION` → `commercial_hvac.lead_response.outreach.v3`;
`PROJECTION_POLICY_VERSION` → `@2`; `QC_POLICY_VERSION` → `@2`.

---

## 3. New schemas / types

### 3.1 `CompanyFact` (opportunity-core)
```
FactCategory = Enum(INTAKE_SURFACE, COMMERCIAL_CONTEXT, RESPONSE_COMMITMENT, SERVICE_AREA_CONTEXT)

@dataclass(frozen=True, slots=True)
class CompanyFact:
    id: UUID
    hypothesis_id: UUID          # logical_id, revision-scoped like assumptions
    category: FactCategory
    phrase: str                  # verbatim substring of evidence fragment, <=160 chars, ws-normalized
    evidence_id: UUID
    fact_class: str              # from M1
    page_purpose: str            # from M1
    source_uri: str
    content_sha256: str
    selector_version: str        # "commercial_hvac.company_fact_selector@1"
    created_at: datetime
```
Persisted: new table `opportunity_company_facts` (keys `hypothesis_id` + `id`,
mirrors `opportunity_assumption_revisions`). `OpportunityHypothesisRevision` gains
`company_fact_ids: tuple[UUID, ...]`.

### 3.2 `AuditFinding` (audit-core)
```
FindingKind = Enum(OBSERVED_INTAKE_SURFACE, OBSERVED_COMMERCIAL_CONTEXT,
                   OBSERVED_RESPONSE_COMMITMENT, OBSERVED_SERVICE_AREA,
                   WHAT_REMAINS_UNKNOWN, CRAWL_COVERAGE)

@dataclass(frozen=True, slots=True)
class AuditFinding:
    id: UUID
    kind: FindingKind
    text: str                    # fixed frame + bound phrase / fixed gap summary
    claim_id: UUID               # the ClaimType.FACT (kinds 1-4) it renders as
    evidence_ids: tuple[UUID, ...]
    observation_ids: tuple[UUID, ...]
    fact_class: str | None
    supporting_excerpt: str      # the raw bounded excerpt (demoted from headline)
```
`AuditRevision` gains `findings: tuple[AuditFinding, ...]` and the rendered text
lists findings under "Publicly observed facts" before any excerpt block.

### 3.3 `ResearchRunStats` on the bundle
```
@dataclass(frozen=True, slots=True)
class ResearchRunStats:
    research_run_id: UUID
    status: str                  # "succeeded" | "partial" | "failed"
    pages_attempted: int
    pages_succeeded: int
    fact_class_histogram: tuple[tuple[str, int], ...]   # sorted
    captured_page_purposes: tuple[tuple[str, str], ...] # (url, purpose), sorted
```
Added to `OpportunityBundle` (read from `ResearchRepository` at M2 assembly and
carried forward to M3/M4/M5 via their existing `source` inputs). Already computed
in `production_runtime._m1`'s output payload — this promotes it to a typed field.

### 3.4 `ReviewRankHint` (opportunity-core, internal-only)
```
@dataclass(frozen=True, slots=True)
class ReviewRankHint:
    priority_band: str           # "HIGH" | "LOW"
    evidence_fact_count: int
    distinct_fact_classes: int
    partial_crawl: bool
```
Persisted alongside `opportunity_score_snapshots` (new nullable columns). Consumed
only by the review-queue ordering. `ArtifactAudience.EXTERNAL` text is QC-checked
to contain none of `{"HIGH","LOW","priority band","high confidence"}` (§5.3).

### 3.5 M4 option types (demo-core)
```
@dataclass(frozen=True, slots=True)
class ServiceCategoryOption:
    label: str; evidence_id: UUID; fact_class: str
@dataclass(frozen=True, slots=True)
class ServiceAreaOption:
    label: str; evidence_id: UUID; fact_class: str
```
`DemoSpecification` gains `service_categories`, `service_area_context`, and
`personalization_provenance: tuple[tuple[str, UUID], ...]` (label → evidence_id).

### 3.6 M5 personalization + completeness (outreach-core)
```
@dataclass(frozen=True, slots=True)
class PersonalizationAssessment:
    company_specific_segment_count: int
    distinct_fact_classes: int
    rendered_evidence_ids: tuple[UUID, ...]
    passes_gate: bool

class OutreachRevisionState(StrEnum):
    ...
    DRAFT_INCOMPLETE = "draft_incomplete"   # NEW
```
`OutreachRevision` gains `personalization: PersonalizationAssessment` and
`unresolved_slot_kinds: tuple[str, ...]`.

---

## 4. Deterministic evidence-selection rules

All ordering keys are total; ties broken by `evidence_id` (a UUID string sort) so
output is byte-stable.

### 4.1 `company_fact_selector@1` (M2)
Input: the full `tuple[EvidenceReference]` for the run (already minimized,
contact-scrubbed, snapshot-bound).

1. **Bucket** each evidence row by `FactCategory` using a fixed
   `fact_class` + keyword map:
   - `INTAKE_SURFACE` ⟸ `fact_class == "public_inbound_path"`.
   - `SERVICE_AREA_CONTEXT` ⟸ `fact_class == "public_service_area"`.
   - `RESPONSE_COMMITMENT` ⟸ fragment contains any of a fixed closed list of
     response-expectation cues (`"response"`, `"respond"`, `"business day"`,
     `"same day"`, `"within"`, `"answered"`, `"monitored"`, `"after hours"`,
     `"call you back"`, `"reply"`) **and** `fact_class` ∈
     {`public_inbound_path`,`public_faq`,`public_about`,`public_other`}.
   - `COMMERCIAL_CONTEXT` ⟸ `fact_class == "public_service_description"` and
     fragment contains `"commercial"` or `"light commercial"`.
2. **Rank within a bucket** by: (a) `page_purpose` priority
   (`contact/request > services > service_area > about > faq > homepage >
   unclassified`); (b) shorter fragment first (favors a crisp phrase);
   (c) `evidence_id`.
3. **Phrase extraction (no inference):** from the top-ranked fragment, take the
   shortest contiguous run of whitespace-delimited tokens that (i) contains the
   bucket's triggering keyword, (ii) is ≥3 and ≤22 tokens, (iii) begins/ends on a
   sentence or list boundary where one exists within ±4 tokens; else a hard
   ≤160-char window. Whitespace-normalize. The result is asserted to be a
   substring of `snapshot.minimized_text` (reuses the existing evidence
   invariant).
4. **Select** at most one `CompanyFact` per category, category order:
   `INTAKE_SURFACE, COMMERCIAL_CONTEXT, RESPONSE_COMMITMENT,
   SERVICE_AREA_CONTEXT`. Cap total at 4. A category with no qualifying evidence
   is simply absent (truthful — "public absence is never internal absence" is
   respected because absence is not rendered as a claim).

### 4.2 M2 statement composition
`build_statement@2`: `"{Business} publicly " + "; ".join(frame[cat](fact.phrase)
for fact in selected) + "." + FIXED_HYPOTHETICAL_TAIL`. If `selected == ()` →
return the exact legacy `SAFE_STATEMENT`.

### 4.3 M3 finding composition
One finding per selected `CompanyFact` (kinds 1–4), plus exactly one
`WHAT_REMAINS_UNKNOWN` (fixed frame over the existing 10 gaps: names the 4
`BLOCKS_MODEL` components) and exactly one `CRAWL_COVERAGE` finding from
`ResearchRunStats`. Order = kind enum order.

### 4.4 M5 projection selection
From M3 FACT findings kinds 1–4: take up to 2, category order as §4.1, **prefer
distinct `fact_class`** (if the top 2 share a class and a 3rd of a different class
exists, swap). Render via `EVIDENCE_DERIVED_FACT` frame + digit-safe phrase
rendering (§2.4.1). `select_second_fact` is retired — count is now
`min(2, available)`.

---

## 5. Personalization quality gate (deterministic)

Implemented as HARD_FAILURE checks in `OutreachQualityPolicy.evaluate`, plus a
state rule.

### 5.1 Company-specificity check
Compute `PersonalizationAssessment`:
- `company_specific_segment_count` = number of external `FIRST_CONTACT_EMAIL`
  segments that are `SegmentKind.BOUND_CLAIM` bound to a projection of mode
  `EVIDENCE_DERIVED_FACT` **whose `evidence_ids` are non-empty and ⊆
  `manifest.evidence_ids`** and whose `rendered_text`, with the business name and
  all fixed frame tokens removed, still contains ≥1 token that appears in the
  bound evidence fragment. (Name-only or frame-only text ⇒ not counted.)
- `distinct_fact_classes` = number of distinct `fact_class` across those
  projections.
- `passes_gate = company_specific_segment_count >= 1`.

**HARD_FAILURE `no_company_specific_evidence`** when `passes_gate` is false.
**WARNING `single_evidence_category`** (non-blocking, surfaced to review) when
`passes_gate` but `distinct_fact_classes < 2` and ≥2 categories were available in
M2 `CompanyFact`s.

### 5.2 Artifact completeness → state
If any external artifact segment of kind `*_SLOT` still contains an unresolved
`{{…}}` token, the revision state is set to **`DRAFT_INCOMPLETE`** (never
`READY_FOR_REVIEW`), and `unresolved_slot_kinds` is populated. The Phase-1 runtime
review step (`production_runtime._m5`) is updated to refuse `APPROVE` on a
`DRAFT_INCOMPLETE` revision and instead record a truthful terminal
`M5_DRAFT_INCOMPLETE` (mirrors the existing `TruthfulTerminal` pattern for
`M2_INSUFFICIENT_EVIDENCE`). This preserves the existing contact-policy separation
— nothing about who may send, or when, changes; only the label stops asserting
"approved content" for a skeleton.

### 5.3 Score-language containment
HARD_FAILURE `internal_score_language_leak` if any `ArtifactAudience.EXTERNAL`
rendered text matches `/\b(high|low)\b.*(priority|confidence|band)|priority band|
review priority/i`. (Belt-and-suspenders; the frames never emit these.)

---

## 6. Example rendered outputs under V2 (sealed evidence only)

These are hand-derived from the sealed fixtures to show shape and divergence.
Exact strings are produced by the deterministic frames at implementation time; the
**material differences** below are the acceptance target.

### 6.1 Webb Air (webbair.com) — HIGH, 24 pages, full crawl

**M2 statement (V2):**
> Webb Air publicly offers commercial and light commercial HVAC services and
> "Request Estimate / Schedule Service" request paths; its contact page also
> publishes specific response expectations for new inquiries. Given those
> observed public intake surfaces, a structured acknowledgement and qualification
> workflow could be evaluated. Actual internal response performance, routing,
> lead volume, conversion, feasibility, and economic impact remain unknown
> pending business verification.

`CompanyFact`s: INTAKE_SURFACE (`public_inbound_path`, /contact-us/),
COMMERCIAL_CONTEXT (`public_service_description`, /light-commercial-hvac/),
RESPONSE_COMMITMENT (`public_inbound_path`, /contact-us/), SERVICE_AREA_CONTEXT
(`public_service_area`, /service-areas/). Score band **HIGH** unchanged;
`ReviewRankHint{HIGH, 4, 3, false}`.

**M3 findings (V2), each evidence-bound:**
- *Observed intake surface* — the site presents public "Request Estimate" and
  "Schedule Service" request paths and a contact form. `[ev 93ce7c35…]`
- *Observed commercial-service context* — pages describe commercial and "Light
  Commercial HVAC" and "Commercial Maintenance Programs". `[ev 1a4dc5bc…]`
- *Observed response commitment* — the contact page states that emails are
  answered the next business day and after-hours requests receive a next-morning
  callback. `[ev …]` (numerals present in the excerpt: "8:00am", "10:00pm",
  "24" — all substrings of the cited fragment, so `unsupported_precision`
  passes).
- *Observed service-area context* — the site lists Fort Worth and Arlington
  service areas. `[ev …]`
- *What remains unknown* — inquiry volume, current acknowledgement performance,
  qualification and conversion rates, verified customer value.
- *Crawl coverage* — 24 of 24 pages captured (full); fact classes:
  service_description 89, other 41, inbound_path 29, service_area 2.

**M4 demo (V2):** scenario intro names Webb Air and "Light Commercial HVAC";
`service_need` options include evidence-derived
`"commercial maintenance program"`, `"light commercial repair/replacement"` +
`other/unknown`; `service_location` includes `"Fort Worth"`, `"Arlington"` +
`other/unknown`. All personas synthetic; all mock-only / safety / handoff
controls unchanged.

**M5 first-contact email (V2), reader-visible:**
> Hello {{functional_role_or_team}},
>
> I was looking at the Webb Air website. It offers commercial and light
> commercial HVAC and has "Request Estimate" and "Schedule Service" paths, and
> your contact page publishes response expectations — next-business-day email
> replies and an after-hours callback window.
>
> That is a clear public intake path, so a step that acknowledges and sorts new
> service requests might be worth looking at. This is not a claim about how your
> team handles requests today — we have no visibility into that.
>
> We built a short deterministic simulation from that public information only.
> It is a simulation—not a system deployed, connected, official, or operated by
> the business.
>
> I noticed your site offers commercial service requests and publishes response
> expectations. I'm curious — roughly how many commercial inquiries arrive in a
> typical month, and how are after-hours ones handled today?
>
> {{verified_sender_signature}}
> {{required_postal_disclosure}}
> {{approved_opt_out_instruction}}

`PersonalizationAssessment{count: 2, distinct_fact_classes: 2, passes_gate:
true}`. Slots unresolved ⇒ state **`DRAFT_INCOMPLETE`**. Subject (≤60):
`"A note about the Webb Air service-request path"`.

### 6.2 BNCAIR (www.bncair.net) — LOW, 3 pages, full crawl

**M2 statement (V2):**
> BNCAIR publicly offers commercial and residential HVAC services and a "Free
> Estimate" request path. Given that observed public intake surface, a structured
> acknowledgement and qualification workflow could be evaluated. Actual internal
> response performance, routing, lead volume, conversion, feasibility, and
> economic impact remain unknown pending business verification.

`CompanyFact`s: INTAKE_SURFACE (`public_inbound_path`, "Click Here for Free
Estimate"), COMMERCIAL_CONTEXT (`public_service_description`, "Commercial &
Residential HVAC Services"). No RESPONSE_COMMITMENT, no SERVICE_AREA_CONTEXT
(none captured — not rendered). Score **LOW**; `ReviewRankHint{LOW, 2, 2,
false}`.

**M3 findings:** intake surface ("Free Estimate"), commercial context, what
remains unknown, crawl coverage (3/3 captured; small corpus). No response /
service-area finding.

**M4 demo:** intro names BNCAIR + "Commercial & Residential HVAC"; `service_need`
includes `"free estimate request"` + synthetic fallback options;
`service_location` falls back to the **synthetic** Texas region set (no
`public_service_area` evidence). Controls unchanged.

**M5 email (reader-visible):**
> Hello {{functional_role_or_team}},
>
> I was looking at the BNCAIR website. It offers commercial and residential HVAC
> and has a "Free Estimate" request path.
>
> That is a public intake path, so a step that acknowledges and sorts new service
> requests might be worth looking at. This is not a claim about how your team
> handles requests today — we have no visibility into that.
>
> We built a short deterministic simulation from that public information only.
> It is a simulation—not a system deployed, connected, official, or operated by
> the business.
>
> I noticed your site offers a "Free Estimate" request path. I'm curious —
> roughly how many service inquiries arrive in a typical month, and how are they
> acknowledged today?
>
> {{verified_sender_signature}} {{required_postal_disclosure}}
> {{approved_opt_out_instruction}}

`PersonalizationAssessment{count: 1, distinct_fact_classes: 2, passes_gate:
true}` + **WARNING** not raised (only 2 categories available, both used).
State **`DRAFT_INCOMPLETE`**.

### 6.3 All Elements Heating & Air (allelementshvac.com) — LOW, partial crawl (13/20)

**M2 statement (V2):**
> All Elements Heating & Air publicly offers residential and commercial HVAC
> services — heating, air conditioning, mini-split, maintenance and installation
> — and lists a Marshall, Texas service area. Given those observed public
> surfaces, a structured acknowledgement and qualification workflow could be
> evaluated. Actual internal response performance, routing, lead volume,
> conversion, feasibility, and economic impact remain unknown pending business
> verification.

`CompanyFact`s: COMMERCIAL_CONTEXT (`public_service_description`,
"commercial HVAC" page), SERVICE_AREA_CONTEXT (`public_service_area`, "Marshall,
Texas" plan page). INTAKE_SURFACE thin (only 4 `public_inbound_path` rows) — a
generic "contact path" phrase if one qualifies, else absent. Score **LOW**;
`ReviewRankHint{LOW, 2-3, 2, partial_crawl: true}`.

**M3 findings:** commercial context, service area (Marshall, TX), what remains
unknown, **crawl coverage — 13 of 20 pages captured (partial); absence of a fact
may reflect incomplete capture**; fact classes service_description 84, other 24,
inbound_path 4, about 3. Scope sentence gains the partial-crawl clause.

**M4 demo:** intro names All Elements + "residential and commercial HVAC";
`service_need` includes `"heating"`, `"air conditioning"`, `"mini-split"`,
`"maintenance"`, `"installation"` (all evidence-bound) + `other/unknown`;
`service_location` includes `"Marshall, TX"` + `other/unknown`. Controls
unchanged.

**M5 email (reader-visible):**
> Hello {{functional_role_or_team}},
>
> I was looking at the All Elements Heating & Air website. It describes
> residential and commercial HVAC — heating, air conditioning, mini-split,
> maintenance and installation — and lists a Marshall, Texas service area.
>
> Given those public pages, a step that acknowledges and sorts new service
> requests might be worth looking at. This is not a claim about how your team
> handles requests today — we have no visibility into that. (Our review of your
> site was partial — some pages did not load.)
>
> We built a short deterministic simulation from that public information only.
> It is a simulation—not a system deployed, connected, official, or operated by
> the business.
>
> I noticed your site covers Marshall, TX and several HVAC service types. I'm
> curious — roughly how many service inquiries arrive in a typical month, and how
> are they acknowledged today?
>
> {{verified_sender_signature}} {{required_postal_disclosure}}
> {{approved_opt_out_instruction}}

`PersonalizationAssessment{count: 2, distinct_fact_classes: 2, passes_gate:
true}`. State **`DRAFT_INCOMPLETE`**.

### 6.4 Divergence check (acceptance target)

| Surface | Webb Air | BNCAIR | All Elements |
|---|---|---|---|
| M2 statement | 4 facts, incl. response commitment | 2 facts, no response/area | 3 facts, incl. Marshall TX, partial note absent from M2 (M2 has no coverage clause — M3 does) |
| M3 findings count | 6 | 4 | 5 (incl. partial-crawl) |
| M4 `service_need` options | evidence-derived commercial-maintenance + light-commercial | "free estimate" + synthetic fallback | heating/AC/mini-split/maintenance/installation |
| M4 `service_location` | Fort Worth, Arlington | synthetic fallback | Marshall, TX |
| M5 fact segments | 2 (inbound_path + response) | 1 (inbound_path) | 2 (service_description + service_area) |
| M5 subject | Webb Air path | BNCAIR free-estimate | All Elements coverage |
| Internal rank hint | HIGH / 4 / 3 / full | LOW / 2 / 2 / full | LOW / ~2 / 2 / partial |

All three now differ materially wherever the evidence differs; identical evidence
⇒ identical bytes (frames + verified substrings are pure functions).

---

## 7. Test plan

**Regression fixtures (no new research):** freeze the sealed M1 evidence tuples +
`ResearchRunStats` for the three businesses as JSON fixtures under
`tests/fixtures/personalization_v2/{webb_air,bncair,all_elements}.json`, sourced
only from the already-sealed rows (evidence ids, fragments, fact_class,
page_purpose, content_sha256, run stats). These are the deterministic corpus.

1. **Golden-output tests** — for each business, assert the composed M2 statement,
   M3 findings list, M4 specification hash, and M5 artifact `content_hash` equal
   checked-in golden values. Golden files are regenerated only by an explicit
   `--update-goldens` run and reviewed in the diff.
2. **Determinism** — compose twice with fresh `IdentifierFactory` seeds mapped to
   a fixed sequence; assert identical `revision_hash` / `content_hash` /
   `specification_hash`. Assert stable ordering under input-tuple shuffling.
3. **Divergence** — assert Webb Air vs BNCAIR vs All Elements produce different
   M2 statements, different M5 `content_hash`, different M4 option sets. Assert
   the §6.4 table row-by-row.
4. **Personalization gate — negative** — a fixture with all `fact_class` forced to
   `public_other` and no qualifying phrases ⇒ M2 falls back to legacy
   `SAFE_STATEMENT`, M5 QC raises `no_company_specific_evidence` HARD_FAILURE,
   state `QC_FAILED`.
5. **Completeness state** — unresolved `{{…}}` slots ⇒ state
   `DRAFT_INCOMPLETE`; `production_runtime._m5` refuses APPROVE and records
   `M5_DRAFT_INCOMPLETE`. A fixture with slots resolved ⇒ `READY_FOR_REVIEW`.
6. **Number-safety** — M3 `AuditQualityPolicy` still raises `unsupported_precision`
   if a finding frame injects a numeral absent from its evidence excerpt; M5
   `FINANCIAL_EXTERNAL` still raises `external_financial_value` if a digit-bearing
   phrase (`"within 2 hours"`) reaches an external artifact — assert the
   digit-safe renderer prevents it for the Webb Air response-commitment fact.
7. **Truth-rule preservation** — assert the 7 alternatives, 10 gaps, 4 UNKNOWN
   assumptions, `INSUFFICIENT_DATA` economics, `could` / `remain unknown`
   qualifiers, simulation disclosure, safety-handoff wording, MOCK_ONLY actions,
   synthetic personas are byte-identical to the legacy fixtures.
8. **Score containment** — assert no external artifact text matches the §5.3
   regex for any fixture; assert `ReviewRankHint` is absent from every
   `ArtifactAudience.EXTERNAL` serialization.
9. **Existing suites** — the full `audit-core`, `demo-core`, `outreach-core`,
   `opportunity-core` unit suites must pass unchanged except for the deliberately
   updated golden strings; `test_m65_activation_readiness.py` reviewed for
   constant references.

**Not tested against live sites.** No fixture is derived from anything other than
the three sealed slots.

---

## 8. Migration / backward-compatibility impact

- **DB:** additive only. New table `opportunity_company_facts`; new nullable
  columns on `opportunity_hypothesis_revisions` (`company_fact_ids_json`),
  `opportunity_score_snapshots` (`review_rank_hint_json`), `audit_revisions`
  (`findings_json`), `demo_revisions.data_json` (`service_categories`,
  `service_area_context`, `personalization_provenance` inside the existing blob),
  `outreach_package_revisions.data_json` (`personalization`,
  `unresolved_slot_kinds`). No column drops, no type changes. Slots 02–04 rows are
  **not touched** — they remain valid under their pinned `@1` policy versions.
- **Policy-version pinning:** every composer records its
  `composition_policy_version` / `template_version` in the manifest and QC checks
  `configuration_drift`. Old artifacts validate under `@1`; new artifacts under
  `@2` / `v3`. A reader that needs to compare must branch on the recorded version
  — no silent reinterpretation of sealed output.
- **`EchoMockReasoner` / port contracts:** `EvidenceReference` gains two fields
  with defaults ⇒ existing constructors keep working; `ResearchEvidenceCatalog`
  is the only populated path.
- **Coordinator binding hashes (important):** M2–M5 composition code lives inside
  the research/intelligence images. The tfvars declared attestations
  `stage_coordinator_sha256` and `m2_m5_runtime_sha256` (and the single-file
  hashes if `rules.py` / composition files are counted) **change** when this ships.
  That means: new image chain link (link 8), new
  `slots…-successor-image-link8-deployment` evidence doc, tfvars bump, terraform
  plan → apply, and a **new execution authorization** before any real slot runs
  under V2. This remediation is code + deployment-plumbing; it is not a hot
  change. Slots 02–04 stay frozen on link 7.
- **Runtime terminals:** `M5_DRAFT_INCOMPLETE` is a new truthful terminal string;
  the coordinator's terminal-stage handling already hashes an arbitrary terminal
  value, so no schema change — but the Phase-1 report taxonomy gains one row.
- **No behavior change** to activation, authority materialization, kill switch,
  contact-phase gate, minimization, or provenance.

---

## 9. Future mechanism for economics (proposed, NOT in this remediation)

The economics weakness (`insufficient_data`, null values on all three) is
**correct** and must not be solved by inventing ROI. A separate future design
(own authorization) could add:

- An owner-approved static `BenchmarkTable` artifact: coarse, source-cited ranges
  keyed by a small set of public shape signals (e.g. "single-location commercial
  HVAC contractor"). Version-pinned, hash-sealed, no per-business tailoring.
- A new `EconomicStatus.ILLUSTRATIVE_BENCHMARK` distinct from `HYPOTHETICAL` and
  `CALCULATED`, rendered only in `INTERNAL_ECONOMIC_CONTEXT` (never external),
  always labelled "illustrative range from published benchmarks — not specific to
  this business, not a claim about its results", with the benchmark row's
  citation in the manifest.
- M2 assumptions stay `UNKNOWN`; the benchmark is a *separate* clearly-typed
  object, never written into an assumption's `decimal_value`.

Explicitly out of scope here. Listed so the personalization work does not
accidentally foreclose it.

---

## 10. Narrow implementation authorization requested

Design is complete. To implement, the following (and nothing broader) is
requested:

1. **Code changes, worktree + local commits only**, in exactly these packages:
   `opportunity-core` (`domain.py`, `rules.py`, `economics.py` untouched),
   `opportunity-local` (`adapters.py`), `audit-core` (`domain.py`,
   `composition.py`), `demo-core` (`domain.py`, `composition.py`, `policy.py`
   untouched), `outreach-core` (`domain.py`, `composition.py`), and the M2-bundle
   assembly + `production_runtime._m5` guard in `workers/intelligence`.
2. **One additive DB migration** (new table + nullable columns as §8).
3. **Regression fixtures** built **only** from the already-sealed Slots 02–04
   evidence; golden output files committed.
4. **No** truth-threshold change, **no** new opportunity definition, **no** AI /
   model / prompt / network call, **no** external benchmark or economic
   assumption, **no** change to activation / authority / kill-switch / contact
   gate / minimization / provenance.
5. **No** regeneration of Slots 02–04 and **no** new real-company research. V2 is
   exercised only against the frozen fixtures until a separate deployment +
   execution authorization is granted.
6. When V2 is ready to run for real: a **separate** authorization covering the
   link-8 image build, deployment-evidence doc, tfvars binding-hash bump,
   terraform plan→apply, and slot execution — not included in this request.
7. Do not start Slots 07–24.

---

## Constraints honored by this document

Design only — no code modified, no slot regenerated, no research run, no threshold
lowered, no AI, no external benchmark or economic assumption introduced. Fixtures
and examples derive solely from the sealed Slots 02–04 evidence.
