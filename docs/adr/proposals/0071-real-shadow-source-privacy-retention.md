# ADR-0071: Real public-research sources, incidental personal data, retention, and environment

- **Status:** Proposed — ready for accountable owner, privacy, security, and legal review
- **Date:** 2026-08-20
- **Decision owners:** Unassigned project, privacy/data, security, and qualified legal owners
- **Decision register:** A-03, A-04, A-07, A-08, A-09, A-17, and A-18

## Context

M6.7A proved a synthetic shadow-validation control plane. A future M6.7 phase may research actual
Texas Commercial HVAC businesses, but public pages can contain incidental names, professional
email addresses, telephone numbers, and other information associated with individuals. Public
availability is neither blanket collection permission nor permission to reuse data for contact.

The exact retention duration, approved source instances, cloud/provider/region, identity provider,
legal interpretation, and monetary budget are not approved. Therefore this ADR is decision-ready
but cannot yet authorize `REAL_BUSINESS_DISCOVERY` or `REAL_PUBLIC_RESEARCH`.

## Decision drivers

- Preserve exact source fidelity and evidence provenance without creating a contact database.
- Separate discovery-source approval from research-source approval.
- Minimize collection and make deletion, access, and audit behavior explicit before live data.
- Keep browser automation, authenticated content, access-control bypass, people/contact projection,
  and communication outside Phase 1.
- Bind every future permission to exact policy, environment, cohort, approval, start, and expiry.

## Considered options

1. Restricted immutable captures with incidental public person/contact content retained only where
   necessary for source fidelity, with no person/contact projection or indexing.
2. Redact all source bytes before hashing or preservation.
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
- Restricted immutable source captures may retain incidental public person/contact information only
  when necessary to preserve source fidelity and the exact evidence hash.
- Phase 1 cannot extract that information into person/contact domain records, index it, expose a
  person/contact search, project it to M6, place values in ordinary logs, or calculate person/contact
  metrics.
- Downstream text and evidence must carry source lineage and the same no-contact classification.
- Access is single-workspace, least-privilege, audited, and confined to an owner-approved US-region
  production-like environment with encrypted storage/transport and isolated research identity.
- Retention values are mandatory release inputs. No duration is implied by this ADR; all retention
  fields remain `UNRESOLVED_PENDING_OWNER_APPROVAL` until the A-08 package is signed.
- Deletion removes primary content, expires encrypted backups under the approved backup schedule,
  and retains only non-content deletion/tombstone evidence. Legal hold is exceptional, scoped,
  authorized, audited, and time-reviewed.
- A future live permission release is immutable and independently binds source-policy, retention,
  environment, cohort, approvals, start, expiry, configuration hash, suspension, and revocation.

The detailed proposed controls are in `docs/readiness/m6.7b/`. Accepting this ADR requires the
accountable owners to fill every unresolved value in those packages and record their approval. A
document marked proposed, reviewed, or technically complete grants no runtime permission.

## Consequences

Restricted captures preserve evidence integrity but create a confidential data store requiring
stronger access, deletion, backup, and incident controls. The company-only Phase 1 stays unable to
build a contact index. Source or retention changes suspend affected permissions and require a new
immutable release.

`REAL_BUSINESS_DISCOVERY` and `REAL_PUBLIC_RESEARCH` remain `NOT_AUTHORIZED`. No real source,
business, person, contact, or external communication is approved by this proposal.

M6.7C implements the policy schema and synthetic fail-closed tests under accepted ADR-0074. That
implementation supplies no retention duration, exact source, real environment attestation, legal
interpretation, accountable approval, or permission and therefore does not accept this ADR for live
use.

## Validation

Before authorization, synthetic preflight must prove that:

- live discovery/research calls fail while their permission is `NOT_AUTHORIZED`;
- authorization of one capability does not authorize the other;
- source, policy, environment, cohort, start/expiry, and approval mismatch fail closed;
- emergency suspension/revocation stops new work and safely checkpoints in-flight work;
- only approved HTTP discovery/research egress can become available;
- person/contact extraction, indexing, metrics, M6 projection, browser fallback, and delivery remain
  structurally unavailable;
- deletion and backup-expiry evidence follow the accepted retention package.

## Revisit triggers

- An accountable owner selects retention durations or an exact cloud/provider/region/IdP.
- Qualified counsel resolves applicability, source terms, copyright, or access questions.
- A browser, PDF, subdomain, directory, search provider, archive, authenticated source,
  person/contact phase, new jurisdiction/vertical, or communication capability is proposed.
- Source terms, robots behavior, law, security posture, or processing purpose changes.
