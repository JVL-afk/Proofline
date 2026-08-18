# ADR-0029: Deterministic outreach templates and disabled wording AI

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

No live model is authorized and outreach correctness must be independent of persuasive prose.

## Decision drivers

- Reproducibility and strict length/claim constraints.
- Credential-free, network-free normal CI.
- No model authority over claims, numbers, CTA, recipients, or approval.

## Considered options

1. Versioned deterministic typed templates with a disabled wording port.
2. Live model-generated drafts.
3. Arbitrary user-supplied templates.

## Decision

`commercial_hvac.lead_response.outreach.v1` is authoritative. It emits plain text, a subject of at
most 60 characters, a first-contact body of at most 130 words, one fact by default and at most two,
one conditional workflow statement, one fixed permission CTA, and the simulation disclosure. A
provider-neutral `OutreachWordingPort` exists only as an unimplemented future boundary and may
never alter semantic inventory or approval.

## Consequences

Copy is plain but identical inputs and versions produce identical hashes.

## Validation

Replay, length, fact-count, schema, prompt-injection, no-provider, and no-network tests apply.

## Revisit triggers

Live wording evaluation or editable production templates are proposed.
