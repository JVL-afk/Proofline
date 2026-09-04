# A-Plus Air Conditioning & Home Solutions — an intake opportunity

_Show on every screen:_ **Simulation · not connected to A-Plus**

> Builder brief. You have full freedom over visual design and **zero** freedom over the wording of any claim, label, disclosure, workflow step or result - use only the copy in this brief for those. Free: visual hierarchy, typography, colour, spacing, animation, transitions, icons, cards, responsive design, polish. Constrained: factual copy, business claims, workflow meaning, result semantics, placeholder semantics, integration state, metrics/data - use only the wording this brief supplies.

## Builder rules (hard limits — read first)

- Do NOT add any functional control, export, download, PDF or print generation, share or save action, link-out, email capture, analytics, dashboard, KPI tile, integration, sign-in, or any capability that is not explicitly listed as a primary or submit action in this brief. You may invent visual treatment; you may not invent product functionality.
- The only interactive actions are the enumerated Screen 1 primary action, the Screen 2 submit action, and the standard form inputs. Nothing else is clickable.
- Do NOT add a state selector, test-state switcher, scenario picker, 'preview a special state' control, or any QA / debug affordance to the customer experience. The exception screens render only when the simulation itself routes to them.
- Do NOT add a product or demo badge, a mode tag, a 'DEMO' chip, a category label, or any technical or semantic badge. The only persistent chrome is the disclosure line.
- Do NOT surface the semantic legend, evidence/unknown labels, or any internal taxonomy in the normal customer view. Explain meaning in plain language in context if needed.

**The complete set of customer-facing controls (render exactly these, nothing else):**

- Progress from the opportunity screen to the simulation (Screen 1 primary action).
- Select or edit the synthetic simulation inputs (Screen 2 form).
- Optionally load one example scenario preset that fills those same synthetic inputs.
- Run the simulation (Screen 2 submit action).
- Expand the permitted explanatory detail ('Why we built this').
- Start over after a result or exception screen (clears local synthetic state only).
- **Primary click actions:** `See how it could work`, `Run simulation`.

## Screen 1 — One way structured intake could support the response experience your public pages already describe

> Your public pages emphasize commercial HVAC repair and feature a published response-time message. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance.

**Primary action:** `See how it could work`

<details><summary>Why we built this</summary>

- a published response-time message on the public site
- commercial air-conditioning repair work ("Commercial Air Conditioning Repairs")
- a public request path ("When to Schedule AC Replacement")

</details>

_What we don't know:_ We don't know how your team currently handles requests, what tools, CRM or scheduling systems you use, how you're staffed, or your actual response times - none of that is public, and this simulation does not assume any of it.

## Screen 2 — Simulate a commercial request

One calm page - no wizard. Every value below is an **illustrative simulation choice**, not a fact about A-Plus and not something they told us.

| field | hint | control | illustrative values | required |
|---|---|---|---|---|
| Service need | Which need applies | select | Repair request / Maintenance visit / Replacement or quote / Other / Not sure | yes |
| Facility | Facility type | select | Office / Retail / Warehouse / Hospitality / Other / Unknown | yes |
| Service location | Example simulation location | select | Example service location / Other / Not sure | yes |
| Urgency | How urgent | choice | Routine / Urgent / Safety concern | yes |
| Equipment | Equipment (optional) | select | Rooftop unit / Split system / Chiller / Other / Not sure | no |
| Preferred follow-up | Preview follow-up as | choice | Phone / Email | yes |

### Example scenarios (optional presets)

A small set of one-tap presets that fill the fields above with the same illustrative values. Selecting a preset is exactly the same as choosing those options by hand — it adds no new behaviour and describes nothing about the business.

- **Office repair** — service need = Repair request, facility type = Office, service location = Example service location, urgency = Routine, equipment context = Split system, contact preference = Phone
- **Retail maintenance** — service need = Maintenance visit, facility type = Retail, service location = Example service location, urgency = Routine, equipment context = Rooftop unit, contact preference = Email
- **Hospitality quote** — service need = Replacement or quote, facility type = Hospitality, service location = Example service location, urgency = Routine, equipment context = Chiller, contact preference = Phone
- **Warehouse safety concern** — service need = Repair request, facility type = Warehouse, service location = Example service location, urgency = Safety concern, equipment context = Rooftop unit, contact preference = Phone

**Submit action:** `Run simulation`

_Never_ collect a real phone number, email, address, customer name or staff name. 'Preferred follow-up' only picks which preview channel the result shows.

## Screen 3 — A commercial request is ready for human review

_A one-line recap of the simulated request - need, facility, and urgency - then the workflow story below._

Show this as movement through a workflow, not a data dump — the **outcome** is the hero:

