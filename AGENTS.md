# Repository Agent Instructions

## Active milestone

Milestone M3 Evidence-Linked Audit Engine only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M2.md`, `docs/milestones/M3.md`, and accepted ADR-0016 through ADR-0020 before
changing the repository.

M1/M2 remain authoritative. M3 may only project canonical inputs into structured claims,
deterministic prose, QC, and version-bound review. Live AI, all M2.6 routes, and production AI remain
disabled. Normal CI remains credential-free and network-free.

Do not implement M4 or later behavior: demos, proposals, outreach, CRM/channel integrations, mass
discovery, autonomous agents, external publication/export, or generated code.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M3 audit path out of the repository unless the user explicitly advances the milestone.

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
