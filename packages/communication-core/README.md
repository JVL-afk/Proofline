# communication-core

M6.8 Evidence-Bound Communication Transformer — pure deterministic core.

The deterministic engine (M2–M5) stays authoritative for **what may be said**; a
provider controls only **how** permitted information is expressed. This package
contains none of that provider integration.

- **M6.8-1** — the deterministic authority (`comm.semantic_envelope@1`,
  `comm.claim_manifest@1`) and the deterministic gate (`comm.output_validator@1`,
  `comm.cta_parser@1`).
- **M6.8-2** — the stubbed generation lifecycle: `comm.generation_orchestrator@1`,
  a deterministic `StubProviderAdapter`, an append-only hash-chained
  `comm.generation_store@1`, `comm.candidate_ranker@1`, raw-response retention
  machinery (`RawResponseVault`, POLICY_PENDING), and an immutable
  `comm.human_review@1` domain.

No real provider adapter, no network, no delivery, no send path. USD 0. A live
provider (M6.8-3) requires separate owner authorization.
