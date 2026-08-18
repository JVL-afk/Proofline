# ADR-0038: Exact send manifests and one-message human authorization

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Content approval does not identify a recipient or authorize a send.

## Decision drivers

- Bind human intent to exact immutable bytes and entities.
- Prevent batch, retry, and follow-up scope creep.

## Considered options

1. One exact manifest and one-send authorization.
2. Campaign/list authorization.
3. Provider-side approval only.

## Decision

An immutable manifest binds one recipient, contact/verification/eligibility, sender, M5 revision and
hashes, policy/configuration, plain-text preview, operation, and trace. AUTHORIZE_ONE_SEND binds one
exact manifest/preview and cannot authorize lists, changed content, retries, follow-ups, or multiple
sends. Local attributed self-review follows M5 policy; production governance stays open.

## Consequences

Every follow-up requires fresh eligibility/readiness and a separate authorization.

## Validation

Hash preconditions, one-recipient, idempotency, expiry, drift, and follow-up tests are required.

## Revisit triggers

Batch approval, production roles, separation of duties, or step-up identity is proposed.
