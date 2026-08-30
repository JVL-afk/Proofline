# Slots 02–04 — M5 Product-Quality Review (2026-08-30)

Human product-quality review of the first three real opportunities that reached M5.
Section A surfaces the **exact sealed outputs** (read-only diagnostic; no artifact modified,
rerun, re-scored, or reinterpreted). Section B is a **separate reviewer analysis**.

**Retrieval**: one further owner-authorized bounded read-only in-VPC SELECT sweep over the
`opportunity_* / audit_* / demo_* / outreach_*` tables plus `research_evidence`, filtered to the
three businesses. Contact-shaped substrings redacted. Pre/post: kill switch TRIPPED (v33), all
authorities NOT_AUTHORIZED, services 0/0/0, zero running tasks, Terraform NO_CHANGES — unchanged.
Transient task definitions `m67-phase1-research-worker:25/26/27/28` all INACTIVE (deregistered).

Business ids: Webb Air `15ea883c…`, BNCAIR `491df72b…`, All Elements `6e8a8f8e…`.
Coordinator runs: Slot 02 `17b75bf7…`, Slot 03 `b5e8cea1…`, Slot 04 `eda72f38…`.

---

## KEY STRUCTURAL FINDING (applies to all three)

The M2 opportunity statement, M2 alternatives list, M2 feasibility dependencies, M2 information-gap
set, M2 assumption set, M3 audit section structure, M4 demo scenario/state-machine, and **the entire
reader-visible M5 message text are byte-identical across Webb Air, BNCAIR, and All Elements.**

The only things that differ per company:
- which evidence-row ids are attached (35 / 4 / 30 supporting ids);
- the M2 **score band**: Webb Air `review_priority_band = HIGH` (evidence_strength=high,
  hypothesis_confidence=high); BNCAIR and All Elements `= LOW` (evidence_strength=low,
  hypothesis_confidence=low);
- the M1 inference `confidence_band`: Webb Air `high`, BNCAIR/All Elements `medium`;
- the M3 audit "Publicly observed facts" section, which quotes each company's own minimized page text;
- internal hashes / projection ids.

`commercial_hvac.inbound_lead_response_qualification@1` is the single opportunity template that fired.

---

# A. EXACT EXISTING OUTPUTS

## A.1 — Slot 02, Webb Air (webbair.com)

