# M4 builder-brief trim — implementation evidence (owner authorization 2026-09-03)

Owner + ChatGPT sign-off 2026-09-03 "BEGIN M4 BUILDER-BRIEF TRIM". The existing
declarative M4 demo authority is **unchanged**. A new deterministic compiler turns
it into an explicit implementation brief a human pastes into a mature builder
(Lovable etc.). First and only target: **A-Plus**. Manual workflow only — no
Lovable API, no browser automation, no deployment, no send.

## 1. Architecture (section 1–2)

```
M1–M3 evidence / opportunity authority
  → M4 deterministic demo authority   (UNCHANGED: DemoSpecification + the fixed
                                        commercial_hvac.inbound_lead_response
                                        scenario + the frozen SemanticEnvelope)
  → demo.builder_brief@1              (NEW, deterministic, no LLM)
  → human pastes the .md into Lovable / another builder
  → generated visual demo
```

The builder is a **presentation renderer**. The compiler hands it: what to build,
what it may say, what it must never imply, and how it should feel. It never hands
it business truth (integrations, CRM, response times, staffing, lead volume,
economics, conversion, internal process, "public absence = internal absence").

**M4 was not rewritten.** New code only:

| file | role |
|---|---|
| `packages/demo-core/src/opintel_demo/scenario.py` | `demo.scenario_skeleton@1` — read-only accessor for the fixed, business-independent scenario (states / transitions / question set / mock actions / handoff conditions / proposed integrations / safeguards / deployment status / safety message). Every value is re-exported from `opintel_demo.composition` / `opintel_demo.policy`; **no composition or QC behaviour changes.** |
| `packages/communication-core/src/opintel_communication/builder_brief.py` | `demo.builder_brief@1` — the deterministic compiler + `BuilderBrief` dataclass + `render_builder_brief_markdown()` + the fail-closed `_assert_within_authority` check. |
| `tests/test_m4_builder_brief.py` | the section-10 regression suite (15 tests, incl. the 11 named invariants). |
| `scripts/generate_aplus_builder_brief.py` | writes the A-Plus artifacts. |

## 2. Compiler design (`demo.builder_brief@1`)

`compile_builder_brief(envelope, skeleton=None) -> BuilderBrief` is a pure
deterministic function of two frozen inputs:

1. the target's `SemanticEnvelope` (the corrected M2–M5 authority: eligible facts
   with exact `FactCategory` + `FactStrength`, `explicit_unknowns` with hard
   prohibitions, `prohibited_claims`, `required_disclosures`,
   `mentionable_demo_facts` `may_say`/`must_not_say`, `structured_cta`,
   `economics_state`, `business_identity`);
2. the fixed M4 scenario skeleton.

It never calls an LLM, never uses a second provider, never trusts a provider
manifest.

### Demo modes (section 4)

| mode | rule |
|---|---|
| `BESPOKE_DEMO` | distinctive anchor (RESPONSE_COMMITMENT / SERVICE_AVAILABILITY / non-generic commercial or intake phrase) **and** ≥2 non-generic company facts **and** `envelope.has_distinctive_fact()` |
| `EVIDENCE_BOUND_DEMO` | ≥1 non-generic company fact, but not enough for a bespoke theme |
| `GENERIC_CAPABILITY_DEMO` | only broad category labels; brief states it demonstrates a generic capability |
| `DEMO_NOT_DISTINCTIVE_ENOUGH` | <2 facts, or no public request path, or no commercial context and no distinctive anchor |

The compiler never forces a bespoke-looking demo: E+M → `GENERIC_CAPABILITY_DEMO`;
E+M minus its commercial fact → `DEMO_NOT_DISTINCTIVE_ENOUGH`.

### Anchor ranking (section 5) — deterministic, no new truth

`RESPONSE_COMMITMENT` (100) > `SERVICE_AVAILABILITY` (90) > non-generic
`COMMERCIAL_CONTEXT` (70) > non-generic `INTAKE_SURFACE` (65) > generic commercial
(35) / generic intake (30) > non-generic service-area (20) > generic furniture
(10). Ties broken by envelope order. The compiler may choose which authorized
fact to emphasise; it may not invent a stronger one.

### Fail-closed authority check (`_assert_within_authority`)

Runs on every compiled brief. Raises `BuilderBriefAuthorityError` if:

1. an evidence item's phrase / verbatim / strength / category / usage-note is not
   an exact eligible fact;
2. the compiler-authored prose (title, use-case, objective, story, rationale)
   contains a forbidden term (CRM/vendor, economics, performance judgement,
   social proof, "deployed/live", dashboard) not present verbatim in a licensed
   phrase;
