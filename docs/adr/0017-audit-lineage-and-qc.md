# ADR-0017: Audit lineage and non-overridable semantic QC

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

Audit wording can misclassify facts, invent precision, omit contradictions, or cross entity boundaries.

## Decision drivers

- Every factual statement must resolve to evidence.
- Unknowns, assumptions, formulas, and contradictions must remain visible.
- Humans may correct but not override semantic failures.

## Considered options

1. Deterministic claim and whole-audit hard gates.
2. Reviewer judgment without machine gates.
3. Aggregate quality scoring that can offset safety failures.

## Decision

Apply the hard gates approved in M3, including exact fact evidence, inference/estimate/recommendation
lineage, unknown preservation, entity match, freshness policy, unsupported precision, contradiction
and material-alternative presentation, manifest containment, prohibited claims, and safe markup.
Warnings remain explicit; hard failures are never averaged away or overridden.

## Consequences

Unsafe drafts fail closed. Corrected content requires a new immutable revision.

## Validation

Every hard-gate family has a deterministic hostile fixture.

## Revisit triggers

Claim semantics, freshness policy, or supported economic formula families change.
