# ADR-0025: Demo eligibility, review, invalidation, and revocation

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

A simulation must not amplify an unaccepted opportunity or unapproved audit.

## Decision drivers

- Bind generation and review to current canonical inputs.
- Keep hard QC non-overridable.
- Stop access when authority is revoked or inputs change.

## Considered options

1. Exact accepted-M2 and approved-M3 eligibility with immutable review and revocation.
2. Permit diagnostic or ready-for-review inputs.
3. Review only at the presentation layer.

## Decision

Generation requires the exact current accepted Texas Commercial HVAC opportunity revision and an
exact current, full, approved, hard-QC-passing M3 audit revision. All other states reject. Operators
generate, revise, and replay; reviewer/admin roles decide. Local self-review is allowed and recorded.
Hard QC cannot be overridden. Review, invalidation, session, and revocation history is append-only.
Revision age does not automatically expire in initial M4.

## Consequences

Eligibility is narrow and historical decisions remain auditable. Upstream drift fails closed.

## Validation

Eligibility, authorization, exact-hash review, upstream invalidation, and revocation tests apply.

## Revisit triggers

Production separation of duties, revision-age expiry, or a different opportunity definition is proposed.
