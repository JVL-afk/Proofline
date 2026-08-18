# ADR-0051: Isolated production delivery and webhook boundaries

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Security, operations, and architecture owners

## Context

Future real delivery requires narrower capabilities than the core API.

## Decision drivers

- Isolate provider credentials and egress.
- Authenticate inbound events without broad application authority.

## Considered options

1. Capability-scoped delivery worker and narrow webhook ingress.
2. Provider SDK and secret inside the API.
3. Generic integration worker.

## Decision

Production readiness requires explicit attestations for OIDC, step-up, field encryption, secret
isolation, provider-only egress, webhook authenticity, backups, reply monitoring, and kill switches.
M6.5 represents requirements/evidence only and provisions no infrastructure or executable adapter.

## Consequences

Missing evidence is an explicit blocker, not guessed satisfaction.

## Validation

Control-gap, secret, egress, forgery, replay, outage, and kill-switch tests are required.

## Revisit triggers

Production infrastructure or a provider adapter is proposed.
