# ADR-0043: Narrow first-production launch envelope

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

M6.5 needs an exact scope without authorizing delivery.

## Decision drivers

- Prevent country scope from implying nationwide permission.
- Keep the first release human-authorized and inspectable.

## Considered options

1. Texas-only one-to-one plain-text B2B email.
2. Nationwide US email.
3. Multi-channel outreach.

## Decision

The proposed production envelope is US country, Texas recipient/business jurisdiction, Commercial
HVAC inbound lead response/qualification, exactly one recipient and one plain-text message per
authorization. Links, attachments, tracking, sequences, integrations, and default-on delivery are
forbidden. AI is unnecessary. US does not imply nationwide authorization.

## Consequences

Expansion requires a successor envelope and matching policy release.

## Validation

Exact scope, one-message, prohibited-feature, and nationwide-mismatch tests are required.

## Revisit triggers

Any geography, channel, link, attachment, tracking, sequence, or integration expands.
