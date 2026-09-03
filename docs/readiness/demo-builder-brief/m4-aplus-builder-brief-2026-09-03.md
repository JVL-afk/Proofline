# Builder brief - A-Plus Air Conditioning & Home Solutions - commercial intake workflow (hypothetical simulation)

**Demo mode:** `BESPOKE_DEMO` - This demo IS meant to feel genuinely built around this specific business, using the public evidence below - not a generic template with a name pasted on.

> You are a presentation renderer. You decide how this looks and feels. You do NOT decide what the business does, what systems it uses, how fast it responds, how it is staffed, or anything about its economics or internal process. Use ONLY the wording in this brief for any claim, label, disclosure or workflow copy.

## 1. Identity & context
- **Business display name:** A-Plus Air Conditioning & Home Solutions
- **Permitted reference identity:** www.aplusac.com (display name + hostname only)
- **Identity rule:** Display name and hostname are the only identity assertions permitted. No inferred location, size, ownership, tenure, or affiliation.
- **Target use case:** Commercial HVAC inbound service / quote request intake and qualification.

## 2. Demo objective
Demonstrate one possible structured commercial-HVAC intake workflow for A-Plus Air Conditioning & Home Solutions, built only from the public evidence supplied, without representing it as the company's actual internal process or performance.

**Central demo story (use this framing, do not embellish):**

> A-Plus Air Conditioning & Home Solutions publishes a commercial-service intake surface: its public pages present a request path ("When to Schedule AC Replacement"); describe commercial HVAC work ("Commercial Air Conditioning Repairs"); and the public site carries a published response-time claim. This demo shows ONE hypothetical structured intake workflow that could sit behind that public request path. It is not a description of how the A-Plus team works today, and it makes no claim about A-Plus's actual response performance, staffing, tools, or lead handling - those are explicit unknowns.

## 3. Licensed public evidence (the ONLY facts you may reflect)

| rank | category | strength | phrase | how to use |
|---|---|---|---|---|
| 0 | response_commitment | PUBLISHED_SELF_CLAIM | (paraphrase only; do not quote) Austin homeowners choose us for flat-rate pricing, fast response times, and technicians registered with the State of Texas. | context / story anchor - NEVER a selectable option |
| 1 | commercial_context | OBSERVED_PUBLIC_TEXT | "Commercial Air Conditioning Repairs" | selectable service-need option |
| 2 | intake_surface | OBSERVED_PUBLIC_TEXT | "When to Schedule AC Replacement" | selectable service-need option |
| 3 | service_area_context | OBSERVED_PUBLIC_TEXT | "Service Area" | selectable service-location option |

**Primary anchor:** the `response_commitment` fact - this is what makes the demo legitimately relevant. Build the story around it; never upgrade it into a stronger claim than its strength tier allows.

**Retained as context, NEVER selectable, NEVER shown as performance:**
- a published response-time claim - demo.commercial_hvac.lead_response@3: a published response promise is retained as context / the demo's story anchor, but is NEVER a selectable dropdown option - a viewer must not be able to 'select' the business's own published response promise inside the simulation, and it must never be shown as verified performance.

## 4. UNKNOWN - do not invent
These are not knowable from public evidence. Do not state, imply, or visually suggest them:

- **RESPONSE_PERFORMANCE:** Current acknowledgement and response performance is unknown.  
  _Hard prohibition:_ Do not state or imply the business responds quickly OR slowly, on time OR late, or that its published response-time claim is or is not accurate.
- **DEMAND_VOLUME:** Applicable monthly inbound inquiry volume is unknown.
- **CONVERSION:** Baseline conversion from qualified inquiry to booked work is unknown.
- **CUSTOMER_VALUE:** Verified average customer value is unknown.
- **CURRENT_PROCESS:** Current intake tools, routing, CRM, staffing, and automation are not publicly verifiable.  
  _Hard prohibition:_ Do not claim the business has, lacks, or under-uses a CRM, automation, dispatcher, or staff.
