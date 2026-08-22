# Repository Agent Instructions

## Active milestone

ADR-0075 workload-plan/workload-apply identities, their private-endpoint/service-discovery successor
permissions, protected state-role trust, and final ECS/RDS/Cloud Map service-dependency permissions
were each applied under separate exact owner approvals and independently observed in AWS account
`785072247535`, region `us-east-2`. PostgreSQL 18 lifecycle parity, fail-closed SSM suspension,
read-only task configuration, and ADR-0076 isolated exact-host egress are validated. The final
service-dependency evidence is in
`docs/readiness/m6.7-deployment/workload-service-dependency-deployed-evidence-2026-08-22.json`.

The first remediated Phase 1 apply stopped before resource creation because Terraform embedded its
plan-time state-plan backend identity in the saved plan. The consumed approval and zero-resource
result are recorded in `docs/readiness/m6.7-deployment/phase1-apply-attempt-2026-08-22.json`; never
retry that predecessor plan. ADR-0075 now records the demonstrated saved-plan constraint.

The successor authenticated Phase 1 application plan in
`docs/readiness/m6.7-deployment/phase1-remediated-plan-successor-review-2026-08-22.json` is exactly
`READY_FOR_PHASE1_APPLY_AUTHORIZATION`: 83 creates, 0 changes, 0 replacements, and 0 destroys. Its
AWS provider plan used the deployed workload-plan identity, its embedded backend uses the protected
state-apply identity required to persist an apply, and its managed changes are byte-semantically
identical to the reviewed predecessor. It binds the same clean immutable successor worker image.
Do not apply it without the owner's exact hash-bound `APPROVE_PHASE1_APPLY_SUCCESSOR` statement.
Application apply remains separate from discovery, research, person/contact, Slot 1, and
communication authority; all remain unauthorized.

The exact worker-registry plan was applied and independently verified, and the immutable Phase 1
worker successor image is stored in the approved ECR repository at digest
`sha256:8af8123b618e5d5024b6d715cd7956a52a79df41e4b5d201c4dc5f993ee3edf5`; its
CycloneDX/Trivy/provider evidence is in
`docs/readiness/m6.7-deployment/worker-image-successor-evidence-2026-08-22.json`. The historical
authenticated Phase 1 application plan proposes 58 creates and zero changes, replacements, or
destroys, but it is **not** ready for apply authorization and remains historical evidence. It was
superseded by the 83-create remediated plan above. Its immutable review is in
`docs/readiness/m6.7-deployment/phase1-plan-review-2026-08-22.json`; never apply the historical plan.
All discovery, research, person/contact, slot, AI, and delivery permissions remain unauthorized.

The exact approved M6.7 Phase 1 Terraform-state bootstrap plan was applied in AWS account
`785072247535`, region `us-east-2`, then independently observed. Its 18 creates, protected S3/KMS
state boundary, state plan/apply roles, and CloudTrail state-object audit controls are recorded in
`docs/readiness/m6.7-deployment/bootstrap-deployed-evidence-2026-08-21.json`. Bootstrap state was
migrated to `m67/bootstrap/terraform.tfstate`; obsolete local resource state was removed. The exact
worker ECR repository is deployed and independently verified. All live-data permissions remain
`NOT_AUTHORIZED`.

M6.7 owner approvals are consolidated: discretionary defaults are recorded once, three actor
pseudonyms are generated with private reconciliation material outside Git, and only the AWS
account/organization fact plus short-lived SSO entry point remain owner-supplied infrastructure
facts. Resource identifiers, hashes, worker-image evidence, seed artifacts, and technical host
metadata are derived or observed. This consolidation grants no permission: OIDC reconciliation,
authenticated reviewed applies, deployed evidence, exact seed/host approval, and the final discovery
signature remain fail-closed gates. Research and slot authority remain separate and unauthorized.

Milestone M6.7C is closed at `8cc38bd19cc45ae3712d6a106b982e3faf75d431`. The final Phase 1
authorization package is documentation only. Owner scope, workload ceilings and the USD 250/AI
USD 0 caps are recorded. A-08 is approved but not live-effective, attorney-provided A-17 is
`APPROVE_WITH_CONTROLS`, and role actors are approved pending opaque identity binding. Exact
sources/environment/identity values remain unapproved, ADR-0071 remains proposed, and every
real-data permission remains `NOT_AUTHORIZED`. M6.6B-9
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
ADR-0070 plus ADR-0072, ADR-0074, and ADR-0075
before changing the repository.

ADR-0075 accepts Terraform for Phase 1 provisioning. Its provider lock and locally validated
configuration grant no AWS, discovery, research, or slot authority. No plan/apply is authorized
without the missing account/backend inputs, exact roles, final data/legal decisions, AWS charge
authorization, short-lived credentials, and separately reviewed plan.

The project owner recorded attorney-provided `A-17 = APPROVE_WITH_CONTROLS` evidence and approved
the minimized-capture A-08 successor policy. These records do not authorize live work. ADR-0071
remains proposed until actual environment/storage evidence and opaque identity bindings exist.
Counsel's conclusion is fact-bound and must not be generalized; every exact first-party host still
requires its own review. Raw page bodies are ephemeral inputs, not ordinary durable snapshots.

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
