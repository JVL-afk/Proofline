# Shared Packages

Stable cross-process/cross-language contracts and adapter packages belong here.

M0 owns the walking-skeleton contracts. M1 adds a separate research/evidence bounded context with
canonical business, run, page, snapshot, extracted-material, and evidence contracts plus local
adapters. It does not contain opportunity or value interpretation.

M2 adds `opportunity-core` for semantic lineage, deterministic rules/economics, factor snapshots,
and review contracts, plus `opportunity-local` for development-only SQLite, evidence-catalog, and
mock-reasoner adapters.

M2.5 adds `qualification-core` for provider-neutral tasks, corpus evaluation, lifecycle, and
qualified-only routing, plus `qualification-local` for isolated SQLite ledgers, deterministic mock
providers, budgets, and the disabled live gate.

M2.6 adds `qualification-live` for explicit synthetic-only provider adapters and tournament support.
Normal application processes and deterministic CI do not import or invoke it.

M3 adds `audit-core` for immutable manifests, structured claims, deterministic composition/QC, and
version-bound review, plus `audit-local` for development-only SQLite and read-only canonical M1/M2
catalog adapters. It includes no live AI or publication boundary.

M4 adds `demo-core` for declarative specifications, deterministic state/replay, mock actions, QC,
review, capabilities, and telemetry contracts, plus `demo-local` for SQLite and read-only canonical
M1-M3 adapters. It includes no live AI, real integration, publication, export, or public sharing.

Shared packages must not become a miscellaneous dumping ground for business logic.
