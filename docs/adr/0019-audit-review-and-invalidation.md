# ADR-0019: Audit review, immutable revision, and invalidation lifecycle

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

Audit approval must bind exact content and become invalid when material canonical inputs change.

## Decision drivers

- Append-only decisions and revisions.
- Explicit local review governance.
- No safety-gate override.

## Considered options

1. Exact hash-bound review with new revisions for changes.
2. Mutable approved audits.
3. Front-end-only approval flags.

## Decision

Reviewer/admin may approve, reject, or request revision; operator may generate/revise/submit but not
approve. Local self-review is permitted and attributed. Decisions bind the revision and manifest
hashes. Requested changes create a new revision. Material source changes invalidate current approval
eligibility. Production separation of duties remains deferred.

## Consequences

Historical decisions remain inspectable while current validity is explicit.

## Validation

Authorization, self-review attribution, stale concurrency, supersession, and invalidation tests apply.

## Revisit triggers

Production identity/governance or separation-of-duties decisions are accepted.
