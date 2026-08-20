# Phase 1 Scope Approval and Independent Authorization Drafts

**Status:** `OWNER_SCOPE_APPROVED_AUTHORIZATION_DRAFTS_NOT_AUTHORIZED`
**Real company identifiers present:** 0

## Human-readable Phase 1 approval record

This record approves scope and selection mechanics only. It must not name, rank, prefer or select a
company and cannot authorize source access.

```text
record_type = PHASE1_COHORT_SCOPE_APPROVAL
state = OWNER_SCOPE_APPROVED_NO_LIVE_AUTHORITY
jurisdiction = US-TX
vertical = COMMERCIAL_HVAC
business_model = B2B_RELEVANT
opportunity = INBOUND_LEAD_RESPONSE
target_size = 24
unit_of_analysis = ONE_DISTINCT_PUBLIC_BUSINESS_LEAD_FLOW
public_first_party_web_presence_required = true
cohort_policy_version = m6.7a.phase-1-cohort-policy@1
source_policy_version = UNAPPROVED_A09_SUCCESSOR_REQUIRED
retention_policy_version = UNAPPROVED_A08_SUCCESSOR_REQUIRED
franchise_shared_brand_cap = 1
multi_location_split = ONLY_WHEN_DISTINCT_PUBLIC_LEAD_FLOW_IS_VERIFIED
sampling = FROZEN_SEEDED_SYSTEMATIC_RANDOM_ORDER
reserve_order = FROZEN_BEFORE_RESEARCH
replacement = PREDETERMINED_COHORT_INELIGIBILITY_ONLY
research_failure_replacement = false
insufficient_evidence_replacement = false
no_supported_opportunity_replacement = false
opportunity_or_yield_based_replacement = false
execution = STAGED
initial_execution_scope = SLOT_1_ONLY
automatic_slot_2 = false
company_selection_performed_by_this_approval = false
owner_approval_id = M67_PHASE1_OWNER_DECISIONS_2026-08-20_01
privacy_approval_id = UNRESOLVED
incident_owner_acknowledgement_id = UNRESOLVED
effective_at = UNRESOLVED
expires_at = UNRESOLVED
configuration_hash = NOT_COMPUTABLE
```

The exact candidate-frame maximum, source-manifest artifact/provenance, negative-QA sample,
contiguous small-batch size and frozen seed generation value remain unresolved. They must be frozen
before outcomes are visible. The owner-approved strategy requires a complete frozen cohort first,
slot one only, mandatory pause, a contiguous small batch only after separate continuation approval,
another mandatory pause, and the remainder only after another separate continuation approval.

## Draft 1 — REAL_BUSINESS_DISCOVERY

```yaml
record_type: LIVE_RESEARCH_PERMISSION_RELEASE
activity: REAL_BUSINESS_DISCOVERY
state: NOT_AUTHORIZED
resulting_governance_state_if_signed: REAL_BUSINESS_DISCOVERY_AUTHORIZED
jurisdiction: US-TX
vertical: COMMERCIAL_HVAC
purpose: B2B_INBOUND_LEAD_RESPONSE_ANALYSIS_COHORT_CONSTRUCTION_ONLY
allowed_sources:
  - PHASE1_OWNER_SEED_MANIFEST_V1@EXACT_HASH_REQUIRED
  - FIRST_PARTY_DISCOVERY_HOST_SET@DERIVED_FROM_SIGNED_MANIFEST
optional_government_sources: []
prohibited:
  - DEEP_PUBLIC_PAGE_RESEARCH
  - PERSON_OR_CONTACT_EXTRACTION_INDEX_SEARCH_OR_PROJECTION
  - SOCIAL_REVIEW_PEOPLE_EMAIL_FINDER_OR_AUTHENTICATED_SOURCE
  - BROWSER_FORM_BOOKING_CHAT_MAILBOX_OR_BYPASS
  - OUTREACH_OR_DELIVERY
retention_policy_revision: UNRESOLVED
source_policy_revision: UNRESOLVED
environment_revision: UNRESOLVED
cohort_scope_approval_id: UNRESOLVED
seed_manifest_hash: UNRESOLVED
workload_budget_revision: UNRESOLVED
monetary_budget_revision: UNRESOLVED
role_assignment_revision: UNRESOLVED
a17_legal_release_id: UNRESOLVED
kill_switch_id: UNRESOLVED
starts_at: UNRESOLVED
expires_at: UNRESOLVED
accountable_approval_ids: []
configuration_hash: NOT_COMPUTABLE
```

Signing this release permits only import/validation of the approved candidate manifest, exact-host
discovery validation within its allocation, deterministic eligibility/deduplication/clustering, and
freezing the frame/selection/reserve order. It grants no `REAL_PUBLIC_RESEARCH` authority.

