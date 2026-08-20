# Phase 1 A-08 Retention Recommendation

**Status:** `OWNER_PROVISIONALLY_APPROVED_PENDING_LEGAL_REVIEW`
**Authority granted:** None

The project owner provisionally approved the values below on 2026-08-20 as architecture and project
retention choices for a small calibration cohort. They are not asserted to be statutory
requirements. Qualified legal review must decide whether a shorter, longer, or event-based period
is required or justified, after which the privacy/data and security/environment owners must approve
the resulting exact policy. A-08 therefore remains blocked and this record grants no capture
authority.

## Provisionally approved schedule

| Data class | Proposed period | Start event | Purpose | Deletion/backup treatment |
|---|---:|---|---|---|
| Restricted successful raw/public snapshots | 90 days | Company reaches a terminal Phase 1 outcome | Source fidelity, provenance challenge, replay and QC | Delete primary bytes; preserve content hash and deletion tombstone; restored backup bytes immediately re-enter deletion queue |
| Failed/aborted restricted captures | 30 days | Capture/run abort | Incident diagnosis without retaining unusable content indefinitely | Same deletion behavior; incident/legal hold may supersede only through an approved scoped hold |
| Extracted page text/material | 90 days | Company terminal outcome | Deterministic extraction replay and evidence locator validation | Delete text and derived search structures; no person/contact index exists |
| Evidence excerpts and locators | 180 days | Company terminal outcome | Auditability of M2-M5 results after raw capture expiry | Delete excerpts at expiry; retain IDs, hashes, disposition and content-free tombstone |
| Analysis artifacts | 180 days | Company terminal outcome | Observations, inferences, assumptions, economics, audit/demo/outreach lineage and calibration | Delete prose/materialized content; preserve safe IDs, hashes and terminal dispositions as approved |
| Human-review records | 365 days | Review completion | Accountability, disagreement analysis and safety review | Delete free text/attachments; preserve decision code, hash and tombstone if approved |
| Company-level metrics | 180 days | Cohort closure | Phase 1 operational and quality analysis | Delete company dimensions at expiry |
| Approved aggregate cohort metrics | 365 days | Cohort closure | Cross-run calibration without person/contact metrics | Retain only after re-identification/cross-business-risk review; otherwise use 180 days |
| Ordinary operational logs | 90 days | Log event | Reliability, bounded retry and cost reconciliation | Automated log-store expiry; never page/contact values |
| Restricted access/security/audit logs | 365 days | Audit event | Access accountability, incident investigation and deletion proof | Append-protected expiry; restricted security consumers only |
| Encrypted backups | 30-day rolling maximum | Backup creation | Disaster recovery | A backup cannot extend a source data class by more than 30 days; restore reapplies tombstones and deletion queue before ordinary access |
| Content-free deletion tombstones | 730 days | Deletion completion | Prove deletion and prevent accidental recreation | IDs/hashes/reason/timestamps only; no page, evidence, person or contact value |

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
