# PHASE1_M1_V2_BOUNDED_SITE_CRAWL — implementation + deployment complete, Slots 02–06 readiness

- **record_type**: `M67_PHASE1_M1_V2_SLOTS02_06_READINESS`
- **state**: `IMPLEMENTATION_AND_DEPLOYMENT_COMPLETE__READY_FOR_SLOTS02_06_BATCH_AUTHORIZATION`
- **recorded_at_utc**: `2026-08-30T09:30:00Z`
- **authorization discharged**: `AUTHORIZE_PHASE1_M1_V2_BOUNDED_SITE_CRAWL_IMPLEMENTATION_AND_ACTIVATION`
  (owner-decision `…owner-decision-2026-08-30.json`, sha256 `467b740ea786aa8a0dfc7b456144553b6865d4b8c14188df31557d035e8a3432`)
- **deployed digest**: `785072247535.dkr.ecr.us-east-2.amazonaws.com/m67-phase1-worker@sha256:62ba45aa295b912a578676dd440c75525206757878242e679923764b61c009e4`
  (chain link 6, protocol-upgrade successor of `sha256:47de97de…`; deployment evidence
  `phase1-m1-v2-deployment-2026-08-30.json`)
- **Slot 01**: frozen `PHASE1_M1_V1_HOMEPAGE`, terminal `M1_SUCCESS → M2_INSUFFICIENT_EVIDENCE`. Not reopened.
- **Slot 02**: NOT started.

---

## 1. Implementation — DONE (branch `worktree-slot01-window2-execution`)

| Commit | Content |
|---|---|
| `f4d9b45` | owner-decision record |
| `7c1b1f1` | `frontier.py`, `sitemap.py`, `url_policy.canonical_crawl_url`, additive `domain.py` types + `CrawlPolicy` v2 ceilings, state-convergent additive-column migration; 25 unit tests |
| `9ecd2ac` | `RuntimeRobotsPolicy.sitemap_directives()` |
| `1987b9f` | `site_crawl.py::BoundedSiteCrawlRunner` (v2 crawl), `workflow._execute` protocol dispatch (v1 path renamed `_execute_homepage`, byte-for-byte unchanged), `ports`/`persistence` coverage + discovery-edge methods + 2 new tables + `research_runs.coverage_record_sha256`; 10 integration tests |
| `207ef34` | `production_runtime._m1` folds `crawl_protocol_version` + `coverage_record_sha256` + `fact_class` + `page_purpose` into the M1 output digest |
| `85fa621` | `synthetic_validation.py` `BOUNDED_SITE_CRAWL_V1` mode + kill-switch discovery guard; 4 synthetic-validation tests |

**Verification**: full suite **785 pass / 3 skip** (skips are Postgres-only), `mypy` + `ruff` clean.
M2/M3/M4/M5 truth rules, thresholds, `INSUFFICIENT_EVIDENCE` semantics and `phase1-minimizer@2`
are untouched.

### Final protocol definition

- `crawl_protocol_version` string: **`phase1-m1@2-bounded-site-crawl`**
- Dispatch: `workflow._execute` runs `BoundedSiteCrawlRunner` **only** when
  `run.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"`; every other run keeps the
  homepage-only path exactly as before. v1 and v2 are explicitly not protocol-identical.

### Final ceilings — sealed

`docs/readiness/m6.7-deployment/phase1-m1-v2-execution-ceiling-envelope-2026-08-30.json`,
`execution_ceilings_sha256` = `083b70520f161d4c21aa72cc221cb063dc2b99cf19ab15caa9c0cd7011b0506b`.
25 useful fetches / 48 total HTTP / 6 discovery / depth 3 / 2 attempts / 18 MB / 300 s /
2 s delay / 0 redirects / 2 000 sitemap entries / USD 0. New bindings: `max_useful_page_fetches`,
`crawl_protocol_version`.

### Safety controls — proven still enforced

- robots evaluated per candidate path (fail-closed, gzip-aware) — now also on sitemap probes
- host equality checked at normalise, at discovery, at enqueue, at dequeue
- `normalize_public_url` + `PublicUrlPolicy` (SSRF / public-IP / DNS-rebinding) on every URL
- `max_redirects=0` retained; ephemeral raw body retained
- `phase1-minimizer@2` byte-for-byte unchanged; quarantine on unsafe pages retained
- one evidence item ↔ one page snapshot; no cross-page text merge
- kill switch: `_discover` returns early and `_fetch_sitemap` no-ops when suspended → zero probes
- coverage record records category **public absence** as public absence only

Covered by `tests/test_m1_frontier.py`, `tests/test_m1_sitemap.py`,
`tests/test_m1_v2_bounded_site_crawl.py` (10 synthetic-site scenarios: sitemap discovery +
prioritisation, deterministic coverage record, M2-signal spread, cross-host rejection, robots
exclusion, gzip sitemap, query-loop bound, useful-page hard cap, no-sitemap link fallback, v1
path untouched) and `tests/test_m67_deployed_synthetic_validation.py` (`BOUNDED_SITE_CRAWL_V1`
multi-page proof + determinism + kill-switch block).

