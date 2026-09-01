# M2–M5 deterministic-engine correctness fixes — 2026-09-01

Owner directive (2026-09-01): fix three deterministic-engine correctness defects
surfaced by the frozen-artifact review **before** any evidence-bound Claude
communication transformer is allowed to treat M2–M5 output as ground truth. No
AI/M6.6, no M5 rewrite, no contact resolution, no delivery. **Not deployed.**

Branch `worktree-slot01-window2-execution`. Historical Slot 02–24 artifacts in RDS
were not mutated, re-scored, or re-rendered — all work is code plus one immutable
read-only evidence fixture, and a regeneration harness that runs in-memory only.

---

## 1. Exact root causes

### A. Fact-propagation loss (Slot 19 A-Plus RESPONSE_COMMITMENT)

`select_company_facts` (M2) correctly selected 4 facts for A-Plus including a
`RESPONSE_COMMITMENT` fact from the public phrase *"…flat-rate pricing, fast
response times, and technicians registered with the State of Texas."*
`DeterministicAuditComposer` (M3) correctly emitted it as an
`observed_response_commitment` finding claim (`predicate finding.response_commitment`).

It was then lost twice, silently:

* **M4** — `DeterministicDemoComposer._specification` iterated `company_facts`
  and built `service_categories` / `service_area_context` / `personalization_provenance`
  **only** for `COMMERCIAL_CONTEXT`, `INTAKE_SURFACE`, `SERVICE_AREA_CONTEXT`.
  `RESPONSE_COMMITMENT` and `SERVICE_AVAILABILITY` facts were skipped with no
  record that they had been considered. `personalization_provenance` was
  therefore always ≤ 3 entries and the demo's semantic input set silently
  excluded the strongest fact.
* **M5** — `DeterministicOutreachComposer._projections` iterated
  `_ordered_company_facts(company_facts)[:2]`. `_ordered_company_facts` sorts
  reader-specific (quotable, digit-free) facts first, so `RESPONSE_COMMITMENT`
  (rendered through a fixed frame, not quotable) always sorted last and the
  `[:2]` slice dropped it before it became a projection. It never appeared in
  `revision.projections`, the `personalization` assessment, or any artifact —
  with nothing recording the omission as intentional.

### B. SERVICE_AREA selector imprecision (Slots 19, 21)

`_bucket` classified any `fact_class == "public_service_area"` fragment
containing a loose keyword (`service area`, `serving`, `, tx`, `texas`, …) as
`SERVICE_AREA_CONTEXT`, and `_extract_phrase` then emitted whatever ≤160-char run
it landed on. There was **no rejection filter**, so:

* Slot 19 A-Plus — a duplicated navigation block matched on `", tx"` →
  *"Air Conditioning Installation Services Austin, TX Heating & Cooling Heating
  Air Conditioning View All Heating Services View All Cooling Services Handyman"*.
* Slot 21 Comfort-Air — the shortest `public_service_area` fragment was
  installation-process boilerplate →
  *"Details can vary between sites and projects, but in general, the HVAC
  installation process includes: Calculate the heating and cooling demands of
  the property"*.

Both propagated verbatim into the M2 statement, the M3 opportunity hypothesis,
the M3 `observed_service_area` finding, and the M4 `service_location` dropdown.

### C. No phrase sanitation before downstream render (Slot 18)

`_extract_phrase` did `.strip().strip("\t|-").strip()` only. A leading footnote
asterisk, a trailing navigation tail, and a mid-clause truncation all survived
into `CompanyFact.phrase`, which every downstream stage renders verbatim. Slot 18
Elite's availability fact was stored and rendered as `*About Our 24-Hour Service`
(M2 fact → M3 finding → M4 semantic input). There was also no separation between
the exact minimized substring and the rendered form.

---

## 2. Exact code / policy-version changes

