# ADR-0011: Provider-neutral intelligence contracts and deployment registry

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-10; ADR-0006, ADR-0010
- **Supersedes:** None

## Context

M2.5 must compare model deployments without embedding provider or model names in application logic
or weakening the deterministic M2 semantic boundary.

## Decision drivers

- Qualify exact deployments for exact tasks rather than declaring a universal model winner.
- Preserve reproducibility across task, schema, policy, corpus, and configuration versions.
- Keep evaluation records outside canonical M2 state.

## Considered options

1. Provider-neutral task contracts plus an immutable deployment and qualification registry.
2. Provider-specific SDK objects in opportunity application services.
3. One global preferred-model setting.

## Decision

Use versioned contracts for evidence interpretation, inference generation, contradiction analysis,
and opportunity reasoning. The registry keys qualification to deployment/version/configuration,
task/version, schema, policy, corpus, and data classification. Application routing requests task
capabilities, never named models. Future audit, vision, and conversation tasks remain taxonomy-only.

A-10 remains unresolved: this ADR approves evaluation structure, not a live provider or model.

## Consequences

### Positive

- Provider substitution and task-specific routing remain possible.
- Drift has an explicit requalification boundary.

### Negative

- Registry and contract versioning add operational records.
- A deployment can qualify for one task and fail another.

## Validation

Contract, lifecycle, exact-key, drift, workspace, and provider-name isolation tests are required.

## Revisit triggers

- A live provider is proposed under A-10.
- A new authoritative task or modality is proposed.
