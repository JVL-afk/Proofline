# M6.7B Draft Live-Research Permission Releases

**Status:** `DRAFT_NOT_AUTHORIZED`
**Runtime records created:** Zero

These are exact design shapes, not application records. Missing values deliberately prevent hashing,
signature, activation, and execution. Discovery and research use separate immutable releases.

## Common immutable envelope

```text
release_id
predecessor_release_id | null
activity
state = NOT_AUTHORIZED | AUTHORIZED | SUSPENDED | EXPIRED
jurisdiction = US-TX
vertical = COMMERCIAL_HVAC
purpose = M67_PHASE1_INBOUND_LEAD_RESPONSE_QUALIFICATION_SHADOW_VALIDATION
prohibited_purposes
source_policy_version
source_instance_ids
retention_policy_version
environment_id + environment_attestation_hash
workspace_id
cohort_policy_version
sampling_frame_id | null
selection_manifest_id | null
run_id | null
configuration_versions
starts_at
expires_at
accountable_approvals
kill_switch_owner_role
suspension_reason | null
revocation_evidence_refs
created_at
configuration_hash
```

Rules:

- `configuration_hash` is computed only when every mandatory value is final.
- `AUTHORIZED` requires a future explicit command binding the final hash and approvals. Drafting,
  accepting an ADR, or authorizing another activity cannot change state.
- Expiry is mandatory and cannot exceed any source, retention, environment, terms, or approval
  expiry. The earliest expiry wins.
- Suspension rejects new work and pauses/checkpoints in-flight work at the next safe boundary.
- Revocation is represented by an immutable successor in `SUSPENDED` or `EXPIRED` state with
  evidence; historical releases are never rewritten.
- Resumption requires a new successor with fresh attestations and approval. No automatic resume.

## Draft discovery release

```yaml
activity: REAL_BUSINESS_DISCOVERY
state: NOT_AUTHORIZED
jurisdiction: US-TX
vertical: COMMERCIAL_HVAC
purpose: M67_PHASE1_COHORT_CONSTRUCTION_ONLY
prohibited_purposes:
  - PUBLIC_PAGE_RESEARCH
  - PERSON_OR_ROLE_RESOLUTION
  - CONTACT_COLLECTION_OR_VERIFICATION
  - OUTREACH_OR_DELIVERY
source_policy_version: m67b-source-policy@UNAPPROVED
source_instance_ids: []
retention_policy_version: m67b-retention-policy@UNAPPROVED
environment_id: UNRESOLVED
environment_attestation_hash: UNRESOLVED
workspace_id: UNRESOLVED
cohort_policy_version: m67a.phase-1-cohort-policy@1
sampling_frame_id: null
selection_manifest_id: null
run_id: null
configuration_versions:
  discovery_adapter: UNSELECTED
starts_at: UNRESOLVED
expires_at: UNRESOLVED
accountable_approvals: []
kill_switch_owner_role: UNASSIGNED
configuration_hash: NOT_COMPUTABLE
```

The discovery release may permit only approved source-instance operations needed to construct and
freeze a candidate frame. It grants no access to a candidate's website for research. Cohort
selection happens only after discovery-source approval and frame review.

## Draft research release

```yaml
activity: REAL_PUBLIC_RESEARCH
state: NOT_AUTHORIZED
jurisdiction: US-TX
vertical: COMMERCIAL_HVAC
purpose: M67_PHASE1_M1_PUBLIC_EVIDENCE_CAPTURE_ONLY
prohibited_purposes:
  - BUSINESS_DISCOVERY_OUTSIDE_FROZEN_SELECTION
  - PERSON_OR_ROLE_RESOLUTION
  - CONTACT_EXTRACTION_INDEXING_SEARCH_OR_PROJECTION
  - BROWSER_AUTOMATION
  - AUTHENTICATED_OR_ACCESS_CONTROLLED_CONTENT
  - FORM_CHAT_BOOKING_MAILBOX_OR_OTHER_SIDE_EFFECT
  - OUTREACH_OR_DELIVERY
source_policy_version: m67b-source-policy@UNAPPROVED
source_instance_ids: []
retention_policy_version: m67b-retention-policy@UNAPPROVED
environment_id: UNRESOLVED
environment_attestation_hash: UNRESOLVED
workspace_id: UNRESOLVED
cohort_policy_version: m67a.phase-1-cohort-policy@1
sampling_frame_id: UNRESOLVED_FUTURE_FROZEN_ID
selection_manifest_id: UNRESOLVED_FUTURE_FROZEN_ID
run_id: UNRESOLVED_FUTURE_RUN_ID
configuration_versions:
  research_policy: m1.http-first@UNAPPROVED_LIVE_SUCCESSOR
  browser_fallback: DISABLED
  shadow_orchestrator: m67.phase1-db-orchestrator@UNIMPLEMENTED
starts_at: UNRESOLVED
expires_at: UNRESOLVED
accountable_approvals: []
kill_switch_owner_role: UNASSIGNED
configuration_hash: NOT_COMPUTABLE
```

The research release is restricted to the exact frozen selection and run. It cannot add, replace,
or discover companies. A research failure remains the company's true outcome. Authorization of
discovery is neither a prerequisite shortcut nor inherited authorization; research receives its own
approval after the cohort is frozen.

## Approval evidence required by both

- Accepted ADR-0071 and exact A-08/A-09 versions.
- Signed A-17 Texas research release.
- Accepted A-03/A-04/A-07 environment and access decision plus attestation.
- Accepted A-18 monetary/non-monetary budget and named operational ownership.
- M6.7C synthetic pre-live test report and zero-delivery dependency proof.
- Project owner, privacy/data owner, security/incident owner, and qualified legal review records.
- Exact start/expiry and tested kill-switch operator.