| File | Change |
|---|---|
| `opportunity-core/…/domain.py` | `CompanyFact` gains `verbatim_phrase: str` (defaults to `phrase` via `__post_init__`); docstring updated. |
| `opportunity-core/…/personalization.py` | `SELECTOR_VERSION` → `commercial_hvac.company_fact_selector@3`; new `SANITATION_VERSION = commercial_hvac.phrase_sanitation@1`. New `_sanitize_phrase` (leading bullet/asterisk strip, `_NAV_TAIL` strip, dangling-connector / trailing-comma trim, first-alpha capitalisation — **character-level only**). New `_valid_service_area_phrase` + `_looks_like_nav_menu` + `_SERVICE_AREA_HEADS` / `_SERVICE_AREA_REJECT_CUES` / `_PLACE_LIST`. `select_company_facts` now: extract verbatim → sanitise → for `SERVICE_AREA_CONTEXT` skip to the next candidate if `_valid_service_area_phrase` fails (no invented geography) → store both `phrase` (sanitised) and `verbatim_phrase`. `STATEMENT_FRAME_VERSION` unchanged (`company_statement@2` — frames untouched). |
| `opportunity-local/…/persistence.py` | Additive idempotent column `opportunity_company_facts.verbatim_phrase TEXT DEFAULT ''` in `_V2_PERSONALIZATION_COLUMNS`; `CompanyFactRow.verbatim_phrase`; row mappers write/read it (read falls back to `phrase` for pre-`@3` rows). |
| `demo-core/…/domain.py` | New `SemanticFactInput(category, phrase, verbatim_phrase, evidence_id, fact_class, page_purpose, rendered_as_demo_option, retention, non_option_reason)`; `DemoSpecification.semantic_fact_inputs: tuple[SemanticFactInput, ...]`. |
| `demo-core/…/composition.py` | `COMPOSITION_POLICY_VERSION` → `demo.commercial_hvac.lead_response@3`. `_specification` now records **every** `company_fact` with valid evidence lineage as a `SemanticFactInput` — `COMMERCIAL_CONTEXT`/`INTAKE_SURFACE`/`SERVICE_AREA_CONTEXT` as `rendered_as_demo_option=True` (`DEMO_SERVICE_NEED_OPTION` / `DEMO_SERVICE_LOCATION_OPTION`), `RESPONSE_COMMITMENT` / `SERVICE_AVAILABILITY` as `rendered_as_demo_option=False`, `retention=SEMANTIC_INPUT_RETAINED`, with an explicit `_NON_OPTION_REASON`. New hard QC: `company_fact_input_dropped` (a selected fact missing from `semantic_fact_inputs`), `semantic_input_outside_manifest`, `semantic_input_missing_reason` (a non-rendered fact without a reason). |
| `demo-local/…/persistence.py` | Deserialise `semantic_fact_inputs`. |
| `outreach-core/…/domain.py` | `PersonalizationAssessment` gains `available_fact_projection_count`, `rendered_fact_projection_count`, `omitted_fact_categories`, `omission_policy_version`. |
| `outreach-core/…/composition.py` | `PROJECTION_POLICY_VERSION` → `outreach.projection@4`; `QC_POLICY_VERSION` → `outreach.qc@3`; `_FIRST_CONTACT_FACT_RENDER_LIMIT = 2`. `_projections` now emits an `EVIDENCE_DERIVED_FACT` projection for **every** ordered `company_fact` that resolves to an M3 `finding.{category}` claim (was `[:2]`). `_artifacts` renders only `all_fact_projections[:2]` in the first-contact body (unchanged QC bound 1–2). `_assess_personalization` records available vs rendered projection counts and the categories omitted from the first contact with `omission_policy_version`. New hard QC: `fact_projection_dropped` (a selected fact with an M3 finding claim but no projection), `unrecorded_fact_omission`. |
| `tests/fixtures/personalization_v2_golden.json` | Regenerated (Slot 02–04 guard). Only All Elements changed, and only for the better — a navigation tail (`… Get Free Quote Air Conditioning Heating HVAC Service Agreements …`) is now stripped from its M2 statement and M4 options. Webb Air / BNCAIR byte-identical. |

Unchanged (per directive): M1, `phase1-minimizer@2`, opportunity definition
`commercial_hvac.inbound_lead_response_qualification@1`, M2 qualification
threshold (`rules@3` / `heuristic_bands@2`), economics
(`potential_incremental_revenue@1`), FACT/INFERENCE/ESTIMATE/RECOMMENDATION/UNKNOWN
taxonomy, A-09, contact/delivery gates, AI/M6.6, M3 composition policy
(`audit.commercial_hvac.deterministic@3`).

---

## 3. Before / after M2 → M5 semantic propagation (Slot 19 A-Plus)

