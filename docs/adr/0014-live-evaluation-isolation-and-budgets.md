# ADR-0014: Live evaluation isolation, budgets, provenance, and data controls

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-08, A-10, A-17, A-18
- **Supersedes:** None

## Context

Live evaluation will eventually require provider credentials and external calls, but no provider is
approved and deterministic CI must remain credential-free and network-free.

## Decision drivers

- Make live execution explicit, attributable, budgeted, and fail-closed.
- Prevent secrets or uncontrolled data from entering prompts or logs.
- Preserve exact invocation cost and provenance.

## Considered options

1. A disabled live boundary with allowlists, data gates, reservations, kill switches, and ledgers.
2. Provider calls from ordinary tests or application workers.
3. Informal developer scripts using personal credentials.

## Decision

Implement interfaces and disabled configuration only. A future live run requires explicit enablement,
deployment/task allowlists, an approved data-policy reference, budget reservation, and an open kill
switch. Invocation records store versions, hashes, usage, latency, retries, fallbacks, pricing
metadata, and validation outcomes without logging page bodies, prompts, or secrets. Normal CI uses
mock providers and performs no provider network access.

A-10 and the production data, legal, operational, and provider decisions remain unresolved.

## Consequences

### Positive

- Future evaluation has an auditable safety and cost boundary.
- Current development needs no credentials or network.

### Negative

- Real latency and cost cannot be measured until a provider is separately approved.
- Additional policy decisions precede any live execution.

## Validation

Disabled, allowlist, kill-switch, budget, safe-ledger, secret, and zero-network CI tests are required.

## Revisit triggers

- A named provider/model is proposed for evaluation.
- Approved data classification, residency, retention, or budget policy changes.
