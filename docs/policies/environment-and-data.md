# Environment and Data Policy — M0 Baseline

## Environment separation

- Development, staging, and production use separate cloud accounts/projects, credentials, encryption keys, storage namespaces, and databases when selected.
- Production data is not copied to lower environments.
- Local/test environments use synthetic fixtures; sanitization requires an approved process, not an ad hoc export.
- Production access is least-privilege, time-bounded where practical, and audited.

## Data classes

| Class | Examples | Baseline handling |
|---|---|---|
| Public | Approved public business pages and source URLs | Still untrusted; retain only under approved source/retention policy |
| Internal | Configuration, non-public operational metadata, evaluation labels | Authenticated access; no public sharing |
| Confidential | Provider payloads, reviewer edits, audit/demo drafts, contact details | Restricted roles, encryption, minimized logs/exports |
| Secret | Credentials, tokens, signing/encryption keys | Secret manager only; never database/plaintext/log/source control |
| Regulated/sensitive | Personal or jurisdictionally protected data | Do not collect until an accountable policy/legal decision permits it |

## Collection and retention

- Collect only data required by an approved product/source decision.
- Attach source, capture time, classification, and retention class at ingestion.
- Raw snapshots, extracts, derived evidence, model/provider payloads, and approved artifacts may have different retention periods.
- A retention schedule and deletion/exception process must be approved before live research.
- “Publicly accessible” does not imply unlimited collection, reuse, or retention.

## Lower-environment controls

- External provider calls default to mocks/fixtures.
- Live-provider smoke tests use separate low-budget credentials and approved test data.
- No live outreach or active business form/chat/booking interactions.
- Test fixtures containing hostile content are isolated and clearly labeled.

## Backups and recovery

Backup scope, encryption, point-in-time recovery, RTO/RPO, region, retention, and restoration cadence remain blocked on A-04, A-08, and A-18. No infrastructure implementation should imply values for them.
