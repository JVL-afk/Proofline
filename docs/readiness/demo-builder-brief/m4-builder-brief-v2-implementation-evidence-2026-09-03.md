# M4 builder-brief V2 — implementation evidence (owner authorization 2026-09-03)

Owner authorization 2026-09-03 "M4 HUMAN-EXPERIENCE SIMPLIFICATION / BUILDER-BRIEF
V2". V1 was accurate but commercially overcomplicated — it exposed the internal
state machine to the customer. V2 keeps every M4 truth, evidence, UNKNOWN, safety,
provenance, mock-action and deterministic-workflow semantic **underneath**, and
compiles a *presentation projection*: a three-screen experience a busy HVAC owner
can understand in ~60 seconds without learning our ontology.

    complex truthful M4  ->  simple human experience   (NOT a simplified truth model)

## 1. What changed (and what did not)

| | |
|---|---|
| **M4 authoritative internals** | **UNCHANGED.** No file in `opintel_demo` changed. `opintel_demo.scenario` (`demo.scenario_skeleton@1`, added in V1) is still a read-only re-export. The authoritative `SemanticEnvelope` / `DemoSpecification` are untouched. |
| **V1 `demo.builder_brief@1`** | UNCHANGED. Still compiled, still the audit-grade artifact, still runs the full fail-closed M4-authority check. |
| **NEW `opintel_communication.builder_experience`** | `demo.builder_brief@2` — `compile_builder_experience(envelope, skeleton=None) -> BuilderExperience` + `render_builder_experience_markdown()` + `BuilderExperienceAuthorityError` + `_assert_experience_within_authority` (12 additional customer-experience checks). It is a pure deterministic function that **builds on the V1 `BuilderBrief`** (so it inherits V1's M4-authority guarantee — the underlying brief's sha256 is recorded) and projects it into the 3-screen model. |

### V1 → V2 diff (presentation only)

| V1 | V2 |
|---|---|
| 17-step workflow table mirroring the state machine | **3 screens** — Opportunity / Simulation input / Result-handoff (+ 3 exception screens only when triggered) |
| full evidence table with `FactCategory` / `FactStrength` enums | plain "what we saw on the public site" bullets (progressive disclosure), enums hidden |
| `demo_objective` + `central_demo_story` (2 paragraphs) | one **40–50 word** deterministic `opportunity_summary` (evidence + proposed simulation + explicit unknown) — A-Plus: **44 words** |
| `unknowns` list with `RESPONSE_PERFORMANCE` / `CURRENT_PROCESS` component names | one plain `unknown_summary` sentence; the component list stays in the machine-readable audit layer |
| `mock_actions` = `CREATE_INTAKE_RECORD` … as primary labels | `prepared_actions` = "Prepare intake record" … ; raw ids only in the audit appendix |
| `{{functional_role_or_team}}` disclosure slot shown literally | a `FICTIONAL_DEMO_PLACEHOLDER` (name + role + concise fictional-disclosure); the `{{…}}` token never reaches customer copy |
| 7 disclosure rows | 4 quiet, strategically-placed disclosures (persistent top indicator; opportunity "what we don't know"; fictional-placeholder note; result footer) |
| `ux_presentation_brief` paragraph | `builder_freedom` (visual = free) + `ux_targets` (~60s, ~10/20-30/10-20) |

## 2. Compiler design (`demo.builder_brief@2`)

`compile_builder_experience` → `compile_builder_brief` (V1, runs the M4-authority
check) → project → `_assert_experience_within_authority`.

### Deterministic translation tables

- `_MOCK_ACTION_LABEL` — internal id → "Prepare …" label (verbs restricted to
  prepare / preview / simulate).
- `_FIELD_META` + fixed option lists — internal M4 question id → friendly label +
  control; **`service_need` / `service_location` options are the exact V1-brief
  labels** (evidence-derived, M4-licensed); "Urgency → Safety concern" == M4
  `safety_critical`.
