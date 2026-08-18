# ADR-0037: Typed M5 delivery and compliance slots

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Required delivery values must not become a back door for rewriting approved M5 prose.

## Decision drivers

- Preserve exact content authority.
- Support sender/disclosure values deterministically.

## Considered options

1. Registered typed slots.
2. Append a generated footer.
3. Let M6 rewrite the draft.

## Decision

M5 template v2 contains registered sender-signature, postal-disclosure, and opt-out slots. M6 fills
them only from a verified synthetic sender and approved fixture policy values. The existing role
salutation resolves from the exact person-role binding. M6 cannot append, rewrite, or patch M5 prose;
absent required slots fail readiness and require an M5 successor.

## Consequences

Final message bytes differ only through typed slot resolution and are re-hashed in the send manifest.

## Validation

Missing slot, unresolved slot, exact body hash, and hostile slot-value tests are required.

## Revisit triggers

A new delivery slot, rich content, localization, or free-form compliance copy is proposed.
