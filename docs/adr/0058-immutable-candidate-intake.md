# ADR-0058: Just-in-time candidate intake and immutable qualification identity

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, security, privacy, and architecture owners

## Context

Current deployments, prices, configurations, and provider terms change frequently.

## Decision drivers

- Avoid hard-coded model preferences.
- Bind results to exact executable identity.
- Review provider handling before data release.

## Considered options

1. Just-in-time frozen intake records.
2. Permanent model names in application configuration.
3. Informal operator selection.

## Decision

Candidate intake records capture exact deployment, configuration, tasks, structured output, data
handling, retention, terms, pricing, and approvals before freezing. M6.6A populates deterministic
fake candidates only. M6.6B performs current official-source discovery immediately before execution.

## Consequences

Any material drift creates a new qualification identity and requires requalification.

## Validation

Draft, approval, freeze, missing-pricing, immutability, and fake-only tests are required.

## Revisit triggers

M6.6B candidate discovery is authorized or provider terms drift.
