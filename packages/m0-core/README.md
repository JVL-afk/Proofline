# M0 Core

## Ownership

Architecture/application team.

## Responsibilities

- M0 campaign, operation, attempt, evidence, principal, and audit-event domain types.
- Typed API/workflow boundary contracts.
- Application use cases and ports for persistence, authentication, workflow dispatch, fixture fetch, clock, and identifiers.
- Deterministic workflow state-transition policies.

## Forbidden responsibilities

- FastAPI, SQLAlchemy, SQLite, filesystem, network, environment, or framework imports.
- Production discovery, AI, opportunities, ROI, scoring, audits, demos, or outreach.
- Provider-specific payloads.

## Public interface

The `opintel_m0` Python package.

## Data access

None. Data access is declared through ports.

## Dependencies

Pydantic is used only for typed transport/workflow contracts. Domain models use standard-library dataclasses and enums.
