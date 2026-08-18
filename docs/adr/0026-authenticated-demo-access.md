# ADR-0026: Authenticated-only demo access and no public sharing

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

Demo drafts are Confidential and public links increase leakage and impersonation risk.

## Decision drivers

- Keep M4 internal and attributable.
- Avoid publication, export, outreach, and anonymous access.
- Support explicit revocation.

## Considered options

1. Authenticated issuance with short-lived runtime sessions only.
2. Expiring public links.
3. Unrestricted public demos.

## Decision

Initial M4 exposes no publish, export, download, public-share, or anonymous-access capability.
Only an authenticated authorized user can request a one-time runtime capability for an approved,
current, non-revoked revision. Recording output is a cue sheet only.

## Consequences

External distribution remains unavailable until a separate product, legal, security, and retention decision.

## Validation

Unauthenticated-access, public-route-absence, no-indexing, issuance, and revocation tests apply.

## Revisit triggers

Any public link, export, recording distribution, or external recipient workflow is proposed.
