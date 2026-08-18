# Architecture Decision Records

ADRs capture decisions that constrain implementation or are expensive to reverse.

## Status values

- `Proposed`: under review; must not be treated as approved.
- `Accepted`: current decision.
- `Superseded`: replaced by a later ADR.
- `Rejected`: considered and deliberately not selected.
- `Deprecated`: still present but scheduled for removal.

## Process

1. Copy `0000-template.md` to the next four-digit number and a short kebab-case title.
2. State context and constraints without presenting a preferred option as fact.
3. Record alternatives and material tradeoffs.
4. Name the accountable approver in the decision metadata.
5. Merge implementation only after the ADR reaches `Accepted`, unless a documented exception exists.
6. Never edit an accepted ADR to change its decision. Add a superseding ADR.

## Index

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-modular-monolith-monorepo.md) | Accepted | Modular monolith in a polyglot monorepo with isolated hostile-content deployables |
| [ADR-0002](0002-runtime-and-workspace-baseline.md) | Accepted | Node.js 24 LTS, npm workspaces, and Python 3.13 baseline for M0 |
| [ADR-0003](0003-python-workspace-and-locking.md) | Accepted | uv workspace and universal lockfile for Python packages |
| [ADR-0004](0004-m0-local-walking-skeleton-adapters.md) | Accepted | Local-only auth, SQLite workflow, fixture fetch, and diagnostic UI adapters for M0 |
| [ADR-0005](0005-m1-bounded-local-research.md) | Accepted | Bounded local M1 research adapters without closing production source/retention decisions |
| [ADR-0006](0006-m2-semantic-lineage-and-review.md) | Accepted | Separate semantic lineage with mandatory hypothesis review |
| [ADR-0007](0007-commercial-hvac-lead-response-definition.md) | Accepted | Texas Commercial HVAC inbound lead-response definition |
| [ADR-0008](0008-m2-deterministic-economics-and-hypotheticals.md) | Accepted | Deterministic potential-incremental-revenue scenarios |
| [ADR-0009](0009-m2-uncalibrated-factor-bands.md) | Accepted | Heuristic factor bands until calibration exists |
| [ADR-0010](0010-m2-rule-based-reasoning.md) | Accepted | Rule-based M2 reasoning and temporary local adapters |
| [ADR-0011](0011-provider-neutral-intelligence-contracts.md) | Accepted | Provider-neutral task contracts and versioned deployment qualification |
| [ADR-0012](0012-fixture-model-qualification-gates.md) | Accepted | Fixture-based qualification metrics and hard safety gates |
| [ADR-0013](0013-deterministic-baseline-ai-routing.md) | Accepted | Advisory-only routing with deterministic M2 fallback |
| [ADR-0014](0014-live-evaluation-isolation-and-budgets.md) | Accepted | Disabled live boundary, budgets, provenance, and data controls |
| [ADR-0015](0015-controlled-live-model-tournament.md) | Accepted | Synthetic-only, budget-capped live model qualification tournament |
| [ADR-0016](0016-structured-audit-claims-and-manifests.md) | Accepted | Structured audit claims and immutable input manifests |
| [ADR-0017](0017-audit-lineage-and-qc.md) | Accepted | Audit lineage and non-overridable semantic QC |
| [ADR-0018](0018-deterministic-audit-composition.md) | Accepted | Deterministic audit composition and disabled wording-only AI port |
| [ADR-0019](0019-audit-review-and-invalidation.md) | Accepted | Exact revision review and invalidation lifecycle |
| [ADR-0020](0020-audit-eligibility-and-publication-boundary.md) | Accepted | Opportunity eligibility and no-publication M3 boundary |
| [ADR-0021](0021-declarative-demo-specification.md) | Accepted | Declarative demo specifications and immutable component registry |
| [ADR-0022](0022-deterministic-demo-state-machine.md) | Accepted | Deterministic state machine and structurally mock-only actions |
| [ADR-0023](0023-demo-personalization-and-disclosure.md) | Accepted | Evidence-bound personalization, synthetic data, and disclosure |
| [ADR-0024](0024-demo-runtime-isolation.md) | Accepted | Separate runtime, capability sessions, CSP, and minimal telemetry |
| [ADR-0025](0025-demo-eligibility-review-and-revocation.md) | Accepted | Exact eligibility, review, invalidation, and revocation |
| [ADR-0026](0026-authenticated-demo-access.md) | Accepted | Authenticated-only demo access with no public sharing |
| [ADR-0027](0027-outreach-packages-and-exact-manifests.md) | Accepted | Immutable M5 packages and exact approved M1-M4 manifests |
| [ADR-0028](0028-outreach-claim-projection-and-economics.md) | Accepted | Typed claim projection and internal-only economics |
| [ADR-0029](0029-deterministic-outreach-templates.md) | Accepted | Deterministic templates and disabled wording AI port |
| [ADR-0030](0030-outreach-artifact-separation-and-qc.md) | Accepted | Internal/external separation and non-overridable hard QC |
| [ADR-0031](0031-outreach-content-review-no-delivery.md) | Accepted | Content-only review, invalidation, and no-delivery boundary |
| [ADR-0032](0032-functional-role-targeting.md) | Accepted | Functional-role targeting without people or impersonation |

The product/compliance decisions A-01 through A-20 are tracked separately in `docs/decisions/README.md` until they become ADRs.
