# ADR-0063: Tournament II qualification identity classes

- **Status:** Accepted
- **Date:** 2026-08-19
- **Decision owners:** Product and architecture owner

## Context

The certified Tournament II roster contains one provider-documented pinned model ID and three
stable model IDs for which the providers do not expose immutable deployment lineage. Tournament II
is a bounded synthetic evaluation, not a production route decision.

## Decision drivers

- Bind every result to the exact provider behavior and configuration that produced it.
- Avoid representing a stable model name as immutable deployment lineage.
- Allow the synthetic tournament to be frozen without weakening production identity requirements.
- Suspend stale approval when a material identity or policy input changes.

## Considered options

1. Admit pinned provider identity and explicitly run-bound stable identity.
2. Treat all stable model IDs as immutable deployments.
3. Exclude every deployment without an immutable snapshot ID.

## Decision

Tournament II accepts exactly two qualification identity classes:

- `PINNED_PROVIDER_IDENTITY` applies to Anthropic `claude-sonnet-5` because current provider
  documentation establishes a pinned model identity.
- `RUN_BOUND_STABLE_IDENTITY` applies to OpenAI `gpt-5.6-sol`, Google `gemini-3.6-flash`, and Google
  `gemini-3.5-flash-lite`.

The run-bound class binds provider, requested and returned model IDs, endpoint/API version,
candidate configuration hash, task-contract version, prompt/schema hashes, execution window,
provider-policy and pricing snapshots, and certification evidence. It is valid only for this
synthetic Tournament II manifest. It does not establish immutable deployment lineage or authorize
an application or production route.

Material model, API, configuration, provider-policy, pricing, task, prompt, schema, corpus, or
evaluator drift suspends the manifest and requires requalification or a new approval.

## Consequences

Tournament reports must state the weaker identity limitation prominently. A result cannot be
silently transferred to a later provider deployment or production route.

## Validation

Tests verify exact identity-class assignment, required lineage fields, drift-sensitive hashes, and
the absence of route authority.

## Revisit triggers

A production route is proposed, a provider publishes immutable snapshot identities, or any bound
identity input changes.