---

## 2. Deployment — DONE (`phase1-m1-v2-deployment-2026-08-30.json`)

| Step | Result |
|---|---|
| Thin successor image (chain link 6, protocol-upgrade, `Dockerfile.window2-m1v2-bounded-site-crawl` FROM `sha256:47de97de…`) | `sha256:62ba45aa295b912a578676dd440c75525206757878242e679923764b61c009e4` — 19 base layers + 1; COPY-only, no dependency/entrypoint/config change |
| Representation equivalence | `LOCAL_REPRESENTATION_EQUIVALENT_PROVEN` + `REPRESENTATION_EQUIVALENT_PROVEN`; reproduced registry manifest byte-equal to registry (`phase1-m1-v2-{local,registry}-image-identity-2026-08-30.json`) |
| ECR scan | COMPLETE, critical/high/blocking **0/0/0** |
| M2 rules / compliance / minimiser | `rules.py` `5575c3a4…` and `compliance_application.py` `99ef700e…` **byte-identical** in predecessor and successor images; `phase1-minimizer@2` |
| ADR-0075 Terraform | plan (workload-plan) → semantic review (image digest sole meaningful change) → apply (workload-apply): 4 add / 3 change / 4 destroy → **NO_CHANGES**. Task defs research-worker:21 / intelligence-worker:18 / controlled-egress:17 / sampled-slot-activator:17 |
| State-convergent DB migration (live RDS, transient Fargate) | `research_pages.page_purpose`, `research_evidence.fact_class`, `research_runs.coverage_record_sha256` present; `research_discovery_edge` + `research_coverage_record` present with intended columns; `converged: true`; immediate second `initialize()` a strict no-op; **historical rows preserved** (only the synthetic run's own rows added, no pre-existing/Slot 01 row deleted) |
| In-cluster `KILL_SWITCH_BLOCK_V1` | real kill switch TRIPPED → run FAILED, no fetch, no snapshot — v2 fetch path is suspended by the real switch |
| In-cluster `BOUNDED_SITE_CRAWL_V1` | `succeeded`, protocol `phase1-m1@2-bounded-site-crawl`, 4 pages captured, `commercial_hvac` + `request_service_scheduling` captured, `/privacy` excluded, no cross-host, no prohibited/contact data, coverage counters consistent, stop reason `["frontier_exhausted"]`, 9 discovery edges + coverage record `2d012945…` persisted, per-page provenance intact. No real Phase 1 company touched (host `synthetic.invalid`, image-embedded fixture) |
| Final dormant state | kill switch TRIPPED (never moved), release `CONSUMED`, approval + egress-lease `NOT_AUTHORIZED`, services 0/0/0, zero tasks, Terraform NO_CHANGES |

**Hard stop reached.** No Slot 02, no real company crawl.

---

## 3. Live-materializer wiring — for the READY_FOR_SLOTS02_06 batch authorization

The sealed envelope (§1) is a document. Making a **live sampled-slot release carry** the v2 bounds
so the deployed activator builds a v2 `CrawlPolicy` requires code that **only affects real Slot
02–24 execution** — which the current authorization does not permit and the batch authorization
does. It is small and additive:

| File | Change |
|---|---|
| `packages/shadow-core/.../gate_domain.py` | `LiveResearchPermissionRelease`: `+ crawl_protocol_version: str \| None = None`, `+ max_useful_page_fetches: int \| None = None` (optional; v1 releases unaffected) |
| `workers/research/.../activation.py` | `release_execution_ceilings_sha256`: include the two new fields **iff present** (v1 hash unchanged). `_policy`: when `release.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"`, build the v2 `CrawlPolicy` from the envelope §7 ceilings + `max_useful_page_fetches` and set `crawl_protocol_version` on the `ResearchRun` |
| `workers/research/.../authorization.py` | `authorize()`: when the run is v2, assert `run.policy` equals the v2 `_policy(release)` output (replaces the hard-coded v1 `min(10, max_logical_requests)` comparisons) |
| `workers/research/.../authority_materialization.py` | emit `crawl_protocol_version` + `max_useful_page_fetches` + the raised numeric ceilings. Source of the raised numbers: a **new sealed owner statement carrying the v2 ceiling numbers**, or this envelope bound by its `execution_ceilings_sha256`. Owner to choose. |
| tests | v2 activation / authorization / materialization round-trip; v1 unaffected |

---

## 4. What the batch authorization should decide

`READY_FOR_SLOTS02_06_PHASE1_M1_V2_EXECUTION_AUTHORIZATION` — a **single** batch gate for
Slots 02–06 under the frozen `phase1-m1@2-bounded-site-crawl` protocol and the sealed envelope,
**not** one authorization per slot and **not** another chain of mechanical implementation
approvals. It would green-light: the §3 live-materializer wiring; per-slot A-09 exact-host
decisions for slots 02–06 (if not already accepted); five bounded real first-party crawls under
the v2 envelope; deterministic offline M2→M5 per slot to the `CONTACT_PHASE_NOT_AUTHORIZED`
terminal; no contact phase, no outreach, no new host scope, no M2 threshold change.
