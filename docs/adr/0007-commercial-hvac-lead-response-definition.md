# ADR-0007: Initial Commercial HVAC inbound lead-response definition

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-01, A-02, and architecture section 13
- **Supersedes:** None

## Context

The initial vertical is Commercial HVAC in Texas, United States. The first opportunity is narrowly
limited to inbound lead response and qualification observable from public digital surfaces.

## Decision drivers

- Deliver one testable vertical without mass discovery or unsupported internal claims.
- Make predicates, contradictions, gaps, and wording deterministic and reviewable.
- Avoid premature multi-plugin generalization.

## Considered options

1. The bounded definition in `docs/milestones/M2.md`.
2. Broad lead management spanning CRM, dispatch, reactivation, and outreach.
3. Model-only opportunity generation.

## Decision

Adopt `commercial_hvac.inbound_lead_response_qualification@1` for Texas. Implement its required,
supporting, contradictory, disqualifying, alternative, information-gap, feasibility, permitted
wording, and prohibited-claim rules as a versioned manifest plus vetted deterministic strategy.
Public evidence may establish an inbound path, never actual internal response performance.

This accepts A-01 and A-02 for the initial M2 slice only.

## Consequences

### Positive

- The first vertical has precise fixtures and safe wording.
- Review data can guide later definition changes.

### Negative

- Public surfaces leave most operational and economic inputs unknown.
- Other opportunity types and geographies remain excluded.

## Validation

Strong, weak, contradicted, insufficient-data, scoped-absence, and hostile-content fixtures produce
distinct deterministic results with complete provenance.

## Revisit triggers

- Another geography, industry, or opportunity family is proposed.
- Reviewed fixtures show systematic classification errors.
