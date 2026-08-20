# ADR-0073: Non-recipient shadow person/contact evaluation

- **Status:** Proposed
- **Date:** 2026-08-20
- **Decision owners:** Unassigned privacy, legal, security, product, and architecture owners

## Context

Later M6.7 phases may evaluate professional identity and contact evidence without creating M6 send
authority.

## Decision drivers

- Keep evaluation artifacts distinct from recipients.
- Require proof-scoped association, suppression, jurisdiction, and eligibility.
- Preserve the ADR-0053 no-send boundary.

## Considered options

1. Non-recipient shadow artifacts with no delivery capability.
2. Reuse M6 recipient stages with a feature flag.
3. Defer all contract design until delivery activation.

## Decision

Unresolved. M6.7A implements no person/contact artifact or endpoint.

## Consequences

All later contact permissions remain `NOT_AUTHORIZED`.

## Validation

Future work must prove source/proof, retention, suppression, eligibility, and structural no-delivery
controls.

## Revisit triggers

Any later person/contact phase is proposed.
