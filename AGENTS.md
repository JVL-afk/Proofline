# Repository Agent Instructions

## Active milestone

Milestone M0 only. Read `GREENFIELD_ARCHITECTURE.md`, `docs/milestones/M0.md`, and the relevant accepted ADRs before changing the repository.

The M0 walking skeleton includes only local authentication, one fixture campaign command, a durable local operation, one controlled fixture fetch, one evidence record, and API/UI traceability.

Do not implement M1 or later behavior: production discovery/crawling, public-web fetch, opportunities, ROI, scoring, audits, demos, outreach, autonomous agents, or live AI/search providers.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M0 walking-skeleton path out of the repository unless the user explicitly advances the milestone.

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
