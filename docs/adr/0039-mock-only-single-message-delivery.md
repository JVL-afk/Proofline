# ADR-0039: Mock-only single-message delivery

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

The lifecycle must be proved before a real provider or message is authorized.

## Decision drivers

- Credential-free deterministic CI.
- Safe ambiguous-submission behavior.

## Considered options

1. Zero-network mock behind a narrow single-message port.
2. Provider sandbox.
3. Real low-volume delivery.

## Decision

The only M6 provider is deterministic, credential-free, and network-free. Its port exposes
submit_one, status query, and signed fixture-event parsing; no bulk or sequence operation exists.
Timeout after possible acceptance becomes STATUS_UNKNOWN and is never blindly retried.

## Consequences

SENT means mock provider acceptance, not delivery, opening, reading, or engagement.

## Validation

Accepted, rejected, ambiguous, duplicate, no-retry, and zero-network tests are required.

## Revisit triggers

A real provider or provider-specific idempotency contract is proposed.
