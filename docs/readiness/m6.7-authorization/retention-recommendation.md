# Phase 1 A-08 Retention Recommendation

**Status:** `APPROVED_POLICY_NOT_LIVE_EFFECTIVE`
**Authority granted:** None

Counsel required ingest minimization, destruction, safeguards, and breach-response controls. The
project owner, acting in the approved privacy/data and security/environment roles pending opaque
identity binding, accepted the successor schedule below on 2026-08-21. These are project controls,
not assertions of statutory retention periods. The policy is approved but is not live-effective;
it grants no capture authority without accepted ADR-0071, a deployed environment, exact sources,
identity bindings, and a separately signed discovery or research release.

## Provisionally approved schedule

| Data class | Proposed period | Start event | Purpose | Deletion/backup treatment |
|---|---:|---|---|---|
| Successful minimized snapshots | 90 days | Company reaches a terminal Phase 1 outcome | Minimized source evidence, provenance challenge, replay and QC | Hard-delete primary/derived bytes and object versions; preserve content-free tombstone; maximum effective retention 120 days including backup overhang |
| Failed/aborted restricted captures | 30 days | Capture/run abort | Incident diagnosis without retaining unusable content indefinitely | Same deletion behavior; incident/legal hold may supersede only through an approved scoped hold |
| Extracted page text/material | 90 days | Company terminal outcome | Deterministic extraction replay and evidence locator validation | Delete text and derived search structures; no person/contact index exists |
| Evidence excerpts and locators | 90 days | Company terminal outcome | Auditability of M2-M5 results | Delete excerpts at expiry; retain approved IDs, hashes, disposition and content-free tombstone; maximum effective retention 120 days |
| Analysis artifacts | 180 days | Company terminal outcome | Observations, inferences, assumptions, economics, audit/demo/outreach lineage and calibration | Delete prose/materialized content; preserve safe IDs, hashes and terminal dispositions as approved |
| Human-review records | 365 days | Review completion | Accountability, disagreement analysis and safety review | Redacted excerpts only; delete free text/attachments; preserve decision code, hash and tombstone if approved; maximum effective retention 395 days |
| Company-level metrics | 180 days | Cohort closure | Phase 1 operational and quality analysis | Delete company dimensions at expiry |
| Approved aggregate cohort metrics | 365 days | Cohort closure | Cross-run calibration without person/contact metrics | Retain only after re-identification/cross-business-risk review; otherwise use 180 days |
| Ordinary operational logs | 90 days | Log event | Reliability, bounded retry and cost reconciliation | Automated log-store expiry; never page/contact values |
| Restricted access/security/audit logs | 365 days | Audit event | Access accountability, incident investigation and deletion proof | Append-protected expiry; restricted security consumers only |
| Encrypted backups | 30-day rolling maximum | Backup creation | Disaster recovery | A backup cannot extend a source data class by more than 30 days; restore reapplies tombstones and deletion queue before ordinary access |
| Content-free deletion tombstones | 730 days | Deletion completion | Prove deletion and prevent accidental recreation | Hashes, internal IDs and content-free audit metadata only; no source URL, page, evidence, person or contact value |

Every governed class binds primary stores, replicas, object versions, backups and derived stores.
Destruction methods are hard deletion, object-version lifecycle deletion, log expiry, cryptographic
erasure/key destruction for expired encrypted backups, and content-free tombstones as appropriate.
The machine-readable schedule is `phase1-retention-policy-v1.json`.

## Recommended legal-hold policy

- Holds are exceptional, exact-data-class and exact-artifact scoped.
- A hold requires a qualified legal approval ID, reason, start, expiry, and accountable custodian.
- Recommended maximum initial hold interval: 90 days, followed by explicit 90-day reapproval.
- Operators cannot use a hold to avoid ordinary retention review.
- Hold release immediately restores the original deletion calculation; it does not begin a new full
  retention period.

## Required approval questions

1. Are the 30/90/180/365/730-day recommendations necessary and proportionate for their purposes?
2. Must any data class be shorter because public pages may contain incidental personal information?
3. Can evidence remain 90 days longer than raw captures using excerpts, locators and hashes?
4. Are security/access logs required or justified for 365 days in the selected environment?
5. Is a 30-day backup overhang technically and legally acceptable, and can restoration enforce
   tombstones before data becomes accessible?
6. Is the 730-day content-free tombstone period justified for deletion proof and recreation safety?
7. What legal-hold authority, custodian, scope and review cadence apply?

Any extension requires a successor retention revision and the same accountable approval classes.
There is no automatic extension and no indefinite-retention option.
