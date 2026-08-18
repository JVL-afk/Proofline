# ADR-0045: Versioned production outreach policy release

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Legal/privacy, product, and security owners

## Context

Engineering cannot invent legal or jurisdictional outreach rules.

## Decision drivers

- Bind enforceable policy to accountable approvals.
- Fail closed when real answers are absent.

## Considered options

1. Signed immutable policy releases.
2. Hard-coded generalized US rules.
3. Free-form reviewer acknowledgment.

## Decision

A production `OutreachPolicyRelease` binds exact scope, sources, proof, disclosures, suppression,
cadence, contact time, behavior, privacy, retention, provider, security, sender, rollout, monitoring,
approvals, effective dates, and hashes. Fixture releases may test mechanics but never activate live
contact. No real legal rules are populated by M6.5.

## Consequences

No active matching release means readiness is blocked.

## Validation

Missing, fixture, expired, suspended, incomplete-approval, and scope-mismatch tests are required.

## Revisit triggers

Qualified policy owners approve or change production rules.
