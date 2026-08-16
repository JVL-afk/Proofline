# ADR-0010: Rule-based M2 reasoning and local adapters

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-03, A-05, A-07, A-10; architecture sections 12 and 13
- **Supersedes:** None

## Context

M2 must prove durable reasoning and review contracts without selecting production AI, identity,
persistence, workflow, or infrastructure providers.

## Decision drivers

- Keep opportunity outputs reproducible and bounded.
- Prevent hostile M1 content from controlling tools or reasoning.
- Continue the validated local adapter approach without implying production decisions.

## Considered options

1. Deterministic rules, mock reasoning, SQLite workflow/persistence, and local development auth.
2. Enable a live model and production platform immediately.
3. Embed provider-specific reasoning in domain code.

## Decision

Live AI remains disabled. Versioned predicates, contradiction rules, wording policies, and
missing-data gates are authoritative. Mock reasoning adapters prove contracts and workflow only.
For M2 local development, authorize SQLite, the local durable queue, and development authentication
as temporary adapters. Reviewer and admin may accept, reject, or request information; operator may
create, recalculate, and submit but not accept. Local self-review is permitted and attributed. Hard
semantic/security gates cannot be overridden. Material revisions invalidate acceptance.

This does not accept production PostgreSQL, Temporal, OIDC, infrastructure, stricter separation of
duties, or A-10 provider decisions. A-08, A-09, and A-17 remain production gates.

## Consequences

### Positive

- M2 remains deterministic, provider-independent, and locally reproducible.
- Prompt-injection content has no instruction/tool channel.

### Negative

- Ambiguous cases remain unresolved or require humans.
- Local adapters are unsuitable for production.

## Validation

Role, self-review attribution, hard-gate, invalidation, mock-boundary, ID allowlist,
prompt-injection, replay, retry, no-network, and non-production settings tests are required.

## Revisit triggers

- Any production deployment or live AI reasoning is proposed.
- A-03, A-05, A-07, A-08, A-09, A-10, A-15, or A-17 receives a production decision.
