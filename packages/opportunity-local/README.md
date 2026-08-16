# Opportunity Local

Owner: development-only M2 adapters.

Responsibilities: SQLite persistence, the M1 evidence-catalog adapter, and a deterministic mock
reasoner with no network or model provider.

Forbidden: production deployment, live AI, web fetching, outreach, arbitrary code execution, and
M3 behavior.

Public interface: M2 repository/evidence/reasoner port implementations. Data access: local SQLite
and M1 public repository contracts only.
