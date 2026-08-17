# M3 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- M0/M1 route compatibility plus M2 opportunity and M3 audit commands, lineage, QC, and review.
- Composition of application services with M0-M3 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture or public-web activities in API request threads.
- Direct external web, live AI/search, demo, proposal, outreach, publication, or M4 behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through declared M0, research, opportunity, and audit repository ports implemented by local adapters.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, and the M0-M3 core/local packages at composition boundaries.
