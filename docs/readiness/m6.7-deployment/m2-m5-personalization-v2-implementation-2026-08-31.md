# M2–M5 Evidence-Preserving Personalization V2 — Implementation Report (2026-08-31)

Implements the design approved in commit `d2d7555`, with the refinement that
**evidence selection and reader-facing rendering are separate**: a `CompanyFact`
carries an exact minimized source fragment for provenance, and every reader-facing
phrase is inserted through fixed deterministic semantic frames that may normalise
grammatical form but may not add a claim, strengthen certainty, infer internal
behaviour, invent economics, or combine facts in a way that changes their meaning.

Branch `worktree-slot01-window2-execution` (local only — no remote). Not deployed.

---

## 1. Implementation commits

| Commit | Scope |
|---|---|
| `67ea321` | **M2** — `EvidenceReference` carries `fact_class` + `page_purpose`; `CompanyFact` / `FactCategory` / `ReviewRankHint` / `ResearchRunStats` types; `personalization.py` (`company_fact_selector@1`, semantic frames, statement builder with exact legacy fallback, internal-only `ReviewRankHint`); `rules@2`; persistence (table + 3 columns + migration) |
| `f5f0f7b` | **M3** — `AuditFinding` / `FindingKind` taxonomy; concise evidence-linked finding claims + crawl-coverage rendering (scope clause, `facts` coverage block, `CRAWL_COVERAGE` finding); `audit.commercial_hvac.deterministic@2`; `audit_revisions.findings_json` + migration |
| `06695ab` | **M4** — `ServiceCategoryOption` / `ServiceAreaOption`; evidence-derived `service_need` / `service_location` option sets with synthetic fallback; `personalization_provenance`; new QC `unsupported_option_personalization`; `demo.commercial_hvac.lead_response@2` / `questions@2` |
| `e081ce4` | **M5** — `ProjectionMode.EVIDENCE_DERIVED_FACT`; digit-safe reader frames; plain-English recommendation + CTA anchored on the safe demand-volume / response-performance questions; "what we are not claiming" line; `PersonalizationAssessment` + gate; `internal_score_language_leak` QC; `OutreachRevisionState.DRAFT_INCOMPLETE`; `outreach.v3` / `projection@2` / `permission_cta@2` / `qc@2`; shared M2 test fixture now classifies `fact_class` + `page_purpose` |
| `374967d` | Reconcile `DRAFT_INCOMPLETE` with downstream contact-policy separation |
| `1213efd` | Deterministic regression fixtures + committed golden renders; `company_fact_sort_key` canonical ordering |
| `fb4ebd1` | Cleaner phrase trimming for truncated reader quotes |

`workers/intelligence/production_runtime.py` has **no net change** — the M2–M5
dispatch flow is untouched; only the composition libraries it bundles changed.

---

## 2. Schema / migration result

Additive only. Verified by the full SQLite suite (a fresh database per test, so
`create_all` exercises every new column/table) and by the state-convergent
`ALTER TABLE … ADD COLUMN` paths, which are idempotent (guarded by a column
-presence inspection, backfill touches only NULL rows).

| DB object | Kind | Table | Migration |
|---|---|---|---|
| `opportunity_company_facts` | **new table** | — | `create_all` (fresh) |
| `opportunity_analysis_runs.run_stats_json` | new nullable column | existing | `_V2_PERSONALIZATION_COLUMNS` state-convergent ALTER, advisory-lock 670002 on PG |
| `opportunity_hypothesis_revisions.company_fact_ids_json` | new nullable column | existing | same |
| `opportunity_score_snapshots.review_rank_hint_json` | new nullable column | existing | same |
| `audit_revisions.findings_json` | new nullable column | existing | idempotent ALTER in `initialize()`, advisory-lock 670003 on PG |
| `demo_revisions.data_json` (+`service_categories`, `service_area_context`, `personalization_provenance`) | JSON blob keys | existing | none — blob |
| `outreach_package_revisions.data_json` (+`personalization`, `unresolved_slot_kinds`) | JSON blob keys | existing | none — blob |

