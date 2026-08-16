# Repository Agent Instructions

## Active milestone

Milestone M1 Research Engine only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M1.md`, and the relevant accepted ADRs before changing the repository.

M1 includes bounded, explicitly permitted public-URL research, immutable page snapshots,
observational extraction, provenance-linked evidence, and API/UI traceability. Local M1
adapters remain constrained by ADR-0005 and do not approve production source, retention,
cloud, workflow-hosting, or legal decisions.

Do not implement M2 or later behavior: opportunity detection, ROI, scoring, product audits,
demos, outreach, autonomous agents, mass discovery, authenticated scraping, or live AI/search
providers.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M1 research path out of the repository unless the user explicitly advances the milestone.

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