- **COST:** Implementation and operating cost constraints are unknown.
- **FEASIBILITY:** Operational ownership and human handoff are unknown.
- **INTEGRATION:** Authorized integration availability is unknown.

## 5. Scenario
Fixed M4 scenario 'commercial_hvac.inbound_lead_response' (demo.lead_response.machine@1). A synthetic commercial-HVAC inbound inquiry is collected through a bounded, deterministic state machine, summarised, and handed to a human review step. Handoff is forced on: Safety-critical or emergency wording. / Unknown or unsupported qualification data. / Any quote, commitment, booking, availability, scheduling, or dispatch decision. Every operational action is MOCK_ONLY and NOT_CONNECTED. Deployment status: PROPOSED SIMULATION - NOT IMPLEMENTED FOR THE TARGET BUSINESS.

## 6. Workflow (translate these steps into screens)

### 1. Simulation notice  `[simulation_notice]`
Persistent, prominent statement that this is a hypothetical simulation, not operated by or connected to the business. Viewer acknowledges to continue.
_Presentation hint:_ Full-bleed notice / modal; must stay visible (header banner) for the whole flow.

### 2. Scenario introduction  `[scenario_start]`
One-screen framing of the hypothetical: a commercial HVAC inbound request is coming in; the simulation will collect synthetic details and stop at a human handoff.
_Presentation hint:_ Hero / intro card with a single primary action.

### 3. Service need  `[service_need]`
Single-choice: which simulated commercial HVAC need matches this scenario. Options are supplied by this brief; include 'other' and 'unknown'.
_Presentation hint:_ Single-select list or segmented control.

### 4. Facility type  `[facility_type]`
Single-choice synthetic commercial facility type (office / retail / warehouse / hospitality / other / unknown).
_Presentation hint:_ Single-select list.

### 5. Service location  `[service_location]`
Single-choice simulated service location. Options are supplied by this brief; include 'other' and 'unknown'. No service-area promise is made.
_Presentation hint:_ Single-select list.

### 6. Urgency  `[urgency]`
Single-choice: routine / urgent / safety_critical / unknown. 'safety_critical' routes straight to the fixed safety handoff.
_Presentation hint:_ Single-select; safety_critical visually distinct.

### 7. Equipment context  `[equipment_context]`
Optional single-choice synthetic equipment context (rooftop_unit / split_system / chiller / other / unknown). 'unknown' is always acceptable.
_Presentation hint:_ Single-select list, skippable.

### 8. Preview channel  `[contact_preference]`
Single-choice simulated follow-up channel (simulated_phone / simulated_email). NO real contact destination is collected.
_Presentation hint:_ Two-option toggle; never a free-text contact field.

### 9. Review  `[review]`
Read-only summary of the synthetic answers so far; viewer confirms or goes back.
_Presentation hint:_ Summary list with edit affordances.

### 10. Qualification summary  `[qualification_result]`
Deterministic summary of the simulated qualification. Anything unknown or out-of-scope routes to human handoff or an out-of-scope close.
_Presentation hint:_ Result card.

### 11. Human handoff  `[human_handoff]`
Explicit statement that a real deployment would hand this case to an approved human review process before any commitment or action. This is the end of the scripted flow.
_Presentation hint:_ Prominent handoff panel; primary action = acknowledge.

### 12. Simulated actions preview  `[mock_actions]`
Show the mock operational actions as PREVIEWS ONLY, each clearly marked SIMULATED / MOCK_ONLY / NOT_CONNECTED. Nothing is sent, booked, dispatched or updated.
_Presentation hint:_ Receipt-style list; each row badged 'MOCK_ONLY'.

### 13. Completion  `[success]`
Close by repeating that nothing was sent, booked, dispatched or updated and that this was a hypothetical simulation.
_Presentation hint:_ Completion panel.

### 14. Out of scope  `[not_qualified]`
Close for cases the simulation does not cover; restate that nothing happened.
_Presentation hint:_ Completion panel (neutral).

