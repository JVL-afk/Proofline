# ADR-0070: Texas Commercial HVAC shadow cohort selection

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product, data-governance, and architecture owners

## Context

The first calibration cohort needs reproducible selection without opportunity-based cherry-picking.
M6.7A may use synthetic businesses only.

## Decision drivers

- Preserve Texas, B2B Commercial HVAC scope.
- Make deduplication, clustering, reserves, and replacements inspectable.
- Retain failures and negative outcomes in the sample.

## Considered options

1. Frozen frame, seed, deterministic ordering, and attempted-slot lineage.
2. Manually selected promising companies.
3. Replace every unusable research result.

## Decision

Phase 1 targets 24 units but requires owner approval before any future real frame. A unit is a
distinct public business/lead-flow representation. Deterministic eligibility, organization
clustering, franchise/shared-brand cap, and multi-location rules run before seeded ordering. The
selection and reserve order are immutable. Replacement is permitted only for predefined cohort
ineligibility; research failure, insufficient evidence, and no supported opportunity remain sampled
outcomes.

## Consequences

Phase 1 calibrates the web-present population and does not claim statewide prevalence.

## Validation

Frame/seed immutability, deduplication, organization caps, ordering, reserve lineage, and exact
replacement-policy tests are required.

## Revisit triggers

The cohort size, geography, vertical, unit of analysis, or sampling inference changes.
