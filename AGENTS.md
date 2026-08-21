# Repository Agent Instructions

## Active milestone

Milestone M6.7C is closed at `8cc38bd19cc45ae3712d6a106b982e3faf75d431`. The final Phase 1
authorization package is documentation only. Owner scope, workload ceilings and the USD 250/AI
USD 0 caps are recorded, but retention remains provisional, exact sources/environment/roles remain
unapproved, A-17 remains blocked, and every real-data permission remains `NOT_AUTHORIZED`. M6.6B-9
remains closed with no qualified binding, no route activation, and no canonical mutation. Read
`GREENFIELD_ARCHITECTURE.md`, `docs/milestones/M6.5.md`, `docs/milestones/M6.6A.md`,
`docs/milestones/M6.6B-2.md`, `docs/milestones/M6.6B-3.md`,
`docs/milestones/M6.6B-3R.md`, `docs/milestones/M6.6B-4.md`,
`docs/milestones/M6.6B-4A.md`, `docs/milestones/M6.6B-4B.md`,
`docs/milestones/M6.6B-5.md`, `docs/milestones/M6.6B-5R.md`,
`docs/milestones/M6.6B-6.md`, `docs/milestones/M6.6B-8.md`,
`docs/milestones/M6.6B-9.md`, `docs/milestones/M6.7A.md`, `docs/milestones/M6.7B.md`,
`docs/milestones/M6.7C.md`, `docs/readiness/m6.7b/README.md`,
`docs/readiness/m6.7-authorization/README.md`,
`docs/readiness/m6.7-authorization/owner-decisions.md`,
`docs/readiness/m6.7-authorization/owner-decisions-successor-2026-08-21.md`,
`docs/readiness/m6.7-authorization/seed-and-selection-policy.md`,
`docs/readiness/m6.7-authorization/discovery-readiness.md`,
`docs/readiness/m6.7-authorization/counsel-review-form.md`, and accepted ADR-0054 through
ADR-0070 plus ADR-0072 and ADR-0074
before changing the repository.

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
No binding qualified. M6.6B-5R completed 105 calls with zero retries and zero new safety failures,
then sealed 20 packages. Its authorization is consumed and must not be reused. The normalized
synthetic review renderings remain sealed except for the three locked primary releases and the exact
41-case locked adjudication review bound by M6.6B-8. M6.6B-9 unblinded only after all human records
were immutable. The three reasoning bindings are `SAFE_BUT_NO_MATERIAL_GAIN`; audit and outreach
wording are `CONDITIONAL / NO_ROUTE`; the seven machine-stage disqualifications remain unchanged.
No binding qualified. The rendered-wording/structured-CTA gap remains a future versioned validator
requirement and must not be patched into or used to rescore historical evidence. OpenAI, Google,
further Sonnet calls, further package release, routes, M6.7 live data, and configuration changes
remain forbidden.

M6.7 owns synthetic cohort/control-plane and gate records only. All seven successor real-data
permissions are `NOT_AUTHORIZED`; ADR-0071 and ADR-0073 are proposed, not accepted for live use.
M6.7C technical readiness grants no permission. Do not execute
Tournament II, approve the manifest, begin M6.7 live discovery/research, M6.7 person/contact phases,
M6.8, M7, or other live
behavior: real research/person/contact data, sender/domain/site, provider/webhook,
cloud/IdP/KMS/secrets, delivery, publication, bulk/sequence, CRM/channel integration, autonomous
follow-up, or autonomous agents.

The owner has frozen a maximum 100-candidate business-only seed frame, seeded 24-company selection,
25%/minimum-three negative QA, and the slot 1 → pause → slots 2-6 → pause → slots 7-24 sequence.
These values grant no source, environment, person/contact, discovery, research, or delivery authority.
The AWS files under `infra/aws/phase1/` are non-executable specifications only; intended configuration
is not actual infrastructure evidence.

## Required behavior

- Do not infer that an open A-01 through A-20 decision is approved.
- Link consequential choices to an accepted ADR.
- Preserve the module and security boundaries in `docs/engineering/module-boundaries.md`.
- Do not add executable infrastructure until its cloud/region/IaC/data decisions are accepted.
- Do not commit secrets, personal data, live provider payloads, generated credentials, or local service data.
- Use exact/locked dependencies and justify new direct dependencies under `docs/engineering/dependencies.md`.
- Keep all behavior outside M6.7A-M6.7C synthetic control/gate scope out unless the user
  advances the milestone.

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
