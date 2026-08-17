# ADR-0020: Audit eligibility and M3 publication boundary

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

M3 audits are opportunity-linked and must not manufacture conclusions when M2 supports none.

## Decision drivers

- Preserve M2 opportunity authority.
- Distinguish diagnostic drafts from approvable audits.
- Prevent M4/external behavior from entering M3.

## Considered options

1. Accepted/full and ready-for-review/diagnostic eligibility only.
2. Generate generic audits from all research runs.
3. Let M3 create missing opportunities.

## Decision

An accepted hypothesis with a valid review may produce a full approvable audit. A
`READY_FOR_REVIEW` hypothesis may produce an internal diagnostic audit that cannot be approved. All
other states reject generation, including `NO_OPPORTUNITY_SUPPORTED`. M3 contains no research-summary
artifact, PDF, publishing, share link, outreach, proposal, demo, or external side effect.

## Consequences

Insufficient economics may be shown only for an otherwise eligible hypothesis.

## Validation

Eligibility-state, no-opportunity refusal, diagnostic approval rejection, and boundary tests apply.

## Revisit triggers

A generic research summary, publication/export, or M4 artifact is proposed.
