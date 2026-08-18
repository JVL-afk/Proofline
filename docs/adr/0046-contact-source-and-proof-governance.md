# ADR-0046: Contact-source governance and production proof profile

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Data-governance, privacy, and product owners

## Context

Source permission and verification proof establish different facts.

## Decision drivers

- Preserve source provenance and permitted use.
- Prevent inference or technical checks from proving person association.

## Considered options

1. Versioned source rules plus atomic proof scopes.
2. Provider confidence score.
3. One verified boolean.

## Decision

The initial inactive proposal includes business-controlled published professional contacts and
explicit first-party confirmation/referral. Third-party enrichment is prohibited and inferred
patterns are never sufficient proof. Production verification proposes current syntax, domain,
mailbox, professional-context, source-use, and person-association or first-party-confirmation proof.
A-09/A-17 approval remains required.

## Consequences

The proposal can prove contracts without becoming live authorization.

## Validation

Unapproved source, inferred-only, insufficient-proof, freshness, and provenance tests are required.

## Revisit triggers

A source, verifier, proof method, or sufficient profile changes.
