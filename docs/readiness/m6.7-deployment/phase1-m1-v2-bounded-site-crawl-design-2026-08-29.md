# PHASE1_M1_V2_BOUNDED_SITE_CRAWL — proposed design

- **record_type**: `M67_PHASE1_M1_V2_BOUNDED_SITE_CRAWL_DESIGN`
- **schema_version**: `1.0.0`
- **state**: `DESIGN_PROPOSAL_PENDING_OWNER_AUTHORIZATION`
- **recorded_at_utc**: `2026-08-29T16:15:00Z`
- **account**: `785072247535` / `us-east-2`
- **supersedes protocol**: `PHASE1_M1_V1_HOMEPAGE` (Slot 01, CLOSED — see
  `slot01-phase1-m1-v1-homepage-freeze-2026-08-29.json`)
- **applies to**: Slots 02–24 (each still gated by its own separate per-slot execution authorization)
- **Slot 02**: NOT started. This document is design only.

---

## 0. Why this exists

Slot 01 closed truthfully at `M1_SUCCESS → M2_INSUFFICIENT_EVIDENCE`. Root cause is not a
defect: the `PHASE1_M1_V1_HOMEPAGE` protocol captured exactly one page (the homepage). The
deterministic M2 detector (`packages/opportunity-core/src/opintel_opportunity/rules.py::detect`)
only forms a hypothesis when the evidence corpus contains **both**

- a commercial-HVAC industry signal (`"commercial hvac"` / `"commercial heating"` / `"commercial cooling"`), and
- a public inbound-path signal (`"request service"`, `"request a quote"`, `"service request"`, …).

Those signals live on the **/services**, **/commercial**, **/contact**, and **/request-service**
style pages, not usually on a homepage in a form the detector recognises. Homepage-only
collection is structurally too shallow. v2 makes M1 collect a **bounded, same-host,
relevance-prioritised multi-page corpus** so M2 has the evidence it deterministically needs —
without weakening any safety control and without lowering the M2 threshold.

---

## 1. Current implementation baseline (what already exists)

`packages/research-core/src/opintel_research/workflow.py::ResearchWorkflowRunner._execute`
already performs a **bounded same-host BFS crawl**:

- FIFO `deque` frontier seeded with `run.start_url`; `max_pages` / `max_depth` / `max_total_bytes`
  / `max_duration_seconds` / `max_attempts` ceilings; kill-switch check each iteration.
