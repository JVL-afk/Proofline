# ADR-0027: Immutable outreach packages and exact upstream manifests

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

M5 may prepare communication only from exact approved M1-M4 authority.

## Decision drivers

- Prevent M5 from creating business truth.
- Make every draft reproducible and invalidatable.
- Preserve workspace, entity, review, and version lineage.

## Considered options

1. Immutable revisions with exact M1-M4 manifests.
2. Mutable drafts referencing current upstream data.
3. Free-form outreach records with optional citations.

## Decision

Each package revision is immutable and content-hashed. Generation requires the exact current
accepted M2 opportunity, approved full M3 audit, and approved non-revoked M4 demo for one workspace
and business. The manifest binds all review, evidence, assumption, economic, score, configuration,
and artifact versions. M5 consumes read-only ports and never mutates M1-M4.

## Consequences

Upstream material change invalidates content approval; correction creates a successor revision.

## Validation

Eligibility, entity match, exact hash, replay, invalidation, authorization, and mutation-isolation
tests are required.

## Revisit triggers

Non-opportunity outreach, mutable approved content, or a different authority chain is proposed.
