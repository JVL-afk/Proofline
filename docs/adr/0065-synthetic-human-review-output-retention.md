# ADR-0065: Minimal synthetic rendered-output retention for human review

- **Status:** Accepted
- **Date:** 2026-08-19
- **Decision owners:** Product and architecture owner

## Context

Tournament II retained safe hashes and machine findings but discarded normalized candidate output
text. This protected provider envelopes but made blinded usefulness review impossible. The original
run is immutable and cannot be reconstructed.

## Decision drivers

- Preserve enough synthetic content for genuine paired human review.
- Keep raw provider transport, credentials, hidden prompts, and reasoning internals out of storage.
- Keep reviewer-facing artifacts blind to candidate identity and machine telemetry.
- Prevent a supplemental sample from being represented as the original stochastic output.

## Considered options

1. Retain normalized deterministic and candidate renderings in a narrow sealed artifact class.
2. Retain only hashes and abandon human review permanently.
3. Persist raw request and response envelopes.

## Decision

Introduce `HUMAN_REVIEW_RENDERED_OUTPUT` for synthetic qualification only. It contains exact
rendered deterministic and candidate text, anonymous case and task identifiers, hashes, rendering
version, safety result, and receipt lineage. It excludes raw HTTP bodies/envelopes, credentials,
headers, prompts, chain-of-thought, provider identity, and unrelated metadata.

The M6.6B-5R recovery is a new one-shot Anthropic-only run producing
`NEW_MODEL_SAMPLES_FOR_HUMAN_USEFULNESS_EVALUATION`. It binds the original manifest, exact surviving
candidate configuration, five tasks, all 21 originally packaged case identities, the frozen
schemas/evaluator, a separate USD 5 cap, and deterministic A/B seeds. It cannot alter the original
run. Packages remain sealed until three primary identities and one conditional adjudicator are
frozen.

## Consequences

Synthetic review content is locally retainable and reviewable without widening raw provider
retention. New samples remain distinct evidence and must pass all hard gates again.

## Validation

Tests verify exact scope and budget, Anthropic-only transport, safe rendering, hard-gate exclusion,
identity-free reviewer serialization, deterministic A/B assignment, and sealed release state.

## Revisit triggers

Real data, production routing, raw provider retention, a different reviewer protocol, or external
artifact storage is proposed.
