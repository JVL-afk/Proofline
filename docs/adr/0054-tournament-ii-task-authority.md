# ADR-0054: Tournament II task authority and inclusion policy

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product and architecture owners

## Context

The completed deterministic M1-M6 system offers production-adjacent reasoning and wording surfaces,
but model capability does not grant product authority.

## Decision drivers

- Preserve deterministic truth and human control.
- Evaluate only tasks with plausible material product value.
- Prevent a universal model selection.

## Considered options

1. Task-specific advisory and wording contracts.
2. General business-analysis agents.
3. Keep all AI tasks permanently taxonomy-only.

## Decision

Use the seven-task core and eight-task extension inventory approved for M6.6A. All tasks are
advisory-only or wording-only and authoritative-ineligible. Subject-line generation is excluded.
M6.6B initially executes only the core set; extension admission requires a frozen revision.

## Consequences

Qualification remains exact per task. Infrastructure exists for extensions without authorizing
their live evaluation.

## Validation

Typed inventory tests prove all approved tasks are present, subject-line generation is absent, and
no task has authoritative or routing capability.

## Revisit triggers

A task gains authority, the core set changes, or subject-line generation is reconsidered.
