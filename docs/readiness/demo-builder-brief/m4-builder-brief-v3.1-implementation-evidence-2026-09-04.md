# M4 builder-brief V3.1 — implementation evidence (owner authorization 2026-09-04)

Owner authorization 2026-09-04 "M4 BUILDER-BRIEF V3.1 CLEANUP + ELITE
PERSONALIZATION PROOF". **Presentation cleanup only** — same module
(`opintel_communication.builder_story`), version bumped `demo.builder_brief@3` →
`demo.builder_brief@3.1`. No M4 / V1 / V2 semantic change; no `opintel_demo` file
touched.

## Part I — V3.1 cleanup

### V3 → V3.1 diff

| # | V3 | V3.1 |
|---|---|---|
| 2 | headline chosen per anchor | **unchanged wording** for the response anchor (owner's stated preference) + a new authority check (`1b`) that the headline **must** carry the anchor keyword (`response` / `availab` / `request path`) and must never say `verified` / `proven` / `actual` / `measured` — it can no longer collapse into a generic "…what your public pages describe" |
| 3 | "## Reading the labels" legend rendered in the customer body | legend **removed from the default customer view**; moved to a trailing **"Semantic legend (audit / optional developer note — not the customer view)"** block after the `---`. The five distinctions stay on the machine artifact (`semantics_legend`, 5 entries, checked). |
| 4 | exception screens listed under "If something needs a person (only when triggered)" | retitled **"Exception screens"** with an explicit builder note: *"render one of these only when the simulation itself routes there. Never a user-facing selector or a way to preview them."* A hard rule forbids any state selector / test-state switcher / scenario picker / "preview a special state" control. |
| 5 | demo-mode badge already out of the body (V3) | new hard rule: no product/demo badge, mode tag, "DEMO" chip, category label or technical/semantic badge; the only persistent chrome is the disclosure line. |
| 6 | — | new **`builder_hard_rules`** (5 rules) + **`allowed_primary_actions`** (`See how it could work`, `Run simulation`) rendered as a **"Builder rules (hard limits — read first)"** section. Forbids invented functionality: exports, downloads, PDF/print, share/save, link-out, email capture, analytics, dashboards, KPI tiles, integrations, sign-in — *"you may invent visual treatment; you may not invent product functionality."* (Directly answers the builder-invented "Download summary (PDF)".) |
| 7 | Screen 2 table had a "why the field exists" column with the full evidence/safety rationale under every field | Screen 2 table now shows a short **`customer_hint`** ("Which need applies", "Example simulation location", "How urgent", …); the long `exists_because` rationale is preserved but moved to the **audit appendix only**. New check `21`: hints ≤ 6 words, no "evidence" / "public page" / "coverage promise" / "M4" / "unknown". |
| 8 | Screen 3 led straight into the 4-stage arrow | adds a concise **`result_recap_line`** then the arrow, with the render note *"the **outcome** is the hero"*; the grouped outcomes ("What could be prepared next") stay the visual focus. Result stage 2 now carries the per-anchor **`scenario_framing`**. |
| — | — | new **`scenario_framing`** field: a per-anchor story clause (response commitment → *"a commercial request, organized and summarized so a person can pick it up"*; service availability → *"a service request that could come in at any time, organized so a person can pick it up"*; intake surface → *"a scheduling or service-call request, …"*). Never pairs availability/response with a speed or response verb (checks `13`, `20`). |

### `_assert_story_within_authority` — new checks (21 total; V3 had 15)

`1b` headline carries the anchor keyword and implies no verified performance ·
`16` semantic legend keeps all five distinctions on the artifact ·
`17` `allowed_primary_actions` == exactly the Screen 1 + Screen 2 actions ·
`18` hard builder rules cover download / export / state selector / badge /
"clickable" · `19` result recap stays concise and claims no real action ·
`20` scenario framing present, unstrengthened, never availability→response ·
`21` Screen-2 customer hints concise and free of architecture wording.

### Section-11 regression results

`tests/test_m4_builder_brief_v3.py` — **27 passed** (16 V3 section-19 invariants +
2 baseline + **7 new V3.1** + **2 Elite personalization**):

| V3.1 test | proves |
|---|---|
| `test_v31_ontology_legend_not_in_default_customer_view` | legend never a section/bullet-list in the body for A-Plus / Elite / E+M; still in the appendix; 5 entries on the artifact |
| `test_v31_no_debug_or_special_state_controls_in_normal_experience` | no state selector / test-state / scenario picker / "preview a special state" in the rendered screens; exception screens are a builder note |
| `test_v31_builder_cannot_invent_unlisted_functionality` | `allowed_primary_actions` is exactly the two; hard rules name download/export/pdf/share/analytics/dashboard; dropping an action → **raises** |
| `test_v31_internal_evidence_and_semantic_metadata_preserved` | `exists_because`, `value_semantics`, `m4_option_labels`, all six `internal_mock_actions`, `demo_mode` + `story_compiler_version` audit rows all survive |
| `test_v31_stronger_headline_cannot_exceed_evidence_strength` | headline carries `response`, no `verified`/`proven`/`fast`/`guarantee`; a "verified response speed" headline **raises**; an anchor-less headline **raises** |
| `test_v31_screen2_customer_hints_are_concise` | every hint 1–6 words, no "evidence"/"public page"; the long rationale ("without making any coverage promise", "so the simulation asks which need applies") is **not** in the body |
| `test_v31_result_still_preserves_grouped_mock_action_meaning` | 3 groups cover the six mock actions exactly once; recap concise |

Repository gates: **full suite 1189 passed / 3 skipped** (was 1180; +9).
`ruff check` + `ruff format --check` + `mypy --strict` clean on every new/changed
file (`mypy` clean over all 25 `opintel_communication` files). **No file under
`opintel_demo` changed. No existing non-V3 test changed** (only
`test_m4_builder_brief_v3.py`'s own version assertion was updated to `@3.1`).

### A-Plus V3.1 — what a reviewer sees

- Screen 1 headline: *"One way structured intake could support the response
  experience your public pages already describe"* (unchanged wording, now
  guaranteed anchor-tied).
- "Builder rules (hard limits — read first)" section forbids the "Download
  summary (PDF)" class of builder invention; only `See how it could work` and
  `Run simulation` are interactive.
- Screen 2: concise hints, no per-field architecture paragraph.
- Screen 3: a one-line recap, then the 4-stage story, then the grouped outcomes
  as the hero.
- No legend, no demo badge, no state selector anywhere in the body.

## Part II — Elite personalization proof

Full write-up: **`m4-aplus-vs-elite-personalization-2026-09-04.md`**.

Elite compiled with the **same** `compile_builder_story` from
`tests/m68_fixtures.elite_envelope()` (frozen; no re-research, no web).

| | A-Plus | Elite |
|---|---|---|
| primary anchor | `response commitment` | `service availability` |
| headline | "…support the **response experience**…" | "…complement the **service availability**…" |
| opportunity summary | "…published **response-time message**…" | "…published **availability message**…" |
| scenario framing | "a commercial request, organized and summarized so a person can pick it up" | "a service request **that could come in at any time**, organized so a person can pick it up" |
| evidence bullets | 3 (incl. `"When to Schedule AC Replacement"`) | 4 (incl. `"Need to schedule a service call?"`, `"Just a Sample of Our Service Areas"`) |
| Screen 2 / result mechanics | shared (section 14) | shared (section 14) |

**Blind test:** with names hidden, a reviewer still sees a different anchor, a
different quoted public signal, a different quoted intake phrase, and a different
scenario premise — all downstream of the two envelopes' different eligible facts.

**Verdict: `PERSONALIZATION_PROOF_PASSED`** — with the honest scoping that the
distinctiveness is entirely in the opportunity layer; the intake mechanics are
deliberately shared, as section 14 permits. Elite's 24-hour availability is used
as **context only** and is never upgraded into a response/acknowledge/dispatch
claim (enforced by the availability→response check, which runs identically for
both).

## Confirmation — authoritative M4 unchanged

- `git status` touches only `communication-core`, `tests/`, `scripts/`, `docs/`.
- Both briefs are projections of the V2 experience → V1 brief; the full
  `_assert_within_authority` M4 check runs first and unchanged.
- Every UNKNOWN, prohibition, mock-only semantic, deployment status and safety
  routing survives in the machine artifact + audit appendix; all six mock actions
  preserved verbatim for both businesses.

## Stop condition

Emergent / Lovable / Base44 not used, not automated. No deployment, no external
links. **STOPPED — A-Plus V3.1 + Elite V3.1 + the personalization comparison are
returned for PROJECT_OWNER + ChatGPT review.** The PROJECT_OWNER will manually
paste Elite into Emergent after review. No E+M, no M5/M6.8 change, no M6.8-4, no
contact.
