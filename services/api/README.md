# M2 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- M0/M1 route compatibility plus M2 opportunity commands, lineage, economics, factors, and review.
- Composition of application services with M0/M1/M2 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture or public-web activities in API request threads.
- Direct external web, live AI/search, audit, demo, proposal, outreach, integration, or M3 behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through the `M0Repository`, `ResearchRepository`, and `OpportunityRepository` ports implemented by
local adapters.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, and the M0/M1/M2 core/local packages at composition boundaries.
