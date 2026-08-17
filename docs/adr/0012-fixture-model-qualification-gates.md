# ADR-0012: Fixture-based model qualification and hard safety gates

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** ADR-0007, ADR-0008, ADR-0009
- **Supersedes:** None

## Context

Model quality must be measured on the product's evidence-backed workload. Aggregate fluency or
reasoning scores cannot compensate for invented business facts.

## Decision drivers

- Make unsupported claims, citations, unknowns, contradictions, and injection measurable.
- Keep ordinary CI deterministic and network-free.
- Prevent safety failures from being hidden by aggregate scores.

## Considered options

1. Controlled versioned fixtures, atomic metrics, and hard disqualification gates.
2. Generic public leaderboards.
3. Human preference scoring without semantic gates.

## Decision

Use development, calibration, hidden-qualification, regression, and rotating-challenge corpus
partitions. Critical fabrication, invented citations, false resolution of protected unknowns,
downgraded hard contradictions, prompt-injection compliance, and persistent schema invalidity are
hard disqualifiers. Non-critical consistency thresholds remain versioned and provisional until
calibration. Reasoning usefulness is recorded only after safety gates.

## Consequences

### Positive

- Qualification is tied to actual product failure modes.
- Deterministic mocks can prove the evaluator itself.

### Negative

- Corpus labeling and adjudication require ongoing governance.
- Passing a finite corpus is not a universal correctness guarantee.

## Validation

Every approved fixture family and critical failure path must have deterministic tests.

## Revisit triggers

- Calibration supports revised non-critical thresholds.
- New evidence classes, tasks, or protected unknowns are introduced.
