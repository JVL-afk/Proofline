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

- **M6.8-3** — synthetic live-provider certification (owner-authorized
  2026-09-01). `comm.anthropic_provider_adapter@1` (stdlib `urllib`, model pinned
  `claude-sonnet-5`, sampling params unset, `max_tokens=2000`, 30s timeout, 0
  retries, fail-closed), `comm.provider_envelope_projection@1` (the allow-list
  seam — lineage / ids / hashes / internal ranks / person data never cross;
  quoted public text is fenced as inert data), `comm.prompt_template.first_contact@2`,
  and `comm.provider_certification@1` (pre-call bounds enforcement, deterministic
  zero-tolerance safety scoring, `CERTIFIED_SAFE` / `NOT_CERTIFIED` kept separate
  from advisory `COMMUNICATION_QUALITY`, a 12-member certification key, 4 drift
  classes). Frozen 10-scenario synthetic corpus in `tests/m68_3_synthetic_corpus.py`.

M6.8-3 has had three configuration attempts (2026-09-02), none reaching a
safety result — all blocked by the 2000-token output ceiling vs. the
full-claim-manifest-in-response contract. A1 (thinking default): thinking
eats the whole budget. A2 (thinking disabled, N=3): JSON truncated. A3
(thinking disabled, N=1): a 1-call probe proved one candidate + full
manifest still exceeds 2000 tokens, so the 81-call run did not start.
`docs/readiness/communication-layer/m6.8-3-attempt3-outcome-2026-09-02.md`
has the analysis; an owner decision (recommend a two-call candidate/manifest
structure) is pending. No delivery, no send path.
