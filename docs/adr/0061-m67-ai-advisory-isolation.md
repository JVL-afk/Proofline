# ADR-0061: M6.7 AI advisory isolation

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, privacy, security, and architecture owners

## Context

Synthetic qualification cannot authorize real M6.7 data or affect `SHADOW_READY`.

## Decision drivers

- Preserve ADR-0053.
- Keep real-data permission independent.
- Prevent AI from entering contact or send authority.

## Considered options

1. Separate advisory artifacts ignored by readiness.
2. AI-assisted readiness scoring.
3. AI output as an eligibility input.

## Decision

M6.6 artifacts are separate and absent from M6.7 readiness inputs. They cannot create permissions,
`SHADOW_READY`, M6 send states, contact authority, or delivery. Any future real-data use needs a
separate exact permission binding.

## Consequences

M6.7 readiness is identical with or without an AI advisory artifact.

## Validation

Non-interference, dependency-boundary, permission, readiness, and no-delivery tests are required.

## Revisit triggers

Any AI use with real data or readiness inputs is proposed.
