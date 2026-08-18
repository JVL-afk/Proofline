# M4 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- M0/M1 route compatibility plus M2 opportunity, M3 audit, and M4 demo commands, lineage, QC, review,
  revocation, authenticated issuance, and minimal telemetry retrieval.
- Composition of application services with M0-M4 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture or public-web activities in API request threads.
- Direct external web, live AI/search, proposal, outreach, publication, public sharing, export, real
  demo actions, or M5 behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through declared M0, research, opportunity, audit, and demo repository ports implemented locally.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, and the M0-M4 core/local packages at composition boundaries.