- `_FICTIONAL_NAMES` + `_HANDOFF_ROLE` — one placeholder, name chosen
  deterministically by `sha256(display_name) % len(pool)`, role fixed to a role
  compatible with the M4 human-handoff step; disclosure always emitted.

### `_assert_experience_within_authority` (12 checks on top of the V1 check)

0. the underlying V1 brief still passes the full M4-authority check;
1. `opportunity_summary` is 30–50 words and carries all three ideas (noticed
   publicly / simulation proposes / unknown);
2. **no `{{…}}` token and no internal-ontology token** (`MOCK_ONLY`,
   `NOT_CONNECTED`, state ids, `RESPONSE_COMMITMENT`, strength enums, `demo.*@n`
   versions, 16+ hex ids, `[A-Z_]{5,}` enums) in any customer-facing string;
3. every fictional placeholder has a name + role + a disclosure that says
   "fictional" / "not a real person" and never implies employment;
   result copy never reads "assigned/sent/routed to `<name>`";
4. `prepared_actions` = exactly the registered mock-action set, deterministic
   labels, prepare/preview/simulate verbs only;
5. result / exception sentences never claim a real action (`sent`, `dispatched`,
   `booked`, `updated`, …) unless the sentence is explicitly negated / simulated;
6. `SERVICE_AVAILABILITY` / `RESPONSE_COMMITMENT` phrases are never a form option;
7. `service_need` / `service_location` options equal the V1 brief exactly;
8. an availability phrase is never rendered with response wording in an
   affirmative customer sentence;
9. `RESPONSE_PERFORMANCE` is UNKNOWN → no response-speed assertion;
10. all three exception screens present; the safety screen keeps its
    non-dispatch / human-process meaning and fabricates no phone number;
11. generic / thin evidence says "generic" in the opportunity summary and never
    manufactures a "built around your …" claim;
12. persistent + result disclosures keep "not connected" / "nothing was sent".

## 3. Section-18 regression results

`tests/test_m4_builder_brief_v2.py` — **20 passed**. Named invariants:

| # | invariant | test |
|---|---|---|
| 1 | internal M4 state / safety semantics unchanged | `test_1_*` — skeleton == composer statics; exact `SAFETY_HANDOFF_MESSAGE`; exact 6 mock actions |
| 2 | 3-screen path is a projection, not an authority change | `test_2_*` — `underlying_brief_sha256` == V1 brief sha; option lists == V1 |
| 3 | opportunity summary ≤ 50 words | `test_3_*` — A-Plus 44, Elite 44, E+M 46 |
| 4 | opportunity summary has evidence + simulation + explicit unknown | `test_4_*` — "public pages" / "simulation" / "don't know"; a 3-word summary → **raises** |
| 5 | fictional names cannot be company facts | `test_5_*` — placeholder name ∉ evidence words, ≠ business name |
| 6 | fictional-placeholder disclosure always emitted | `test_6_*` — "fictional" + "not a real person" for every fixture; stripping it → **raises** |
| 7 | internal unresolved tokens never leak | `test_7_*` — no `{{`, `}}`, `functional_role_or_team` in customer copy or md body |
| 8 | mock-action ids not required in normal customer UI | `test_8_*` — labels start "Prepare …", raw ids only in the appendix |
| 9 | customer labels semantically equivalent to internal | `test_9_*` — `{id: label}` == the fixed mapping; exact registered set |
| 10 | result never implies a real action | `test_10_*` — "nothing was sent" present; "was dispatched" line → **raises** |
| 11 | result never implies the fictional role/person exists at the company | `test_11_*` — no "employee"/"on staff"/"<name> works"; "Assigned to <name>" line → **raises** |
| 12 | safety exception still routes correctly | `test_12_*` — 3 triggers; safety body keeps non-dispatch + human meaning, no phone number; "Safety concern" ⇒ M4 `safety_critical` |
| 13 | UNKNOWNs remain UNKNOWN | `test_13_*` — "don't know" in copy; V1 brief still carries every component; no "responds fast/quick/minutes" |
| 14 | availability cannot become response behaviour | `test_14_*` — Elite copy check; "…availability means the team responds…" → **raises** |
| 15 | no fake CRM / integration / metrics | `test_15_*` — "Connected to your ServiceTitan" / "response time 11 minutes" → **raises** |
| 16 | thin evidence still downgrades | `test_16_*` — E+M → `GENERIC_CAPABILITY_DEMO`; E+M − commercial → `DEMO_NOT_DISTINCTIVE_ENOUGH`; both say "generic" |
| 17 | ontology never surfaces in customer copy | `test_17_*` — none of `mock_only` / `not_connected` / `response_commitment` / `current_process` / `published_self_claim` / `observed_public_text` / `human_handoff` |
| 18 | persistent + result disclosures preserve meaning | `test_18_*` — "not connected", "nothing was sent"; closing line "Imagine this fitted…" carries no ROI / urgency / scheduling pitch |

