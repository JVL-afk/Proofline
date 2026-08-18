# ADR-0041: Referrals and controlled upstream re-analysis

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Replies can contradict upstream assumptions or name another person without authorizing contact.

## Decision drivers

- Preserve upstream ownership.
- Prevent inherited referral authority.

## Considered options

1. Candidate restart plus request-only re-analysis.
2. Automatic contact and truth update.
3. Ignore reply information.

## Decision

A referral creates at most an unverified candidate and inherits no verification, eligibility,
readiness, or authorization. M6 can emit ReanalysisRequested from exact first-party statement IDs
but cannot mutate M2/M3 or other M1-M5 truth. Operational opt-out/wrong-person safety applies
immediately within M6.

## Consequences

Canonical business revisions remain owned by their original bounded contexts.

## Validation

Referral restart, no inherited stages, assertion isolation, and mutation-isolation tests are required.

## Revisit triggers

First-party promotion policy, conversational validation, or CRM ownership is proposed.
