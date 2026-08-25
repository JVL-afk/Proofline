# Dependency Policy

## Principles

- Prefer standard-library or existing capabilities before adding dependencies.
- Every dependency must serve a current approved milestone requirement.
- Direct dependencies require an identified owning package/team role.
- Commit authoritative lockfiles and use frozen/clean installation in CI.
- Pin CI actions by reviewed major version initially and by immutable commit SHA before production hardening.
- Generate an SBOM and scan dependencies/container images before production release.

## Introduction checklist

- [ ] Need cannot be met safely and simply by an existing dependency.
- [ ] Package is maintained and supports the accepted runtime.
- [ ] License is compatible with intended use.
- [ ] Security history and transitive dependency footprint were reviewed.
- [ ] Data/network behavior is understood.
- [ ] Exact resolution is recorded in a lockfile.
- [ ] Upgrade/removal owner is assigned.
- [ ] Tests cover the boundary that depends on it.

## Current M1 state

npm is the accepted Node workspace manager. ADR-0003 selects uv for the Python workspace and universal lockfile. Runtime and development dependency resolutions are committed in `uv.lock`; CI installs with `uv sync --locked --all-packages`. Changing the Python resolver/locker requires a superseding ADR.

The M0 direct dependencies are limited to FastAPI/Uvicorn/Pydantic, SQLAlchemy, and the test/lint/type toolchain. The static diagnostic UI has no package dependencies.

M1 intentionally uses Python standard-library URL, DNS, TLS, HTTP, decompression, and HTML parsing
behind research ports. This avoids introducing an HTTP client whose DNS behavior cannot guarantee
validated-address pinning. SQLAlchemy/Pydantic are reused for local persistence and typed contracts.
Playwright 1.62.x is owned only by the separate browser worker and supplies non-persistent Chromium
contexts. It is fail-closed by default; installing a browser binary and enabling live fallback are
separate local actions. Production use remains blocked until network/container isolation is approved.
The package is maintained by Microsoft, declares Apache-2.0, supports the Python baseline, and its
network/process behavior is confined to the browser-worker boundary. Adversarial tests cover the
credential-free job contract; removal is owned by the research/browser boundary owner.

M2 adds no third-party runtime dependency. `opportunity-core`, `opportunity-local`, and the
intelligence worker reuse Pydantic, SQLAlchemy, and the locked workspace tools. Deterministic rules,
Decimal economics, hashing, and mock reasoning use the Python standard library. Live AI SDKs and
providers are prohibited by ADR-0010.

M2.5 adds no third-party dependency. `qualification-core` uses the standard library and shared M0
principal/clock contracts. `qualification-local` reuses the already locked SQLAlchemy dependency.
No provider SDK, network client, credential library, or telemetry exporter is authorized.

M2.6 adds no third-party dependency. `qualification-live` uses a narrow standard-library HTTPS
transport behind provider-native adapter boundaries. This keeps provider request/response types and
credentials out of application contracts, avoids SDK drift in deterministic CI, and permits complete
fake-transport coverage. The explicit tournament runner is the sole live-network entry point.

M3 adds no third-party dependency. `audit-core` uses standard-library hashing, JSON, regular
expressions, and existing typed contracts. `audit-local` reuses locked SQLAlchemy. No renderer,
provider SDK, PDF, publishing, or network dependency is introduced.

M4 adds no third-party dependency. `demo-core` uses standard-library hashing, declarative typed
contracts, and the existing M0-M3 contracts. `demo-local` reuses locked SQLAlchemy. The separate
runtime reuses FastAPI/Uvicorn and its local core gateway uses only the standard library. It contains
no provider SDK, real action adapter, browser automation, arbitrary renderer, or external telemetry.

M5 adds no third-party dependency. `outreach-core` uses standard-library hashing, regular
expressions, typed projections, deterministic templates, and existing M1-M4 contracts.
`outreach-local` reuses locked SQLAlchemy. There is no provider SDK, recipient/contact library,
mailer, CRM/calendar client, renderer, exporter, or network dependency.

