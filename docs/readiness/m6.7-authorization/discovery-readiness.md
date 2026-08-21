# REAL_BUSINESS_DISCOVERY Readiness

**Current state:** `NOT_READY_TO_AUTHORIZE_DISCOVERY`
**Permission state:** `NOT_AUTHORIZED`
**Release signed:** No

Run `python scripts/validate_m67_authorization_package.py` for the machine-readable current blocker
projection. The validator performs no DNS, network, cloud, person/contact, provider, or delivery
operation.

## Exact unsigned release scope

The future `REAL_BUSINESS_DISCOVERY` release may authorize only:

- ingestion of the exact approved `PHASE1_OWNER_SEED_MANIFEST_V1` hash;
- bounded validation of exact approved first-party host candidates;
- eligibility, deduplication, organization/shared-brand clustering, and identity review;
- deterministic freezing of the 24-company order and reserve order.

It must bind the exact A-08, A-09, A-17, ADR-0071, environment, role, budget, seed-manifest,
cohort-policy, kill-switch, start/expiry, approval, and configuration hashes. It must retain state
`NOT_AUTHORIZED` until the project owner performs a separate final signature event.

It cannot authorize deep research, browser use, person/contact extraction/index/search/projection,
forms, booking, chat, mailboxes, communication, M6 activity, delivery, or AI.

## Current exact blockers

- Actual deployed AWS environment and evidence; intended configuration is insufficient.
- Accepted A-03 tenancy, A-04 cloud/region/data, and A-07 identity/governance records.
- Actual protected state bucket/KMS key, approved partial backend configuration, and reviewed plan
  under accepted ADR-0075. The cross-platform AWS provider lock is complete but grants no authority.
- Explicit AWS charge authorization remains absent. The owner's Terraform-code authorization permits
  formatting, validation and non-creating plan preparation only; it does not permit apply or charges.
- Opaque stable subject bindings for the owner actor, PRIMARY_A actor, and external-attorney record;
  the human role decisions are approved but no identity-provider subjects were invented.
- Exact A-09 approval for the provenance-backed seed artifact and every discovery host instance.
- Acceptance of ADR-0071 after the deployed storage/environment and identity dependencies are
  complete. A-08 is approved but not live-effective, and A-17 is `APPROVE_WITH_CONTROLS`.
- A populated, provenance-backed, approved and frozen seed manifest with at most 100 candidates.
- Final project-owner discovery-release signature after every other blocker clears.

Only when every blocker except the final signature is resolved may the state become
`READY_FOR_DISCOVERY_AUTHORIZATION_SIGNATURE`. No transition is automatic.
