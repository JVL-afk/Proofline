# ADR-0006: M2 semantic lineage and hypothesis review boundary

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** Architecture sections 6, 7, 11, 13, 14, and 17; A-15
- **Supersedes:** None

## Context

M2 must not collapse sourced material, normalized observations, reasoning, assumptions, and
opportunities into one ambiguous claim type.

## Decision drivers

- Prevent public evidence from becoming unsupported internal-process claims.
- Preserve complete revision, contradiction, and calculation lineage.
- Place mandatory review at the consequential hypothesis boundary.

## Considered options

1. Separate each semantic stage and require review only for hypothesis acceptance.
2. Use one polymorphic claim table with optional provenance.
3. Require human approval for every inference revision.

## Decision

Use `Evidence -> Observation -> Inference -> Opportunity Hypothesis -> Assumption -> Economic Run ->
Score Snapshot -> Human Review`. Research owns canonical evidence. Opportunity Intelligence owns
M2's normalized evidence-linked observations, inferences, and hypotheses; ROI/scoring owns
assumptions and calculations; Review owns decisions. Inferences remain inspectable, revisioned, and rejectable without separate mandatory
approval. Every accepted hypothesis requires a human decision bound to the exact complete manifest.

## Consequences

### Positive

- Semantics, uncertainty, and invalidation are explicit.
- Review focuses on the user-visible opportunity decision.

### Negative

- More entities and relations than a generic claim table.
- Material changes require consistent review invalidation.

## Validation

Contract, state-machine, authorization, rejection, revision-invalidation, and end-to-end lineage
tests prove the boundary.

## Revisit triggers

- Production review governance changes.
- A future artifact requires stricter intermediate approval.