No column drops, no type changes, no data rewrites. **The frozen Slot 02–04 rows
are not touched** and remain valid under their pinned `@1` policy versions.
PostgreSQL was not exercised (`OPINTEL_TEST_POSTGRES_URL` unset → 3 PG parity
tests skipped); the ALTER path mirrors the existing
`research_local::_converge_v2_bounded_site_crawl_schema` precedent.

---

## 3. Version changes

| Component | Before | After |
|---|---|---|
| M2 rules | `commercial_hvac.lead_response.rules@1` | `…rules@2` |
| M2 score config | `commercial_hvac.lead_response.heuristic_bands@1` | `…heuristic_bands@2` |
| M2 selector (new) | — | `commercial_hvac.company_fact_selector@1` |
| M3 composition policy | `audit.commercial_hvac.deterministic@1` | `…deterministic@2` |
| M4 composition policy | `demo.commercial_hvac.lead_response@1` | `…lead_response@2` |
| M4 question set | `demo.commercial_hvac.questions@1` | `…questions@2` |
| M5 template | `commercial_hvac.lead_response.outreach.v2` | `…outreach.v3` |
| M5 projection policy | `outreach.projection@1` | `outreach.projection@2` |
| M5 CTA policy | `outreach.permission_cta@1` | `outreach.permission_cta@2` |
| M5 QC policy | `outreach.qc@1` | `outreach.qc@2` |

Unchanged: `commercial_hvac.inbound_lead_response_qualification@1` (opportunity
definition), `commercial_hvac.lead_response.potential_incremental_revenue@1`
(economics formula), `audit.schema@1`, `audit.qc@1`, `demo.schema@1`,
`demo.qc@1`, `demo.lead_response.machine@1`, `outreach.schema@1`,
`outreach.roles.commercial_hvac@1`, all M1 versions.

A reader comparing sealed Slot 02–04 output (all `@1`/`v2`) to a V2 run must
branch on the recorded policy version — no silent reinterpretation.

---

## 4. Golden before / after renders

**Before** (sealed Slots 02–04 — byte-identical across all three companies,
`slots02-04-m5-product-quality-review-2026-08-30.md`):

- **M2 statement:** *"Public pages show that the business invites commercial HVAC
  inquiries through observed digital channels. A structured acknowledgement and
  qualification workflow could be evaluated for those channels. Current response
  performance, internal routing, lead volume, conversion, feasibility, and
  economic impact remain unknown pending business verification."* — identical for
  Webb Air / BNCAIR / All Elements.
- **M3 facts:** 3 `[FACT]` claims per company, each a raw minimized-text dump; no
  finding taxonomy; no crawl-coverage rendering.
- **M4 `service_need` / `service_location`:** fixed synthetic sets
  (`repair/maintenance/replacement_quote/unknown`,
  `north_texas/central_texas/gulf_coast/other/unknown`) for all three.
- **M5 subject:** "A question about commercial service-request intake" (all three).
- **M5 first-contact email** (`content_hash 217bc695…`, identical all three):
  > Hello {{functional_role_or_team}}, / The public website invites commercial
  > HVAC service or quote inquiries through an observed contact path. / A
  > structured acknowledgement and qualification workflow could be evaluated for
  > that public request path. / We prepared a short deterministic simulation …
  > / It is a simulation—not a system deployed … / Would it be useful to compare
  > the simulation with your actual process and decide whether the idea is
  > relevant? / {{verified_sender_signature}} …

**After** (`tests/fixtures/personalization_v2_golden.json`, pinned against the
reconstructed sealed evidence — em dashes shown as `—`):

### Webb Air — HIGH, full crawl (24/24)

