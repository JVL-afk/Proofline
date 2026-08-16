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