- Per-URL runtime robots evaluation (`RuntimeRobotsPolicy`, fail-closed, gzip/deflate aware —
  Repair #3).
- `normalize_public_url` + SSRF / public-IP / DNS-rebinding / port / scheme / credential guards
  (`url_policy.py`); same-host enforcement on every dequeued URL and every enqueued link.
- Deterministic block-level minimisation (`phase1-minimizer@2`, Repair #5) or quarantine.
- Ephemeral raw body; durable artefact is the minimised text + provenance-bound evidence rows.
- `max_redirects=0` in the sampled-slot policy (`activation.py::_policy`).
- M2 (`production_runtime.py::_m1`) already reads the **entire** `list_evidence(run)` set across
  all pages — the corpus plumbing to M2 is multi-page-ready today.

**What Slot 01 actually ran**: `activation.py::_policy` sets `max_pages = min(10, max_logical_requests)`
and `max_depth = 1`, but the sealed execution ceilings capped `max_logical_requests` low and the
homepage yielded no same-host links the detector cared about, so exactly one page was captured.

**Gaps vs. the v2 objective** (the rest of this document):

| # | Gap | v2 addition |
|---|-----|-------------|
| G1 | No sitemap / robots-`Sitemap:` / conventional-endpoint discovery | §2 discovery |
| G2 | Plain FIFO frontier — no semantic prioritisation, no low-value exclusion | §3 frontier |
| G3 | No query-parameter-loop / tracking-param canonicalisation beyond byte normalisation | §3.3 |
| G4 | No per-page purpose classification; no discovery-edge record | §4 corpus |
| G5 | No deterministic M1 coverage record | §5 coverage |
| G6 | Only hard-ceiling stopping; no "categories exhausted / no new evidence" early stop | §6 |
| G7 | Ceilings sized for 1–5 pages, not ~25 | §7 |
| G8 | No protocol-version tag distinguishing v1 from v2 | §8 |

---

## 2. Discovery

Deterministic candidate-URL discovery, in this fixed order, all same-host only:

1. **Runtime `robots.txt`** — already fetched once per run. Additionally parse every
   `Sitemap:` directive line; keep only same-host `https://903hvac.com/...` targets.
2. **Declared sitemap locations** — fetch each robots-declared sitemap (bounded, §7).
   Support `sitemapindex` (recurse one level only), `urlset`, and `.xml.gz` / `Content-Encoding: gzip`
   via the existing `decode_http_content` path.
3. **Conventional same-host sitemap endpoints, only where robots allows the path**:
   `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-index.xml`, `/wp-sitemap.xml`,
   `/sitemap.xml.gz`. Tried in this fixed order; stop after the first that returns a valid
   sitemap or after the endpoint budget is spent.
4. **Same-host links on successfully fetched pages** — `<a href>` targets from
   `ExtractedMaterial.links` (already `(href, anchor_text, rel)`), normalised and host-checked.

**Normalisation & dedup** (§3.3): every candidate passes through `normalize_public_url`
(unchanged safety layer) **and** a new `canonical_crawl_url` (crawl-dedup layer). Candidates are
deduped by canonical form. A candidate already visited, already queued, or already excluded is
dropped.

**Hard rules preserved**: never follow or crawl an unapproved hostname (checked at discovery,
at enqueue, and again at dequeue); robots re-evaluated for **every** candidate path before any
fetch; certificate validation, TLS/SNI controls, SSRF / public-IP / DNS-rebinding protections,
`max_redirects=0`, ephemeral raw-body policy, deterministic minimisation, provenance, and the
truth taxonomy are all unchanged and still enforced on the sitemap/robots fetches too.

---

## 3. Relevance prioritisation

### 3.1 Semantic categories (deterministic keyword table)

A frozen table `SEMANTIC_CATEGORIES: dict[SemanticCategory, tuple[str, ...]]` matched
case-insensitively against **(path segments + query keys) ∪ (anchor text) ∪ (discovered page
`<title>`/`<h1>` once fetched)**. This is semantic matching on tokens, **not** dependence on
exact URL names.

High-value categories (each contributes to M2-relevance and to coverage):
`homepage`, `services`, `commercial_hvac`, `residential_hvac`, `heating`, `cooling_ac`,
`repair`, `installation`, `maintenance`, `emergency_service`, `request_service_scheduling`,
`estimate_quote`, `contact_mechanism`, `about`, `service_area_location`, `financing`, `faq`.

Example keyword sets (illustrative, full table in the implementation):
- `commercial_hvac`: `commercial`, `commercial hvac`, `commercial heating`, `commercial cooling`, `business`, `industrial`
- `request_service_scheduling`: `request service`, `schedule`, `scheduling`, `book`, `appointment`, `service request`
- `estimate_quote`: `estimate`, `quote`, `get a quote`, `free estimate`, `request an estimate`
- `contact_mechanism`: `contact`, `contact us`, `get in touch`, `reach us`
- `service_area_location`: `service area`, `areas we serve`, `locations`, `service map`, `cities`

### 3.2 Scoring & frontier ordering

`frontier.py::score_candidate(canonical_url, anchor_text, discovery_source) -> CandidateScore`
returns `(category | None, score: int, tie_break_key: str)`. Deterministic priority (higher first):

1. `homepage` seed — always first.
2. High-value category hit — base 100, `+15` if the hit is in the path (vs. only anchor text),
   `+10` if discovered from a sitemap (site-declared as significant), `+5` per additional
   distinct high-value category the same URL matches.
3. `depth` penalty: `-5 * depth`.
4. Unknown/unclassified same-host page — base 20.
5. Low-value (see §3.4) — excluded entirely (never scored, never fetched).

Ties broken by `(-score, category_name, canonical_url)` — a total order, so the crawl is
**fully deterministic** given the same site bytes.

`frontier.py` is a **pure module**: no I/O, no clock, no randomness. Everything it needs
(visited set, per-category counts, captured-evidence keyword hits, remaining budget) is passed in.

### 3.3 URL canonicalisation & loop defence

`url_policy.py::canonical_crawl_url(normalized_url) -> str` (new, additive; does **not** replace
`normalize_public_url`):

- lowercase host (already done), strip default ports (already), strip trailing `/` except root,
  strip fragment (already gone).
- drop a frozen tracking-parameter set: `utm_*`, `gclid`, `fbclid`, `mc_cid`, `mc_eid`,
  `ref`, `source`, `_ga`, `msclkid`, `igshid`, `si`.
- sort remaining query keys; collapse repeated keys to first value.
- **query-loop defence**: if a canonical path has already been seen with ≥ `MAX_QUERY_VARIANTS`
  (proposed 3) distinct query strings, further query variants of that path are excluded and
  counted as `excluded:query_variant_loop`.
- **path-depth cap**: paths with > 6 segments are excluded (`excluded:path_too_deep`).

### 3.4 Low-value exclusion (deterministic predicate)

`frontier.py::is_low_value(canonical_url, anchor_text) -> str | None` returns an exclusion
reason or `None`. Excluded unless the URL **also** matches a high-value category with a path hit
(then it is demoted, not excluded):

- pagination / archives: `/page/N`, `/20\d\d/\d\d/`, `?paged=`, `/category/`, `/tag/`, `/author/`
- search: `/search`, `?s=`, `?q=`
- auth / account: `/login`, `/account`, `/wp-admin`, `/wp-login`, `/my-account`, `/cart`, `/checkout`
- legal boilerplate: `/privacy`, `/cookie`, `/terms`, `/legal`, `/disclaimer`, `/accessibility`
- feeds / assets: `/feed`, `.xml` (non-sitemap), `.rss`, `.pdf`, `.jpg`, `.png`, `.css`, `.js`, `.zip`
- blog archives: `/blog/*`, `/news/*`, `/articles/*` — **deprioritised to base 10, capped at 2
  total**, kept only if the anchor/title matches a high-value category.

Absence rule: a category not found in discovery or not captured is recorded in the coverage
record as **public absence only**. It must never be turned into an internal fact. (Enforced by
M2 truth rules, which are unchanged, plus a coverage-record assertion test.)

---

## 4. Evidence corpus

Each successfully minimised page stays **independently provenance-bound** — unchanged. v2 makes
the run's output an explicit **business evidence corpus**:

- **page capture identities** — `MinimizedPageSnapshot.id` + `snapshot_version`
  (`minimized-sha256:…`) + `source_content_sha256` (raw) — already persisted.
- **source URLs** — `ResearchPage.requested_url` / `normalized_url` — already persisted.
- **page-purpose classification** — new `ResearchPage.page_purpose: PagePurpose` (StrEnum, one of
  the §3.1 categories or `unclassified`). Assigned deterministically from the final fetched
  URL + title + h1 using the same table. Persisted, included in evidence provenance.
- **retained evidence items** — `ResearchEvidence` rows (title, headings, `visible-text:0-2000`)
  — already persisted; each already binds exactly one `snapshot_id` and asserts the fragment
  is a substring of that page's minimised text (`DurablePageBundle.__post_init__`).
- **FACT classifications** — new lightweight `evidence.fact_class` derived deterministically:
  `public_service_description`, `public_inbound_path`, `public_service_area`, `public_about`,
  `public_faq`, `public_other`. No inference, no synthesis — pure keyword class of the fragment.
- **minimisation / provenance identities** — `minimization_event_sha256`, `minimizer_version`,
  removed-contact counters, `required_evidence_markers` — already on `MinimizedPageSnapshot`.
- **crawl / discovery relationship** — new `research_discovery_edge` rows:
  `(from_page_id | NULL for seed/sitemap/robots, discovered_url_canonical, discovery_source,
  category, score, disposition)` where `disposition ∈ {captured, queued, excluded:<reason>,
  robots_denied, transport_failed, quarantined, budget_skipped}`.

**Never merge text across pages.** The corpus is a list of per-page bundles; M2 consumes the
list. There is no concatenated blob. Which page supported which evidence item is always
recoverable via `evidence.snapshot_id → page.id → page.requested_url`.

---

## 5. Deterministic M1 coverage record

New immutable `M1CoverageRecord` (dataclass + persisted row + `sha256` folded into the M1 stage
output digest). Fully deterministic given the site bytes:

```
crawl_protocol_version:            "phase1-m1@2-bounded-site-crawl"
candidate_urls_discovered:         int      + per discovery_source breakdown
eligible_urls:                     int      (passed dedup + low-value + host + robots-path)
duplicate_or_excluded_urls:        list[(canonical_url, reason)]   # reason taxonomy from §3
pages_attempted:                   int
pages_successfully_captured:       int      + list[(url, page_purpose)]
pages_quarantined:                 int      + list[(url, quarantine_reason)]
pages_denied_by_robots:            int      + list[(url, robots_reason_code)]
transport_failures:                int      + list[(url, error_code)]
semantic_categories_searched:      list[SemanticCategory]   # everything in the table
semantic_categories_found:         list[SemanticCategory]   # appeared among discovered candidates
semantic_categories_captured:      list[SemanticCategory]   # appear on a captured page
sitemap_documents_fetched:         int
robots_sitemap_directives_seen:    int
stop_reasons:                      list[CrawlStopReason]    # may be multiple
byte_budget_used / time_used / attempts_used / logical_requests_used
coverage_record_sha256:            hex
```

`semantic_categories_found` minus `semantic_categories_captured` is **public absence**, labelled
as such, and carried to M2 as "not observed on captured public pages" — never as a negative fact.

---

## 6. Bounded crawl & deterministic early stopping

The crawl is **not** "download every URL". It stops at the **first** of:

**A. Hard ceilings** (§7) — `max_useful_page_fetches`, `max_total_bytes`, `max_duration_seconds`,
`max_total_http_requests`, `max_discovery_fetches`, kill-switch active. Each records a
`CrawlStopReason`.

**B. High-value categories satisfied** — every high-value category is either **captured** (≥1
page) or **exhausted** (no remaining frontier candidate matches it) **and** the best remaining
frontier score is `< LOW_RELEVANCE_FLOOR` (proposed 20, i.e. only unclassified/low pages left).
Records `stop_reasons += ["high_value_categories_satisfied"]`.

**C. No materially new evidence** — the last `NO_PROGRESS_WINDOW` (proposed 3) successful
captures each added **0** new `semantic_categories_captured` **and 0** new M2-relevant keyword
hits (industry / inbound / strong / contradiction tokens from `rules.py`). Records
`stop_reasons += ["no_new_evidence"]`.

**D. Frontier empty** — nothing left to consider. `stop_reasons += ["frontier_exhausted"]`.

`frontier.py::should_stop(state) -> list[CrawlStopReason]` is pure and evaluated once per
iteration before dequeue.

Per-category cap: at most `MAX_PAGES_PER_CATEGORY` (proposed 4) captured pages per category, so
one section (e.g. a large `/services/*` tree) cannot consume the whole budget.

---

## 7. Proposed new ceilings

Sized for real multi-page research with a hard cap near **25 useful page fetches per company**.

| Ceiling | v1 (Slot 01 effective) | **v2 proposed** | Rationale |
|---|---|---|---|
| `max_useful_page_fetches` (successful captures) | ~1–5 | **25** | owner target |
| `max_total_http_requests` (pages + retries + discovery) | ~15 | **48** | 25 pages × ≤2 attempts − cache misses, hard stop |
| `max_discovery_fetches` (robots + sitemaps) | 1 (robots) | **6** | robots + up to 1 sitemap index + up to 4 child/conventional sitemaps |
| `max_depth` (link-graph backstop) | 1 | **3** | reach `/services/commercial/…`; discovery is category-driven, depth is only a backstop |
| `max_attempts` per URL | 3 | **2** | one retry; keeps request ceiling bounded |
| `max_response_bytes` (single response) | 1,000,000 | **1,000,000** | unchanged |
| `max_compressed_bytes` | 1,000,000 | **1,000,000** | unchanged |
| `max_total_bytes` (cumulative raw, whole run) | 5,000,000 | **18,000,000** | 25 pages × ~480 KB raw HTML + sitemap overhead |
| `max_sitemap_entries_parsed` | n/a | **2,000** | bound sitemap blow-up; excess ignored deterministically (first 2,000 in document order) |
| `max_duration_seconds` | 30–120 | **300** | 2 s politeness delay × ~30 fetches ≈ 60 s wait + fetch/parse/minimise |
| `per_domain_delay_seconds` | 2.0 | **2.0** | unchanged politeness |
| `request_timeout_seconds` | 8.0 | **8.0** | unchanged |
| `max_redirects` | 0 | **0** | unchanged — zero followed redirects |
| `MAX_QUERY_VARIANTS` per path | n/a | **3** | §3.3 loop defence |
| `MAX_PAGES_PER_CATEGORY` | n/a | **4** | §6 |
| `NO_PROGRESS_WINDOW` | n/a | **3** | §6C |
| `LOW_RELEVANCE_FLOOR` | n/a | **20** | §6B |
| cost ceiling | USD 0 | **USD 0** | unchanged — no paid APIs |

**Authority-envelope impact**: the sealed execution-ceiling envelope
(`SampledSlotExecutionApproval` / `LiveResearchPermissionRelease` /
`execution_ceilings_sha256`) currently binds `max_logical_requests`, `max_attempts`,
`max_total_bytes`, `max_response_bytes`, `max_duration_seconds`. v2 needs those raised to the
values above **and** two new bound fields: `max_useful_page_fetches` (= 25) and
`crawl_protocol_version` (= `"phase1-m1@2-bounded-site-crawl"`). `execution_ceilings_sha256`
therefore changes; the `ConsumedLiveBudget` carry-forward mechanism (Repair #3) is unchanged and
still subtracts already-consumed live activity per slot.

Estimated worst-case spend per slot under v2: ≤ 48 HTTPS GETs, ≤ 18 MB transfer, ≤ 300 s wall
clock, USD 0. Across Slots 02–24 (23 slots): ≤ 1,104 requests, ≤ 414 MB, all first-party,
same-host, robots-respecting.

---

## 8. Protocol / versioning

| | v1 | v2 |
|---|---|---|
| protocol name | `PHASE1_M1_V1_HOMEPAGE` | `PHASE1_M1_V2_BOUNDED_SITE_CRAWL` |
| `crawl_protocol_version` string | `phase1-m1@1-homepage` (assigned retroactively to Slot 01 records via the freeze doc; **no Slot 01 row is mutated** — the mapping lives in the freeze record) | `phase1-m1@2-bounded-site-crawl` (persisted on every v2 `ResearchRun` + coverage record + M1 output digest) |
| minimiser | `phase1-minimizer@2` | `phase1-minimizer@2` — **unchanged** |
| M2 rules | `RULE_VERSION` in `rules.py` | **unchanged** |

Slot 01 (v1) and Slot 02+ (v2) results are **explicitly not** claimed protocol-identical. Any
cross-slot comparison must cite both protocol versions. The M1 stage output digest includes
`crawl_protocol_version` so downstream artefacts are self-identifying.

---

## 9. Implementation impact (file by file)

### research-core (`packages/research-core/src/opintel_research/`)
- **`domain.py`**: extend `CrawlPolicy` with the §7 fields; add `SemanticCategory` (StrEnum),
  `SEMANTIC_CATEGORIES` table, `PagePurpose` (alias of the categories + `unclassified`),
  `CrawlStopReason` (StrEnum), `CandidateDisposition` (StrEnum), `DiscoverySource` (StrEnum);
  add `UrlCandidate`, `DiscoveryEdge`, `M1CoverageRecord` frozen dataclasses; add
  `page_purpose` to `ResearchPage`, `coverage_record_sha256` + `crawl_protocol_version` to
  `ResearchRun`, `fact_class` to `ResearchEvidence`. All additive; existing fields unchanged.
- **`frontier.py`** (new, pure): `score_candidate`, `is_low_value`, `classify_category`,
  `should_stop`, `PriorityFrontier` (deterministic heap keyed by the §3.2 total order).
- **`sitemap.py`** (new, pure): `parse_sitemap(body: bytes, content_encoding: str,
  max_entries: int) -> SitemapParseResult` — handles `urlset`, `sitemapindex` (one level),
  gzip; defensive XML (no external entities, bounded size); returns same-host candidates +
  child-sitemap URLs + parse diagnostics. No I/O.
- **`url_policy.py`**: add `canonical_crawl_url` + `TRACKING_PARAMS` frozenset. `normalize_public_url`
  and `PublicUrlPolicy` untouched.
- **`ports.py`**: add `sitemap_directives: tuple[str, ...]` to the robots evidence path (or a
  `RobotsPolicy.sitemap_urls(run_id, host) -> tuple[str, ...]`); extend `ResearchRepository`
  with `save_coverage_record`, `save_discovery_edges`, `list_discovery_edges`,
  `get_coverage_record`. `HttpTransport` reused for sitemap fetches.
- **`workflow.py`**: the main change. Replace the FIFO `deque` with `PriorityFrontier`; add a
  discovery pass (robots `Sitemap:` → declared sitemaps → conventional endpoints → on-page
  links, each recording a `DiscoveryEdge`); classify each fetched page's `page_purpose`; feed
  captured-evidence keyword hits back into the frontier + `should_stop`; assemble and persist the
  `M1CoverageRecord`; apply per-category cap + early stop. **All existing safety branches
  (robots eval, host check, minimiser/quarantine, byte/time/attempt ceilings, kill-switch,
  zero-redirect, ephemeral body) are kept verbatim and now also run on discovery fetches.**
- **`extraction.py`**: ensure anchor text is retained on `links` (it already is: `(href, text, rel)`);
  no behavioural change to contact stripping.
- **`application.py`**: expose `get_coverage_record` / `list_discovery_edges` read methods.
- **`contracts.py`**: add coverage-record + discovery-edge DTOs.

### research-local (`packages/research-local/src/opintel_research_local/`)
- **`persistence.py`**: new tables `research_url_candidate`, `research_discovery_edge`,
  `research_coverage_record`; new columns `research_page.page_purpose`,
  `research_run.coverage_record_sha256`, `research_run.crawl_protocol_version`,
  `research_evidence.fact_class`. **State-convergent, independently idempotent migration** in
  `initialize()` — same discipline as the schema-convergence repair: inspect each intended
  invariant (table exists? column exists? column NOT NULL where required?) and converge only
  what is missing; a fully-migrated schema is a strict no-op; no marker-column shortcut.
- **`robots.py`**: capture `Sitemap:` directive lines into the robots evidence (bounded count);
  fail-closed behaviour unchanged.
- **`http.py`**: reuse `decode_http_content` for `.xml.gz` sitemaps (already gzip-capable).

### workers/research (`workers/research/src/opintel_research_worker/`)
- **`activation.py::_policy`**: build the v2 `CrawlPolicy` from the new envelope ceilings
  (`max_useful_page_fetches`, raised `max_total_bytes` / `max_duration_seconds` / `max_attempts`,
  `max_depth=3`); set `crawl_protocol_version` on the run.
- **`authorization.py`**: verify the release carries `crawl_protocol_version ==
  "phase1-m1@2-bounded-site-crawl"` and the raised ceilings; reject a v1 envelope for a v2 run
  and vice-versa.
- **`synthetic_validation.py`**: new scenario `BOUNDED_SITE_CRAWL_V1` — runs the deployed image
  against an in-cluster synthetic multi-page fixture and asserts the coverage record, category
  capture, early stop, and determinism before Slot 02.

### workers/intelligence (`workers/intelligence/src/opintel_intelligence_worker/`)
- **`production_runtime.py::_m1`**: fold `coverage_record_sha256` + per-page `page_purpose` +
  `crawl_protocol_version` into the M1 output digest; attach the coverage record to the stage
  artefact. `list_evidence` consumption is unchanged (already whole-corpus).
- **`_m2` and everything downstream**: **unchanged**. M2 already iterates the full evidence set.
  M2 truth rules, thresholds, and `INSUFFICIENT_EVIDENCE` semantics are **not touched**. More
  evidence does not lower the bar — it just gives the existing detector the pages it needs.

### authority / materialization
- **`authority_materialization.py` / envelope schema**: add `max_useful_page_fetches` +
  `crawl_protocol_version` to the execution-ceilings payload; raise the numeric ceilings;
  `execution_ceilings_sha256` recomputed. `ConsumedLiveBudget` carry-forward unchanged.
- **`infra/terraform/phase1/terraform.tfvars`**: new successor image digest (chain link 6) +
  any ceiling values surfaced as tf vars. The six approval-binding sha256s change only for the
  files that actually change (`m1_runtime_sha256`, `m2_m5_runtime_sha256` if the worker code
  hash moves; the container digest is the authoritative code identity per the Repair #2/#3/#5
  precedent).

### deployment
- New successor container image = **chain link 6**
  (`… → edda5c6 → 47de97de → <v2>`). Built by the existing thin-successor Dockerfile pattern,
  published through `m67-phase1-worker-image-publisher`, representation-equivalence proven by
  both verifiers, ECR scan COMPLETE 0/0/0, appended to
  `OPINTEL_REPAIR_SUCCESSOR_{REGISTRY,DEPLOYMENT}_EVIDENCE_PATHS`. **Note**: this is a
  *protocol upgrade*, not a repair — it must be tracked as a new successor lineage entry with
  its own evidence, not as a "repair".
- ADR-0075 identity-separated plan → semantic review → apply; post-apply `NO_CHANGES`.
- State-convergent DB migration verified against the live RDS catalog via a transient
  Fargate task (same method as the schema-convergence repair).

### docs
- This design doc + the Slot 01 freeze record (both committed).
- On authorization: an owner-decision record, a deployment record, a validation record.

---

## 10. Test plan

New file `tests/test_m1_v2_bounded_site_crawl.py` + pure-unit files
`tests/test_m1_frontier.py`, `tests/test_m1_sitemap.py`. Synthetic fixtures served by an
in-memory transport (no network). Every test asserts **determinism** (byte-identical coverage
record + ordered evidence set across two runs on the same fixture).

Owner-required synthetic websites:

| Fixture | Assertion |
|---|---|
| sitemap with many pages (500 URLs) | first ≤2,000 parsed in document order; frontier prioritises high-value categories; ≤25 captured; `max_sitemap_entries_parsed` respected |
| no sitemap | conventional endpoints tried in fixed order, all 404 → on-page-link discovery only; still captures services/contact |
| duplicate URLs (same page via `/x`, `/x/`, `/x?utm_source=…`) | canonicalised to one candidate; captured once; dedup counted |
| query-parameter loop (`/cal?d=1..1000`) | ≤`MAX_QUERY_VARIANTS` fetched; rest `excluded:query_variant_loop` |
| cross-host links (`facebook.com`, `supplier.com`) | never queued, never fetched; `excluded:offsite` (or silently dropped) recorded |
| robots exclusions (`Disallow: /private`, `Disallow: /services/internal`) | those paths `robots_denied`, never fetched; allowed siblings still captured |
| gzip sitemap + gzip robots.txt | decoded via `decode_http_content`; parsed correctly (Repair #3 regression guard) |
| contact-heavy pages (emails, phones, staff cards) | `phase1-minimizer@2` redacts/drops; page captured if safe evidence remains, else quarantined; **minimiser sha256 unchanged** |
| multiple useful service pages (`/services`, `/commercial`, `/residential`, `/heating`, `/cooling`, `/repair`, `/install`, `/maintenance`) | each classified to the right `page_purpose`; per-category cap enforced; corpus has ≥1 per captured category |
| hundreds of irrelevant blog URLs (`/blog/2019/…` ×300) | deprioritised, ≤2 captured (only if title matches a high-value category), rest `excluded:blog_archive` / `budget_skipped` |
| deterministic early stopping | when all high-value categories captured and only low pages remain → stop with `high_value_categories_satisfied`; when 3 consecutive captures add nothing → `no_new_evidence` |
| byte ceiling exhaustion | stops at `max_total_bytes` with `stop_reasons=["byte_budget_exceeded"]`; partial corpus still valid & provenance-bound |
| page-count ceiling exhaustion | stops at 25 captures with `useful_page_budget_exceeded` |
| time ceiling exhaustion (fake clock) | stops at `max_duration_seconds` with `crawl_duration_exceeded` |
| provenance across multiple pages | every `ResearchEvidence.snapshot_id` resolves to exactly one page; fragment is a substring of that page's minimised text; no cross-page merge |
| public absence | fixture missing `financing` + `faq` → `semantic_categories_found` excludes them, coverage record labels them absent, **no** observation/fact generated for them; M2 still runs on what exists |
| M2 handoff | fixture with `/commercial` (industry) + `/request-service` (inbound) → M2 forms a hypothesis (no longer `INSUFFICIENT_EVIDENCE`); fixture with only homepage → M2 still `INSUFFICIENT_EVIDENCE` (threshold unchanged) |

Regression suite (must stay green): all existing `tests/test_m1_research_engine.py`,
`tests/test_m67_runtime_robots.py`, `tests/test_m67_production_minimization.py`,
`tests/test_m2_opportunity_engine.py`, `tests/test_m67_coordinator_schema_convergence.py`,
full workspace suite (currently 749 pass). `compliance_application.py` sha256 asserted
unchanged. mypy + ruff clean.

In-cluster: `synthetic_validation.py::BOUNDED_SITE_CRAWL_V1` PASS on the deployed successor
image before any Slot 02 authorization is requested.

---

## 11. Safety invariants preserved (explicit checklist)

- [x] robots controls — evaluated per candidate path, fail-closed, gzip-aware; now also on sitemaps
- [x] certificate validation / TLS / SNI — unchanged transport
- [x] SSRF / public-IP / DNS-rebinding — `PublicUrlPolicy.validate` on every URL incl. sitemaps
- [x] zero followed redirects — `max_redirects=0` retained
- [x] ephemeral raw-body — raw bytes discarded after minimisation; only minimised text persists
- [x] deterministic minimisation — `phase1-minimizer@2`, byte-for-byte unchanged
- [x] provenance — every evidence item binds one page snapshot; no cross-page merge
- [x] truth taxonomy — M2 rules, thresholds, `INSUFFICIENT_EVIDENCE` unchanged; absence stays public absence
- [x] same-host only — checked at discovery, enqueue, dequeue
- [x] cost USD 0 — no paid services
- [x] cumulative Window 2 counters — not reset; `ConsumedLiveBudget` carry-forward intact
- [x] Slot 01 records — immutable; v1 tag applied only in the freeze record, no row mutated

---

## 12. Narrow authorization required to activate v2 for Slots 02–24

**Proposed decision event**: `AUTHORIZE_PHASE1_M1_V2_BOUNDED_SITE_CRAWL_IMPLEMENTATION_AND_ACTIVATION`

**Permits exactly**:
1. Implement `PHASE1_M1_V2_BOUNDED_SITE_CRAWL` per this design document (bound by its SHA-256),
   §§2–10, with the §7 ceilings.
2. Build **one** new successor container image (successor-chain link 6) via the existing bounded
   publisher; representation-equivalence proven by both verifiers; ECR scan COMPLETE
   critical/high/blocking 0/0/0; appended to the sealed successor chain as a **protocol-upgrade**
   entry (not a repair).
3. ADR-0075 identity-separated Terraform plan → semantic review → apply for the new image digest
   and ceiling variables; post-apply `NO_CHANGES`.
4. One state-convergent, independently idempotent database migration for the new corpus tables /
   columns; verified against the live RDS catalog via a transient task; historical rows preserved.
5. A new sealed execution-ceiling envelope with the §7 raised bounds plus the
   `max_useful_page_fetches` and `crawl_protocol_version` bindings; `execution_ceilings_sha256`
   recomputed; `ConsumedLiveBudget` carry-forward unchanged.
6. Run `synthetic_validation BOUNDED_SITE_CRAWL_V1` against the deployed image.
7. Commit the implementation, tests, and evidence records.

**Does NOT authorize** (each needs its own separate owner decision):
- Starting Slot 02 or **any** slot execution (M1–M5) — per-slot execution authorization is
  unchanged and still required.
- Reopening, rerunning, or re-labelling Slot 01.
- Any change to M2/M3/M4/M5 truth rules, evidence thresholds, or `INSUFFICIENT_EVIDENCE`
  semantics.
- Weakening any safety control in §11.
- The contact phase (`CONTACT_PHASE_NOT_AUTHORIZED` remains the terminal boundary).
- Any paid API or non-first-party data source.

**Constraints carried forward**:
- Preserve all cumulative Window 2 target-transport counters. No reset.
- Do not alter `phase1-minimizer@2` semantics.
- Do not delete, mutate, reopen, or replace any historical run, coordinator run, work item,
  evidence, coverage record, or terminal history.
- Do not manually arm the kill switch to RUN — the activator's `enter_run()` owns
  `TRIPPED → RUN → TRIPPED`.
- No Slot 02 until separately authorized.
- If an unrelated operational defect appears during implementation, stop for owner review.

**After this authorization is discharged**, the next owner decision would be a per-slot
`AUTHORIZE_SLOT02_*_EXECUTION` (or a batch authorization for Slots 02–24), which is out of scope
here.

---

## 13. Deliverables summary for owner review

| Artefact | Path | Status |
|---|---|---|
| Slot 01 freeze / closure | `docs/readiness/m6.7-deployment/slot01-phase1-m1-v1-homepage-freeze-2026-08-29.json` | committed |
| This design proposal | `docs/readiness/m6.7-deployment/phase1-m1-v2-bounded-site-crawl-design-2026-08-29.md` | committed |

No code has been changed. No image built. No Terraform run. No slot started. Awaiting a
narrow owner authorization (§12) before any implementation.