M6 adds no third-party dependency. `contact-core` reuses Pydantic and standard-library hashing,
time-zone logic, typed contracts, and policy checks. `contact-local` reuses locked SQLAlchemy. No
provider SDK, DNS/mail verifier, contact/enrichment library, webhook server, encryption service,
mailer, CRM, tracking, or network dependency is introduced.

M6.5 adds no third-party dependency. `activation-core` reuses Pydantic and shared identity/clock
contracts for immutable governance projections. `activation-local` reuses locked SQLAlchemy. It has
no cloud, OIDC, KMS, secret, provider, domain, mail, webhook, contact-source, verification, AI, or
network dependency.

M6.6A adds no third-party dependency. Tournament II contracts, corpus, evaluators, fake providers,
review artifacts, budgets, lifecycle, and reports use the Python standard library inside
`qualification-core`. No live adapter, provider SDK, credential loader, network client, or route
dependency is introduced.

M6.6B-2 adds no third-party dependency. Its draft manifest validation, conservative serialized-shape
token ceilings, dated price calculations, and certification plan use the Python standard library in
`qualification-core`. It adds no provider SDK, transport, credential reader, hidden-corpus reader,
or executable live boundary.

M6.6B-3 adds no third-party dependency. Its separately invoked one-shot certification process uses
the existing `qualification-live` standard-library HTTPS transport, now constrained by exact
provider host allowlists and redirect checks. Deterministic CI uses fake transports and never reads
credentials or opens external connections.

M6.6B-3R adds no third-party dependency. The Gemini-only successor validator, one-shot repair
authorization, redacted error diagnostics, and fake transport tests reuse the same standard-library
boundary. Only the separately invoked repair script can open the exact Google HTTPS endpoint.

M6.6B-4/M6.6B-4A add no third-party dependency. Immutable freeze/readiness manifests, account
finding classification, pacing, budget and reviewer-stage controls use the standard library. Four
explicitly invoked read-only model-metadata checks reuse the existing exact-host HTTPS transport;
normal CI uses fake transports and opens no network connection. The credential-value audit uses
standard-library subprocess and Git plumbing without placing secret values in arguments or output.

M6.6B-4B adds no third-party dependency and no live transport. Human-attested provider-control
evidence, official-policy conclusions, and the immutable final readiness successor use the standard
library. Deterministic tests perform no provider or external-network call.

M6.7A adds no third-party dependency. `shadow-core` reuses Pydantic and the existing M0-M5 typed
contracts; `shadow-local` reuses locked SQLAlchemy. It has no discovery/research transport, browser,
person/contact provider, AI SDK, model registry, sender, delivery, CRM, calendar, messaging, form,
booking, or network dependency.

M6.7C adds no direct dependency. Its gate layer reuses the existing M1 URL policy and locked
SQLAlchemy/Pydantic workspace dependencies. The fake resolver and transport use no network library.

M6.7 Phase 1 production-runtime remediation adds `psycopg` 3.2.x, owned by `research-local`, as
SQLAlchemy's PostgreSQL 18 driver. Critical lifecycle parity is exercised against an ephemeral local
PostgreSQL server; SQLite remains the local/test adapter and is rejected in Phase 1 configuration.
The research worker adds `boto3` 1.x solely for an authenticated, fail-closed read of the exact SSM
kill-switch parameter through a private VPC endpoint. It does not provide business-web transport,
discovery, AI, browser, or delivery capability. Both resolutions are frozen in `uv.lock`, included
in the worker SBOM, and covered by deterministic adapter tests plus the successor image scan.

The Phase 1 research-worker composition root also directly depends on the existing workspace-only
`opintel-shadow-core` package. It reuses the counsel-required deterministic minimizer through a
narrow `CaptureMinimizer` port; `research-core` remains independent of the M6.7 bounded context.
This adds no third-party package, transport, credential, AI, browser, or delivery capability. The
boundary is covered by hostile raw-input, quarantine, durable-sink, and adapter parity tests.

The M6.7 Slot 01 runtime successor declares the already locked `boto3` 1.x dependency directly in
the deterministic intelligence worker because that process must read only the exact SSM kill-switch
parameter through the existing private endpoint. This does not add a new resolved package or any
business-web, AI, browser, contact, sender, or delivery client. The worker fails closed on every SSM
error and has an IAM policy containing only `ssm:GetParameter` for that one parameter.
