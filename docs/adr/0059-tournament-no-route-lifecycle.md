# ADR-0059: Tournament-only lifecycle and no-route outcome

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, security, and architecture owners

## Context

Qualification evidence must not become application activation.

## Decision drivers

- Preserve the accepted lifecycle.
- Make route activation structurally separate.
- Keep deterministic fallback authoritative.

## Considered options

1. Qualification reports with no route writer.
2. Automatic shadow activation after qualification.
3. Global model fallback.

## Decision

Preserve `UNASSESSED` through qualification, suspension, requalification, and retirement. `QUALIFIED`
does not activate a route; `CONDITIONAL` never routes. M6.6A contains only a fake runner and task
reports. Live execution requires a distinct future M6.6B authorization and boundary.

## Consequences

Tournament output can recommend a candidate but cannot change runtime behavior.

## Validation

No-route, deterministic-preference, conditional, drift-binding, and fake-only runner tests apply.

## Revisit triggers

Any evaluation, shadow, or advisory route is proposed.
