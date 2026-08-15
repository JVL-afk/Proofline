# M0 Local Adapters

## Ownership

Architecture/platform team.

## Responsibilities

- SQLite/SQLAlchemy persistence for M0 campaigns, operations, attempts, evidence, and audit events.
- Fixture-only fetcher with no network capability.
- Deterministic HTML title/excerpt extraction for controlled fixtures.
- Local environment bearer authentication adapter.

## Forbidden responsibilities

- Public-web HTTP requests, DNS resolution, browser execution, search, AI, or external side effects.
- Product opportunity, ROI, audit, demo, or outreach behavior.
- Production deployment.

## Public interface

The `opintel_m0_local` Python package implementing ports from `opintel_m0`.

## Data access

One configured local SQLite database and one configured fixture-root directory.

## Dependencies

`opintel-m0-core` and SQLAlchemy. This package must not import the API or worker composition roots.