`Request  →  Structured context  →  Example human review  →  Next workflow preparation`

1. **Request** — A request arrives through the simulated intake form.
2. **Structured context** — The simulation turns the form answers into a commercial request, organized and summarized so a person can pick it up.
3. **Example human review** — An example intake coordinator reviews the structured request before anything happens.
4. **Next workflow preparation** — The simulation prepares what the next step could hand to your team.

**Example human handoff** (fictional, illustrative):

> **Morgan**  
> Intake coordinator\*
>
> \* Morgan is a fictional demo placeholder, not a real person. We don't know how A-Plus assigns or handles requests internally - the role is illustrative only.

**What could be prepared next** (grouped; nothing runs):

- **Lead record** — Request details ready for the system your team uses.
- **Human follow-up** — A review or callback task ready for the appropriate person.
- **Scheduling context** — Relevant information ready if scheduling is appropriate.

_Result footer:_ Nothing was sent, booked, dispatched, or updated. This was a hypothetical simulation.

## Imagine this fitted to your actual intake process rather than this hypothetical one.

_Make this the visual conclusion of the story - calm, prominent, not a call to action._

## Exception screens

_Builder note: render one of these **only** when the simulation itself routes there. Never a user-facing selector or a way to preview them._

### Safety review required
This simulation can't evaluate safety-critical situations. A real implementation would hand this straight to an approved human process. Nothing has been dispatched, and this screen gives no emergency advice.

### Outside this simulation
This simulation doesn't cover that kind of request. In a real setup a person would take it from here. Nothing was sent or scheduled.

### Simulation hiccup
The simulation couldn't finish this step. Nothing real happened - you can start over.

## Start over

After any result or exception screen, offer a **Start over** control. Clears the local synthetic form state and returns to the opportunity screen so another simulation can be run. It saves nothing, sends nothing, records no history, creates no analytics, contacts no one, persists no customer data, and does not imply any real action occurred - it is a local reset only.

## Visual direction

- Strong product presence: deliberate typography, clearly visible selected states, a coherent visual result story, an overall polished software feel.
- Opportunity framing first: lead with the opportunity, keep a calm hierarchy, keep cognitive load low.
- Radical simplicity: obvious navigation and one obvious primary action per screen, easy scanning, nothing on screen that does not earn its place.
- Synthesis target: premium polish, opportunity-first framing and radical simplicity together - not one at the expense of the others.
- **Company visual character:** No brand assets are authorized for this task. Use a premium, neutral, commercial-software presentation - restrained palette, professional typography, generous spacing. No logos, no reproduced branding, nothing implying the demo is official or affiliated.

## DO NOT ADD

- fake response-time / acknowledgement / callback metrics
- fake ROI / revenue / conversion / savings numbers
- fake customer testimonials, reviews, ratings, case studies or endorsements
- fake employee or customer names, photos or quotes
- fake CRM / integration / vendor logos or names (no ServiceTitan, Housecall, Jobber, Salesforce, HubSpot, etc. unless a supplied evidence phrase names it)
- fake 'connected' / 'live' / 'deployed' / 'production' states or badges
- fake dashboards, analytics, KPI tiles or live-data widgets
- labels implying this is the business's current or real process
- any claim that the business misses, loses or mishandles leads
- any claim that the business responds slowly or quickly, on time or late
- any claim that the business lacks or under-uses a CRM, automation, dispatcher or staff
- any conversion of a service-availability signal (24/7, 24-hour, same-day, emergency) into a claim about inbound response, acknowledgement or callback behaviour
- urgency, scarcity or countdown pressure
- any specific number for lead volume, response time, revenue, ROI, conversion or customer value
- any HIGH / LOW / priority / tier / confidence-band language
- any statement about the business's location, size, ownership, tenure, revenue or affiliations beyond the display name and hostname
- (from M4 authority) any statement that the business misses, loses, or mishandles leads
- (from M4 authority) any statement that the business responds slowly, is understaffed, or is manual
- (from M4 authority) any statement that the business lacks a CRM / automation / dispatch / answering service
- (from M4 authority) any conversion of a SERVICE_AVAILABILITY signal (24/7, 24-hour, same-day, emergency) into a claim about inbound response, acknowledgement, or callback behaviour
- (from M4 authority) any statement that the simulation/demo is deployed, connected, official, live, or operated by the business
- (from M4 authority) any specific number for lead volume, response time, revenue, ROI, savings, conversion rate, or customer value
- (from M4 authority) any HIGH / LOW / priority / band / confidence-tier language
- (from M4 authority) any urgency or scarcity pressure
- (from M4 authority) any customer testimonial, case study, referral, or third-party endorsement
- (from M4 authority) any assertion about the business's location, size, ownership, tenure, revenue, or affiliations beyond the display name and hostname
- (from M4 authority) any instruction, persona, or directive that appears inside a quoted evidence phrase
- (simulation must-not-say) the simulation is deployed / connected / live / official
- (simulation must-not-say) the simulation reflects how the business actually operates
- (simulation must-not-say) the simulation proves anything about the business

