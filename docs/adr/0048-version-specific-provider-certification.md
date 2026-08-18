# ADR-0048: Version-specific provider certification

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Provider, security, privacy, legal, and operations owners

## Context

A live provider introduces duplicate, ambiguity, webhook, data, secret, and reputation risks.

## Decision drivers

- Certify exact capabilities and configuration rather than vendor names.
- Preserve M6 no-blind-retry behavior.

## Considered options

1. Version-specific certification records.
2. Vendor-wide approval.
3. Production smoke send as certification.

## Decision

Certification binds the exact provider deployment, envelope, policy/source hashes, one-message API,
idempotency and ambiguity reconciliation, receipts, signed/replay-protected webhooks, tracking-off,
egress, secrets, sandbox evidence, contractual review, and expiry. M6.5 selects and calls no provider.

## Consequences

Configuration or policy drift suspends readiness until recertification.

## Validation

Drift, timeout ambiguity, webhook forgery/replay, tracking, isolation, and expiry tests are required.

## Revisit triggers

A real provider/configuration or API version is proposed.
