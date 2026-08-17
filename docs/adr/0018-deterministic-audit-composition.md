# ADR-0018: Deterministic audit composition and non-authoritative prose port

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

No model qualified in M2.6, and audit correctness must be independent of prose quality.

## Decision drivers

- Reproducibility and honest wording.
- No provider dependency in normal CI.
- A future model must not create claims or numbers.

## Considered options

1. Deterministic authoritative composition with a disabled wording-only port.
2. Live model composition.
3. Free-form templates edited without claim validation.

## Decision

Use the versioned deterministic composer as M3 authority. A future `ProseComposerPort` may propose
wording keyed only to existing claim IDs; it cannot add claims, entities, bindings, or numbers.
There is no live implementation and no M2.6 route activation.

## Consequences

Initial prose is plain but stable and safe. Stylistic model evaluation remains deferred.

## Validation

Replay, prompt-injection, fake composer, retry, timeout, schema, and no-network tests are required.

## Revisit triggers

A complete end-to-end workflow is ready for a separately approved live composition evaluation.