### 1. Executive result
- **Exact terminal stage**: `CONTACT_PHASE_NOT_AUTHORIZED` (coordinator TERMINAL; accepted_stage_count 6 = M1→M2→M3→M4→M5→contact gate, all `ACCEPTED`).
- **M2 opportunity / hypothesis**: definition `commercial_hvac.inbound_lead_response_qualification@1`; hypothesis revision `9f1d4617…`, status `ready_for_review`.
- **M2 statement (verbatim)**: *"Public pages show that the business invites commercial HVAC inquiries through observed digital channels. A structured acknowledgement and qualification workflow could be evaluated for those channels. Current response performance, internal routing, lead volume, conversion, feasibility, and economic impact remain unknown pending business verification."*
- **Score / classification**: `review_priority_band = HIGH`. Factor bands — evidence_strength `high`, hypothesis_confidence `high`, business_fit `high`, potential_value `unknown`, implementation_feasibility `unknown`, important_unknowns `high`. Config `commercial_hvac.lead_response.heuristic_bands@1`.
- **Exact M2 reason it cleared the threshold**: the hypothesis reached `ready_for_review` on a deterministic predicate match — three observations (`business.industry.commercial_hvac_supported`, `inbound_path.observed`, `inbound_path.structured_fields`), all scoped "captured public pages only", plus `business_fit=high` (this factor's `missing_behavior` is `block`, i.e. it is the gate). Economics and feasibility being unknown did **not** block; the model advances a "ready for review" hypothesis when public fit + an observed inbound path are established, explicitly deferring value and feasibility.
- **Economics classification**: **UNKNOWN**. `opportunity_economic_runs` status `insufficient_data`; `monthly_value = null`, `annualized_value = null`; `result_label = "insufficient data — required business inputs are unknown"`. All four economic assumptions (`monthly_inbound_leads`, `affected_share`, `conversion_lift`, `average_customer_value`) have `value_state = unknown`, `source_kind = UNKNOWN`, no value. Formula `commercial_hvac.lead_response.potential_incremental_revenue@1`.
- **Exact major UNKNOWNs that remained** (10 information gaps; 6 `critical`/`blocks_model`, 4 `high`/`materially_changes_model`): monthly inbound inquiry volume; current acknowledgement/response performance; qualified-inquiry definition and rate; qualified→booked conversion; verified average customer value + value semantics; inbound channel mix & seasonality; current intake tools & routing; operational ownership/staffing/human handoff; authorized integration availability; implementation & operating cost constraints.
- **Not summarized as fact**: the output does **not** assert Webb Air has slow responses, missed leads, no CRM, or lost revenue. It asserts only that a public inbound path exists and a workflow *could be evaluated*.

### 2. M1 evidence that drove the opportunity
M2 consumed 3 **observations** bound to specific evidence rows:

| Observation predicate | Value (verbatim) | Evidence id | Page | Fact class | Why M2 used it |
|---|---|---|---|---|---|
| `business.industry.commercial_hvac_supported` | "commercial HVAC publicly described" | `1a4dc5bc…` | `webbair.com/` (visible-text) | `public_service_description` | Establishes `business_fit=high` for the Commercial HVAC definition |
| `inbound_path.observed` | "public inbound service path observed" | `93ce7c35…` | contact / request path | `public_inbound_path` | Establishes that a public request channel exists (the opportunity's subject) |
| `inbound_path.structured_fields` | "public structured intake details observed" | `1a4dc5bc…` | `webbair.com/` | `public_service_description` | Supports that intake is structured enough to reason about |

Supporting evidence pool: 35 rows (e.g. `/commercial-maintenance-programs/`, `/contact-us/`, `/service-areas/`, `/light-commercial-hvac/`, `/financing/`, Arlington service-area pages). One inference (`59d52c38…`, `confidence_band = high`): *"A bounded public inbound path exists; evaluating structured acknowledgement and qualification may be relevant. No internal response behavior is established."* Zero contradictory evidence.

Verbatim public text actually captured (from the M3 audit's "publicly observed facts"): the Webb Air homepage lists AC/heating/commercial services, "Light Commercial HVAC", "Commercial Maintenance Programs", "Welcome To Webb Air Of Fort Worth", "Request Estimate / Schedule Service", a contact page stating *"Phones are answered 24 hours/monitored. Email responses are sent the next business day… Requests after 10:00pm will be contacted after 8:00am the following day,"* NATE-certified technicians, a 10% military discount, "Fort Worth, TX 76104", and one testimonial ("Fast, Friendly, and fair. I have been using Webb for 6yrs at a Commercial business…").

- **FACT** (public, cited): Webb Air publicly describes commercial + light-commercial HVAC; publicly offers "Request Estimate" / "Schedule Service" paths and a contact form; publicly states a stated intake SLA on the contact page ("email responses next business day", after-hours callback next morning); publicly lists Fort Worth + Arlington service areas. Totals: 161 evidence rows — `public_service_description` 89, `public_other` 41, `public_inbound_path` 29, `public_service_area` 2.
- **INFERENCE** (1, confidence high): a structured acknowledgement/qualification workflow "may be relevant" to that public path.
- **ESTIMATE**: none. No economic value was estimated (insufficient_data).
- **UNKNOWN**: all 10 information gaps above; all 4 economic assumptions; whether the stated public SLA reflects actual performance.

### 3. M2 opportunity output (complete, human-readable)
- **Detected opportunity** (not a claimed problem): "a structured acknowledgement and qualification workflow **could be evaluated**" for the observed public commercial-HVAC request path. The statement explicitly withholds any claim about current response performance, routing, volume, conversion, feasibility, or economics.
- **Evidence chain**: 3 evidence rows → 3 observations → 1 inference (`confidence high`) → 1 hypothesis (`ready_for_review`). Manifest `594c9281…`.
- **Score**: `HIGH` review-priority band; potential_value and implementation_feasibility both `unknown`; important_unknowns `high`.
- **Economics**: `insufficient_data`; monthly/annualized value `null`; `result_label = "insufficient data — required business inputs are unknown"`.
- **Assumptions** (all UNKNOWN, source UNKNOWN): monthly_inbound_leads (leads/month), affected_share (ratio), conversion_lift (ratio), average_customer_value (USD/win).
- **Unknowns**: the 10 information gaps.
- **Confidence**: hypothesis_confidence factor `high` for Webb Air; underlying inference `confidence_band high`.
- **Rejection / acceptance criteria present**: 7 recorded alternative explanations that would each reduce or remove the opportunity — "Existing staff may answer calls or messages promptly"; "Existing CRM, answering-service, or routing automation may not be publicly visible"; "The public form may route to a well-staffed dispatcher"; "Customers may predominantly use phone, referrals, portals, or established-account channels"; "The captured website may be stale or incomplete"; "A third-party workflow may exist outside the permitted capture scope"; "Capacity constraints may make faster intake undesirable at present."
- **Why it advanced**: public business-fit + an observed structured inbound path were established with no contradictory evidence; the model advances such a hypothesis to review while deferring value/feasibility to business verification.
- **Does M2 claim a current internal problem?** **No.** Preserved verbatim: it says a workflow *"could be evaluated"* and that internal performance *"remains unknown pending business verification."*

### 4. M3 audit (evidence-linked)
`audit_revisions` revision `1d4c6cf4…`, kind `full`, state `approved`, revision_hash `faa50b06…`, 14,110-char rendered text, 6 claims, **0 QC findings**. Deterministic composer `audit.commercial_hvac.deterministic@1`.

- **Headline / scope**: *"This audit is limited to cited public digital surfaces and canonical M2 records. Internal operations and actual business impact remain unknown unless explicitly verified."*
- **11 sections**: (1) scope & limitations; (2) business & research scope; (3) **Publicly observed facts** — 3 `[FACT]` claims, each of which is a **verbatim dump of minimized page text** (homepage, contact page) rather than a synthesized finding; (4) relevant inferences — the single M2 inference; (5) opportunity hypothesis — the M2 statement; (6) contradictions & alternative explanations — the 7 alternatives; (7) information gaps & validation questions — the 10 gaps with wording; (8) economic scenarios — assumptions listed, all `unknown`; (9) proposed solution & feasibility constraints — 6 feasibility dependencies (authorized channel access; qualification rubric + capacity + handoff policy; named ownership + after-hours escalation; compatible form/email/phone/CRM/scheduling/dispatch interfaces; data-minimization/access-control/retention/monitoring/fallback; prohibition on autonomous commitments/quotes/bookings/unsafe emergency guidance); (10) recommended validation steps — the 10 questions; (11) methodology & provenance (manifest hash, QC policy).
- **Findings**: there are no analytical "findings" — section 3 is raw observations (public facts), section 5 is the single inferred opportunity, sections 6–10 are unknowns / dependencies / questions. **Observation vs inferred**: sections 3 are observations; section 5 is the only inference; nothing is stated as an established internal condition.
- **Economic framing**: none quantified — "insufficient data."
- **Provenance**: evidence fingerprints (id : minimized-sha256 : url : timestamp) for each cited row; audit manifest `abf3affc…`.

### 5. M4 demo
`demo_revisions` revision `74acf5f2…`, state `review_required`, validity `current`, specification_hash `720398bb…`. Composer `demo.commercial_hvac.lead_response@1`.

- **Demo title / scenario**: `commercial_hvac.inbound_lead_response` — "This scripted simulation demonstrates a proposed intake workflow." `deployment_status: "PROPOSED SIMULATION — NOT IMPLEMENTED FOR THE TARGET BUSINESS."`
- **What a business owner would see**: a **persistent "this is a simulation" notice**, then a scripted linear flow — pick a synthetic commercial HVAC need (repair / maintenance / replacement_quote / unknown), synthetic facility type (office / retail / warehouse / hospitality / other / unknown), synthetic Texas region, urgency, equipment context, contact preference — then an input-review screen, a qualification summary, a **mandatory human-handoff panel** ("This simulated case now requires human review"), then **mock-only** action receipts ("Simulated intake record", "Simulated CRM lead", "Simulated human callback queue", "Simulated dispatch notification preview", "Simulated scheduling review", "Acknowledgment preview"), then a completion panel that repeats *"nothing was sent, booked, dispatched, or updated."*
- **Scenario / user flow**: `simulation_notice → scenario_start → service_need → facility_type → service_location → urgency → (safety_handoff if urgency = safety_critical) → equipment_context → contact_preference → review → qualification_result → (not_qualified if outside_scope | human_handoff otherwise) → mock_actions → success / failure / ended`. `maximum_transitions: 24`.
- **Inputs**: service_need, facility_type, service_location, urgency, equipment_context, contact_preference (all single-choice, all synthetic value sets; `collects_contact_destination: false`).
- **Outputs**: a qualification summary + mock action receipts + human-handoff notice. No document, quote, or booking.
- **Calculator / automation / interactive behavior**: **there is no calculator and no economic output** (economics were insufficient_data). Interactivity is a deterministic registered state machine with fixed transitions; two synthetic personas ("Avery Example" / "Jordan Example", "Synthetic Texas region").
- **Personalization tied to public evidence**: only `business_display_name = "Webb Air"` and one `statements` entry that restates the captured homepage text as a `source_fact`. The scenario, questions, states, transitions, and personas are 100% template.
- **Explicit hypothetical / unknown labels**: "PROPOSED SIMULATION — NOT IMPLEMENTED"; all proposed integrations marked `NOT_CONNECTED / MOCK_ONLY` (CRM, Scheduling, Dispatch, Email/SMS/phone); "Synthetic input only"; "No external side effects"; "Persistent anti-impersonation disclosure."
- **Exact claims the demo refuses to make**: any "quote, commitment, booking, availability, scheduling, or dispatch decision"; any handling of "safety-critical or emergency wording" (routed to a safety handoff); any action on "unknown or unsupported qualification data."

### 6. M5 outreach package
`outreach_package_revisions` revision `1d5c39dd…`, state `content_approved`, validity `current`, package content_hash `8b9ac65e…`, target_role `service_operations_lead` (`person_identified: false`, `NO_PERSON_IDENTIFIED`). `economic_context.external_use_permitted: false`.

- **Subject** (`content_hash 3a89ba0a…`): **"A question about commercial service-request intake"**
- **First-contact email body** (`content_hash 217bc695…`, verbatim):
  > Hello {{functional_role_or_team}},
  >
  > The public website invites commercial HVAC service or quote inquiries through an observed contact path.
  >
  > A structured acknowledgement and qualification workflow could be evaluated for that public request path.
  >
  > We prepared a short deterministic simulation based only on approved public information.
  >
  > It is a simulation—not a system deployed, connected, official, or operated by the business.
  >
  > Would it be useful to compare the simulation with your actual process and decide whether the idea is relevant?
  >
  > {{verified_sender_signature}}
  >
  > {{required_postal_disclosure}}
  >
  > {{approved_opt_out_instruction}}
- **CTA**: "Would it be useful to compare the simulation with your actual process and decide whether the idea is relevant?"
- **Evidence claims used**: two `bound_claim` segments — "The public website invites commercial HVAC service or quote inquiries through an observed contact path" and "A structured acknowledgement and qualification workflow could be evaluated for that public request path." Both generic; both bound to projection ids internally but rendered without any company detail.
- **Personalization**: none visible to the reader. No business name, city, service, or evidence specific to Webb Air appears in the message. (Package-level content_hash differs from the other two slots only because of internal projection/evidence-id binding.)
- **Required disclaimers / qualification**: the "It is a simulation—not a system deployed, connected, official, or operated by the business" line, plus three **unfilled** required slots: `{{verified_sender_signature}}`, `{{required_postal_disclosure}}`, `{{approved_opt_out_instruction}}`. The conditional follow-up draft carries an explicit `external_precondition`: *"A human must verify outside M5 that a lawful first contact was actually sent through an approved future process."*
- **Also in the package (not in the email)**: a call-opening script, a conditional follow-up draft, 10 validation questions (only `DEMAND_VOLUME` and `RESPONSE_PERFORMANCE` flagged `safe_for_first_contact: true`), and the 7 alternative explanations recorded as `INTERNAL_VISIBLE` risks.
- **Artifact identity**: revision `1d5c39dd…`; email artifact id `2daba224…`.

---

## A.2 — Slot 03, BNCAIR (www.bncair.net)

Same template as A.1. Deltas only:

- **1. Executive**: terminal `CONTACT_PHASE_NOT_AUTHORIZED` (6 stages accepted). M2 statement, alternatives, feasibility dependencies, 10 gaps, 4 assumptions — **identical text to Webb Air**. **Score `review_priority_band = LOW`** (evidence_strength `low`, hypothesis_confidence `low`, business_fit `high`, potential_value/implementation_feasibility `unknown`, important_unknowns `high`). Inference `confidence_band = medium`. Economics `insufficient_data`, all values null, `result_label` identical. Same 10 UNKNOWNs.
- **2. M1 evidence**: 20 evidence rows total (`public_service_description` 12, `public_inbound_path` 5, `public_other` 3) from **3 pages only** (`/`, `/contact-us/`, `/services/`). 2 observations. Supporting evidence pool: 4 rows. Captured public text includes: "BNCAIR / Services / Commercial & Residential HVAC Services / Click Here for Free Estimate", "Contact Us - BNCAIR", a partial street address on the contact page, and an "Air C…" services list. A second projection exists (`mode: conditional_inference`: "The approved public evidence may support evaluating an inbound acknowledgement and qualification opportunity; internal performance remains unknown") but it is **not used in the rendered email**.
  - FACT: BNCAIR publicly describes commercial & residential HVAC and a "Free Estimate" / contact path. INFERENCE: 1, confidence medium. ESTIMATE: none. UNKNOWN: the 10 gaps + everything internal.
- **3. M2 output**: identical statement; **does not claim a current internal problem**; score LOW; economics insufficient_data.
- **4. M3 audit**: revision `603cccb6…`, state `approved`, 9,377-char rendered text, **5 claims, 0 QC findings**. Same 11-section structure; section 3 quotes BNCAIR's (much shorter) captured page text.
- **5. M4 demo**: revision `1d077797…`, state `review_required`. Identical scenario/state-machine/personas/mock-actions/disclaimers; `business_display_name = "BNCAIR"`; no calculator.
- **6. M5 outreach**: revision `d2f37048…`, state `content_approved`, package content_hash `9055c836…`. **Subject and email body byte-identical to Webb Air** (`content_hash 217bc695…`). No BNCAIR-specific content visible to the reader. Same unfilled disclaimer slots, same conditional-follow-up precondition, target_role `service_operations_lead`.

---

## A.3 — Slot 04, All Elements Heating & Air (allelementshvac.com)

Same template. Deltas only:

- **1. Executive**: terminal `CONTACT_PHASE_NOT_AUTHORIZED` (6 stages accepted). M2 statement/alternatives/dependencies/gaps/assumptions **identical text**. **Score `review_priority_band = LOW`** (evidence_strength `low`, hypothesis_confidence `low`, business_fit `high`). Inference `confidence_band = medium`. Economics `insufficient_data`, values null. Same 10 UNKNOWNs.
- **2. M1 evidence**: 115 evidence rows (`public_service_description` 84, `public_other` 24, `public_inbound_path` 4, `public_about` 3) from a **partial crawl (13 of 20 pages captured; 7 page failures)**. 2 observations; supporting evidence pool 30 rows. Captured public text includes service headings ("Heating Services", "HVAC System Maintenance"), commercial-HVAC pages, an About page, and a "Marshall, Texas" service-plan page. A second `conditional_inference` projection exists; **not used in the rendered email**.
  - FACT: All Elements publicly describes residential + commercial HVAC (heating, A/C, mini-split, maintenance, installation), has an About page and a Marshall TX service-area page, and a public contact path. INFERENCE: 1, confidence medium. ESTIMATE: none. UNKNOWN: the 10 gaps + everything internal + the 7 pages that failed to capture.
- **3. M2 output**: identical statement; **does not claim a current internal problem**; score LOW.
- **4. M3 audit**: revision `7646c741…`, state `approved`, 10,216-char rendered text, **5 claims, 0 QC findings**. Same 11 sections; section 3 quotes All Elements' captured page text.
- **5. M4 demo**: revision `f13efff5…`, state `review_required`. Identical template; `business_display_name = "All Elements Heating & Air"`; no calculator.
- **6. M5 outreach**: revision `fbae1127…`, state `content_approved`, package content_hash `227b8f89…`. **Subject and email body byte-identical to the other two** (`content_hash 217bc695…`). No All-Elements-specific content visible to the reader.

---

# B. REVIEWER QUALITY AUDIT (separate analysis — not part of the sealed output)

Scale 1–10. These are the reviewer's judgements about the immutable outputs above.

## B.1 — Per-slot scores

| Dimension | Webb Air | BNCAIR | All Elements |
|---|---|---|---|
| Evidence quality | 6 | 3 | 5 |
| Opportunity specificity | 2 | 2 | 2 |
| Truthfulness / calibration | 9 | 9 | 8 |
| Economic usefulness | 1 | 1 | 1 |
| Audit usefulness | 3 | 2 | 3 |
| Demo usefulness | 4 | 4 | 4 |
| Personalization | 2 | 2 | 2 |
| Outreach quality | 3 | 3 | 3 |
| A real HVAC owner would understand it | 6 | 6 | 6 |
| Would earn a reply / discovery call | 3 | 2 | 2 |

### Why — Webb Air
- **Evidence quality 6**: 24 pages, 161 rows, real signal — an actual **stated public intake SLA** ("email responses next business day; after-hours requests contacted after 8am"), commercial-maintenance-program pages, per-city service-area pages, a commercial testimonial. This is genuinely more than a homepage. Held back because ~25% is `public_other` noise and the "observations" collapse all of it into three generic predicates.
- **Opportunity specificity 2**: the opportunity is the template `inbound_lead_response_qualification` with a statement that could be pasted onto any HVAC company with a contact form. It never references Webb Air's actual published SLA, its 24/7 phone answering, or its commercial-maintenance focus — all of which were captured.
- **Truthfulness / calibration 9**: excellent. It explicitly refuses to claim an internal problem, lists 7 alternative explanations, marks every economic input UNKNOWN, and bands potential_value/feasibility `unknown`. This is the strongest part of the whole system.
- **Economic usefulness 1**: there is no economic output. `insufficient_data`, all nulls. Correct, but a business owner gets zero quantified "why should I care."
- **Audit usefulness 3**: the audit's "publicly observed facts" are raw minimized-text dumps of the same homepage repeated three times, not synthesized findings. Sections 6–10 (alternatives, gaps, questions) are useful as a discovery checklist; sections 3–5 add little.
- **Demo usefulness 4**: the state machine, safety handoff, and mock-only framing are well built and safe, but the demo shows a **generic synthetic intake bot** with synthetic personas and no Webb-Air-specific scenario. An owner would see a competent prototype of "an intake assistant" but nothing that reflects their business.
- **Personalization 2**: `business_display_name` + one quoted page blob. Nothing else.
- **Outreach quality 3**: truthful and non-deceptive, but generic to the point of being cold-open spam-shaped: no name, no specific observation, a vague CTA. The three unfilled `{{…}}` slots mean it is not even a finished draft.
- **Understandable 6**: the email is short and plain-English; an owner would parse it, but "structured acknowledgement and qualification workflow" and "deterministic simulation" are consultant-speak that a field-services owner may bounce off.
- **Reply likelihood 3**: low. It reads like an unsolicited vendor pitch with no hook specific to them and an abstract ask.

### Why — BNCAIR
- **Evidence quality 3**: only 3 pages / 20 rows were available on the site; the crawl exhausted the frontier. Real but thin.
- **Opportunity specificity 2 / personalization 2 / outreach 3**: identical template; nothing BNCAIR-specific reaches the reader.
- **Truthfulness 9**: the LOW score band and `medium` inference confidence correctly reflect the thin evidence — good calibration.
- **Audit usefulness 2**: with only 3 pages the audit is mostly scaffolding.
- **Reply likelihood 2**: lowest — thin evidence, generic message, and (unknown to the recipient) a LOW internal priority.

### Why — All Elements
- **Evidence quality 5**: 115 rows but from a **partial crawl (7/20 pages failed)**; heavy on service-description headings, light on conversion-path evidence (only 4 `public_inbound_path` rows). The About page and Marshall-TX page are useful and unused.
- **Truthfulness 8**: correct LOW band; the only ding is that the M2/M3 output does not surface that the crawl was partial — a reviewer only learns "13/20, 7 failures" from `research_runs.status = partial`, not from the opportunity or audit text.
- Everything else: identical template behavior.

## B.2 — Cross-cutting observations

- **Strongest part (all three)**: truth calibration. The system is scrupulous about not inventing internal facts, records contradictory explanations, marks economics UNKNOWN, and gates the demo/outreach behind simulation disclosures and a human-handoff. It will not embarrass anyone.
- **Weakest part (all three)**: the output is a **template with the company name swapped in**. The M2 statement, M3 section text, M4 scenario, and the entire M5 message are identical across three genuinely different businesses. The pipeline captured company-specific, commercially-relevant facts (Webb Air's published response SLA; All Elements' Marshall-TX coverage; BNCAIR's "Free Estimate" CTA) and used **none of them** in any reader-facing artifact.
- **Generic**: the M2 statement, all 7 alternatives, all 10 gaps, all 6 feasibility dependencies, the demo scenario and personas, the M5 subject + body + CTA.
- **Awkward**: "A structured acknowledgement and qualification workflow could be evaluated for that public request path" — passive, nominal, three abstractions in one sentence. "It is a simulation—not a system deployed, connected, official, or operated by the business" is legally careful but reads as a disclaimer, not a value proposition.
- **Commercially unconvincing**: there is no "here is what we noticed about *your* site," no quantified or even ranged value, no reference customer, no concrete next step beyond "would it be useful to compare." The unfilled `{{verified_sender_signature}}` / `{{required_postal_disclosure}}` / `{{approved_opt_out_instruction}}` slots mean M5 is a skeleton, not a sendable draft.
- **Sounds more certain than the evidence supports**: essentially nothing does — this is a strength. The one soft spot: calling it an "opportunity" (a positive framing) when the artifact's own content establishes only "a public contact form exists and we don't know anything about how it performs."
- **Improvable without changing truth rules**: (a) inject 2–3 specific captured facts into the M2 statement and the M5 email ("your contact page states email replies come the next business day and after-hours requests are returned after 8am — we simulated an acknowledgement step against that stated process"); (b) make the M4 demo scenario use the company's own captured service list and service area instead of synthetic personas; (c) surface `research_runs.status` (partial vs succeeded) and the fact-class mix into the audit so a reviewer sees coverage; (d) replace the abstract CTA with a concrete, low-commitment ask ("2 questions: roughly how many commercial inquiries a month, and how are after-hours ones handled today?" — both already flagged `safe_for_first_contact`); (e) fill the required disclosure slots or mark the package `draft_incomplete` rather than `content_approved`.

## B.3 — Cross-company comparison

| | Webb Air | BNCAIR | All Elements |
|---|---|---|---|
| Opportunity found | inbound lead-response / qualification workflow (template) | same template | same template |
| Genuinely personalized? | No — name + one quote | No | No |
| Evidence-supported opportunity strength | **Strongest** (24 pages, real intake-SLA text, service-area depth, HIGH band) | Weakest (3 pages, LOW band) | Middle (partial crawl, service-desc heavy, LOW band) |
| Strongest audit | **Webb Air** (most cited public facts, incl. the published SLA) | — | All Elements (About + service-area content, but partial) |
| Strongest demo | Tie — the demo is identical; Webb Air's has the richest `statements` binding | — | — |
| Strongest M5 outreach | Tie — byte-identical text; Webb Air's package binds the most supporting evidence | — | — |
| First real pilot candidate (from existing outputs only) | **Webb Air** | | |

**Why Webb Air as the first pilot candidate**: it is the only slot the system itself scored `review_priority_band = HIGH` with `hypothesis_confidence = high` and inference `confidence_band = high`; it has by far the deepest evidence (24 pages vs 3 and 13); and it is the only one where the captured evidence contains a **concrete, checkable public statement about intake behavior** (the contact-page SLA), which gives a real discovery conversation something specific to open with. BNCAIR's site is too thin to support a confident approach; All Elements' crawl was partial and its conversion-path evidence is sparse.

## B.4 — Product-level verdict

1. **Commercially useful, or merely technically valid?** As delivered: **technically valid, not yet commercially useful.** M2–M5 run deterministically, chain provenance correctly, and never overclaim — but the reader-facing artifacts (M2 statement, M3 audit prose, M4 scenario, M5 email) are a single template with a name substitution. Nothing in the outputs would make an HVAC owner feel *seen*.
2. **Does personalization materially reflect the individual company?** **No.** Only `business_display_name` and (in M3) verbatim page quotes vary. The score band and inference confidence differ internally (HIGH vs LOW) but that is never surfaced to the company, and the M5 message is byte-identical across all three.
3. **Are the opportunities specific enough to justify outreach?** **Not yet.** "You have a public contact form and a structured acknowledgement workflow could be evaluated" is true of essentially every business with a website. The specific facts that would justify outreach (Webb Air's published SLA; All Elements' geography; BNCAIR's estimate CTA) were captured and discarded.
4. **Is the demo strong enough to make the opportunity tangible?** **Partially.** The state machine, safety handoff, and mock-only discipline are genuinely good and safe. But with synthetic personas, synthetic inputs, no calculator, and no company-specific scenario, it demonstrates "a generic intake bot," not "what this could do for *your* front desk."
5. **Is M5 good enough to send once the later gates are authorized?** **No.** It is truthful and non-deceptive (a real achievement), but it is a skeleton: three unfilled required-disclosure slots, no personalization, an abstract CTA, and a subject line ("A question about commercial service-request intake") that reads as cold B2B spam. It would need the personalization and a concrete ask before it is worth a send.
6. **Top 3 product deficiencies revealed by these first real outputs**:
   - **(1) Zero reader-facing personalization.** The pipeline extracts company-specific, commercially-relevant facts and then renders identical template text in M2/M3/M4/M5. This is the single biggest gap between "valid" and "useful."
   - **(2) No economic signal of any kind.** Every slot is `insufficient_data` with null values. Correct given the data, but the product currently offers an owner no reason — not even a range or a comparable — to care. Either M2 needs a defensible "typical range for a business of this shape" ESTIMATE band (clearly labelled), or the outreach needs to lead with the discovery questions instead of an unquantified "opportunity."
   - **(3) The audit and demo don't earn their place.** M3's "findings" are re-dumped page text; M4 is a synthetic-persona generic bot. Neither gives a reviewer or an owner more than the M2 statement already does. They add provenance weight and QC structure but little analytical or persuasive value.

---

## Constraints honored
No code or artifact was changed, rerun, re-scored, or reinterpreted. No AI was used to rewrite M5.
M6.6 not activated. Slots 07–24 not started. Read-only diagnostic only; environment dormant throughout;
Terraform NO_CHANGES; all transient task definitions deregistered.
