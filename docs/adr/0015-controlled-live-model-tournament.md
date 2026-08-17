# ADR-0015: Controlled synthetic live model qualification tournament

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

M2.5 supplies provider-neutral, deterministic qualification infrastructure. The product owner has
authorized a bounded tournament against current OpenAI, Anthropic, and Google Gemini deployments to
measure the approved M2 reasoning tasks on controlled synthetic fixtures.

## Decision drivers

- Truth and unknown preservation must dominate fluency or benchmark reputation.
- Evaluation must use the actual product contracts while preserving deterministic M2 authority.
- Live cost, data release, credentials, and network behavior require explicit fail-closed controls.
- Normal CI must remain reproducible without credentials or network access.

## Considered options

1. Continue mock-only evaluation.
2. Permit unrestricted provider integration.
3. Permit a synthetic-only, explicit, budget-capped local tournament.

## Decision

Choose option 3. A-10 becomes `Controlled evaluation authorized` only for synthetic repository-owned
qualification fixtures. The exact initial deployments are `gpt-5.6-terra`, `gpt-5.6-sol`,
`claude-sonnet-5`, `claude-opus-5`, and `gemini-3.6-flash`. Configuration is part of qualification
identity. Live execution requires an explicit command, allowlists, a kill switch, preflight budget
reservation, a USD 50 total cap, and deployment sub-budgets. No tools or external side effects are
enabled. Raw payloads are not persisted. Results remain non-authoritative and uncommitted pending
human review.

This decision does not authorize real-business data, production routing, shadow/advisory production
operation, provider selection, autonomous behavior, or M3 functionality.

## Consequences

- A separate `qualification-live` adapter package and explicit runner are allowed.
- Provider-native wire formats remain private to adapters.
- Provider/config/task/policy/corpus identity and safe usage metadata are recorded.
- Any confirmed critical hard-gate failure disqualifies that exact deployment/configuration/task and
  stops later expensive rounds for that pair.

## Validation

- Fake-transport tests cover authentication headers, schemas, retries, timeouts, rate limits,
  malformed responses, redaction, usage, and cost without network access.
- The deterministic M0–M2.5 suite passes before and after M2.6 changes.
- The live runner refuses non-synthetic data, missing allowlists, closed kill switches, or budgets
  above USD 50.

## Revisit triggers

- Any proposal to send real or uncontrolled data.
- Any production, shadow, advisory, or autonomous provider use.
- Provider terms, retention, regions, pricing, model IDs, or API behavior change.
- Tournament results require a production-provider decision.

## Experimental checkpoint outcome

Tournament Run 1 closed with no qualified deployment/task pair. Deterministic M2 remains
authoritative, production AI and all routes remain disabled, and the controlled evaluation
infrastructure remains available. Provider/model selection is deferred until representative
end-to-end product workflows exist. The checkpoint does not authorize tuning, additional
qualification, provider retries, or another tournament run. A-10 remains unresolved for production
provider/model selection.
