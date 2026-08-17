# Qualification Local Adapters

Owner: local-only M2.5 adapters.

Responsibilities: SQLite registry/evaluation/ledger persistence, deterministic mock providers,
in-memory budget enforcement, provider catalog, and disabled live-evaluation gate.

Forbidden: provider SDKs, external network calls, production credentials, canonical M2 writes,
authoritative model decisions, autonomous behavior, and M3 functionality.

Public interface: implementations of qualification-core ports. Data access: qualification-prefixed
SQLite tables only.
