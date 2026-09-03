# M4 builder-brief V3 — implementation evidence (owner authorization 2026-09-03)

Owner authorization 2026-09-03 "M4 BUILDER-BRIEF V3: OPPORTUNITY -> EXPERIENCE ->
HANDOFF". V2 (`demo.builder_brief@2`) collapsed the internal state machine into a
three-screen human experience. V3 is a **further presentation projection** — it
changes nothing about M4 authority, the V1 brief, or the V2 experience semantics —
and reframes the same three screens as a short opportunity story:

    1. We noticed this  ->  2. Here is how it could work  ->  3. Here is what your
    team could receive  ->  4. Imagine it fitted to your real process

Externally V3 optimises for **comprehension + relevance + desire**; M4 keeps
optimising internally for **truth + safety + provenance**.

## 1. What changed (and what did not)

| | |
|---|---|
| **M4 authoritative internals** | **UNCHANGED.** `git status packages/demo-core/` is empty. No `opintel_demo` file touched. |
| **V1 `demo.builder_brief@1`** | UNCHANGED. Still the audit-grade brief, still runs the full fail-closed M4-authority check. |
| **V2 `demo.builder_brief@2`** | UNCHANGED. No file in `builder_experience.py` modified; V2's 20 tests still pass. |
| **NEW `opintel_communication.builder_story`** | `demo.builder_brief@3` — `compile_builder_story(envelope, skeleton=None) -> BuilderStory` + `render_builder_story_markdown()` + `BuilderStoryAuthorityError` + `_assert_story_within_authority` (15 story-level checks). Pure deterministic; **builds on the V2 `BuilderExperience`** (so it inherits V1's *and* V2's fail-closed checks — `underlying_experience_sha256` + `underlying_brief_sha256` are recorded). |

### V2 → V3 diff (presentation only)

