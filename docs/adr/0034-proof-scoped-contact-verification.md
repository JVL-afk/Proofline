# ADR-0034: Proof-scoped contact verification

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Observed, inferred, and verified contact semantics prove different things.

## Decision drivers

- Prevent domain or syntax checks from implying person association.
- Preserve acquisition provenance.

## Considered options

1. Independent origin, lifecycle, proof scopes, and limitations.
2. One boolean verified field.
3. Provider confidence score.

## Decision

Acquisition origin (OBSERVED, INFERRED, FIRST_PARTY_PROVIDED) remains independent from verification.
Verification records explicit proof scopes and limitations. Initial fixture eligibility requires
current person/contact-association proof; syntax, domain capability, mailbox acceptance, and
directory observation cannot silently establish more.

## Consequences

An inferred origin remains visible after verification and generic verified status is insufficient.

## Validation

Observed-only, inferred-then-verified, stale, and insufficient-proof fixtures are required.

## Revisit triggers

A live verification method or different sufficient proof scope is proposed.