| Stage | BEFORE (frozen run) | AFTER (regenerated) |
|---|---|---|
| M2 CompanyFacts | intake, commercial, **response_commitment**, service_area(nav dump) | intake, commercial, **response_commitment**, service_area(`"Service Area"`) |
| M3 findings | `observed_intake_surface`, `observed_commercial_context`, **`observed_response_commitment`**, `observed_service_area` (nav dump) | same kinds; `observed_service_area` excerpt now `"Service Area"` |
| **M4 semantic input set** | provenance = 3 entries; **response_commitment absent, no record** | `semantic_fact_inputs` = **4 entries**; `response_commitment` present, `rendered_as_demo_option=False`, `retention=SEMANTIC_INPUT_RETAINED`, `non_option_reason` set. `{evidence_id of every M2 fact} == {evidence_id of every semantic input}` (QC-enforced). |
| **M5 projections** | 2 (`[:2]` slice) — response_commitment **never projected** | **4** `EVIDENCE_DERIVED_FACT` projections; `available_fact_projection_count=4`, `rendered_fact_projection_count=2`, `omitted_fact_categories=["service_area_context","response_commitment"]`, `omission_policy_version="outreach.projection@4"`. No `fact_projection_dropped`. |
| M5 first-contact email | 2 rendered facts (intake + commercial) | **byte-identical** — the fixed frame still renders the first two; the omission is now recorded, not silent |

## 4. Before / after — A-Plus and Comfort-Air outputs

**Slot 19 A-Plus** — M2 statement service-area clause
`… lists a public service area ("Air Conditioning Installation Services Austin, TX Heating & Cooling Heating Air Conditioning View All Heating Services View All Cooling Services Handyman")`
→ `… lists a public service area ("Service Area")`. M4 `service_location` dropdown
`["Air Conditioning Installation Services Austin,", "other", "unknown"]` →
`["Service Area", "other", "unknown"]`. Response-commitment fact now carried into
M4 semantic inputs + M5 projections (see §3). First-contact email unchanged.

**Slot 21 Comfort-Air** — M2 statement service-area clause
`… lists a public service area ("Details can vary between sites and projects, but in general, the HVAC installation process includes: Calculate the heating and cooling demands of the property")`
→ `… lists a public service area ("Service Area")`. M3 `observed_service_area`
excerpt likewise. M4 `service_location`
`["Details can vary between sites and projects, but in general, the HVAC installation process includes:", "other", "unknown"]`
→ `["Service Area", "other", "unknown"]`. First-contact email unchanged.

Both replacement `"Service Area"` phrases come from a genuine
`page_purpose=service_area_location` public page — no geography was invented; the
selector fell through to the next real candidate.

**Slot 18 Elite** — availability fact `*About Our 24-Hour Service` →
`phrase="About Our 24-Hour Service"`, `verbatim_phrase="*About Our 24-Hour Service"`.
The asterisk no longer appears in the M2 fact, the M3 `observed_service_availability`
finding, or the M4 semantic input; the exact minimized fragment is retained on
the CompanyFact and (once deployed) in `opportunity_company_facts.verbatim_phrase`.

**Slots 07 Polar Pros / 20 E+M** — M2 statement, M3 findings, M4 options and M5
email all byte-identical; both gain the new `semantic_fact_inputs` record (Slot 07
`service_availability` retained-not-rendered; Slot 20 all three facts rendered).

All 5 regenerated M5 packages: `state=draft_incomplete`, unresolved
`{approved_opt_out_instruction_slot, required_postal_disclosure_slot, verified_sender_slot}`,
`qc_findings=[]`, no `_SCORE_LEAK` match and no `\bhigh|low\b` token in any
external artifact.

---

## 5. Full regression result

* `pytest` (whole suite): **855 passed, 3 skipped** (PostgreSQL-only), **1 failed**.
  The single failure is
  `test_m67_sampled_slot_bundle_attestation.py::test_tfvars_binding_equals_canonical_calculator[m2_m5_runtime-…]`:
  the operator-local `terraform.tfvars` still binds the deployed Link-9 M2–M5
  bundle `bc5390bf…`; the canonical recompute of the changed source is now
  `5c4fad6ae618ac9135d602ed2100abd9ca3113884e3f9bd994ad186c0f2a384f`. This is the
  expected "not deployed yet" signal, not a regression; it turns green only on a
  deploy that updates the tfvars binding.
* New `tests/test_personalization_v2_slots07_21_regression.py` — **11 passed**:
  selector ≥ `@3`; Slot 19 response-commitment selected + reaches M4
  `semantic_fact_inputs` + M5 projection set + omission recorded; Slot 19 nav-menu
  SERVICE_AREA rejected; Slot 21 installation-boilerplate SERVICE_AREA rejected;
  service-area heads still pass (`Our Service Area`, `Service Areas`,
  `Just a Sample of Our Service Areas`, `Areas We Serve`, `Proudly Serving…`) and
  Slots 07/18/20 keep exactly one genuine SERVICE_AREA fact; Slot 18 leading
  asterisk sanitised with `verbatim_phrase` preserved and `content_sha256`
  intact; `_sanitize_phrase` character-level only (digits, `24/7`, `?` untouched);
  selector deterministic (same frozen input → identical `(category, phrase,
  verbatim_phrase)`); full pipeline byte-identical (same `content_hash` /
  `revision_hash` on repeated compose).
