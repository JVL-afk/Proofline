# ADR-0040: Receipts, replies, and first-party assertions

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Provider events and recipient statements have different evidentiary meaning.

## Decision drivers

- Prevent read/engagement invention.
- Keep reply content untrusted and non-canonical.

## Considered options

1. Separate immutable records with deterministic classification.
2. One engagement status.
3. Immediate canonical promotion.

## Decision

Provider acceptance, receipts, bounce/complaint, and reply records remain distinct. Signed fixture
events are replay-protected. Replies receive deterministic taxonomy with authoritative human
correction. Atomic reply statements begin as FIRST_PARTY_ASSERTED and prove only that a person made
the statement.

## Consequences

There is no read/open state, tracking pixel, automatic reply, or live AI classifier.

## Validation

Signature, replay, bounce, complaint, taxonomy, hostile reply, and correction tests are required.

## Revisit triggers

Live inbound webhooks, AI assistance, attachment handling, or engagement telemetry is proposed.