### 15. Safety handoff  `[safety_handoff]`
Fixed non-business safety message: the simulation cannot evaluate safety-critical situations; a real deployment would route to an approved human emergency process; no dispatch or emergency action has occurred. Use the exact supplied wording.
_Presentation hint:_ Distinct safety panel; no emergency advice, no phone numbers.

### 16. Simulated error  `[mock_error]`
If a mock action 'fails', show a plain error notice and end; still nothing real happened.
_Presentation hint:_ Error notice.

### 17. Ended  `[ended]`
Terminal close state.
_Presentation hint:_ Completion panel.

**Service-need options (exact labels, in order):** ['When to Schedule AC Replacement', 'Commercial Air Conditioning Repairs', 'other', 'unknown']
**Service-location options (exact labels, in order):** ['Service Area', 'other', 'unknown']

## 7. Simulated actions (previews only)
Every action below is a PREVIEW. Nothing is sent, booked, dispatched or updated.

- `CREATE_INTAKE_RECORD` - "Simulated intake record" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**
- `CREATE_CRM_LEAD` - "Simulated CRM lead" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**
- `QUEUE_HUMAN_CALLBACK` - "Simulated human callback queue" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**
- `NOTIFY_DISPATCH` - "Simulated dispatch notification preview" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**
- `REQUEST_SCHEDULING_REVIEW` - "Simulated scheduling review" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**
- `CREATE_ACKNOWLEDGMENT_PREVIEW` - "Acknowledgment preview" - **SIMULATED / MOCK_ONLY / NOT_CONNECTED**

## 8. Required disclosures (must appear, materially intact)

- **simulation_disclosure** - It is a simulation—not a system deployed, connected, official, or operated by the business.
  _Placement:_ Persistent, prominent - visible on every screen.
- **not_claiming_transition** - This is not a claim about how your team works today — we have no visibility into that.
  _Placement:_ Wherever any observation about the business's public pages appears.
- **verified_sender_slot** - [unresolved slot] keep the placeholder token '{{verified_sender_signature}}' literally; the brief stays DRAFT_INCOMPLETE until a human resolves it.
  _Placement:_ Retain the literal placeholder token; do not render a value.
- **required_postal_disclosure_slot** - [unresolved slot] keep the placeholder token '{{required_postal_disclosure}}' literally; the brief stays DRAFT_INCOMPLETE until a human resolves it.
  _Placement:_ Retain the literal placeholder token; do not render a value.
- **approved_opt_out_instruction_slot** - [unresolved slot] keep the placeholder token '{{approved_opt_out_instruction}}' literally; the brief stays DRAFT_INCOMPLETE until a human resolves it.
  _Placement:_ Retain the literal placeholder token; do not render a value.
- **functional_role_or_team** - [unresolved slot] keep the placeholder token '{{functional_role_or_team}}' literally; the brief stays DRAFT_INCOMPLETE until a human resolves it.
  _Placement:_ Retain the literal placeholder token; do not render a value.
- **deployment_status** - PROPOSED SIMULATION — NOT IMPLEMENTED FOR THE TARGET BUSINESS
  _Placement:_ State near the simulation notice; integrations are NOT_CONNECTED / MOCK_ONLY.

## 9. DO NOT ADD (hard negative specification)

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

## 10. Look & feel (your call)
Produce something polished, premium, modern and immediately understandable - credible to a commercial-HVAC operator who has seen good software. It must be fully responsive, visually clear, and interactive enough that the owner can picture using it. You choose layout, typography, spacing, colour, motion, component styling and overall composition. Do NOT invent product copy that asserts anything about the business; use only the wording this brief supplies for any claim, label, disclosure or workflow text. Keep the required simulation disclosure visible and unmissable at all times - it is not decorative chrome.

---

## Appendix - provenance (not for the rendered UI)

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
| compiled_at | 2026-09-01T00:00:00+00:00 |
