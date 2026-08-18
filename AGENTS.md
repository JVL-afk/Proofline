# Repository Agent Instructions

## Active milestone

Milestone M6 Contact Eligibility & Controlled Delivery only. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M5.md`, `docs/milestones/M6.md`, and accepted ADR-0033 through ADR-0042 before
changing the repository.

M1-M5 remain authoritative. M6 may only use synthetic identities, fixture policies, exact approved
M5 revisions, and a deterministic zero-network single-message mock. Live AI, real providers, all
M2.6 routes, and production AI remain disabled. Normal CI remains credential-free/network-free.

Do not implement M7 or live behavior: real person/contact discovery or verification, real sender,
email/webhook provider, copy/export/publication, bulk/sequence delivery, CRM/channel integration,
autonomous follow-up, or autonomous agents.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact mock-only M6 path out unless the user advances the milestone.

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
