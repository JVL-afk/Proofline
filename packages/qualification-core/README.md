# Qualification Core

Owner: AI qualification bounded context.

Responsibilities: provider-neutral task contracts, corpus and evaluation semantics, hard safety
gates, immutable qualification lifecycle, advisory routing policy, and budget/live-evaluation ports.

Forbidden: provider SDKs, network access, M2 persistence imports, evidence creation, authoritative
economics/scoring, opportunity acceptance, autonomous behavior, and M3 functionality.

Public interface: `opintel_qualification` typed domain, evaluator, application, routing, and ports.
Data access: none.