Repository gates: **full suite 1162 passed / 3 skipped** (was 1142; +20).
`ruff` + `ruff format --check` + `mypy --strict` clean on every new/changed file.
**No file under `opintel_demo` changed. No existing test changed.** V1
(`demo.builder_brief@1`) tests all still pass.

## 4. Section-17 acceptance questions — A-Plus V2

| question | answer |
|---|---|
| **Comprehension** — under 60 seconds? | Yes. Screen 1 is a 44-word statement + one action. Screen 2 is a single 6-field form (no wizard). Screen 3 is a one-line recap + four checkmarks + a clearly-fictional handoff card. `ux_targets`: ~10s / ~20–30s / ~10–20s. |
| **Relevance** — arises from something genuinely observed about A-Plus? | Yes. The story anchor is A-Plus's own **published response-time message** (`PUBLISHED_SELF_CLAIM`), and the intake surface is A-Plus's own public request-path wording. Screen 1 says exactly what was seen on the public site. |
| **Desire** — "I can imagine having this in my business"? | The form fields are A-Plus's own public service labels; the result is a recognisable "request prepared for a person to pick up" flow; the closing line invites the owner to picture it fitted to their real process. It creates the desire without a pitch. |
| **Truth** — explicit about public evidence vs. hypothetical vs. unknown internal process? | Yes. Persistent "Simulation · not connected to A-Plus"; Screen 1 "We don't know your current internal process, systems, staffing, or response performance"; the handoff card is labelled fictional; the result footer says nothing happened. |
| **Simplicity** — any element present only because the architecture contains it? | Removed from the presentation layer: the 17 state ids, the transition guards, `MOCK_ONLY`/`NOT_CONNECTED` badges as primary UI, the `FactCategory`/`FactStrength` enums, the source hashes, the raw mock-action ids. They remain in the machine-readable artifact + audit appendix. |
| **Humanity** — feels like a useful business workflow, not a state-machine debugger? | Yes — three screens, plain verbs ("Prepare intake record"), a named (fictional, disclosed) coordinator, a result that answers "so what would this do for my business?". |

## 5. Frozen source (unchanged from V1)

`tests/m68_fixtures.aplus_envelope()` — envelope sha256
`c5a6307f4427d450359946b87d64cecd43f090ed28946c90bd175eaa2b0b380e`, m2_m5 bundle
`a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7`. **No
re-research, no web, no new evidence.**

## 6. A-Plus V2 — selections