After the exact 24-company frame and selection are frozen, the control plane pauses. No M1 deep
research command can be claimed while the research release remains `NOT_AUTHORIZED`.

## Draft 2 — REAL_PUBLIC_RESEARCH

This release can be completed only after discovery has produced immutable frame, selection and exact
source-host records.

```yaml
record_type: LIVE_RESEARCH_PERMISSION_RELEASE
activity: REAL_PUBLIC_RESEARCH
state: NOT_AUTHORIZED
resulting_governance_state_if_signed: REAL_PUBLIC_RESEARCH_AUTHORIZED
jurisdiction: US-TX
vertical: COMMERCIAL_HVAC
purpose: B2B_INBOUND_LEAD_RESPONSE_ANALYSIS_PUBLIC_EVIDENCE_CAPTURE
discovery_release_id_and_hash: UNRESOLVED_FUTURE_IMMUTABLE_VALUE
sampling_frame_id_and_hash: UNRESOLVED_FUTURE_IMMUTABLE_VALUE
cohort_selection_id_and_hash: UNRESOLVED_FUTURE_IMMUTABLE_VALUE
exact_24_research_source_ids_and_hashes: []
browser_fallback: DISABLED
person_contact_projection: PROHIBITED
interactive_or_state_changing_operations: PROHIBITED
retention_policy_revision: UNRESOLVED
environment_revision: UNRESOLVED
workload_and_monetary_budget_revision: UNRESOLVED
role_assignment_revision: UNRESOLVED
a17_legal_release_id: UNRESOLVED
kill_switch_id: UNRESOLVED
starts_at: UNRESOLVED
expires_at: UNRESOLVED
accountable_approval_ids: []
configuration_hash: NOT_COMPUTABLE
```

The approval event must be distinct from discovery approval and must occur after reviewers inspect
the frozen cohort and exact source entries. It cannot add, replace, reorder or discover companies.

## Draft 3 — RUN_PHASE_1_SLOT_1_ONLY

Even after both permissions are independently authorized, no company run begins without this exact
run authorization.

```yaml
record_type: STAGED_RUN_AUTHORIZATION
activity: RUN_PHASE_1_SLOT_1_ONLY
state: NOT_AUTHORIZED
resulting_governance_state_if_signed: READY_TO_RUN_SLOT_1
discovery_release_id_and_hash: UNRESOLVED
research_release_id_and_hash: UNRESOLVED
sampling_frame_id_and_hash: UNRESOLVED
cohort_selection_id_and_hash: UNRESOLVED
frozen_order_hash: UNRESOLVED
slot_number: 1
slot_1_business_id: UNRESOLVED_FROZEN_VALUE
slot_1_exact_research_source_id: UNRESOLVED_FROZEN_VALUE
maximum_companies: 1
worker_concurrency: 1
automatic_slot_2: false
mandatory_pause_after_terminal_outcome: true
kill_switch_id: UNRESOLVED
budget_reservation_id: UNRESOLVED
owner_approval_id: UNRESOLVED
incident_owner_acknowledgement_id: UNRESOLVED
privacy_owner_acknowledgement_id: UNRESOLVED
starts_at: UNRESOLVED
expires_at: UNRESOLVED
configuration_hash: NOT_COMPUTABLE
```

## Mandatory slot-one pause report

Before any slot-two/small-batch decision, the immutable report must contain:

- Candidate, discovery, identity, sampling-slot and exact source provenance.
- Every source access attempt: time, source ID, exact safe URI, method, robots/terms revision, status,
  bytes, retries, cache and cost; no ordinary-log page/contact body.
- M1 pages/snapshots/extracted material/evidence and exact hashes/lineage.
- M2 observation/inference/contradiction/alternative/information-gap/opportunity/economics outcome,
  preserving UNKNOWN and human-review records.
- M3 audit, M4 demo and M5 outreach states and QC/review outcomes if each stage was eligible.
- Required, completed, escalated and outstanding human reviews plus measured durations.
- Workload and monetary reservation/reconciliation by stage; human time separately.
- Warnings, source drift, unsupported/scoped-absence/entity/contradiction findings.
- Safety incidents, quarantine/pause/termination decisions and kill-switch state.
- Incidental-data observations, restricted-access events, deletion schedule and privacy findings,
  without person/contact projection.
- Exact terminal company state and explanation of any stopped/bypassed downstream stage.

The failure, insufficiency, rejection or no-opportunity outcome of slot one remains the true cohort
outcome. It does not authorize replacement, reordering, tuning or automatic slot two.
