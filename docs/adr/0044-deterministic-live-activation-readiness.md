# ADR-0044: Deterministic live-activation readiness

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Production prerequisites span governance, policy, security, providers, senders, and operations.

## Decision drivers

- Explain exact blockers without guessing missing answers.
- Prevent readiness labels from authorizing contact.

## Considered options

1. Immutable deterministic projections.
2. Manual readiness promotion.
3. Aggregate readiness score.

## Decision

`LiveActivationReadiness` is derived from exact immutable inputs and produces `NOT_READY`,
`READY_FOR_PROVIDER_CERTIFICATION`, or `READY_FOR_FIRST_REAL_CONTACT_REVIEW`. Every hard gate emits
structured evidence and remediation metadata. There is no score or manual promotion, and no state
creates recipient-specific M6 records.

## Consequences

Missing, stale, expired, suspended, failed, or scope-mismatched inputs fail closed.

## Validation

State progression, regression, blocker detail, immutability, and M6-isolation tests are required.

## Revisit triggers

A readiness state is proposed to imply authorization or delivery.
