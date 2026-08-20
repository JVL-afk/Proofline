# ADR-0072: Synthetic shadow review, measurement, and stop controls

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product, security, privacy, and architecture owners

## Context

M6.7 needs review sampling and useful metrics without averaging away safety failures or fabricating
unavailable denominators.

## Decision drivers

- Preserve mandatory canonical reviews.
- Inspect negative outcomes without requiring maximum-depth review of every company.
- Make safety stops independent of commercial yield.

## Considered options

1. Mandatory advancement review plus seeded, stratum-covering negative QA.
2. Review every artifact at maximum depth.
3. Aggregate quality and safety into one score.

## Decision

M6.7A implements synthetic review assignments, independent second review for accepted opportunities,
seeded negative QA with observed-stratum coverage, measured review duration, typed metric numerator/
denominator states, stage costs, zero-tolerance incidents, company quarantine, cohort pause, and
run termination. Person/contact metrics are `NOT_MEASURED` in Phase 1. AI cost is exactly USD 0 with
reason `NO_M6_6_BINDING_ELIGIBLE_FOR_M6_7`.

This ADR accepts control-plane mechanics only. It approves no real source, retention period,
reviewer identity, operational threshold, or live run.

## Consequences

Hard safety findings cannot be hidden by yield or aggregate performance. Unknown denominators stay
unmeasured.

## Validation

Review prerequisites, reviewer independence, deterministic QA, metric-state, zero-cost AI, every
hard-stop category, and commercial-non-override tests are required.

## Revisit triggers

Real reviewers, thresholds, sampling rates, or operational stop/resume policy are approved.
