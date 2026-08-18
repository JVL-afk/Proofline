# ADR-0024: Separate demo runtime, capability sessions, CSP, and minimal telemetry

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

Interactive demo content has a different trust profile from the authenticated application.

## Decision drivers

- Prevent access to application cookies, credentials, persistence, and external systems.
- Bind access to an exact approved revision for a short period.
- Minimize interaction data.

## Considered options

1. Separate origin/process with one-time capabilities and a narrow runtime gateway.
2. Render demos directly in the core application origin.
3. Public static hosting.

## Decision

M4 has a separate runtime process/origin. It receives no core cookies, database or provider
credentials, research/browser credentials, or general-purpose API credential. Authenticated core
users may receive a one-time 15-minute issuance capability; an exchanged runtime session lasts at
most 60 minutes. CSP denies external content, forms, frames, workers, and arbitrary connections.
Only approved metadata-only telemetry events are accepted.

## Consequences

A narrow capability exchange is required, but compromise of the runtime does not confer core or
external-system authority.

## Validation

Origin, cookie, CSP, token hashing, expiry, replay, telemetry allowlist, and credential tests apply.

## Revisit triggers

Production hosting, public access, third-party assets, or broader telemetry is proposed.