| V2 | V3 |
|---|---|
| Screen 1 titled "Opportunity"; a `**Demo mode:** BESPOKE_DEMO` badge printed in the body | Screen 1 title **is the opportunity headline** ("One way structured intake could support the response experience your public pages already describe"); demo-mode badge removed from the UI, kept in the audit appendix only |
| "What we actually saw on the public site" list, always visible | "Why we built this" — **collapsed** `<details>` by default; licensed public evidence only when opened |
| `service_need` / `service_location` options were the **M4 evidence-derived labels** ("When to Schedule AC Replacement", "Service Area") — the V2 "known tension" | every selectable value is an explicit **`SYNTHETIC_DEMO_INPUT`** ("Repair request", "Example service location", …); an evidence phrase is never a pick; the M4 labels are retained in `m4_option_labels` for audit. New `EVIDENCE_CONTEXT` vs `SYNTHETIC_DEMO_INPUT` distinction: public evidence justifies that a *field* exists (`exists_because`), not its literal value. |
| Screen 3 led with "Request details organized / Urgency captured / …" (restates the user's input) | Screen 3 is a **4-stage workflow story**: Request → Structured context → Example human review → Next workflow preparation |
| six "Prepare …" previews rendered flat | grouped into **three** customer outcomes — **Lead record** / **Human follow-up** / **Scheduling context** — each mapping to its internal mock-action ids; all six preserved verbatim in `internal_mock_actions` + the audit appendix |
| closing thought a trailing line | **closing bridge** is its own prominent section heading ("Imagine this fitted to your actual intake process …"), explicitly "not a call to action" |
| — | new `builder_visual_guidance` (Emergent polish + Lovable opportunity framing + Base44 simplicity, expressed as qualities, **no builder brand names**) + `company_visual_character` ("premium neutral commercial-software", no brand assets authorized) |
| — | new `semantics_legend` — the five artifact distinctions (`PUBLIC_EVIDENCE` / `UNKNOWN` / `SYNTHETIC_DEMO_INPUT` / `FICTIONAL_DEMO_PLACEHOLDER` / `SIMULATED_OUTPUT`) rendered as plain language ("Public evidence", "Synthetic demo input", …), never the enum names |

## 2. Compiler design (`demo.builder_brief@3`)

`compile_builder_story` → `compile_builder_brief` (V1) + `compile_builder_experience`
(V2, which itself runs the V1 M4-authority check) → project into the story model →
`_assert_story_within_authority`.

### `_assert_story_within_authority` — 15 story-level checks on top of V1 + V2

0. the underlying V2 experience (hence the V1 brief) still passes its full check;
1. opportunity headline: framed as a possibility ("could"), ≤ 20 words, no
   strengthening word, never quotes a non-quotable evidence phrase;
2. no internal ontology / demo-mode value / hash / `@n` version / `[A-Z_]{5,}`
   enum in any customer-facing string;
2b. V3-authored copy introduces no CRM/vendor name and no economics/performance
   term that is not already in a licensed phrase;
3. every form value is marked `SYNTHETIC_DEMO_INPUT`; no value equals an eligible
   fact's sanitized/verbatim phrase; "Safety concern" still maps to M4
   `safety_critical`;
4. synthetic values are short and digit-free (look illustrative, not like real
   data) and appear in `synthetic_input_values`;
5. exactly three outcome groups; every registered mock action mapped **exactly
   once**; group copy never uses a completed-action verb;
6. `internal_mock_actions` byte-equals the fixed skeleton (all six preserved);
7. result story is a 4-stage ordered workflow; no stage claims a real action; the
   human stage leads with the **role**, never the fictional name;
8. the fictional placeholder stays disclosed as fictional; the story never
   "sends to `<name>`" and never says the person is real;
9. closing bridge is byte-equal to the approved V2 closing thought, keeps
   "imagine … hypothetical", asserts nothing about the real current process, and
   carries no ROI / urgency / meeting pitch;
10. persistent + result disclosures keep "not connected" / "nothing was sent";
11. evidence detail is exactly the V2 licensed public context, tagged
    `PUBLIC_EVIDENCE`;
12. the semantics legend covers the five distinctions in plain language with no
    enum name exposed;
13. an availability phrase is never rendered with response wording in an
    affirmative sentence;
14. `RESPONSE_PERFORMANCE` is UNKNOWN → no response-speed pairing anywhere;
15. no inferred geography.

## 3. Section-19 regression results

`tests/test_m4_builder_brief_v3.py` — **18 passed** (16 named section-19
invariants + version/determinism + three-screen shape).

| invariant | test |
|---|---|
| authoritative M4 semantics unchanged | `test_1_*` — skeleton == composer statics; `underlying_brief_sha256` == V2's; `internal_mock_actions` == the fixed six |
| opportunity headline cannot strengthen the anchor | `test_2_*` — no fast/quick/immediate/guarantee/24-7/same-day/always in any headline; a "respond faster than any other contractor" headline → **raises** |
| builder mode / internal taxonomy does not leak | `test_3_*` — none of `bespoke_demo` / `demo.builder_brief` / `mock_only` / `not_connected` / `response_commitment` / `safety_critical` in customer copy or the rendered body |
| evidence phrases aren't auto-converted into selectable inputs | `test_4_*` — no field value intersects the fact phrases; "Service Area" / "When to Schedule AC Replacement" absent; the field still exists (`exists_because`) and keeps `m4_option_labels` for audit |
| synthetic input values are explicitly synthetic | `test_5_*` — every field `value_semantics == SYNTHETIC_DEMO_INPUT`; the md says "illustrative simulation choice" |
| fictional human remains fictional | `test_6_*` — disclosure fictional/not-a-real-person; result story uses the role, never "Morgan"; no "sent/assigned/routed to Morgan" |
| outcome groups preserve underlying mock-action meaning | `test_7_*` — 3 groups; union of ids == the registered six; disjoint |
| grouping actions cannot imply they occurred | `test_8_*` — no was/were/has-been/sent/dispatched/created in group copy; "The lead record was sent to your CRM." → **raises** |
| no CRM / vendor is invented | `test_9_*` — no ServiceTitan/Housecall/Jobber/Salesforce/HubSpot in V3-authored copy; "Ready for your ServiceTitan account." → **raises** |
| no location is inferred | `test_10_*` — no austin/dallas/houston in customer copy |
| no response performance is inferred from response positioning | `test_11_*` — no "responds … minutes/fast"; "show you respond in minutes" headline → **raises** |
| closing bridge cannot become a current-process assertion | `test_12_*` — has "imagine"/"hypothetical"; "Your current intake process is losing you leads" and "Book a call today …" → **raise** |
| safety and UNKNOWN semantics remain intact | `test_13_*` — 3 exception triggers; safety body keeps non-dispatch + human, no phone; "don't know" in the unknown summary; "Safety concern" ⇒ M4 `safety_critical`; V1 brief still carries every UNKNOWN component |
| result story is a 4-stage workflow | `test_14_*` — orders (1,2,3,4); labels Request / Structured context / Example human review / Next workflow preparation; no "was sent/dispatched/booked/created" |
| semantics legend is plain language only | `test_15_*` — the five plain labels; no `_` and no `[A-Z]{4,}` in any legend value |
| evidence detail is collapsed licensed context only | `test_16_*` — `evidence_detail` text == V2 `known_public_context`; md renders a `<details>` block |

Repository gates: **full suite 1180 passed / 3 skipped** (was 1162; +18).
`ruff check` + `ruff format --check` + `mypy --strict` clean on every new/changed
file (`mypy` clean over all 25 `opintel_communication` source files). **No file
under `opintel_demo` changed. No existing test changed.** V1 + V2 tests all still
pass.

## 4. Section-18 acceptance questions — A-Plus V3

| question | answer |
|---|---|
| **Opportunity** — does Screen 1 make clear why this exists *for this company*? | Yes. The screen title *is* the opportunity ("One way structured intake could support the response experience your public pages already describe"), anchored on A-Plus's own **published response-time message**. The 44-word summary says what was seen publicly, what the simulation explores, and what is unknown. |
| **Speed** — usable in under ~60 seconds? | Yes. One headline + one action; one calm 6-field form; a 4-step visual result. `ux_targets`: ~10s / ~20–30s / ~10–20s. |
| **Humanity** — does the result feel like a workflow the team could use? | Yes — Request → Structured context → Example human review → Next workflow preparation, an example *Intake coordinator* (fictional, disclosed), and three plain outcomes (Lead record / Human follow-up / Scheduling context). |
| **Imagination** — does Screen 3 encourage "what would this look like with our real process?" | Yes — the closing bridge is its own prominent section: *"Imagine this fitted to your actual intake process rather than this hypothetical one."* |
| **Truth** — are all real-company claims still evidence-bound? | Yes. Inherits the V1 + V2 fail-closed checks; the headline is generated from the licensed anchor category and cannot strengthen it; every form value is synthetic; persistent + result disclosures intact. |
| **Synthetic clarity** — can a user tell illustrative inputs/people/results from facts about the company? | Yes. Screen 2 says every value is "an illustrative simulation choice, not a fact about A-Plus"; the handoff card is labelled fictional; the "Reading the labels" legend spells out the five distinctions in plain language. |
| **Restraint** — have we removed detail that shows our architecture but adds little customer value? | Yes — the demo-mode badge, the evidence-phrase form values, the flat six-action list and the always-open provenance list are gone from the UI; all of it remains in the machine artifact + audit appendix. |

## 5. A-Plus V3 — selections

| | |
|---|---|
| **story version** | `demo.builder_brief@3` |
| **demo mode (audit only, not shown)** | `BESPOKE_DEMO` |
| **primary anchor** | published response-time message (`response_commitment`) |
| **opportunity headline** | *"One way structured intake could support the response experience your public pages already describe"* |
| **opportunity summary (44 words, inherited from V2)** | *"Your public pages emphasize commercial HVAC repair and feature a published response-time message. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance."* |
| **Screen 2 fields** | Service need · Facility · Service location · Urgency · Equipment (optional) · Preferred follow-up — **all values `SYNTHETIC_DEMO_INPUT`** |
| **synthetic `service_need` values** | Repair request / Maintenance visit / Replacement or quote / Other / Not sure |
| **synthetic `service_location` values** | Example service location / Other / Not sure |
| **Screen 3 result story** | Request → Structured context → Example human review → Next workflow preparation |
| **human handoff** | **Morgan — Intake coordinator** (`FICTIONAL_DEMO_PLACEHOLDER`; disclosed fictional; the result story leads with the *role*) |
| **grouped customer-facing outcomes** | **Lead record** (`CREATE_INTAKE_RECORD`, `CREATE_CRM_LEAD`) · **Human follow-up** (`QUEUE_HUMAN_CALLBACK`, `NOTIFY_DISPATCH`, `CREATE_ACKNOWLEDGMENT_PREVIEW`) · **Scheduling context** (`REQUEST_SCHEDULING_REVIEW`) |
| **closing bridge** | *"Imagine this fitted to your actual intake process rather than this hypothetical one."* |
| **disclosures** | persistent *"Simulation · not connected to A-Plus"* · Screen 1 explicit unknown-process sentence · fictional-placeholder note · result *"Nothing was sent, booked, dispatched, or updated."* |
| **exception branches** | `safety_critical` · `out_of_scope` · `mock_error` (unchanged from V2) |
| **evidence used** | all 4 eligible A-Plus facts — response-time message = headline anchor; commercial + intake justify the `service_need` field; service-area justifies the `service_location` field |
| **evidence omitted** | none |
| **UNKNOWNs (still enforced, audit layer)** | RESPONSE_PERFORMANCE, DEMAND_VOLUME, CONVERSION, CUSTOMER_VALUE, CURRENT_PROCESS, COST, FEASIBILITY, INTEGRATION |
| **forbidden additions** | the V1/V2 negative spec, carried through |

## 6. Frozen source (unchanged from V1/V2)

`tests/m68_fixtures.aplus_envelope()` — envelope sha256
`c5a6307f4427d450359946b87d64cecd43f090ed28946c90bd175eaa2b0b380e`, m2_m5 bundle
`a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7`. **No
re-research, no web, no new evidence.**

## 7. Artifacts

| artifact | path |
|---|---|
| V3 compiler + renderer + authority check | `packages/communication-core/src/opintel_communication/builder_story.py` |
| V3 regression tests (18) | `tests/test_m4_builder_brief_v3.py` |
| generator (V1 + V2 + V3) | `scripts/generate_aplus_builder_brief.py` |
| **A-Plus V3 machine-readable** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v3-2026-09-03.json` |
| **A-Plus V3 paste-ready brief (.md)** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v3-2026-09-03.md` |
| this evidence doc | `docs/readiness/demo-builder-brief/m4-builder-brief-v3-implementation-evidence-2026-09-03.md` |

Schema / compiler version: `demo.builder_brief@3`.
`underlying_experience_sha256`
`21395a65fa7b780fa52239661cf92febb339553ba5dfa015851124e0586aa0c2`;
`underlying_brief_sha256`
`4d9f26412893d85fc21473b65e50466433d3655275957ad3523b20323538636a` (byte-equal to
the V2 brief that passed the full M4-authority check).

## 8. Confirmation — M4 authoritative semantics did not change

- No file under `packages/demo-core/src/opintel_demo/` was modified (`git status`
  touches only `communication-core`, `tests/`, `scripts/`, `docs/`).
- V3 is a projection of the V2 `BuilderExperience`, which is a projection of the
  V1 `BuilderBrief`, whose `_assert_within_authority` (the full M4-authority
  check) runs first and unchanged.
- Every UNKNOWN, prohibition, mock-only semantic, deployment status and safety
  routing survives in the machine-readable artifact and the audit appendix; all
  six mock actions are preserved verbatim in `internal_mock_actions`.

## 9. Stop condition (section 20)

Lovable / Base44 / Emergent not used, not automated. No previously-generated demo
browsed. No deployment, no external links. **STOPPED — the A-Plus V3 builder
prompt is returned for PROJECT_OWNER + ChatGPT review.** The PROJECT_OWNER will
manually render A-Plus V3 and review it with ChatGPT. If V3 works, the next proof
is **Elite** (does the same compiler make Elite feel meaningfully different from
A-Plus using only Elite's evidence?) — not started; needs explicit authorization.
No Elite, no M6.8-4, no M5 change, no outreach, no contact resolution, no send.
