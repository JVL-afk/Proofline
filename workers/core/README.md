# M0 Core Worker

## Ownership

Workflow/application team.

## Responsibilities

- Poll and claim durable M0 operations.
- Recover stale local operation leases on startup.
- Execute the typed fixture-fetch activity with bounded retries.
- Persist attempt outcomes, evidence, operation state, and audit events idempotently.

## Forbidden responsibilities

- HTTP/DNS/browser/search/AI/provider access.
- Product discovery, opportunity, ROI, score, audit, demo, outreach, or autonomous-agent behavior.
- Mutating campaign commands outside the application use case.

## Public interface

The `opintel-worker` CLI and `opintel_worker` Python package.

## Data access

Through the `M0Repository` port implemented by the local SQLite adapter.

## Dependencies

`opintel-m0-core` and `opintel-m0-local` at the composition boundary.
