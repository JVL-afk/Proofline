# Research Local Adapters

Owner: research and evidence bounded context infrastructure.

Responsibilities: local SQLite research persistence, pinned-IP HTTP transport, bounded decoding,
DNS/IP policy adapters, and local browser-process client.

Forbidden: production deployment, credentials/cookies, internal-network access, form submission,
business interpretation, and use outside ADR-0005.

Public interface: `opintel_research_local` adapters. Data access: M1 tables in the local SQLite
database. Dependencies: research-core, stable M0 core protocols, Pydantic Settings, and SQLAlchemy.

The research worker uses a dedicated settings model that has no authentication-token, user-session,
provider-key, or application-secret field.
