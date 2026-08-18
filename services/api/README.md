# M5 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- M0/M1 compatibility plus M2 opportunity, M3 audit, M4 demo, and M5 package commands, lineage, QC,
  content-only review, revocation, authenticated demo issuance, and minimal telemetry retrieval.
- Composition of application services with M0-M5 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture or public-web activities in API request threads.
- Direct external web, live AI/search, contact/recipient discovery, copy/export, publication, public
  sharing, sending/delivery, real demo actions, channel integration, or M6 behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through declared M0, research, opportunity, audit, demo, and outreach repository ports locally.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, and the M0-M5 core/local packages at composition boundaries.
