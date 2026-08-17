# ADR-0013: Deterministic-baseline AI routing and fail-closed fallback

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** ADR-0006, ADR-0008, ADR-0009, ADR-0010
- **Supersedes:** None

## Context

Future qualified models may assist reasoning, but M2 evidence, economics, scoring, and review remain
authoritative.

## Decision drivers

- Prevent advisory output from becoming semantic truth.
- Route only to deployments qualified for the exact request contract.
- Fail safely when providers, schemas, policies, or budgets fail.

## Considered options

1. Evaluation-only, shadow, and advisory routing with deterministic fallback.
2. Direct authoritative model decisions.
3. Fallback to any available model.

## Decision

Support only `EVALUATION_ONLY`, `SHADOW`, and `ADVISORY`. Routing filters exact active qualification
records and never selects an unqualified deployment. Retries and fallbacks are bounded and logged.
When no qualified route succeeds, deterministic M2 remains the fallback. No model creates evidence,
assumptions, authoritative calculations, scores, acceptance, or changed review requirements.

## Consequences

### Positive

- Provider failure cannot reduce M2 correctness.
- Model assistance can be introduced gradually and reversibly.

### Negative

- Advisory disagreements require human interpretation.
- Deterministic fallback may be less expressive.

## Validation

Unqualified routing, bounded retry, provider failure, fallback, stage, and M2-isolation tests are
required.

## Revisit triggers

- Any authoritative or autonomous stage is proposed.
- A model is proposed to modify M2 economics, scoring, or review state.
