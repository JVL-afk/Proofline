# M6.7B A-08 Retention, Privacy, and Deletion Decision Package

**Status:** `AWAITING_ACCOUNTABLE_APPROVAL`
**Version:** `m67b-retention-policy@draft-1`
**Authority granted:** None

This package is concrete about lifecycle behavior but intentionally contains no invented duration.
Every `RETENTION_VALUE_REQUIRED` cell must be replaced by an owner-approved ISO-8601 duration or a
precise event-based rule before the policy can be accepted. Empty, unlimited, “reasonable,” and
“until no longer needed” values are invalid.

## Required policy constants

| Field | Required decision |
|---|---|
| `active_run_window` | `RETENTION_VALUE_REQUIRED` |
| `post_run_review_window` | `RETENTION_VALUE_REQUIRED` |
| `approved_artifact_window` | `RETENTION_VALUE_REQUIRED` |
| `security_audit_log_window` | `RETENTION_VALUE_REQUIRED` |
| `deletion_tombstone_window` | `RETENTION_VALUE_REQUIRED` |
| `backup_expiry_window` | `RETENTION_VALUE_REQUIRED` |
| `legal_hold_review_interval` | `RETENTION_VALUE_REQUIRED` |
| `failed_or_aborted_capture_window` | `RETENTION_VALUE_REQUIRED` |

The privacy/data owner proposes values using documented operational need and qualified legal input.
The project owner accepts the product tradeoff. Security verifies that storage, backup, and deletion
systems can enforce the selected values. Extension always requires a successor policy and explicit
approval; operators cannot extend retention ad hoc.

## Data-class schedule

| Data class | Purpose | Sensitivity | Allowed consumers | Proposed retention binding | Deletion behavior | Backup treatment | Extension |
|---|---|---|---|---|---|---|---|
| Restricted raw snapshots | Exact source fidelity, hashing, replay, provenance | Confidential; may include incidental public person/contact data | Research worker, evidence reviewer, privacy/incident owner under audited break-glass | Active run + review + `approved_artifact_window`; exact values required | Revoke access, delete primary bytes, retain content-free hash/tombstone | Encrypted; inaccessible after primary deletion except controlled restoration; expires by `backup_expiry_window` | Successor policy approval |
| Extracted page text/material | Deterministic extraction and evidence location | Confidential; untrusted source content | M1 worker, authorized M2-M5 readers, reviewers | No longer than source snapshot unless a shorter approved value applies | Delete fragments/indexes and invalidate dependent cache; keep content-free deletion evidence | Same or shorter than source snapshot | Successor policy approval |
| Evidence | Exact public observation with snapshot locator | Internal/Confidential depending on excerpt | M1-M5 canonical readers and reviewers | `approved_artifact_window`; cannot outlive required provenance unless policy defines an integrity-preserving tombstone | Delete excerpt/value; keep IDs, hashes, disposition, and deletion reason if approved | Encrypted and expiry-bound | Successor policy approval |
| Observations/inferences | Company-level reasoning lineage | Internal; potentially confidential when text repeats source material | M2-M5 and reviewers | `approved_artifact_window`, with supersession rule below | Delete prose/materialized values; preserve non-content state/hash tombstone | Encrypted and expiry-bound | Successor policy approval |
| Review artifacts | Decisions, warnings, rationale, measured time | Confidential | Assigned reviewers, project/privacy/incident owner | `post_run_review_window` or approved artifact window as explicitly selected | Delete free text and attachments; retain decision code/hash/tombstone if approved | Encrypted and expiry-bound | Successor policy approval |
| Metric snapshots | Cohort measurement without person/contact metrics | Internal | Project owner, reviewers, operations | Separately approved aggregate window only after re-identification/cross-company risk review | Delete company dimensions first; retain aggregate only under explicit rule | Aggregates and detailed data use separate backup classes | Successor policy approval |
| Operational logs | IDs, hashes, safe states, timings, error codes; never source/contact values | Internal security/operations | Operations, security, incident owner | `security_audit_log_window` | Log-store expiry; no page bodies/contact values to redact | Encrypted, access-logged, same expiry class | Successor policy approval |
| Access/audit logs | Who accessed restricted data, when, purpose, outcome | Confidential security record | Security/privacy/incident owner | `security_audit_log_window` | Expire under append-protected policy; legal hold only by controlled override | Separate protected backup class | Successor policy approval |
| Backups | Recovery of in-policy data | Same as highest contained class | Restore identity and authorized recovery operators | `backup_expiry_window`; cannot become an undeclared archive | Crypto-erasure or provider-supported deletion; restoration reapplies pending deletions | Inventory, restore test, destruction evidence required | Successor policy approval |
| Superseded artifacts | Auditability and revision comparison | Same as original artifact | Same consumers as original | Bind to original class and supersession event; no indefinite default | Delete content at class expiry; retain successor/predecessor IDs and hashes only if approved | Same as original class | Successor policy approval |
| Deletion/tombstone records | Prove deletion without retaining deleted content | Internal | Privacy/security/audit owners | `deletion_tombstone_window` | Final expiry removes tombstone unless an accepted recordkeeping rule says otherwise | Backed up only within its own window | Successor policy approval |
| Legal-hold copies | Preserve specifically identified material when legally required | Confidential/restricted | Named legal custodian and minimum technical operators | Until hold release, with mandatory `legal_hold_review_interval`; no blanket hold | Delete promptly after release under recorded instruction | Segregated, encrypted, no ordinary restore | Named legal authorization only |

## Incidental personal-information controls

- Incidental person/contact information remains only within the restricted capture or unavoidable
  source-faithful text/evidence fragment.
- It is never projected to person/contact tables, indexed as a person/contact field, exposed by a
  search endpoint, included in Phase 1 metrics, or written in ordinary logs.
- Access requires a purpose code and is audit logged. Bulk export is prohibited.
- A deletion/correction/request process cannot be claimed until qualified counsel determines
  applicable law, scope, authentication, exceptions, and response ownership.
- Public availability is source metadata, not a universal exemption from contract, copyright,
  privacy, security, or ethical constraints.

## Deletion workflow

1. Create a request bound to workspace, business, run, artifact classes, authority, and policy.
2. Suspend affected access and prevent new downstream use.
3. Delete primary bytes, extracted values, caches, indexes, and derived copies in dependency order.
4. Mark canonical projections invalid/stale without rewriting historical truth.
5. Record content-free hashes, affected IDs, reason, executor identity, and timestamps.
6. Queue backup expiry; restoration replays the deletion ledger before data becomes usable.
7. Verify deletion and close with independent privacy/security review.

## Approval checklist

- [ ] Every retention constant has an exact value and rationale.
- [ ] Qualified legal reviewer records applicability and legal-hold conclusions.
- [ ] Privacy/data owner approves incidental-data handling and request procedures.
- [ ] Security owner verifies deletion, encryption, access, audit, backup, and restore controls.
- [ ] Project owner accepts evidence-integrity and deletion tradeoffs.
- [ ] A-18 owner verifies operational cost and storage feasibility.
- [ ] Synthetic deletion/restore tests pass before any live permission release.
