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

## M2.5 qualification data

- Controlled corpus labels, evaluator decisions, and model-quality annotations are `Internal`.
- Raw future provider requests/responses are `Confidential` and require an approved retention rule;
  M2.5 does not persist them.
- Invocation ledgers contain identifiers, hashes, safe outcomes, usage, latency, and cost metadata,
  not page bodies or prompts.
- Normal CI uses deterministic mocks and controlled synthetic fixtures with zero provider network
  access.
- A future live evaluation may use only an explicitly approved data class, provider policy,
  deployment/task allowlist, and budget under ADR-0014.

## M2.6 controlled live evaluation

- Only repository-owned synthetic qualification fixtures may leave the local environment.
- Real prospect, customer, confidential, private, personal, raw website, and production workflow data
  are prohibited.
- Raw provider request/response bodies are ephemeral and are not persisted.
- Safe results contain fixture/deployment identifiers, semantic outputs, hashes, gate outcomes, token
  usage, latency, retry counts, provider response identifiers, and calculated cost only.
- The explicit tournament runner has a USD 50 total hard cap and per-deployment sub-budgets.
- Normal tests never load credentials and deny network access through fake transports.

## M3 audit data

- Audit drafts and reviewer edits are `Confidential`.
- M3 stores bounded evidence excerpts and canonical IDs/hashes only; M1 remains owner of snapshots
  and raw source content.
- M3 stores no provider payload and invokes no live provider.
- Ordinary logs contain IDs, hashes, statuses, timings, and QC codes rather than audit prose,
  evidence bodies, or reviewer edits.
- M3 establishes no retention schedule and inherits future A-08 policy.

## M4 demo data

- Demo manifests, specifications, reviews, and drafts are `Confidential`; safe registry/configuration
  metadata is `Internal`.
- Personas and interactive lead data are repository-owned synthetic fixtures. Actual names, contact
  destinations, addresses, credentials, payment/health data, and production leads are prohibited.
- One-time capability and runtime-session plaintext tokens are returned only to their authorized
  caller and are never persisted; local persistence stores SHA-256 digests.
- Telemetry is limited to approved IDs, registered event/outcome codes, durations, and synthetic
  fixture IDs. It stores no free text, contact data, evidence body, audit prose, token, or transcript.
- M4 establishes no production telemetry or demo-retention schedule.

## M5 outreach-package data

- Outreach manifests, projections, artifacts, risks, reviews, and reviewer edits are `Confidential`;
  safe template/role/policy metadata is `Internal`.
- M5 stores no person, recipient address, phone, email, social profile, contact destination, delivery
  event, reply, or engagement data.
- External drafts retain exact approved claim IDs and lineage; internal economics preserve source
  value states and never authorize external financial use.
- Ordinary logs contain IDs, hashes, states, timings, and QC codes rather than draft prose, evidence
  bodies, internal notes, contact data, or reviewer edits.
- M5 establishes no copy, export, publication, delivery, or production retention schedule.

## M6 synthetic contact and delivery data

- Local/test M6 accepts only repository-owned synthetic identities and reserved `fixture.invalid`
  contact/sender values. Real personal or regulated data remains prohibited.
- Contact details, reply bodies, and first-party statements are `Confidential`. API views redact
  contact values and raw replies; ordinary logs contain safe IDs, hashes, states, and QC codes.
- Production field protection, access policy, retention/deletion, suppression tombstone policy, and
  a signed A-17 release are required before real data or delivery.
- Deterministic CI has no provider credential and performs zero external person, verification,
  email, webhook, DNS, or delivery calls.

## M6.5 activation-readiness data

- M6.5 stores configuration, artifact references, hashes, approvals, safe gate outcomes, fixture
  attestations, and deterministic test evidence only. Local records contain no real person/contact,
  provider payload, domain credential, legal rule, secret, or message.
- Initial source/proof records are visibly inactive proposals. A governance schema or accepted ADR
  does not constitute a signed production legal/privacy release.
- Real company research, identity resolution, contact storage, verification, eligibility, and
  SHADOW_READY each require independent future permission. All are disabled in M6.5.
- SHADOW_READY is Confidential governance metadata when later used with real candidates, but M6.5
  tests use repository-owned synthetic identifiers only.

## Backups and recovery

Backup scope, encryption, point-in-time recovery, RTO/RPO, region, retention, and restoration cadence remain blocked on A-04, A-08, and A-18. No infrastructure implementation should imply values for them.
