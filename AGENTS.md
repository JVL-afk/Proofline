# Repository Agent Instructions

## Active milestone

Milestone M6.6B-5 closed the original Tournament II machine run as immutable evidence. Read
`GREENFIELD_ARCHITECTURE.md`, `docs/milestones/M6.5.md`, `docs/milestones/M6.6A.md`,
`docs/milestones/M6.6B-2.md`, `docs/milestones/M6.6B-3.md`,
`docs/milestones/M6.6B-3R.md`, `docs/milestones/M6.6B-4.md`,
`docs/milestones/M6.6B-4A.md`, `docs/milestones/M6.6B-4B.md`,
`docs/milestones/M6.6B-5.md`, and accepted ADR-0054 through ADR-0064 before changing the repository.

M1-M6.5, M6.6A, and the closed M6.6B-2 package remain authoritative and frozen. The M6.6B-3
authorization was consumed after exactly five synthetic certification calls and must not be reused.
Its code and safe receipt may be maintained, but no additional live call is authorized. Hidden
fixtures, real data, application routes, qualification scoring, candidate freeze/readiness,
production AI, and all other live behavior remain disabled. Normal CI remains
credential-free/network-free.

The M6.6B-3R authorization was consumed after exactly two successful synthetic successor calls and
must not be reused. Its code and safe receipt may be maintained, but no additional live call is
authorized. No OpenAI or Anthropic call is authorized. The original M6.6B-3 evidence blob remains
append-only and byte-identical.

The original Tournament II authorization is consumed. Its 194 attempted calls, 190 released calls,
zero retries, USD 1.145397 cost, seven disqualified bindings, and five safety-only Sonnet bindings
must not be changed or rerun. The five Sonnet results are
`AUTOMATED_SAFETY_PASS_HUMAN_REVIEW_UNAVAILABLE`; missing review text must not be reconstructed.
No binding qualified. Do not access hidden fixtures, create or consume another live authorization,
make inference calls, release packages, or activate a route unless a new explicit task authorizes a
separate successor run with exact scope and budget.

Do not execute Tournament II, approve the manifest, implement M6.7, M7, or other live
behavior: real research/person/contact data, sender/domain/site, provider/webhook,
cloud/IdP/KMS/secrets, delivery, publication, bulk/sequence, CRM/channel integration, autonomous
follow-up, or autonomous agents.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside the exact non-executable M6.6B-4 freeze out unless the user advances the milestone.

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
