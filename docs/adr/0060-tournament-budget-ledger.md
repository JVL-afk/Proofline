# ADR-0060: Tournament II hierarchical budget reservation and unit-cost reporting

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Finance, product, and architecture owners

## Context

Live evaluation has variable token and retry costs; M6.6A must prove controls without choosing a real
budget.

## Decision drivers

- Fail closed before spend.
- Attribute usage to task and deployment.
- Preserve an emergency reserve.

## Considered options

1. Hierarchical preflight reservation and reconciliation.
2. Provider invoices after execution.
3. One unpartitioned soft limit.

## Decision

Use total, provider, deployment, task, and stage caps plus emergency reserve. Reserve conservative
maximum cost before each invocation and reconcile actual usage afterward. Unknown pricing fails
closed. M6.6A uses fixture prices; the M6.6B budget remains unchosen.

## Consequences

Cost projections remain traceable and cannot silently exceed an approved dimension.

## Validation

Every cap, reserve, reconciliation, pricing, token, latency, and exhaustion path requires tests.

## Revisit triggers

The M6.6B budget or provider pricing is proposed.
