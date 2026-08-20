# ADR-0071: Real shadow source, privacy, and retention controls

- **Status:** Proposed
- **Date:** 2026-08-20
- **Decision owners:** Unassigned legal/privacy, data-governance, security, and product owners

## Context

Real public research can contain incidental public person/contact data and requires approved source,
environment, and lifecycle rules.

## Decision drivers

- Keep public accessibility distinct from permitted collection and retention.
- Prevent Phase 1 snapshots from becoming a contact index.
- Resolve A-08, A-09, and A-17 before live use.

## Considered options

1. Restricted snapshots with no contact projection and an approved lifecycle.
2. Unrestricted retention because the source is public.
3. Redact every snapshot without assessing evidence-integrity tradeoffs.

## Decision

Unresolved. M6.7A models restricted snapshot references, no person/contact indexing, no M6
projection, and no retention duration. No live source or permission is approved.

## Consequences

Real discovery and research remain disabled.

## Validation

Future approval must cover sources, terms/robots, incidental data, retention/deletion, access,
encryption, environment, and logging.

## Revisit triggers

Accountable owners supply the missing A-08/A-09/A-17 decisions.
