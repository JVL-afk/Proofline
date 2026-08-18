# Repository Agent Instructions

## Active milestone

Milestone M6.6A Tournament II Qualification Infrastructure only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M6.5.md`, `docs/milestones/M6.6A.md`, and accepted ADR-0054 through ADR-0062 before
changing the repository.

M1-M6 remain authoritative and frozen. M6.6A may only implement synthetic task contracts, corpus,
semantic evaluation, fake candidate/provider machinery, blinded review tooling, budgets, and reports.
Live AI, real data/providers/senders/infrastructure, all routes, and production AI remain disabled.
Normal CI remains credential-free/network-free.

Do not execute M6.6B, implement M6.7, M7, or live behavior: real research/person/contact data,
sender/domain/site, provider/webhook, cloud/IdP/KMS/secrets, delivery, publication, bulk/sequence,
CRM/channel integration, autonomous follow-up, or autonomous agents.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside exact M6.6A qualification infrastructure out unless the user advances the milestone.

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
