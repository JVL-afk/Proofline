# M0 Application API

## Ownership

Application/API team.

## Responsibilities

- FastAPI transport and OpenAPI contract.
- Local authentication dependency and server-side role checks.
- Campaign commands and operation/evidence retrieval.
- Composition of application services with M0 local adapters.
- Static health/readiness endpoints and safe structured logging.

## Forbidden responsibilities

- Executing fixture fetch or workflow activities in API request threads.
- Direct external web, AI, search, demo, audit, ROI, opportunity, or outreach behavior.
- Production identity assumptions.

## Public interface

HTTP `/api/v1` and `/healthz` endpoints documented by FastAPI OpenAPI.

## Data access

Through the `M0Repository` port implemented by the local adapter.

## Dependencies

FastAPI, Uvicorn, Pydantic Settings, `opintel-m0-core`, and `opintel-m0-local` at the composition boundary.
