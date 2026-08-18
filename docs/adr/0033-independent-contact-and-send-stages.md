# ADR-0033: Independent contact and send stages

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

M6 crosses from approved content into a simulated communication lifecycle.

## Decision drivers

- Prevent one state from implying another.
- Preserve exact lineage and invalidation.

## Considered options

1. Six independent persisted stages.
2. One progressive outreach status.
3. UI-only gate flags.

## Decision

M6 persists PERSON_IDENTIFIED, CONTACT_DETAIL_VERIFIED, CONTACT_ELIGIBLE, SEND_READY,
SEND_AUTHORIZED, and SENT as independent evidence-bearing stage records. No stage implies or
automatically creates the next. Each binds exact revisions, provenance, policies, actor/operation,
time, trace, and separate invalidation events.

## Consequences

The lifecycle prevents discovery, verification, policy, readiness, human authority, and provider
acceptance from collapsing into one misleading status.

## Validation

Stage inventory, provenance, independence, suppression-invalidation, and replay tests are required.

## Revisit triggers

A stage is proposed for removal, implication, or automatic advancement.
