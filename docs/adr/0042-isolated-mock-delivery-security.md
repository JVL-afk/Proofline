# ADR-0042: Isolated mock delivery security and synthetic-data boundary

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

Delivery introduces personal data, secrets, hostile replies, and external side effects.

## Decision drivers

- Prove controls without collecting real data or secrets.
- Keep message construction and provider capabilities narrow.

## Considered options

1. Synthetic-only data, strict QC, redaction, and isolated future port.
2. Shared API credentials and generic MIME.
3. Immediate provider integration.

## Decision

M6 accepts only reserved synthetic identities and fixture sources. Plain text, one recipient, no
CC/BCC, no URLs, arbitrary headers, HTML/MIME, scripts, attachments, fake thread prefixes, pixels,
or open/click tracking are enforced. Contact/reply views redact raw values. A confidential-value
protection port and provider-worker isolation boundary exist, but no live secret or provider
infrastructure is configured. Normal CI performs zero external calls.

## Consequences

Local SQLite may contain only repository-owned synthetic fixture data; real data requires A-08,
A-17, encryption, retention, access, and deployment approval.

## Validation

Header/MIME/pixel/URL, redaction, authorization, secrets, and zero-network tests are required.

## Revisit triggers

Real personal data, provider secrets, webhook ingress, encryption service, or live worker is proposed.
