# ADR-0057: Blinded human usefulness and material-gain disposition

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product and architecture owners

## Context

Safety and schema validity are necessary but do not show that AI improves the finished product.

## Decision drivers

- Compare against deterministic output without provider bias.
- Preserve raw reviewer observations.
- Prefer deterministic behavior when gain is absent.

## Considered options

1. Safety-first blinded paired review.
2. Automated safety alone.
3. Unblinded model preference voting.

## Decision

Human review begins only after automated safety passes and records clarity, naturalness, concision,
usefulness, relevance, trustworthiness, and paired preference. Preserve raw distributions. Final
disposition distinguishes `QUALIFIED_WITH_MATERIAL_GAIN`, `SAFE_BUT_NO_MATERIAL_GAIN`,
`CONDITIONAL`, and `DISQUALIFIED`. Reviewer count and gain threshold remain M6.6B approvals.

## Consequences

Safe but unhelpful models do not displace deterministic behavior.

## Validation

Blinding, randomized ordering, rubric validation, safety prerequisites, and no-aggregate tests apply.

## Revisit triggers

The human-review protocol or definition of material gain is approved for execution.
