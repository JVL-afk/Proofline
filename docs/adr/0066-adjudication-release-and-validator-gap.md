# ADR-0066: Frozen adjudication release and post-run validator-gap treatment

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product and architecture owner

## Context

All three Tournament II primary reviews are locked. One anonymous outreach case has a mechanically
confirmed wording/CTA semantic inconsistency that the frozen evaluator did not encode. The primary
policy already requires adjudication for material defect reports, disagreement, and high variance,
but it does not authorize creating a retrospective hard gate.

## Decision drivers

- Apply only the human-review protocol frozen before the primary reviews.
- Preserve a confirmed semantic inconsistency without turning it into a retrospective gate.
- Keep the adjudicator blind to primary answers and candidate identity.
- Block final disposition until both human adjudication and the policy gap are resolved.

## Considered options

1. Release the frozen-trigger subset and retain a separate policy blocker.
2. Convert the newly found inconsistency into a retrospective automatic hard gate.
3. Ignore the inconsistency and allow adjudicator preference to erase it.

## Decision

Compute one deduplicated adjudication set using only the frozen primary triggers. Release only that
set through the already frozen `CONDITIONAL_ADJUDICATOR_SLOT` mapping to `ADJUDICATOR_D`; do not
regenerate A/B order or expose primary observations, candidate identity, or machine telemetry.

Case `51ee87af09907a072639e7b6` receives both
`MECHANICALLY_CONFIRMED_SEMANTIC_CONFLICT` and `POLICY_ADJUDICATION_REQUIRED`. It remains eligible
for blinded adjudication, but human stylistic preference cannot erase the confirmed inconsistency.
Because the frozen evaluator lacks the exact rendered-wording/CTA cross-field rule, the case also
blocks final disposition until a separately authorized policy decision resolves the validator gap.
This is not a retrospective hard-gate amendment.

A completed adjudicator workbook locks as `LOCKED_ADJUDICATION_REVIEW`. No final qualification,
material-gain disposition, identity reveal, route, or M6.7 capability is created here.

## Consequences

Potentially material reviewer reports remain preserved even when mechanical inspection does not
confirm them. The adjudicator sees only anonymous A/B text, minimum context, and the standard
rubric. Final disposition remains blocked both on the locked adjudication response and the explicit
policy gap for the confirmed case.

## Validation

Tests cover exact frozen trigger behavior, deduplication, confirmed-conflict preservation,
identity-free release, immutable case/order/text validation, UTC completion, and fail-closed lock
creation.

## Revisit triggers

The adjudication review is locked or the post-run validator-gap disposition is separately approved.
