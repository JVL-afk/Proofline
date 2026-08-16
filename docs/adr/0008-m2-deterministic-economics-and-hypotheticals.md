# ADR-0008: Deterministic M2 economics and hypothetical labelling

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-13 and architecture section 14
- **Supersedes:** None

## Context

M2 requires reproducible economics while verified business-specific inputs are normally unavailable.

## Decision drivers

- Prevent invented precision and fabricated lost-revenue claims.
- Reproduce every output from exact typed inputs and a formula version.
- Permit clearly labelled scenario exploration.

## Considered options

1. Versioned typed deterministic formulas with explicit unknown/proposed inputs.
2. Narrative model estimates.
3. Silent industry defaults that always produce a number.

## Decision

Accept A-13 for the initial formula:

- `affected_leads = monthly_inbound_leads × affected_share`;
- `incremental_wins = affected_leads × conversion_lift`;
- `potential_incremental_revenue = incremental_wins × average_customer_value`.

It is monthly, may display annualized values, and uses USD and Decimal arithmetic. There is no
arbitrary expression execution, silent default, or embedded unapproved benchmark. Required unknowns
produce `INSUFFICIENT_DATA`. Proposed inputs produce a visibly `HYPOTHETICAL` potential incremental
revenue scenario, never actual lost revenue, profit, verified impact, or realized gain.

## Consequences

### Positive

- Numeric results are reproducible and honest about uncertainty.
- Formula execution remains a safe, typed infrastructure boundary.

### Negative

- Many initial hypotheses produce no numeric result.
- The formula represents potential revenue only, not profit or realized value.

## Validation

Unit, currency, time basis, Decimal/range, unknown, hypothetical-labelling, reproducibility,
overflow, and prohibited-wording tests are required.

## Revisit triggers

- Another opportunity type, currency, geography, value meaning, or formula family is approved.
- Verified business inputs or approved benchmarks become available.
