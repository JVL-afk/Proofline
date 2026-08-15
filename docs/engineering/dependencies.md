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

## Current M0 state

npm is the accepted Node workspace manager. ADR-0003 selects uv for the Python workspace and universal lockfile. Runtime and development dependency resolutions are committed in `uv.lock`; CI installs with `uv sync --locked --all-packages`. Changing the Python resolver/locker requires a superseding ADR.

The M0 direct dependencies are limited to FastAPI/Uvicorn/Pydantic, SQLAlchemy, and the test/lint/type toolchain. The static diagnostic UI has no package dependencies.
