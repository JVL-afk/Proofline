# ADR-0035: Fixture eligibility policy and A-17 live gate

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

No real jurisdictional contact policy has been approved.

## Decision drivers

- Fail closed on unknown policy/context.
- Avoid encoding invented legal rules.

## Considered options

1. Fixture-only policy plus separate signed live gate.
2. Generalized US rules embedded in code.
3. Human approval as a universal override.

## Decision

M6 evaluates deterministic ELIGIBLE, INELIGIBLE, REQUIRES_REVIEW, and UNKNOWN outcomes. Unknown and
review outcomes are not sendable. Only a non-live TEST_ONLY fixture policy is present. A signed,
scoped A-17 legal/privacy policy release remains mandatory before any live adapter.

## Consequences

No real legal rule, jurisdiction, consent, or permission is inferred by the implementation.

## Validation

All four outcomes, unknown jurisdiction, hard prohibition, and non-live policy tests are required.

## Revisit triggers

Any real recipient, provider, jurisdiction, or delivery activation is proposed.
