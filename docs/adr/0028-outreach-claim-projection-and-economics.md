# ADR-0028: Outreach claim projection and external economic restrictions

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Prospect-facing wording can silently turn qualified M3 claims into unsupported certainty.

## Decision drivers

- Preserve fact, inference, scoped absence, recommendation, and unknown semantics.
- Prevent unsupported or misleading financial claims.
- Bind every business statement to an approved M3 claim.

## Considered options

1. Typed allowlisted projections with hard QC.
2. Free paraphrasing with reviewer judgment.
3. Directly expose audit prose.

## Decision

M5 permits only narrow fact restatement, conditional inference, explicitly scoped absence,
conditional recommendation, and internal-only economic context. Every external business statement
resolves to an exact approved M3 claim and upstream lineage. Initial email, follow-up, and call
artifacts contain no currency, percentage, ROI, revenue, savings, loss, conversion, volume,
customer-value, or economic output. `UNKNOWN`, `PROPOSED`, `HYPOTHETICAL`, and
`INSUFFICIENT_DATA` remain exact internally.

## Consequences

Initial copy is deliberately conservative; external financial use requires a later decision.

## Validation

Unsupported claim, removed qualifier, scoped-absence, unknown, proposed-input, and financial-value
hostile tests are required.

## Revisit triggers

External economic claims or another semantic projection type is proposed.
