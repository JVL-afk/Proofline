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

M6.8-3 has had two configuration attempts (2026-09-02, Option A local, 27
real `claude-sonnet-5` calls each, ≈ USD 0.84 each), both **`NOT_CERTIFIED`**
on configuration blockers — neither a safety failure. Attempt 1
(thinking default): extended thinking eats the whole 2000-token ceiling →
zero text. Attempt 2 (thinking disabled): on-policy text is produced but the
N=3-candidate JSON is truncated at 2000 output tokens → 0 candidates parsed.
`docs/readiness/communication-layer/m6.8-3-attempt2-outcome-2026-09-02.md`
has the analysis; a response-format decision (recommend N=1/call → 81 calls)
is now on the owner. No delivery, no send path.
