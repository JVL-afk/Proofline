# Repository Agent Instructions

## Active milestone

Milestone M5 Evidence-Bound Outreach Package Engine only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M4.md`, `docs/milestones/M5.md`, and accepted ADR-0027 through ADR-0032 before
changing the repository.

M1-M4 remain authoritative. M5 may only project exact approved upstream claims into deterministic,
audience-separated drafts with hard QC and content-only human review. Live AI, all M2.6 routes, and
production AI remain disabled. Normal CI remains credential-free and network-free.

Do not implement M6 or later behavior: contact discovery, recipients, copy/export/download,
publication, delivery/sending, CRM/channel integrations, mass outreach, or autonomous agents.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M5 package path out of the repository unless the user explicitly advances the milestone.

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
