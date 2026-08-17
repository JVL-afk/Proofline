# ADR-0016: Structured audit claims and immutable input manifests

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

M3 must produce useful audits without allowing generated prose to become product truth.

## Decision drivers

- Preserve exact M1/M2 lineage.
- Make every revision reproducible and invalidatable.
- Keep prose downstream of typed claims.

## Considered options

1. Immutable manifests and structured claims.
2. Free-form documents with optional citations.
3. Mutable audit records pointing at current data.

## Decision

An audit revision binds a content-hashed manifest of exact canonical input revisions. Its eleven
sections are projections of atomic `FACT`, `INFERENCE`, `ESTIMATE`, and `RECOMMENDATION` claims.
`UNKNOWN` is a gap/missing-value state, never an assertion. M3 cannot create canonical truth.

## Consequences

Revisions remain reproducible and auditable, at the cost of more explicit records and bindings.

## Validation

Manifest completeness, deterministic replay, exact lineage, and mutation-isolation tests are required.

## Revisit triggers

Any new claim type, mutable approved artifact, or non-opportunity-linked artifact is proposed.
