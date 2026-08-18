# ADR-0030: Internal/external artifact separation and hard outreach QC

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Internal uncertainty, risks, and economics must not become prospect-facing certainty.

## Decision drivers

- Make audience classification structural.
- Retain contradictions, alternatives, gaps, and economics internally.
- Prevent aggregate quality from masking deception or semantic failure.

## Considered options

1. Typed audience-separated artifacts with non-overridable hard gates.
2. One draft document with hidden sections.
3. Aggregate quality scoring plus reviewer override.

## Decision

Every artifact and segment has an explicit audience and semantic kind. External business segments
must bind approved projections. Economics, hidden reasoning, reviewer notes, and complete risk
context are internal-only. Claim-level and whole-package hard failures cannot be averaged away or
overridden.

## Consequences

The diagnostic UI can compare internal reasoning with external wording without leaking it.

## Validation

Audience leakage, contradictions, prohibited wording, personal data, active content, links, and
unbound segment tests are required.

## Revisit triggers

An artifact audience, export format, or override mechanism is proposed.
