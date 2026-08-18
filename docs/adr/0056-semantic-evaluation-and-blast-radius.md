# ADR-0056: Deterministic semantic evaluation, hard gates, and failure blast radius

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Security, product, and architecture owners

## Context

Fluent output can conceal semantic changes. A task-local failure also must not automatically suspend
unrelated task bindings.

## Decision drivers

- Make claim and qualifier preservation machine-checkable.
- Keep critical failures non-aggregatable.
- Scope suspension to demonstrated blast radius.

## Considered options

1. Atom-level semantic graphs and evidence-based blast radius.
2. Aggregate quality scoring.
3. Provider-wide disqualification for every failure.

## Decision

Wording outputs must preserve claim inventory, semantic labels, unknowns, contradictions, material
qualifiers, CTA, economics, entities, and authority. Critical violations hard-fail. Classify findings
as `TASK_LOCAL_FAILURE`, `CONFIGURATION_WIDE_FAILURE`, or `PROVIDER_SECURITY_FAILURE`. The normal
qualification unit is exact provider, deployment, configuration, task, contract, corpus, and
evaluator policy. Broader suspension requires cross-task or provider-boundary evidence.

## Consequences

Safety remains strict without turning one task defect into unsupported provider-wide judgment.

## Validation

Every hard gate, semantic equality rule, and blast-radius escalation condition requires a test.

## Revisit triggers

New semantic labels, authority types, or evidence for broader failure propagation appear.
