# ADR-0069: Split M6.7 real-data permissions with no inheritance

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product, privacy, security, and architecture owners

## Context

The M6.5 `REAL_COMPANY_RESEARCH` permission combines discovery and research. M6.7 requires each
real-data capability to be independently authorized and revocable.

## Decision drivers

- Prevent upstream permission from implying downstream authority.
- Preserve explicit unknown and blocked states.
- Keep legacy releases from silently gaining new meaning.

## Considered options

1. A versioned seven-capability successor taxonomy.
2. Interpret the legacy permission as discovery plus research.
3. Use one phase-wide authorization.

## Decision

Use `REAL_BUSINESS_DISCOVERY`, `REAL_PUBLIC_RESEARCH`, `PROFESSIONAL_IDENTITY_RESOLUTION`,
`REAL_CONTACT_STORAGE`, `CONTACT_VERIFICATION`, `SHADOW_ELIGIBILITY_EVALUATION`, and
`SHADOW_READY_ASSESSMENT`. Each is independently `NOT_AUTHORIZED`, `AUTHORIZED`, `SUSPENDED`, or
`EXPIRED`. No capability inherits another. Legacy `REAL_COMPANY_RESEARCH` grants none. M6.7A
initializes every successor permission `NOT_AUTHORIZED`.

## Consequences

Phase 1 cannot create person/contact artifacts or a shadow assessment even if discovery and public
research are later approved.

## Validation

Exact taxonomy, all-disabled baseline, legacy non-equivalence, independent suspension/expiry, and
phase-ceiling tests are required.

## Revisit triggers

A capability is split, combined, or proposed to imply another.
