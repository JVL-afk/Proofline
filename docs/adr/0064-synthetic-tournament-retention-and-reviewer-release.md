# ADR-0064: Synthetic Tournament II retention and reviewer release gates

- **Status:** Accepted
- **Date:** 2026-08-19
- **Decision owners:** Product and architecture owner

## Context

Tournament II uses synthetic inputs only. The initial freeze required named reviewers before any
execution, while the automated stages can safely finish and seal blinded packages before reviewer
release.

## Decision drivers

- Keep synthetic evaluation separate from real-world M6.7 data.
- Avoid blocking machine safety evaluation on reviewer scheduling.
- Ensure reviewers cannot see outputs or identities before assignments are frozen.
- Preserve provider logging transparency without requiring production-grade zero retention.

## Considered options

1. Accept standard provider retention for synthetic M6.6 only and move reviewer identity to release.
2. Require zero-data-retention and named reviewers before any automated stage.
3. Allow anonymous or unblinded review after execution.

## Decision

Standard documented OpenAI, Anthropic, and Google API security/abuse logging is acceptable only for
M6.6 synthetic Tournament II. Inputs contain no real business, person, contact, customer, production,
secret, first-party reply, or M6.7 data. This approval does not extend to M6.7, production routing,
real communications, or real-world data.

Requests continue to prohibit provider files, explicit caching, grounding, search, tools, functions,
code/computer use, saved conversation state, and opt-in training/data sharing. OpenAI and Google use
`store=false`; OpenAI also disables background mode. Material provider-policy drift suspends the
manifest.

Automated stages reserve three distinct primary-reviewer slots and one conditional-adjudicator slot.
Named identities are not required to run automated stages. Stage 5B may generate and seal blinded,
randomized packages, but no package may be released and no score may be created until all names are
frozen. The project owner may fill one primary slot but may not be the sole adjudicator.

## Consequences

Reviewer scheduling is a package-release gate, not an automated-execution gate. Console-only
evidence that an explicitly prohibited provider data-sharing opt-in is disabled can still block
automated readiness.

## Validation

Tests verify reserved slots, sealed package state, prohibited release, synthetic-only data policy,
and exact account-setting blockers.

## Revisit triggers

M6.7 data, real-world data, a live route, changed provider data policy, or a new review protocol is
proposed.