3. the prose states a numeric sequence not present in a licensed phrase;
4. any `explicit_unknowns` component is dropped;
5. any `required_disclosures` slot is dropped;
6. a RESPONSE_COMMITMENT / SERVICE_AVAILABILITY item is marked selectable, or
   loses its published-self-claim / availability caveat;
7. any eligible fact category silently disappears from the brief; a
   service-need / service-location option is not an exact fact label or a fixed
   base value; a non-selectable category's phrase is offered as an option;
8. a mock action is unregistered or not marked `SIMULATED / MOCK_ONLY / NOT_CONNECTED`;
9. evidence exists but no primary anchor was selected;
10. a SERVICE_AVAILABILITY phrase appears in a sentence with response wording;
11. thin/generic mode produced a bespoke "built around" claim;
12. RESPONSE_PERFORMANCE is an explicit UNKNOWN and the prose pairs a response
    verb with a speed/quality qualifier (asserts the business responds fast/slow/
    on time).

The fixed scaffolding (workflow steps, scenario description, disclosure text,
forbidden-additions list, UX brief) is pinned by byte-equality
(`_assert_scaffolding_is_fixed`) so the compiler cannot drift it.

## 3. Section-10 regression results

`tests/test_m4_builder_brief.py` — **15 passed**. The 11 named invariants:

| # | invariant | test |
|---|---|---|
| 1 | brief cannot introduce a fact absent from M4 authority | `test_1_*` — injected "uses ServiceTitan / books 40 jobs a week" → **raises** |
| 2 | UNKNOWNs stay UNKNOWN | `test_2_*` — all 8 components carried with hard prohibitions; dropping one → **raises** |
| 3 | SERVICE_AVAILABILITY ≠ RESPONSE_COMMITMENT | `test_3_*` — availability item non-selectable, story says "availability signal" not "responds"; "…team responds around the clock" → **raises** |
| 4 | no CRM/vendor unless supplied | `test_4_*` — ServiceTitan / Housecall / Salesforce / HubSpot each → **raises** |
| 5 | no fake metric | `test_5_*` — "12 minutes" / "30%" / "$5000" each → **raises** |
| 6 | mock actions stay mock | `test_6_*` — all 6 registered + `MOCK_ONLY`; adding `SEND_REAL_EMAIL` → **raises** |
| 7 | required disclosure survives | `test_7_*` — all envelope slots present; the simulation disclosure text is in the rendered `.md`; dropping one → **raises** |
| 8 | weak evidence downgrades, not personalises | `test_8_*` — E+M → `GENERIC_CAPABILITY_DEMO`; E+M − commercial → `DEMO_NOT_DISTINCTIVE_ENOUGH` |
| 9 | strongest eligible anchor retained | `test_9_*` — A-Plus anchor = `response_commitment` (rank 0); Elite anchor = `service_availability` |
| 10 | A-Plus RESPONSE_COMMITMENT not silently dropped | `test_10_*` — present, `PUBLISHED_SELF_CLAIM`, non-selectable, caveat intact, in the story; removing it from the brief → **raises** |
| 11 | E+M-like thin evidence cannot produce bespoke claims | `test_11_*` — every thin variant stays generic/thin and passes the authority check with no "built around" assertion |

Repository gates: **full suite 1142 passed / 3 skipped** (was 1127; +15).
`ruff check` + `ruff format --check` + `mypy --strict` clean on every new/changed
file. No existing M4 test changed.

## 4. Frozen source identity (A-Plus)

| field | value |
|---|---|
| source | `tests/m68_fixtures.aplus_envelope()` — frozen corrected M2–M5 evidence, grounded in the sealed Slot 07 M1 evidence (`tests/fixtures/personalization_v2_slots07_21_sealed_evidence.json`) |
| envelope sha256 | `c5a6307f4427d450359946b87d64cecd43f090ed28946c90bd175eaa2b0b380e` |
| m2_m5 bundle sha256 | `a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7` |
| scenario | `commercial_hvac.inbound_lead_response` / `demo.lead_response.machine@1` / `demo.commercial_hvac.questions@2` |
| skeleton version | `demo.scenario_skeleton@1` |
| compiler version | `demo.builder_brief@1` |
| composition policy | `demo.commercial_hvac.lead_response@3` |

The fixture's `audit_revision_hash` / `demo_specification_hash` are synthetic
placeholders (`b*64` / `c*64`) — the frozen *evidence content* (fact phrases,
categories, strengths, findings, UNKNOWNs, disclosures) is the real corrected
M2–M5 output; only those two lineage hashes are fixture stand-ins. No
re-research, no web fetch, no new evidence was introduced.

## 5. A-Plus builder brief — selections

