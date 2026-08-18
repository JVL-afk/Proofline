# ADR-0062: Tournament execution security and safe result retention

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Security, privacy, and architecture owners

## Context

Future tournament execution will handle credentials and untrusted model output, while M6.6A must
remain credential-free and network-free.

## Decision drivers

- Isolate credentials and egress.
- Retain useful provenance without sensitive payloads.
- Keep normal CI provider-free.

## Considered options

1. Separate execution boundary with safe metadata only.
2. Application-worker provider calls.
3. Persist raw prompts and responses indefinitely.

## Decision

M6.6A implements deterministic fake transports only. A future M6.6B boundary must isolate secrets,
allowlist provider egress, disable tools/search/actions, validate structured output, treat it as
untrusted, minimize approved data, and retain safe hashes, findings, usage, latency, and cost rather
than raw credentials or bodies.

## Consequences

Normal CI requires no credential and performs no external network access.

## Validation

Fake transport, redaction, schema, unsupported-field, injection, zero-network, and safe-report tests
are required.

## Revisit triggers

M6.6B execution, raw-payload retention, or a new provider boundary is proposed.
