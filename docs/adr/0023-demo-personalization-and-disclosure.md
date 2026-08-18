# ADR-0023: Evidence-bound personalization, synthetic data, and disclosure

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

Personalization can create unsupported claims, expose personal data, or impersonate the target business.

## Decision drivers

- Preserve M1-M3 semantic authority.
- Make synthetic inputs unmistakable.
- Prevent brand cloning and implied endorsement.

## Considered options

1. Evidence-bound fact projection with neutral presentation and runtime-owned disclosure.
2. Website cloning and brand extraction.
3. Generic demos without a business reference.

## Decision

M4 may project only allowlisted M3 `FACT` claims with exact evidence lineage, plus the canonical
business display name. Initial presentation is neutral and uses no logo, trademark, copied color,
proprietary imagery, real endpoint, employee, customer, or scraped personal data. Personas and lead
inputs are synthetic. Every runtime state forcibly displays the approved anti-impersonation notice.

## Consequences

The demo is personalized enough to be relevant without resembling an official business property.

## Validation

Lineage, entity match, unsupported personalization, PII, disclosure, and scoped-absence tests apply.

## Revisit triggers

Brand assets, customer data, real contact input, or different disclosure language is proposed.