* `personalization_v2_golden.json` regenerated; `test_golden_renders_match`
  passes; Webb Air / BNCAIR unchanged, All Elements improved (nav tail stripped).
* `ruff check` clean on all `packages/` and the new test. `ruff format --check`
  clean on every changed file. (`tests/test_m67_tdlr_*` and
  `tests/test_m67_manual_exact_host_a09_review.py` carry 6 pre-existing ruff
  errors unrelated to this change.)
* `mypy` clean (all `src/` targets; 187 source files).
* `compileall` clean.

New immutable fixture:
`tests/fixtures/personalization_v2_slots07_21_sealed_evidence.json` — one bounded
read-only in-VPC SELECT export of the sealed Slot 07/18/19/20/21 M1 evidence
(transient `m67-phase1-research-worker:47`, 0 mutation, INACTIVE; defensive
contact scrub re-applied on export). Histograms match the consolidated execution
report exactly.

---

## 6. Deployment impact

* **Bundle digest**: `sampled_slot_m2_m5_runtime_sha256` changes
  `bc5390bfbe6024bbe44fd712cd7eca6cf260f26c87bf3df6db1b1513b18b790b` →
  `5c4fad6ae618ac9135d602ed2100abd9ca3113884e3f9bd994ad186c0f2a384f` (canonical
  `m67.sampled-slot-bundle@1` — M2–M5 source changed). `stage_coordinator`,
  `m1_runtime`, `activation_*`, `release_applicator` bindings unchanged. A future
  deploy needs a new successor image (Link 10) baking the changed
  `personalization.py` / `composition.py` files, plus the tfvars image-URI +
  bundle-digest updates.
* **PostgreSQL migration**: one additive, idempotent, state-convergent column
  `opportunity_company_facts.verbatim_phrase TEXT DEFAULT ''`. `create_all`
  makes it on a fresh DB; the `_V2_PERSONALIZATION_COLUMNS` converger adds it to
  the existing DB and backfills `''`; the row mapper reads
  `verbatim_phrase or phrase`, so pre-migration rows and pre-`@3` rows behave
  unchanged. No data rewrite, no historical re-render. (Genuinely additive, not
  a structural change — same shape as the three existing V2 personalization
  columns.)
* **Historical artifacts**: untouched. Re-running M2–M5 against a business's
  existing evidence under the new versions would produce the corrected outputs;
  Slots 07–24 are frozen/dormant and no such re-run is authorised by this work.
* **No** M1 / minimizer / opportunity-definition / M2-threshold / economics /
  truth-taxonomy / A-09 / contact-gate / delivery / AI / browser / network-policy
  / new-host change.

---

## 7. Do M4 and M5 now receive the full allowed fact set?

**Yes.** After the fix:

* M4 — `DemoSpecification.semantic_fact_inputs` contains **one entry per
  selected M2 CompanyFact** with valid evidence lineage; a QC hard failure
  (`company_fact_input_dropped`) fires if any is missing. Every entry the demo
  does not surface as a synthetic option carries an explicit `retention` and
  `non_option_reason` (QC-enforced by `semantic_input_missing_reason`). The
  demo's *rendered* options are still limited to the intake/commercial/service-area
  categories by policy — but that is now a recorded decision, not a silent loss.
* M5 — `revision.projections` contains an `EVIDENCE_DERIVED_FACT` projection for
  **every** selected M2 CompanyFact that has an M3 finding claim; a QC hard
  failure (`fact_projection_dropped`) fires if any is missing. The first-contact
  email still renders the first two (fixed frame), and
  `PersonalizationAssessment` records `available_fact_projection_count`,
  `rendered_fact_projection_count`, `omitted_fact_categories`, and
  `omission_policy_version` so the transformer can see exactly which facts are
  available-but-unrendered and why.

For **Slot 19 A-Plus specifically**: the `RESPONSE_COMMITMENT` fact
(*"…fast response times…"*) now survives into the M4 semantic input set
(`retention=SEMANTIC_INPUT_RETAINED`) and the M5 projection set
(`available_fact_projection_count=4`), recorded as an intentional first-contact
omission rather than being silently truncated.

Not deployed. No outreach rewrite. No AI/M6.6.
