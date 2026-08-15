# Opportunity Intelligence Platform

Greenfield repository for the evidence-first business opportunity detection and demo generation system described in [GREENFIELD_ARCHITECTURE.md](GREENFIELD_ARCHITECTURE.md).

## Current status

The repository implements the **Milestone M0 walking skeleton** only. It proves local authentication, a campaign command, durable fixture workflow execution, persisted evidence provenance, and API/UI traceability. All external systems are local adapters or controlled fixtures.

Do not start M1 or production integration work until the unresolved decision gates in [docs/milestones/M0.md](docs/milestones/M0.md) are satisfied.

## Repository map

| Path | Purpose |
|---|---|
| `apps/` | Separate M0 diagnostic web UI |
| `services/` | Authenticated M0 API composition root |
| `workers/` | Separate durable M0 worker process |
| `packages/` | M0 domain/application ports and local adapters |
| `infra/` | Infrastructure-as-code and local-platform boundaries |
| `docs/adr/` | Durable architectural decisions |
| `docs/decisions/` | Human-approval decision register from the accepted architecture |
| `docs/engineering/` | Module, coding, testing, and dependency rules |
| `docs/policies/` | Environment, data, and secret-handling policies |
| `scripts/` | Repository-only validation utilities |

## Prerequisites

- Node.js 24 LTS
- npm 11 or the npm version bundled with the selected Node.js 24 release
- Python 3.13
- uv 0.11.32–0.11.x
- Git

Docker, PostgreSQL, Temporal, Redis, cloud services, search, and AI providers are not required for M0.

## Run the M0 walking skeleton

From a fresh checkout:

```powershell
python -m pip install "uv==0.11.32"
uv sync --locked --all-packages
python scripts/bootstrap_local.py
```

Start three terminals from the repository root:

```powershell
uv run --locked opintel-api
```

```powershell
uv run --locked opintel-worker
```

```powershell
python -m http.server 3000 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:3000`. Copy `OPINTEL_AUTH_TOKEN` from the ignored local `.env`, authenticate, create one of the controlled campaigns, start the operation, and refresh until it succeeds or fails. The transient fixture deliberately retries once. The missing fixture deliberately fails safely.

The API schema is available at `http://127.0.0.1:8000/docs`. All non-health API endpoints require the bearer token.

## Validate the repository

```powershell
npm ci --ignore-scripts
npm run check:repo
npm run check:python
npm run typecheck
npm test
```

The repository validator uses only the Python standard library. Python lint, types, and tests run from the committed uv lockfile.

## Local M0 data and reset

SQLite state is stored at `local-data/m0.db` and is ignored by Git. Stop the API/worker and remove that single local file to reset the walking skeleton. The repository never performs this deletion automatically.

The local token adapter, SQLite workflow, static UI, and fixture fetcher are prohibited from production use by [ADR-0004](docs/adr/0004-m0-local-walking-skeleton-adapters.md).

## Authoritative documents

1. [Accepted greenfield architecture](GREENFIELD_ARCHITECTURE.md)
2. [M0 scope and exit criteria](docs/milestones/M0.md)
3. [Human decision register](docs/decisions/README.md)
4. Accepted ADRs in [docs/adr/](docs/adr/)

When these conflict, stop and resolve the conflict through an ADR rather than silently choosing an implementation.