| | |
|---|---|
| **demo mode** | `BESPOKE_DEMO` |
| **primary anchor** | the `response_commitment` fact — `PUBLISHED_SELF_CLAIM` ("…fast response times…") |
| **licensed evidence** (4) | intake `"When to Schedule AC Replacement"` (OBSERVED_PUBLIC_TEXT, selectable), commercial `"Commercial Air Conditioning Repairs"` (OBSERVED_PUBLIC_TEXT, selectable), response-commitment (PUBLISHED_SELF_CLAIM, **context anchor, never selectable, never performance**), service-area `"Service Area"` (OBSERVED_PUBLIC_TEXT, generic, selectable location) |
| **evidence deliberately not used** | none — all 4 eligible facts are carried |
| **service-need options** | `When to Schedule AC Replacement`, `Commercial Air Conditioning Repairs`, `other`, `unknown` |
| **service-location options** | `Service Area`, `other`, `unknown` |
| **UNKNOWNs (8)** | RESPONSE_PERFORMANCE (hard), DEMAND_VOLUME, CONVERSION, CUSTOMER_VALUE, CURRENT_PROCESS (hard — CRM/automation/staffing), COST, FEASIBILITY, INTEGRATION |
| **required disclosures (7)** | simulation_disclosure, not_claiming_transition, verified_sender_slot, required_postal_disclosure_slot, approved_opt_out_instruction_slot, functional_role_or_team, deployment_status |
| **forbidden additions** | 30 items (fixed negative spec + 11 M4 `prohibited_claims` + 3 `must_not_say`) |

## 6. Section-9 A-Plus acceptance questions

1. **What is the central demo story?** A-Plus publishes a commercial-service
   intake surface — a public request path (`"When to Schedule AC Replacement"`)
   and commercial-repair descriptions (`"Commercial Air Conditioning Repairs"`),
   and its public site carries a published response-time claim. The demo shows
   ONE hypothetical structured intake workflow that could sit behind that public
   request path.
2. **Which exact public evidence made that story legitimate?** The three
   non-generic eligible facts: the intake phrase, the commercial-repair phrase,
   and the RESPONSE_COMMITMENT self-claim (`PUBLISHED_SELF_CLAIM`). The
   RESPONSE_COMMITMENT is what lifts A-Plus from "generic HVAC intake demo" to
   "built around something real" — a business that publicly markets fast response
   is a business for whom a structured intake step is a plausible fit.
3. **Which UNKNOWNs remain visible?** All 8, listed in section 4 of the brief,
   with the RESPONSE_PERFORMANCE and CURRENT_PROCESS hard prohibitions shown
   inline.
4. **What would the builder be tempted to invent?** A response-time number or
   "12-minute average"; a "connected to your CRM" badge; a live dashboard with
   fake lead counts; a testimonial; a "you're currently missing leads" framing.
5. **How does the negative specification prevent that?** Section 9 of the brief
   enumerates all of the above as DO-NOT-ADD; the compiler's authority check
   would reject the brief itself if any of that language leaked into it; and the
   builder is told, at the top and in the UX section, to use only supplied
   wording for any claim.
6. **Does the brief distinguish hypothetical workflow from current company
   workflow?** Yes — the mode header, the central story ("ONE hypothetical…",
   "not a description of how the A-Plus team works today"), the scenario section
   ("PROPOSED SIMULATION — NOT IMPLEMENTED"), the simulation-notice step, and the
   `not_claiming_transition` disclosure all say it.
7. **Would an HVAC owner plausibly think "I can imagine this in my business"?**
   Yes — the workflow (request → facility/context → urgency → safety check →
   equipment → preview channel → qualification → human handoff → mock previews)
   is a recognisable inbound-intake flow, and the service-need options are the
   business's own public labels, so it reads as tailored rather than templated.

## 7. Artifacts (section 11)

| artifact | path |
|---|---|
| compiler + renderer + authority check | `packages/communication-core/src/opintel_communication/builder_brief.py` |
| M4 scenario-skeleton accessor | `packages/demo-core/src/opintel_demo/scenario.py` |
| regression tests (15) | `tests/test_m4_builder_brief.py` |
| generator | `scripts/generate_aplus_builder_brief.py` |
| **A-Plus machine-readable brief** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-2026-09-03.json` |
| **A-Plus paste-ready brief (.md)** | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-2026-09-03.md` |
| this evidence doc | `docs/readiness/demo-builder-brief/m4-builder-brief-implementation-evidence-2026-09-03.md` |

Brief-schema version: `demo.builder_brief@1`. Scenario-skeleton version:
`demo.scenario_skeleton@1`.

## 8. Stop after A-Plus (section 12)

No Elite / E+M briefs generated. Lovable not used. No demo changes based on
guesses about Lovable behaviour. **STOPPED — the A-Plus builder-ready brief is
returned for PROJECT_OWNER + ChatGPT review.** If it is good, the PROJECT_OWNER
will manually paste it into Lovable and the visual result will be inspected
before deciding whether to formalise or expand this capability.
