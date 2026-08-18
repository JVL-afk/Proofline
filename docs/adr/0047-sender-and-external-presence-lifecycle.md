# ADR-0047: Sender and external-presence lifecycle

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, security, and sender-domain owners

## Context

Domain ownership, website credibility, sender authentication, and delivery readiness differ.

## Decision drivers

- Prevent one external milestone from implying another.
- Keep absent real assets visible as blockers.

## Considered options

1. Four independent attestations.
2. One sender-ready status.
3. Provider verification as the sole authority.

## Decision

`DOMAIN_ACQUIRED`, `WEBSITE_READY`, `SENDER_DOMAIN_VERIFIED`, and `EMAIL_DELIVERY_READY` are
independent, versioned, expiring attestations. M6.5 creates none for real assets.

## Consequences

Each state requires its own evidence and can fail or revoke independently.

## Validation

Missing, failed, expired, independent-state, and revocation tests are required.

## Revisit triggers

Real domains, websites, mailboxes, or sender configurations are proposed.
