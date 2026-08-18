# ADR-0022: Deterministic demo state machine and mock actions

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

The demo must illustrate a proposed future workflow without calling or claiming to call real systems.

## Decision drivers

- Exact replay from the same specification, persona, seed, and events.
- Mandatory human handoff before commitments or safety-sensitive handling.
- Structural prevention of external effects.

## Considered options

1. A finite deterministic state machine with structurally mock-only actions.
2. A model-controlled conversational workflow.
3. Real integrations in a test account.

## Decision

M4 uses a finite, versioned state machine with registered events and pure guards. Scheduling, CRM,
dispatch, callback, and notification behavior is represented only by `MOCK_ONLY` definitions and
receipts. There is no authoritative or live action adapter. Safety, booking, quote, availability,
and dispatch paths require a fixed human-handoff state.

## Consequences

The simulation is less open-ended but cannot silently cross into operational behavior.

## Validation

Replay, reachability, bounded-transition, handoff, idempotency, mock-failure, and no-network tests apply.

## Revisit triggers

Any live tool, conversational model, real availability, or operational integration is proposed.
