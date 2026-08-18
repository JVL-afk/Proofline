# ADR-0036: Suppression, cadence, contact-time, and kill-switch precedence

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Safety state can change after readiness or authorization.

## Decision drivers

- Stop stale authorizations.
- Prevent race, cadence, and time-zone bypass.

## Considered options

1. Immutable events plus pre-submit recheck.
2. Readiness-time-only checks.
3. Human override.

## Decision

Immutable suppression events override eligibility, readiness, authorization, follow-up, and provider
submission. Opt-out invalidates pending authorization. Submission rechecks suppression. Versioned
cadence reservations, explicit time-zone checks, and global kill switches fail closed.

## Consequences

Human approval cannot bypass a safety prohibition. Production thresholds remain unresolved.

## Validation

Opt-out race, cadence, unknown zone, DST, and kill-switch tests are required.

## Revisit triggers

Suppression scope, retention, frequency, or contact-time rules are approved for live use.
