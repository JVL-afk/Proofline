# Repository Agent Instructions

## Active milestone

Milestone M2.6 is closed as an experimental checkpoint. Read `GREENFIELD_ARCHITECTURE.md`,
`docs/milestones/M2.md`, `docs/milestones/M2.5.md`, `docs/milestones/M2.6.md`, and accepted ADR-0011
through ADR-0015 before changing the repository. M3 is authorized for design only; implementation
requires a later explicit instruction.

M2 remains authoritative. Tournament Run 1 must remain preserved exactly. Do not run further live
evaluation, optimize prompts, retry Gemini, or begin Tournament Run 2 without new authorization.
Normal CI remains credential-free and network-free. No provider or model is approved for production
use, and provider/model selection is deferred until representative end-to-end workflows exist.

Do not implement M3 or later behavior: audits, demos, proposals, outreach, CRM/channel
integrations, mass discovery, autonomous agents, external publication, or generated code.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the closed M2.6 checkpoint out of the repository unless the user explicitly advances the milestone.

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
