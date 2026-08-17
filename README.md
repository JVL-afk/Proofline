# Opportunity Intelligence Platform

Greenfield repository for the evidence-first business opportunity detection and demo generation system described in [GREENFIELD_ARCHITECTURE.md](GREENFIELD_ARCHITECTURE.md).

## Current status

The repository implements **Milestone M3 evidence-linked audits** as a deterministic local slice.
M1/M2 remain authoritative. M3 adds immutable input manifests, eleven structured audit sections,
typed claims, exact lineage, hard semantic QC, leased composition, and version-bound human review.
No model route is active; live AI, publication, export, demos, and external effects remain disabled.
Normal CI remains credential-free and network-free.

M1/M2/M2.5 local adapters are constrained by
[ADR-0005](docs/adr/0005-m1-bounded-local-research.md),
[ADR-0010](docs/adr/0010-m2-rule-based-reasoning.md), and
[ADR-0014](docs/adr/0014-live-evaluation-isolation-and-budgets.md).
Open production source, retention, legal, workflow, and infrastructure decisions remain unresolved.

## Repository map

| Path | Purpose |
|---|---|
| `apps/` | Separate M3 diagnostic web UI |
| `services/` | Authenticated API composition root |
| `workers/` | Separate core, HTTP research, browser, and deterministic M2/M3 intelligence processes |
| `packages/` | M0-M3 contracts/local adapters plus isolated M2.6 evaluation adapters |
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

Docker, PostgreSQL, Temporal, Redis, cloud services, search, and AI providers are not required for
normal deterministic development or CI. M2.6 live evaluation is a separate explicit local command.

## Run the M3 evidence-linked audit engine

From a fresh checkout:

```powershell
python -m pip install "uv==0.11.32"
uv sync --locked --all-packages
python scripts/bootstrap_local.py
```

Start four terminals from the repository root:

```powershell
uv run --locked opintel-api
```

```powershell
$env:OPINTEL_RESEARCH_LIVE_ENABLED="true"
uv run --locked opintel-research-worker
```

```powershell
uv run --locked opintel-intelligence-worker
```

```powershell
python -m http.server 3000 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:3000`. Copy `OPINTEL_AUTH_TOKEN` from ignored `.env`, authenticate,
name one known business, enter one explicitly permitted public URL, start the bounded run, and
refresh its pages/evidence, start deterministic M2 analysis, inspect gaps/economics/factors, record
opportunity review, then generate and review the M3 audit. Keep live research disabled unless the
URL is authorized. Production live AI remains disabled; M2.6 adapters are tournament-only.

Browser fallback is off by default. For an approved local browser test, run
`uv run playwright install chromium`, then set `OPINTEL_RESEARCH_BROWSER_ENABLED=true` only on the
research worker. A local process is not accepted production containment.

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

## Local data and reset

SQLite state is stored at `local-data/m0.db` and is ignored by Git. Stop the API/worker and remove that single local file to reset the walking skeleton. The repository never performs this deletion automatically.

The local token, SQLite, static UI, HTTP, and browser-process adapters are prohibited from
production use by ADR-0004, ADR-0005, and ADR-0010.

## Authoritative documents

1. [Accepted greenfield architecture](GREENFIELD_ARCHITECTURE.md)
2. [M3 scope and exit criteria](docs/milestones/M3.md)
3. [Human decision register](docs/decisions/README.md)
4. Accepted ADRs in [docs/adr/](docs/adr/)

When these conflict, stop and resolve the conflict through an ADR rather than silently choosing an implementation.
