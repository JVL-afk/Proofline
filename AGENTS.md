# Repository Agent Instructions

## Active milestone

Milestone M4 Personalized Demo Engine only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M3.md`, `docs/milestones/M4.md`, and accepted ADR-0021 through ADR-0026 before
changing the repository.

M1-M3 remain authoritative. M4 may only project exact accepted/approved inputs into declarative,
deterministic, synthetic, mock-only simulations with a separate capability-scoped runtime. Live AI,
all M2.6 routes, and production AI remain disabled. Normal CI remains credential-free and network-free.

Do not implement M5 or later behavior: proposals, outreach, real CRM/channel integrations, mass
discovery, autonomous agents, external publication/export, media generation, or generated code.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M4 demo path out of the repository unless the user explicitly advances the milestone.

## Validation

Run:

```text
python scripts/check_repository.py
python -m compileall -q packages services workers scripts
git diff --check
```

When Node.js 24/npm 11 are available, also run:

```text
npm ci --ignore-scripts --no-audit --no-fund
npm run check:repo
npm run check:python
npm run typecheck
npm test
```
