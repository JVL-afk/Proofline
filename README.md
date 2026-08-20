# Opportunity Intelligence Platform

Greenfield repository for the evidence-first business opportunity detection and demo generation system described in [GREENFIELD_ARCHITECTURE.md](GREENFIELD_ARCHITECTURE.md).

## Current status

The repository implements **Milestone M6.7C synthetic live-research gate preflight**. M1-M6
remain authoritative and frozen. M6 adds synthetic identity,
proof-scoped verification, fixture-only eligibility, immutable suppression, exact plain-text send
manifests, one-message human authorization, mock acceptance/receipts/replies, and first-party
re-analysis requests. M6.5 adds immutable prerequisite records, exact blocker diagnostics, and a
mandatory non-send `SHADOW_READY` boundary. Tournament II is closed with no qualified-with-gain
binding and no route. M6.7A adds independent real-data permissions, frozen 24-slot synthetic cohort
selection, deterministic M1-M5 projections, review/QA, metrics/costs/stops, and M6.8 evidence-package
generation. M6.7C adds explicit retention/source/environment/release/budget/role gates, bounded
SQLite work leases, fake-only egress, deletion controls, and staged preflight. Every real-data
permission is `NOT_AUTHORIZED`; Phase 1 stops at
`CONTACT_PHASE_NOT_AUTHORIZED`. No real infrastructure, source, business, person, contact, AI route,
sender, domain, provider, or delivery is active. Normal CI remains credential-free and network-free.

M1/M2/M2.5 local adapters are constrained by
[ADR-0005](docs/adr/0005-m1-bounded-local-research.md),
[ADR-0010](docs/adr/0010-m2-rule-based-reasoning.md), and
[ADR-0014](docs/adr/0014-live-evaluation-isolation-and-budgets.md).
Open production source, retention, legal, workflow, and infrastructure decisions remain unresolved.

## Repository map

| Path | Purpose |
|---|---|
| `apps/` | Authenticated M6/M6.5 diagnostic web UI |
| `services/` | Authenticated API plus separate M4 demo runtime |
| `workers/` | Separate core, HTTP research, browser, and deterministic M2-M5 intelligence processes |
| `packages/` | M0-M6.7C contracts/local adapters plus isolated M2.6 evaluation adapters |
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

## Run the M6 mock lifecycle and M6.5 readiness diagnostic

From a fresh checkout:

```powershell
python -m pip install "uv==0.11.32"
uv sync --locked --all-packages
python scripts/bootstrap_local.py
```

Start five terminals from the repository root:

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

```powershell
uv run --locked opintel-demo-runtime
```

Open `http://127.0.0.1:3000`. Copy `OPINTEL_AUTH_TOKEN` from ignored `.env`, authenticate,
name one known business, enter one explicitly permitted public URL, start the bounded run, and
refresh its pages/evidence, start deterministic M2 analysis, inspect gaps/economics/factors, record
opportunity review, generate and approve the M3 audit, then generate, inspect, approve, and launch
the M4 simulation on `http://127.0.0.1:8100`, then generate and review the M5 package. The M6 API/UI
can use only synthetic fixture.invalid identities and its deterministic mock provider; it cannot
send a real message. Keep live research disabled unless the URL is authorized. Production live AI
and delivery remain disabled; M2.6 adapters are tournament-only.

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
2. [M6 scope and exit criteria](docs/milestones/M6.md)
3. [Human decision register](docs/decisions/README.md)
4. Accepted ADRs in [docs/adr/](docs/adr/)

When these conflict, stop and resolve the conflict through an ADR rather than silently choosing an implementation.
