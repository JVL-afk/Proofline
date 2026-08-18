# ADR-0052: Operational ownership, rollout, and emergency suspension

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Operations, security, and product owners

## Context

One real message still requires observable operation and an accountable stop mechanism.

## Decision drivers

- Ensure every safety function has an owner.
- Suspend on complaint, monitoring, provider, duplicate, or audit uncertainty.

## Considered options

1. Versioned ownership/runbook attestation.
2. Informal first-send checklist.
3. Provider dashboard as operations control.

## Decision

Readiness requires named operational roles, a first-contact runbook, reply monitoring, kill-switch
evidence, provider-outage and ambiguous-status procedures, and no active complaint-threshold
suspension. Exact SLOs, thresholds, RTO/RPO, and people remain A-18 decisions.

## Consequences

An operational gap blocks first-real-contact readiness.

## Validation

Missing owner/runbook, complaint suspension, reply-monitoring, outage, ambiguity, and kill tests are required.

## Revisit triggers

Pilot size, operating hours, SLOs, thresholds, or ownership changes.
