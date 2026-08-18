# M6 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- M0-M5 compatibility plus synthetic M6 identity, verification, eligibility, suppression, exact
  readiness, one-message authorization, mock attempt/receipt/reply, and re-analysis commands.
- Composition of application services with M0-M6 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture or public-web activities in API request threads.
- Direct external web, live AI/search, real contact/enrichment/verification, copy/export/publication,
  real delivery/webhooks, bulk/sequence actions, channel integration, or M7 behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through declared M0, research, opportunity, audit, demo, outreach, and contact repository ports.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, and the M0-M6 core/local packages at composition boundaries.
