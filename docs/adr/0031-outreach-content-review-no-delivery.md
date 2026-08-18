# ADR-0031: Outreach content review, invalidation, and no-delivery boundary

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Content approval must not be confused with permission or authority to contact a business.

## Decision drivers

- Exact, attributed human review.
- Automatic failure on upstream drift.
- Structural absence of contact, copy, export, publication, and delivery.

## Considered options

1. `CONTENT_APPROVED` as wording-only approval with no delivery capability.
2. An `OUTREACH_READY` state that implies operational readiness.
3. Approval only in the front end.

## Decision

Operators generate/request review; reviewer/admin roles approve content, reject, or request a new
revision. Local self-review is allowed and attributed. Decisions bind revision, manifest, and
content hashes. Hard QC cannot be overridden. `CONTENT_APPROVED` authorizes no contact, legal use,
copy, export, sending, publishing, scheduling, discovery, or integration. Follow-up remains
`CONDITIONALLY_USABLE` and M5 never resolves its external precondition.

## Consequences

A future delivery capability requires separate legal, product, security, identity, and suppression
decisions. A-16 remains open.

## Validation

Authorization, stale hash, self-review attribution, invalidation, follow-up precondition, and route
absence tests apply.

## Revisit triggers

Copy, export, delivery, recipient, suppression, or interaction tracking is proposed.
