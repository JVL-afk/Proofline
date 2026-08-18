# ADR-0050: Contact-data lifecycle and suppression tombstones

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Privacy/data-governance, legal, and security owners

## Context

Real identity, contact, reply, delivery, and suppression records need different lifecycles.

## Decision drivers

- Minimize confidential data while preserving non-recontact safety.
- Avoid inventing retention periods.

## Considered options

1. Versioned per-category policy with protected tombstones.
2. One global retention duration.
3. Deleting suppression with contact data.

## Decision

Every production category must declare classification, encryption, redaction, logging, retention,
deletion, legal hold, and where applicable suppression-tombstone behavior. Periods and exact
tombstone handling remain A-08 decisions; absence blocks readiness.

## Consequences

Deletion cannot silently permit recontact, and legal hold never restores eligibility.

## Validation

Retention-gap, deletion, tombstone non-recontact, backup, and hold tests are required.

## Revisit triggers

Qualified owners approve lifecycle periods or rights processes.