- **M2 statement:** *"Webb Air publicly presents a public request path ("Request
  service or a free estimate — contact us to schedule service online"), describes
  commercial HVAC work ("Light Commercial HVAC and Commercial Maintenance
  Programs for Fort Worth businesses"), publishes response expectations for new
  inquiries on its contact page, and lists a public service area ("Service areas
  we serve: Fort Worth, TX and Arlington, TX"). Given those observed public
  intake surfaces, a structured acknowledgement and qualification workflow could
  be evaluated. Current response performance, internal routing, lead volume,
  conversion, feasibility, and economic impact remain unknown pending business
  verification."*
- **M3 finding kinds:** `observed_intake_surface`, `observed_commercial_context`,
  `observed_response_commitment`, `observed_service_area`, `what_remains_unknown`,
  `crawl_coverage` (6).
- **M4 `service_need`:** `["Request service or a free estimate", "Light
  Commercial HVAC and Commercial", "other", "unknown"]`
- **M4 `service_location`:** `["Service areas we serve: Fort Worth, TX and",
  "other", "unknown"]`
- **M5 subject:** "A note about the Webb Air service path"
- **M5 first-contact email:**
  > Hello {{functional_role_or_team}},
  >
  > your website has a public request path — "Request service or a free estimate".
  >
  > your site describes commercial HVAC work — "Light Commercial HVAC and
  > Commercial Maintenance Programs".
  >
  > a step that acknowledges and sorts new service requests could be evaluated.
  >
  > This is not a claim about how your team works today — we have no visibility
  > into that.
  >
  > We prepared a short deterministic simulation based only on approved public
  > information.
  >
  > It is a simulation—not a system deployed, connected, official, or operated by
  > the business.
  >
  > I noticed your site offers "Request service or a free estimate". I'm curious —
  > roughly how many commercial inquiries arrive in a typical month, and how
  > after-hours ones are handled today?
  >
  > {{verified_sender_signature}}
  > {{required_postal_disclosure}}
  > {{approved_opt_out_instruction}}
- **Personalization:** `company_specific_segment_count 2`, `distinct_fact_classes
  2`, `passes_gate true`. State **`DRAFT_INCOMPLETE`**.

### BNCAIR — LOW, full crawl (3/3), appropriately sparse

- **M2 statement:** *"BNCAIR publicly presents a public request path ("Contact Us
  - BNCAIR") and describes commercial HVAC work ("BNCAIR provides commercial HVAC
  and residential heating and cooling services"). Given those observed public
  intake surfaces, a structured acknowledgement and qualification workflow could
  be evaluated. Current response performance, internal routing, lead volume,
  conversion, feasibility, and economic impact remain unknown pending business
  verification."*
- **M3 finding kinds:** `observed_intake_surface`, `observed_commercial_context`,
  `what_remains_unknown`, `crawl_coverage` (4) — **no response-commitment or
  service-area finding invented**.
- **M4 `service_need`:** `["Contact Us - BNCAIR", "BNCAIR provides commercial HVAC
  and residential", "other", "unknown"]`
- **M4 `service_location`:** synthetic fallback `["north_texas", "central_texas",
  "gulf_coast", "other", "unknown"]` — no `public_service_area` evidence.
- **M5 subject:** "A note about the BNCAIR service path"
- **M5 email:** same fixed structure; 1 evidence-derived fact segment; CTA "I
  noticed your site offers "Contact Us - BNCAIR". …"
- **Personalization:** `count 1`, `distinct_fact_classes 1`, `passes_gate true`.
  State **`DRAFT_INCOMPLETE`**.

### All Elements Heating & Air — LOW, partial crawl (13/20)

- **M2 statement:** *"All Elements Heating & Air publicly presents a public
  request path ("Contact us to request service for your facility"), describes
  commercial HVAC work ("All Elements Heating and Air provides commercial HVAC,
  heating, air conditioning, mini-split, maintenance and installation"), and
  lists a public service area ("Areas we serve: Marshall, Texas and the
  surrounding area"). Given those observed public intake surfaces, …"*
- **M3 finding kinds:** `observed_intake_surface`, `observed_commercial_context`,
  `observed_service_area`, `what_remains_unknown`, `crawl_coverage` (5).
- **M3 crawl-coverage finding:** *"Crawl coverage: 13 of 20 pages captured
  (partial); absence of a fact may reflect incomplete capture."* — the `scope`
  section limitation gains *"Coverage was partial (13 of 20 pages captured);
  absence of a fact may reflect incomplete capture."*
- **M4 `service_location`:** `["Areas we serve: Marshall, Texas and the", "other",
  "unknown"]`
- **M5 subject:** "A note about the All Elements Heating & Air service path"
- **Personalization:** `count 1`, `distinct_fact_classes 1`, `passes_gate true`.
  State **`DRAFT_INCOMPLETE`**.

**Divergence:** 3 distinct M2 statements, 3 distinct M5 emails, 3 distinct
subjects, 3 distinct M4 `service_need` sets, different M3 finding counts
(6 / 4 / 5). Webb Air alone is internally `review_priority_band = HIGH` /
`review_rank_hint.partial_crawl = false`; All Elements
`review_rank_hint.partial_crawl = true`; none surfaced externally.

**Byte-identical determinism:** `test_identical_evidence_is_byte_identical`
composes M5 twice from one source with fixed identifiers and asserts equal
`content_hash` + `revision_hash`.

---

## 5. Proof truth thresholds are unchanged

`git diff 48f0959..HEAD -- packages/opportunity-core/src/opintel_opportunity/rules.py`
shows **no `+`/`-` line touching threshold logic**:

- `if not industry or not inbound: return …None…` — unchanged (M2 hypothesis gate).
- `HypothesisStatus.NEEDS_INFORMATION if contradiction else READY_FOR_REVIEW` —
  unchanged.
- `priority = "HIGH" if has_structured_support and not contradicted else "LOW"` —
  unchanged.
- `evidence_band = Band.LOW if contradicted or not has_structured_support else
  Band.HIGH`; `confidence_band = Band.LOW if contradicted else evidence_band` —
  unchanged.
- All six `FactorResult` bands (`business_fit=HIGH block`, `potential_value` /
  `implementation_feasibility` = `UNKNOWN`, `important_unknowns=HIGH cap`, …) —
  unchanged.

`packages/opportunity-core/src/opintel_opportunity/economics.py` — **not in the
diff** (`git diff --name-only` count = 0). `production_runtime._m2` (the
`M2_INSUFFICIENT_EVIDENCE` terminal) — **not in the diff**.

Additions to `rules.py`: the deterministic statement text, `company_fact_ids` on
the hypothesis, the `select_company_facts` call, and the internal `ReviewRankHint`
(folded into the score manifest checksum). The FACT/INFERENCE/ESTIMATE/UNKNOWN
taxonomy is preserved — M2 assumptions stay `UNKNOWN`, economics stays
`INSUFFICIENT_DATA` with null values, the M2 statement keeps `could` and
`remain unknown`, and the fixed hypothetical tail keeps the exact substrings
"response performance", "internal routing", and "unknown".

Regression proof: `tests/test_m2_opportunity_engine.py` (the `contradicted` case
still hits the hard contradiction gate; `insufficient` still returns no
hypothesis; `weak` stays LOW; `strong` stays HIGH), plus
`test_personalization_v2_fixtures.py::test_all_public_other_fails_company_specific_m5_approval`
asserting the exact legacy `SAFE_STATEMENT` for evidence-poor input.

---

## 6. Personalization-gate tests

| Test | Asserts |
|---|---|
| `test_company_name_alone_never_satisfies_gate` | all-`public_other` fixture → `personalization.passes_gate is False`, QC `no_company_specific_evidence` HARD_FAILURE, `state == QC_FAILED` |
| `test_all_public_other_fails_company_specific_m5_approval` | `not m5.hard_qc_passed`; M2 statement == exact `LEGACY_SAFE_STATEMENT` |
| `test_webbair_response_and_service_facts_survive_to_reader_output` | "response expectations", "commercial", "request" present in the M2 statement / M5 email; response + service-area + commercial findings present |
| `test_bncair_is_sparse_not_padded` | no `observed_response_commitment` / `observed_service_area` finding; 1–2 evidence-derived projections; gate passes |
| `test_all_elements_partial_crawl_visible_in_m3` | `crawl_coverage` finding text contains "partial" and "13 of 20"; `scope` section structured item contains "partial" |
| `test_unresolved_placeholders_produce_draft_incomplete` | all three → `DRAFT_INCOMPLETE` with the three unresolved slot kinds |
| `test_no_score_language_leaks_into_external_artifacts` | regex + literal `HIGH`/`LOW` absent from every external artifact |
| `test_three_companies_diverge_where_evidence_differs` | 3 distinct statements / emails / subjects / `service_need` sets; internal band HIGH/LOW correct; `partial_crawl` hint correct |
| `test_identical_evidence_is_byte_identical` | equal `content_hash` + `revision_hash` on re-compose |
| `test_golden_renders_match` | full golden JSON equality (writes on first run, compares thereafter) |

The gate itself is a HARD_FAILURE `no_company_specific_evidence` in
`OutreachQualityPolicy` — the first-contact email must contain ≥1
`EVIDENCE_DERIVED_FACT` bound-claim segment whose rendered text, with the
business name and fixed frame tokens removed, still shares a token with the
bound evidence excerpt. Company-name interpolation and frame-only text do not
count. A non-blocking `single_evidence_category` warning is emitted when only one
`fact_class` is used but ≥2 were available.

---

## 7. Full test results

```
809 passed, 3 skipped, 0 failed   (~88 s)
```

Skips are the three PostgreSQL-parity tests (`OPINTEL_TEST_POSTGRES_URL` unset).
`ruff check` clean on every file this change touches (six pre-existing
`test_m67_*` lint warnings are untouched and predate this work). `mypy --strict`
clean on `opportunity-core`, `opportunity-local`, `audit-core`, `audit-local`,
`demo-core`, `demo-local`, `outreach-core`, `outreach-local`, and
`production_runtime.py`.

Test-file changes:
- `test_m2_opportunity_engine.py`: `seed_research_evidence` now classifies
  `fact_class` (`classify_public_fact`) and `page_purpose`, and gained
  `business_name` / `pages_attempted` / `pages_succeeded` / `run_status` /
  `fact_classes` overrides for fixtures.
- `test_m4_demo_engine.py`: four runtime drive-sequences now answer `"unknown"`
  for `service_need` / `service_location` (valid in both synthetic and
  company-derived option sets).
- `test_m5_outreach_engine.py`: assertions updated to V2 semantics —
  `EVIDENCE_DERIVED_FACT` projections, `DRAFT_INCOMPLETE` fresh state +
  `unresolved_slot_kinds`, wording-approval still succeeds (→ `content_approved`
  with `unresolved_slot_kinds` retained as the not-send-ready marker).
- `test_personalization_v2_fixtures.py`: new (10 tests) +
  `tests/fixtures/personalization_v2_golden.json`.

---

## 8. Exact deployment impact

**Not deployed.** When V2 ships:

1. **New research/intelligence image (chain link 8).** `rules.py`,
   `personalization.py` (new), `opportunity-local/*`, `audit-core/composition.py`,
   `audit-local/*`, `demo-core/*`, `demo-local/*`, `outreach-core/*`,
   `outreach-local/*` all changed. `workers/intelligence/production_runtime.py`
   is byte-unchanged but bundles the changed libraries.
2. **tfvars binding-hash bump.** `stage_coordinator_sha256` and
   `m2_m5_runtime_sha256` (bundle hashes over the M2–M5 composition code) change.
   `m1_runtime_sha256`, `activation_entry_point_sha256`,
   `sampled_slot_release_applicator_sha256` (`release_application.py`),
   `sampled_slot_activation_adapter_sha256` (`activation.py`) are **unchanged** —
   none of those files were touched.
3. **New deployment-evidence doc** (predecessor `sha256:34e5974f…` → link-8
   successor; ECR scan critical/high/blocking = 0; both image verifiers PROVEN;
   representation-equivalence PROVEN).
4. **DB migration** runs on `initialize()` — additive columns/table via the
   state-convergent guarded ALTER path (advisory locks 670002 / 670003 on
   PostgreSQL). Idempotent; a fully-migrated catalog is a strict no-op. No
   backfill of existing rows beyond `… IS NULL` defaults.
5. **Terraform** plan → apply under the ADR-0075 identity separation
   (`m67-phase1-terraform-workload-plan` / `-apply`).
6. **New execution authorization** required before any real slot runs under V2
   (the frozen Slot 02–04 artifacts stay on link 7 / `@1` and are never
   regenerated). No change to activation, authority materialization, kill switch,
   contact-phase gate, minimization, provenance, or the Phase-1
   `CONTACT_PHASE_NOT_AUTHORIZED` terminal.
7. **Runtime-terminal taxonomy:** unchanged. `DRAFT_INCOMPLETE` is a new
   *revision state* only; the worker does not terminate on it (contact-policy
   separation preserved), so the Phase-1 report row set is unchanged.

Backward compatibility: sealed Slot 02–04 rows validate under their pinned `@1`
policy versions; new artifacts validate under `@2` / `v3`; comparison code must
branch on the recorded version.

---

## 9. Narrow deployment / activation authorization requested

Design + implementation are complete, committed locally, and fully green. To
deploy and exercise V2, the following (and nothing broader) is requested:

1. **Build and publish research/intelligence image chain link 8** from this
   branch; produce the deployment-evidence doc (predecessor `sha256:34e5974f…`,
   ECR scan 0/0/0, both verifiers PROVEN).
2. **Bump the two changed tfvars binding attestations**
   (`stage_coordinator_sha256`, `m2_m5_runtime_sha256`) and the image digests;
   `terraform plan` → owner-reviewed `terraform apply` under the ADR-0075
   plan/apply identities. Expected in-cluster: kill switch remains TRIPPED, all
   authorities NOT_AUTHORIZED, services 0/0/0, zero running tasks.
3. **One bounded read-only in-VPC SELECT export** of the sealed Slot 02–04 M1
   evidence rows (`research_evidence` fragments + `fact_class` + `page_purpose`,
   `research_pages.page_purpose`, `research_runs` page counts/status) — SELECT
   only, no mutation — solely to **re-pin `tests/fixtures/personalization_v2_golden.json`**
   against the true sealed evidence before deploy. The current golden is pinned
   against faithful reconstructions from the sealed review doc.
4. **A fresh sampled-slot execution authorization** for any real V2 slot run
   (Slots 02–06 reruns are *not* requested and Slot 02–04 artifacts stay frozen).

Not requested / not in scope: economics or benchmark ranges (deferred, per the
design's §9); M6.6 activation; Slots 07–24; any AI / browser / contact-phase /
outreach / delivery; any new host scope; any threshold, minimization, or
provenance change.

---

## Constraints honored

Preserved all existing M2 truth thresholds, `INSUFFICIENT_EVIDENCE` behaviour,
FACT/INFERENCE/ESTIMATE/UNKNOWN semantics, provenance, minimization, and
external-use controls. No AI. No economics/benchmarks. No regeneration or
reinterpretation of the frozen Slot 02–04 artifacts — their sealed M1 evidence is
used only as immutable regression fixtures (reconstructed from the sealed review
doc). Not deployed. Slots 07–24 not started.
