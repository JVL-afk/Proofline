# ADR-0005: Bounded local research adapters for M1

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owners:** Product owner and architecture owner
- **Related architecture decisions:** A-05, A-08, A-09, A-17; architecture sections 10, 11, and 18
- **Supersedes:** None

## Context

The product owner explicitly advanced the repository to M1 and requested safe research of a known
business from a permitted public URL. Production source approval, retention, legal review, cloud,
workflow hosting, and network containment decisions remain open. M1 must validate the domain and
security seams without silently resolving those decisions.

## Decision drivers

- Prove complete `Business -> Research Run -> Page -> Snapshot -> Material -> Evidence` lineage.
- Enforce SSRF and crawl limits outside hostile content.
- Keep raw content quarantined from application secrets and interpretive business logic.
- Keep CI deterministic and live calls explicit.
- Avoid infrastructure whose governing decisions remain open.

## Considered options

1. Local SQLite snapshots, a pinned-IP standard-library HTTP adapter, explicit per-run host permit,
   and separate research/browser process boundaries.
2. Adopt production PostgreSQL, Temporal, object storage, Redis, and cloud egress controls now.
3. Implement unrestricted crawling in the API process.
4. Continue fixture-only M0 behavior and omit the requested M1 vertical slice.

## Decision

For M1 local development only:

- require an operator to name one business and one normalized `http`/`https` start URL;
- permit only that normalized host and HTTP ports 80/443, validating every DNS result and redirect;
- pin each HTTP connection to a validated public IP and apply response, decompression, redirect,
  timeout, page, depth, byte, duration, retry, cache, duplicate, and per-domain limits;
- persist immutable, content-hashed snapshot bytes and observational extraction in SQLite because
  the local payload ceiling is deliberately small;
- execute research in a separate credential-free worker; retain local bearer authentication only
  in the API;
- define a separate fail-closed Playwright subprocess using non-persistent contexts and a minimal
  stdin/stdout job. Browser navigation is exact-host only and Chromium is pinned to a
  policy-validated public address. The repository does not claim that a local OS process supplies
  production browser containment; live enablement requires approved network/container controls;
- keep live public research disabled by default and require `OPINTEL_RESEARCH_LIVE_ENABLED=true`
  plus the explicit per-run host permit. Deterministic tests use synthetic transports.

This ADR does not accept or close A-05, A-08, A-09, or A-17.

## Consequences

### Positive

- M1 contracts, provenance, safety policies, and hostile-input tests can mature independently of
  vendor and cloud choices.
- The HTTP connection cannot silently re-resolve to a private address after policy validation.
- Content remains data: no model, tool execution, or business-value inference exists in M1.

### Negative

- SQLite BLOB snapshots and the local durable queue are not production storage/orchestration.
- Browser fallback is fail-closed until an isolated Playwright runtime is separately provisioned.
- Explicit host permission is a technical allowlist, not legal or terms-of-service approval.

### Risks and mitigations

- Local adapter used in production: settings reject non-development environments.
- Sensitive public contact data retained indefinitely: local state is ignored and disposable;
  production retention remains blocked.
- SSRF bypass: normalize once, validate all resolved IPs and redirects, pin connections, disallow
  credentials/nonstandard ports, and test hostile cases.
- Prompt injection: extraction labels content untrusted and supplies no instruction/tool channel.

## Validation

Unit, integration, and adversarial tests cover normalization, DNS/IP/redirect policy, limits,
retry/cache/deduplication, extraction, provenance, authorization, traceability, and browser job
sanitization. A live smoke test is optional and separately authorized per URL.

## Revisit triggers

- Any non-local deployment or production data collection.
- A-05, A-08, A-09, or A-17 is accepted.
- Browser fallback is enabled against the public web.
- Snapshot volume exceeds the deliberately bounded local payload ceiling.
