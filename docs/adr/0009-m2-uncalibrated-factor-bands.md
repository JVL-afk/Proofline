# ADR-0009: Uncalibrated M2 factor bands and missing-data behavior

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-14, A-19, and architecture sections 13.4 and 14.2-14.4
- **Supersedes:** None

## Context

No labeled baseline justifies statistical confidence percentages, calibrated weights, or a
definitive numeric Opportunity Score.

## Decision drivers

- Expose ranking reasons without false precision.
- Make missing information explicitly reduce or block ranking.
- Preserve snapshots for later calibration.

## Considered options

1. Transparent factor bands and explicit missing-data rules.
2. Publish provisional weighted percentages.
3. Let a reasoning model assign scores.

## Decision

A-14 and A-19 remain deferred. Expose evidence strength, hypothesis confidence, potential value,
implementation feasibility, business fit, and important unknowns as `LOW`, `MEDIUM`, `HIGH`,
`UNKNOWN`, or `NOT_APPLICABLE`. Missing behavior is `BLOCK`, `CAP_BAND`, `LOWER_BAND`, or
`INCOMPLETE`. Expose no probability, weighted total, or definitive headline score. A deterministic
heuristic review-priority band may order the review queue only.

## Consequences

### Positive

- Users see uncertainty and components without misleading precision.
- Snapshots support later backtesting.

### Negative

- Cross-candidate ordering is deliberately coarse.
- Band rules still require explicit versions and tests.

## Validation

Every factor, band, missing-data behavior, contradiction effect, snapshot revision, and explanation
has deterministic tests.

## Revisit triggers

- A-14 or A-19 is accepted after a reviewed labeled baseline exists.
