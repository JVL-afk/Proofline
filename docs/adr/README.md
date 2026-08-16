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

The product/compliance decisions A-01 through A-20 are tracked separately in `docs/decisions/README.md` until they become ADRs.
