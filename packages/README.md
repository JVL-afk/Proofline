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

M5 adds `outreach-core` for exact manifests, claim projections, deterministic plain-text artifacts,
hard QC, and content-only review, plus `outreach-local` for SQLite and a read-only M1-M4 catalog.
It contains no people, recipient, copy, export, delivery, channel, live-AI, or side-effect adapter.

M6 adds `contact-core` for independent identity/verification/eligibility/readiness/authorization/send
records and `contact-local` for append-only SQLite plus synthetic, fixture-only adapters. The sole
delivery adapter is a credential-free zero-network mock and has no bulk surface.

M6.5 adds `activation-core` for immutable production-prerequisite contracts, deterministic
fail-closed readiness, phased real-data permissions, and mandatory non-send `SHADOW_READY`, plus
`activation-local` for append-only SQLite. It has no infrastructure, identity, provider, source,
real-data, domain, AI, network, or delivery adapter.

M6.6A extends `qualification-core` with synthetic Tournament II task projections, semantic hard
gates, immutable qualification history, fake-only candidate/provider machinery, blinded review,
hierarchical fixture budgets, and task-level reports. It adds no live transport, credential, route,
real-data permission, M6/M6.7 authority, or delivery capability.

M6.7A adds `shadow-core` for split permissions, frozen synthetic cohorts, read-only M1-M5 lineage,
outcome/review/QA/metric/cost/stop records, and M6.8 evidence packages, plus `shadow-local` for
append-only SQLite and synthetic canonical projections. It has no real-data, person/contact, AI,
network, M6 command, sender, or delivery interface.

Shared packages must not become a miscellaneous dumping ground for business logic.