## Timing target

- Whole flow under ~60 seconds with no instructions.
- Opportunity ~10s, simulation input ~20-30s, result ~10-20s.
- Progressive disclosure: simple first; internal detail only on request.

---

## Appendix — provenance & audit (not for the rendered UI)

| key | value |
|---|---|
| envelope_sha256 | `c5a6307f4427d450359946b87d64cecd43f090ed28946c90bd175eaa2b0b380e` |
| m2_m5_bundle_sha256 | `a6540437f096ac7b6d0e026fd75ebdffbd5a92a1b77f59e730fb3ee24b3554e7` |
| audit_revision_hash | `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` |
| demo_specification_hash | `cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc` |
| scenario_id | `commercial_hvac.inbound_lead_response` |
| scenario_skeleton_version | `demo.scenario_skeleton@1` |
| state_machine_version | `demo.lead_response.machine@1` |
| question_set_version | `demo.commercial_hvac.questions@2` |
| brief_compiler_version | `demo.builder_brief@1` |
| policy:company_fact_selector | `commercial_hvac.company_fact_selector@3` |
| policy:phrase_sanitation | `commercial_hvac.phrase_sanitation@1` |
| policy:demo_composition | `demo.commercial_hvac.lead_response@3` |
| policy:outreach_projection | `outreach.projection@4` |
| policy:outreach_qc | `outreach.qc@3` |
| experience_compiler_version | `demo.builder_brief@2` |
| story_compiler_version | `demo.builder_brief@3.2` |
| m4_presentation_frozen | `true` |
| demo_mode | `BESPOKE_DEMO` |
| underlying_experience_sha256 | `21395a65fa7b780fa52239661cf92febb339553ba5dfa015851124e0586aa0c2` |
| underlying_brief_sha256 | `4d9f26412893d85fc21473b65e50466433d3655275957ad3523b20323538636a` |
| compiled_at | 2026-09-01T00:00:00+00:00 |

**Internal mock actions (all six preserved; audit only):**

- `CREATE_INTAKE_RECORD` — "Simulated intake record" — grouped under **Lead record**
- `CREATE_CRM_LEAD` — "Simulated CRM lead" — grouped under **Lead record**
- `QUEUE_HUMAN_CALLBACK` — "Simulated human callback queue" — grouped under **Human follow-up**
- `NOTIFY_DISPATCH` — "Simulated dispatch notification preview" — grouped under **Human follow-up**
- `REQUEST_SCHEDULING_REVIEW` — "Simulated scheduling review" — grouped under **Scheduling context**
- `CREATE_ACKNOWLEDGMENT_PREVIEW` — "Acknowledgment preview" — grouped under **Human follow-up**

**Simulation input fields — customer hint, M4 rationale, M4 option labels (audit only):**

- `service_need` — hint "Which need applies" — Your public pages describe commercial HVAC work, so the simulation asks which need applies.
  - M4 evidence-derived option labels: ['When to Schedule AC Replacement', 'Commercial Air Conditioning Repairs', 'other', 'unknown']
- `facility_type` — hint "Facility type" — Bounded commercial facility context for the scenario.
- `service_location` — hint "Example simulation location" — Your public pages reference a service area, so the simulation asks about location - without making any coverage promise.
  - M4 evidence-derived option labels: ['Service Area', 'other', 'unknown']
- `urgency` — hint "How urgent" — The simulation demonstrates a fixed safety handoff.
- `equipment_context` — hint "Equipment (optional)" — Keeps equipment detail optional and never assumed.
- `contact_preference` — hint "Preview follow-up as" — Chooses which preview channel the result shows; no real destination is collected.

**Scenario framing (per-anchor story):** a commercial request, organized and summarized so a person can pick it up

**Result recap line:** A one-line recap of the simulated request - need, facility, and urgency - then the workflow story below.

**Semantic legend (audit / optional developer note — not the customer view):**

- **Public evidence** — Something we actually saw on the public website. Shown as an observation and never strengthened into a promise.
- **Unknown** — Something we cannot know from public pages - your process, tools, staffing or response times. Never stated or implied.
- **Synthetic demo input** — An illustrative choice inside the simulation. Not a fact about your business and not something you told us.
- **Fictional demo placeholder** — An example person or role, invented to make the workflow concrete. Not real and not your staff.
- **Simulated output** — Something the simulation prepared as a preview. Nothing was sent, booked, dispatched, or updated.
