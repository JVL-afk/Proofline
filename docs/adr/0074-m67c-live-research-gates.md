# ADR-0074: M6.7C live-research gates without live authority

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product and architecture owner

## Context

M6.7B approved the design for controls that must exist before real discovery or public research can
be considered. ADR-0071, exact retention values, source instances, environment, legal release,
monetary budgets, named people, and both live permissions remain unresolved.

## Decision drivers

- Prove fail-closed controls without touching a real business or granting permission.
- Reuse M1 URL/DNS/SSRF protections rather than create a weaker parallel implementation.
- Keep M6.7 separate from M6 delivery and M6.6 AI authority.
- Use the smallest durable orchestrator appropriate to a 24-company staged pilot.

## Considered options

1. Add immutable gate records, a bounded SQLite/database orchestrator, and fake-only transports.
2. Introduce Temporal before measured Phase 1 orchestration requires it.
3. Add a live HTTP adapter while permissions remain disabled.
4. Extend M6 send/contact state with research gates.

## Decision

M6.7C adds an inward-facing gate layer to `shadow-core` and fake/SQLite adapters to `shadow-local`.
It models data handling, retention, source registration, environment attestations, independent
discovery/research releases, budgets, roles, kill-switch events, deletion evidence, cohort gates,
staged progression, and synthetic preflight results.

There is no application command that authorizes a release and no live transport adapter. The fake
egress service checks authorization before resolver or transport invocation and then delegates URL,
DNS, redirect, port, and public-address validation to the M1 policy. All seven successor permissions
finish `NOT_AUTHORIZED`.

Phase 1 uses a bounded database-backed orchestrator with deterministic idempotency keys, atomic
leases, stale recovery, three-attempt maximum, pause/kill checks, immutable lineage, and workload
reservations. Temporal is reconsidered if any of these occurs: more than one process must claim work
concurrently for two consecutive cohorts; a run must remain active beyond 24 hours; cross-service
signals/timers or compensations become required; or more than two stale-lease recoveries occur in
each of two consecutive 24-company cohorts. Reconsideration requires a successor ADR and does not
automatically select Temporal.

ADR-0071 remains proposed for live use. Implementing its schema does not supply policy values,
approval, legal interpretation, environment evidence, or authority.

## Consequences

The repository can prove the future authorization boundary and operational recovery using synthetic
data. A later milestone may add exact approved records, but cannot inherit authority from this ADR,
technical readiness, or a passing preflight.

## Validation

Tests must cover incomplete policies, permission independence, rejection before DNS, M1 SSRF and
DNS-rebinding controls, source/redirect restrictions, leases/retries, budgets, role separation,
kill/suspension, deletion/legal holds, cohort/stage immutability, readiness semantics, and structural
absence of delivery, contact, AI, credentials, and live network adapters.

## Revisit triggers

A real source, browser, cloud environment, retention period, named operator, live authorization,
person/contact path, delivery capability, or workflow threshold above is proposed or observed.
