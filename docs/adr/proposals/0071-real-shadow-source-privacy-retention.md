# ADR-0071: Real public-research sources, incidental personal data, retention, and environment

- **Status:** Proposed — controls implemented; blocked on deployed environment and identity binding
- **Date:** 2026-08-20
- **Decision owners:** Unassigned project, privacy/data, security, and qualified legal owners
- **Decision register:** A-03, A-04, A-07, A-08, A-09, A-17, and A-18

## Context

M6.7A proved a synthetic shadow-validation control plane. A future M6.7 phase may research actual
Texas Commercial HVAC businesses, but public pages can contain incidental names, professional
email addresses, telephone numbers, and other information associated with individuals. Public
availability is neither blanket collection permission nor permission to reuse data for contact.

The project owner accepted exact retention values and recorded counsel's `APPROVE_WITH_CONTROLS`
result on 2026-08-21. Exact source instances, a deployed environment, identity-provider bindings,
and deployment evidence remain absent. Therefore this ADR is implementation-ready but cannot yet
be accepted for live use or authorize `REAL_BUSINESS_DISCOVERY` or `REAL_PUBLIC_RESEARCH`.

## Decision drivers

- Preserve exact source fidelity and evidence provenance without creating a contact database.
- Separate discovery-source approval from research-source approval.
- Minimize collection and make deletion, access, and audit behavior explicit before live data.
- Keep browser automation, authenticated content, access-control bypass, people/contact projection,
  and communication outside Phase 1.
- Bind every future permission to exact policy, environment, cohort, approval, start, and expiry.

## Considered options

1. Ephemeral raw fetch followed by deterministic minimization and a durable minimized capture.
2. Restricted immutable raw captures with no person/contact projection or indexing.
3. Treat publicly accessible content as unrestricted and retain it indefinitely.
4. Allow source capture but immediately extract person/contact records for later use.

## Decision

The proposed Phase 1 policy is:

- `HTTP_FIRST`; browser fallback remains `DISABLED`.
- A source instance must be present in a versioned source register as either a
  `DISCOVERY_SOURCE` or `RESEARCH_SOURCE`; one classification grants no other permission.
- The initial research category is an approved business's ordinary, unauthenticated, first-party
  public website over ports 80/443. Exact domains remain unselected and unauthorized.
- Each domain requires a documented terms/source review, a declared crawler identity, Robots
  Exclusion Protocol processing, exact-host/redirect policy, and bounded crawl configuration.
- Authenticated, access-controlled, paywalled, CAPTCHA-bypassed, archived, cached, social/review,
  form, chat, booking, mailbox, and adversarially obtained content is prohibited in Phase 1.
- Raw HTTP response bytes are ephemeral processing inputs only. The system hashes the raw bytes,
  deterministically removes safely identifiable email addresses, telephone numbers, structured
  contact fields, and structured person/staff contact blocks, and durably stores only the minimized
  capture. It does not claim perfect human-name detection.
- When required business evidence cannot be safely preserved after minimization, the result is a
  content-free `QUARANTINE_AND_REVIEW` record rather than an unrestricted durable capture.
- Phase 1 cannot extract that information into person/contact domain records, index it, expose a
  person/contact search, project it to M6, place values in ordinary logs, or calculate person/contact
  metrics.
- Downstream text and evidence must carry source lineage and the same no-contact classification.
- Access is single-workspace, least-privilege, audited, and confined to an owner-approved US-region
  production-like environment with encrypted storage/transport and isolated research identity.
- Retention uses approved policy `A08_PHASE1_MINIMIZED_RETENTION_V1`; evidence excerpts are 90 days,
  every class has an explicit destruction method, and maximum effective retention includes the
  maximum 30-day encrypted-backup overhang.
- Deletion removes primary content, expires encrypted backups under the approved backup schedule,
  and retains only non-content deletion/tombstone evidence. Legal hold is exceptional, scoped,
  authorized, audited, and time-reviewed.
- A future live permission release is immutable and independently binds source-policy, retention,
  environment, cohort, approvals, start, expiry, configuration hash, suspension, and revocation.

Every first-party host requires a distinct terms, robots, access, automated-access,
capture/storage/reuse, and copyright/contract review. Robots is a technical control, not legal
authorization. Material prohibition or unresolved material risk produces `SOURCE_BLOCKED`.

Accepting this ADR still requires an actually deployed and attested environment/storage boundary,
completed opaque identity bindings for privacy/incident/security owners, and exact source records.
A document marked proposed, reviewed, or technically complete grants no runtime permission.

## Consequences

Minimized captures preserve raw-content hashes and usable business evidence while reducing durable
incidental information. They cannot guarantee removal of every human name, so quarantine and
restricted access remain necessary. The company-only Phase 1 stays unable to build a contact index.
Source or retention changes suspend affected permissions and require a new immutable release.

`REAL_BUSINESS_DISCOVERY` and `REAL_PUBLIC_RESEARCH` remain `NOT_AUTHORIZED`. No real source,
business, person, contact, or external communication is approved by this proposal.

The 2026-08-21 successor implementation supplies minimization, exact retention/destruction,
incident-deadline authority provenance, and per-host review controls. It still supplies no exact
real source, real environment attestation, identity-provider subject, or permission and therefore
does not accept this ADR for live use.

## Validation

Before authorization, synthetic preflight must prove that:

- live discovery/research calls fail while their permission is `NOT_AUTHORIZED`;
- authorization of one capability does not authorize the other;
- source, policy, environment, cohort, start/expiry, and approval mismatch fail closed;
- emergency suspension/revocation stops new work and safely checkpoints in-flight work;
- only approved HTTP discovery/research egress can become available;
- person/contact extraction, indexing, metrics, M6 projection, browser fallback, and delivery remain
  structurally unavailable;
- raw fixture bodies are not durably retained and unsafe minimization quarantines;
- deletion and backup-expiry evidence follow the accepted retention package;
- incident timers activate only from verified authority and unresolved rules fail closed;
- unreviewed or materially risky exact hosts cannot become approved sources.

## Revisit triggers

- An accountable owner selects retention durations or an exact cloud/provider/region/IdP.
- Qualified counsel resolves applicability, source terms, copyright, or access questions.
- A browser, PDF, subdomain, directory, search provider, archive, authenticated source,
  person/contact phase, new jurisdiction/vertical, or communication capability is proposed.
- Source terms, robots behavior, law, security posture, or processing purpose changes.
