# A-Plus Air Conditioning & Home Solutions — commercial intake demo

_Persistent indicator (show on every screen):_ **Simulation · not connected to A-Plus**

> Build a **3-screen** interactive demo a busy HVAC owner can get through in about 60 seconds with no instructions. You have full freedom over visual design; you have **no** freedom over the wording of any claim, label, disclosure, workflow step or result. Use only the copy in this brief for those. Free: visual hierarchy, typography, colour, spacing, animation, transitions, icons, cards, responsive design, polish. Constrained: factual copy, business claims, workflow meaning, result semantics, placeholder semantics, integration state, metrics/data - use only the wording this brief supplies.

**Demo mode:** `BESPOKE_DEMO` · **story anchor:** response commitment

## Screen 1 — Opportunity

> Your public pages emphasize commercial HVAC repair and feature a published response-time message. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance.

_What we actually saw on the public site (optional detail, progressive disclosure):_
- a published response-time message on the public site
- commercial air-conditioning repair work ("Commercial Air Conditioning Repairs")
- a public request path ("When to Schedule AC Replacement")

_What we don't know:_ We don't know how your team currently handles requests, what tools, CRM or scheduling systems you use, how you're staffed, or your actual response times - none of that is public, and this simulation does not assume any of it.

**Primary action:** `See the simulation`

## Screen 2 — Simulate a commercial request

One page. Title: **Simulate a commercial request**. Collapse everything below into a single coherent form — no multi-step wizard.

| field | control | options | required |
|---|---|---|---|
| Service need | select | When to Schedule AC Replacement / Commercial Air Conditioning Repairs / other / unknown | yes |
| Facility | select | Office / Retail / Warehouse / Hospitality / Other / Unknown | yes |
| Service location | select | Service Area / other / unknown | yes |
| Urgency | choice | Routine / Urgent / Safety concern | yes |
| Equipment | select | Rooftop unit / Split system / Chiller / Other / Unknown | no |
| Preferred follow-up | choice | Phone / Email | yes |

**Submit action:** `Run simulation`

_Never_ collect a real phone number, email, address, customer name or staff name. 'Preferred follow-up' only picks which preview channel the result shows.

## Screen 3 — Result / human handoff

Title: **Request prepared for human review**

- _A one-line recap of the simulated request: service need, facility, equipment, urgency, and preferred follow-up channel - filled from the form the owner just completed._
- ✓ Request details organized
- ✓ Urgency captured
- ✓ Preferred follow-up captured
- ✓ Human review required before anything happens

**Example human handoff** (fictional, illustrative):

> **Morgan**  
> Intake coordinator\*
>
> \* Morgan is a fictional demo placeholder, not a real person. We don't know how A-Plus assigns or handles requests internally - the role is illustrative only.

**Prepared previews** (all simulated — nothing runs):
- Prepare intake record
- Prepare lead for CRM
- Prepare callback task
- Prepare dispatch notification
- Prepare scheduling review
- Prepare acknowledgment preview

_Result footer:_ Nothing was sent, booked, dispatched, or updated. This was a hypothetical simulation.

_Closing line:_ Imagine this fitted to your actual intake process rather than this hypothetical one.

## Exception screens (only when triggered)

### Safety review required  `[safety_critical]`
This simulation can't evaluate safety-critical situations. A real implementation would hand this straight to an approved human process. Nothing has been dispatched, and this screen gives no emergency advice.

### Outside this simulation  `[out_of_scope]`
This simulation doesn't cover that kind of request. In a real setup a person would take it from here. Nothing was sent or scheduled.

### Simulation hiccup  `[mock_error]`
The simulation couldn't finish this step. Nothing real happened - you can start over.

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

## Appendix — provenance (not for the rendered UI)

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
| underlying_brief_sha256 | `4d9f26412893d85fc21473b65e50466433d3655275957ad3523b20323538636a` |
| compiled_at | 2026-09-01T00:00:00+00:00 |

Internal M4 identifiers (audit only — do not surface to users): `CREATE_INTAKE_RECORD`→"Prepare intake record", `CREATE_CRM_LEAD`→"Prepare lead for CRM", `QUEUE_HUMAN_CALLBACK`→"Prepare callback task", `NOTIFY_DISPATCH`→"Prepare dispatch notification", `REQUEST_SCHEDULING_REVIEW`→"Prepare scheduling review", `CREATE_ACKNOWLEDGMENT_PREVIEW`→"Prepare acknowledgment preview"
