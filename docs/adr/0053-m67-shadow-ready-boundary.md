# ADR-0053: Mandatory M6.7 SHADOW_READY boundary

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, privacy, security, and architecture owners

## Context

Real-world zero-send validation must not misuse M6 `SEND_READY`.

## Decision drivers

- Keep real-data permissions independently scoped.
- Make zero-send status structurally unusable by delivery.

## Considered options

1. Mandatory distinct `SHADOW_READY` projection.
2. M6 `SEND_READY` with a feature flag.
3. Documentation-only no-send convention.

## Decision

M6.7 uses a distinct immutable `SHADOW_READY` assessment with exact lineage. It cannot create M6
`SEND_READY`, transition to `SEND_AUTHORIZED`, or be consumed by a delivery worker. Real company
research, identity resolution, contact storage, verification, eligibility, and shadow readiness each
require separate permission; no stage implies the next.

## Consequences

Even fully evidenced shadow candidates remain impossible to send.

## Validation

Phase-permission, Texas scope, lineage, non-authorization, and no-delivery tests are required.

## Revisit triggers

M6.7 scope changes or any shadow-to-live transition is proposed.
