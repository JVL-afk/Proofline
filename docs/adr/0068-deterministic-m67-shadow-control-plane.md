# ADR-0068: Deterministic M6.7 shadow-validation control plane

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product and architecture owner

## Context

M6.7 must exercise the real-world M1-M5 workflow without giving shadow artifacts recipient,
authorization, or delivery authority. M6.6 qualified no AI binding for M6.7.

## Decision drivers

- Keep M1-M6 canonical ownership unchanged.
- Make external communication structurally unavailable.
- Prove the control plane using synthetic fixtures before any real-data permission exists.

## Considered options

1. A separate deterministic shadow-validation bounded context.
2. Extend M6 contact/delivery state with a shadow feature flag.
3. Reuse M6.5 readiness as a workflow engine.

## Decision

Create separate `shadow-core` and `shadow-local` packages. They own cohort, run, lineage, outcome,
review, metric, cost, incident, stop, and evidence-package records only. M1-M5 are consumed through
declared canonical contracts. M6.7 has no delivery port, sender credential, provider SDK, AI route,
or M6 command dependency. Phase 1 ends at `CONTACT_PHASE_NOT_AUTHORIZED`.

`SHADOW_READY` remains a later immutable assessment with literal false send capabilities under
ADR-0053. The initial M6.7A runtime is synthetic, credential-free, and network-free.

## Consequences

Removing M6.7 changes no M1-M6 or M6.5 state. Live discovery/research and all contact phases remain
separately blocked.

## Validation

Dependency, permission, state-ceiling, zero-network, no-contact, no-delivery, non-interference, and
workspace-authorization tests are required.

## Revisit triggers

Any real source, person/contact phase, AI artifact, delivery dependency, or post-shadow transition
is proposed.
