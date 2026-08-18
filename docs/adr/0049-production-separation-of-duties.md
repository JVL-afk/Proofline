# ADR-0049: Production separation of duties and step-up authorization

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product and security owners

## Context

Local attributed self-review is insufficient for real communication.

## Decision drivers

- Prevent self-approval and stale authority.
- Keep hard safety gates non-overridable.

## Considered options

1. Separate content reviewer, contact steward, and send authorizer with step-up.
2. One operator role.
3. UI acknowledgment only.

## Decision

The initial production policy requires separate content review, contact stewardship, and one-send
authorization; prohibits self-authorization; requires step-up, reason, expiry, exact preview, and
one-message acknowledgment; and permits no hard-gate override. Exact IdP/role values remain A-07/
A-15 prerequisites.

## Consequences

M6.5 represents the policy but provisions no identity system.

## Validation

Missing step-up, role collision, expiry, hash drift, and override tests are required.

## Revisit triggers

Production roles or approval duties change.
