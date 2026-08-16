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

The product/compliance decisions A-01 through A-20 are tracked separately in `docs/decisions/README.md` until they become ADRs.