| | |
|---|---|
| **experience version** | `demo.builder_brief@2` |
| **demo mode** | `BESPOKE_DEMO` |
| **primary anchor** | published response-time message (`response_commitment`, `PUBLISHED_SELF_CLAIM`) |
| **opportunity summary (44 words)** | *"Your public pages emphasize commercial HVAC repair and feature a published response-time message. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance."* |
| **simulation input (one page)** | Service need · Facility · Service location · Urgency · Equipment (optional) · Preferred follow-up |
| **`service_need` options** | `When to Schedule AC Replacement`, `Commercial Air Conditioning Repairs`, `other`, `unknown` — A-Plus's own public labels (M4-licensed, shown verbatim) |
| **`service_location` options** | `Service Area`, `other`, `unknown` |
| **result** | "Request prepared for human review" + one-line recap + ✓ organized / ✓ urgency / ✓ follow-up / ✓ human review required |
| **fictional placeholder** | **Morgan — Intake coordinator** (`FICTIONAL_DEMO_PLACEHOLDER`); disclosure: *"Morgan is a fictional demo placeholder, not a real person. We don't know how A-Plus assigns or handles requests internally — the role is illustrative only."* |
| **prepared previews** | Prepare intake record · Prepare lead for CRM · Prepare callback task · Prepare dispatch notification · Prepare scheduling review · Prepare acknowledgment preview |
| **disclosures** | persistent: *"Simulation · not connected to A-Plus"* · result: *"Nothing was sent, booked, dispatched, or updated. This was a hypothetical simulation."* |
| **closing thought** | *"Imagine this fitted to your actual intake process rather than this hypothetical one."* |
| **exception branches** | `safety_critical` ("Safety review required") · `out_of_scope` ("Outside this simulation") · `mock_error` ("Simulation hiccup") |
| **evidence used** | all 4 eligible A-Plus facts (response-time message = story anchor; commercial + intake = form options; service-area = location option) |
| **evidence omitted** | none |
| **UNKNOWNs (still enforced, in the audit layer)** | RESPONSE_PERFORMANCE, DEMAND_VOLUME, CONVERSION, CUSTOMER_VALUE, CURRENT_PROCESS, COST, FEASIBILITY, INTEGRATION |
| **forbidden additions** | the V1 30-item negative spec, carried through |

### Known tension (flagged, not resolved here)

The `service_need` options are A-Plus's own page titles ("When to Schedule AC
Replacement"), which read a little oddly as a "service need" dropdown. That is an
**M4 evidence-selection** property, not a presentation choice — the V2 compiler
is not allowed to invent friendlier option text. If the owner wants shorter
option labels, that is an M4-authority change (a display-label layer in the M4
demo composition), out of scope for this presentation-only iteration.

## 7. Artifacts (section 16 / 20)

| artifact | path |
|---|---|
| V2 compiler + renderer + authority check | `packages/communication-core/src/opintel_communication/builder_experience.py` |
| V2 regression tests (20) | `tests/test_m4_builder_brief_v2.py` |
| generator (V1 + V2) | `scripts/generate_aplus_builder_brief.py` |
| **A-Plus V2 machine-readable** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v2-2026-09-03.json` |
| **A-Plus V2 paste-ready brief (.md)** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v2-2026-09-03.md` |
| this evidence doc | `docs/readiness/demo-builder-brief/m4-builder-brief-v2-implementation-evidence-2026-09-03.md` |
| (V1, unchanged) | `m4-aplus-builder-brief-2026-09-03.{json,md}`, `m4-builder-brief-implementation-evidence-2026-09-03.md` |

Schema / compiler version: `demo.builder_brief@2`.

## 8. Confirmation — M4 authoritative semantics did not change

- No file under `packages/demo-core/src/opintel_demo/` was modified in this
  iteration (`git diff` touches only `communication-core`, `tests/`, `scripts/`,
  `docs/`).
- The V2 experience is a projection of the V1 `BuilderBrief`, whose
  `_assert_within_authority` (the full M4-authority check) runs first and
  unchanged; `underlying_brief_sha256` records it.
- `demo_scenario_skeleton()` is re-derived from `DeterministicDemoComposer`'s own
  statics; `test_1` asserts byte-equality.
- Every UNKNOWN, prohibition, mock-only semantic, deployment status and safety
  routing survives in the machine-readable artifact and the audit appendix.

## 9. Stop condition (section 19–20)

Lovable / Base44 not used, not automated. No previously-generated demo browsed.
No deployment, no external links. **STOPPED — the A-Plus V2 builder prompt is
returned for PROJECT_OWNER + ChatGPT review.** The PROJECT_OWNER will manually
paste the same brief into Lovable and Base44 and compare the results. No
Elite/E+M, no M6.8-4, no outreach change, no contact resolution, no send.
