# Shared Packages

Stable cross-process/cross-language contracts and adapter packages belong here.

M0 owns the walking-skeleton contracts. M1 adds a separate research/evidence bounded context with
canonical business, run, page, snapshot, extracted-material, and evidence contracts plus local
adapters. It does not contain opportunity or value interpretation.

M2 adds `opportunity-core` for semantic lineage, deterministic rules/economics, factor snapshots,
and review contracts, plus `opportunity-local` for development-only SQLite, evidence-catalog, and
mock-reasoner adapters.

Shared packages must not become a miscellaneous dumping ground for business logic.
