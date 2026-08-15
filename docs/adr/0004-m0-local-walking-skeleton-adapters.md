# ADR-0004: Local-only walking-skeleton adapters for M0

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owners:** Architecture owner
- **Related architecture decisions:** A-03, A-05, A-07, A-09; architecture section 28
- **Supersedes:** None

## Context

The M0 walking skeleton must prove authentication, a campaign command, durable/retryable workflow execution, a controlled fetch, persisted evidence, and API/UI traceability. Production tenancy, OIDC provider, workflow engine/hosting, cloud, public sources, and retention decisions remain open and must not be silently decided by a prototype.

## Decision drivers

- Complete the required end-to-end M0 path without external accounts or live network research.
- Preserve ports that production OIDC, PostgreSQL/Temporal, and approved fetch adapters can implement later.
- Persist enough state to survive process restart and demonstrate retries/idempotency.
- Keep local setup small and cross-platform.
- Avoid introducing M1 intelligence or product breadth.

## Considered options

1. Local bearer auth, SQLite operation journal/queue, fixture-only fetcher, and static diagnostic UI.
2. Deploy PostgreSQL, Temporal, and an OIDC provider locally before their decisions are approved.
3. In-memory mocks with no process separation or persistence.
4. A single API request that performs all work synchronously.

## Decision

For M0 only:

- authenticate API requests with a constant-time compared, environment-injected bearer token mapped to one local principal/workspace;
- persist campaigns, operation state, activity attempts, immutable audit events, and evidence in SQLite through SQLAlchemy;
- run workflow activities in a separate worker process using a durable database queue with bounded retries, stale-run recovery, and semantic idempotency keys;
- allow the fetch port to resolve only `fixture://public/<safe-file>.html` from a configured fixture root, with no network stack;
- serve a separate static diagnostic UI that calls the API and stores the development token in session storage;
- label all of these as local adapters that must not be deployed as production identity, orchestration, persistence, or research infrastructure.

This ADR does not accept or close A-03, A-05, A-07, or A-09.

## Consequences

### Positive

- Proves the architectural seams and complete traceability path with no external side effects.
- Failure, retry, restart, duplicate-command, and authorization behavior are testable.
- Fresh development requires no database, workflow, search, or identity server.

### Negative

- The local workflow engine is intentionally not feature-equivalent to Temporal.
- Bearer-token login is a developer boundary, not OIDC/OAuth.
- SQLite concurrency and durability are insufficient for production.
- The static UI is diagnostic rather than the planned Next.js product UI.

### Risks and mitigations

- Prototype becomes production by inertia: runtime refuses non-development mode for local auth/SQLite/fixture adapters and documentation labels the boundary.
- Adapter leakage into domain code: ports and composition roots isolate dependencies.
- Retry divergence: typed operation/activity contracts and tests define only the M0 semantics that a production adapter must preserve.
- Token exposure: generate it locally, keep it in ignored `.env`, never log it, and use session storage in the diagnostic UI.

## Validation

Automated tests cover success, invalid fixture input, permanent fixture failure, transient retry, stale-run recovery, duplicate command/activity execution, evidence provenance, workspace scoping, and unauthorized access.

## Revisit triggers

- A-03, A-05, A-07, or A-09 is accepted.
- Any non-local environment is introduced.
- M1 implementation begins.
- Concurrency or workflow semantics exceed the deliberately narrow M0 contract.
