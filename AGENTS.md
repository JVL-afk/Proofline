# Repository Agent Instructions

## Active milestone

Milestone M2.5 AI Qualification Infrastructure only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M2.md`, `docs/milestones/M2.5.md`, and accepted ADR-0011 through ADR-0014 before
changing the repository.

M2 remains authoritative. M2.5 adds only provider-neutral evaluation, registry, routing, mock,
budget, and ledger infrastructure. Live AI is disabled, A-10 remains unresolved, and local adapters
remain non-production.

Do not implement M3 or later behavior: audits, demos, proposals, outreach, CRM/channel
integrations, mass discovery, autonomous agents, external publication, or generated code.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact M2.5 qualification path out of the repository unless the user explicitly advances the milestone.

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
