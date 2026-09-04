# M4 presentation layer — FROZEN (owner authorization 2026-09-04, Part A)

Owner authorization 2026-09-04 "FREEZE M4 → RUN M6.8-4 … → DRAFT M6.9", Part A.
Two manually-discovered UX controls are formalized generically in the
builder-brief compiler, and the M4 presentation layer is then **frozen**.

## Frozen version

| | |
|---|---|
| **frozen builder-brief compiler** | `demo.builder_brief@3.2` (`opintel_communication.builder_story`) |
| **freeze marker** | `M4_PRESENTATION_FROZEN = True` (module constant; also in every artifact's `audit_appendix` as `m4_presentation_frozen=true`) |
| **authoritative M4 demo semantics** | **UNCHANGED** — no file under `packages/demo-core/src/opintel_demo/` modified; the V1 `BuilderBrief` M4-authority check runs first and unchanged; `underlying_brief_sha256` recorded per artifact |
| **A-Plus + Elite** | generated through this same compiler (`scripts/generate_aplus_builder_brief.py`) |
| **builder rendering** | remains **manual**; no external builder (Emergent / Lovable / Base44) is part of the authority chain |

After this freeze: **no further M4 aesthetic tuning.** Only bug / authority
fixes touch `builder_story.py`.

## 1. Example scenarios (Part A.1.A)

New `BuilderStory.example_scenarios: tuple[ExampleScenario, ...]` +
`_EXAMPLE_SCENARIOS` presets. Rendered as an optional Screen-2 subsection.

- Four presets: **Office repair**, **Retail maintenance**, **Hospitality quote**,
  **Warehouse safety concern** (the last routes `urgency = Safety concern` → the
  M4 `safety_critical` branch).
- Every preset value is a **`SYNTHETIC_DEMO_INPUT`** value already present on its
  field. `_example_scenarios()` drops any preset whose values don't all land on
  real options, so a preset can never introduce a value.
- **Semantics:** *"Selecting a preset is exactly the same as choosing those
  options by hand — it adds no new behaviour and describes nothing about the
  business."* No new workflow authority; never a fact about the target company;
  never implies real customers/events; no unsupported services/geography/process.
- Authority check **22**: preset name is a short label and not an evidence
  phrase; every `(field_id, value)` is a known field set to one of its synthetic
  options; no value equals an evidence phrase.

## 2. Start over (Part A.1.B)

New `BuilderStory.start_over_label` (`"Start over"`) +
`start_over_semantics`. Rendered as a `## Start over` section after the result /
exception screens.

Semantics (verbatim): *"Clears the local synthetic form state and returns to the
opportunity screen so another simulation can be run. It saves nothing, sends
nothing, records no history, creates no analytics, contacts no one, persists no
customer data, and does not imply any real action occurred — it is a local reset
only."*

Authority check **23**: label ∈ {start over, start again, reset}; semantics must
describe a pure local reset (`clears` / `local` / `another simulation` /
`saves nothing` / `sends nothing`) and must **deny** history / analytics /
tracking / persistence / contact.

## 3. Builder-function allowlist preserved + closed (Part A.2)

New `BuilderStory.customer_facing_controls` — the **closed six-item list** of
everything a builder may render:

1. progress from the opportunity screen to the simulation (Screen 1 primary action);
2. select or edit the synthetic simulation inputs (Screen 2 form);
3. optionally load one example scenario preset;
4. run the simulation (Screen 2 submit action);
5. expand the permitted explanatory detail ("Why we built this");
6. start over after a result or exception screen.

`allowed_primary_actions` (the two click actions) is unchanged. The
`builder_hard_rules` still forbid PDF export / download / save / share / email /
analytics / dashboards / external integrations / booking / calendar / contact
forms / real CRM actions / deployment controls / state selectors / demo badges.
Authority check **24**: `customer_facing_controls` is exactly the six items.

Rendered as *"The complete set of customer-facing controls (render exactly
these, nothing else)"*.

## Tests

`tests/test_m4_builder_brief_v3.py` — **34 tests** (was 27; +7 V3.2):

| test | proves |
|---|---|
| `test_v32_frozen_version_and_marker` | `@3.2`; `M4_PRESENTATION_FROZEN`; `m4_presentation_frozen=true` in the audit appendix |
| `test_v32_example_scenarios_only_fill_existing_synthetic_options` | 4 presets; every value is a real synthetic option; no preset name/value is an evidence phrase; "Warehouse safety concern" routes to `Safety concern` |
| `test_v32_example_scenario_tampering_is_rejected` | a preset value that is not a field option → **raises** |
| `test_v32_start_over_is_a_local_reset_only` | label + semantics deny history/analytics/persistence/contact; `## Start over` in the body |
| `test_v32_customer_facing_controls_are_the_closed_six` | the closed six; dropping one → **raises** |
| `test_v32_builder_function_allowlist_still_forbids_invented_capability` | PDF/download/export/share/email/analytics/dashboard/integration/sign-in all in the hard rules; "render exactly these, nothing else" in the body |
| `test_v32_authoritative_m4_semantics_unchanged` | `underlying_brief_sha256` == V2's; six mock actions; skeleton == composer statics |

Repository gates: **full suite 1196 passed / 3 skipped** (was 1189; +7).
`ruff check` + `ruff format --check` + `mypy --strict` clean on all new/changed
files. **No `opintel_demo` file changed. No existing non-V3 test changed** (only
`test_m4_builder_brief_v3.py`'s own version assertion → `@3.2` and one V3.1
render-label assertion updated).

## Confirmation

- Authoritative M4 demo semantics unchanged.
- Presentation compiler frozen at `demo.builder_brief@3.2`.
- A-Plus and Elite generated through the same compiler.
- Builder rendering remains manual.
- No external builder is part of the authority chain.
