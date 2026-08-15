# ADR-0003: Python workspace and dependency locking

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owners:** Architecture owner
- **Related architecture decisions:** ADR-0001, ADR-0002
- **Supersedes:** None

## Context

M0 introduces multiple Python packages for shared domain/application contracts, local adapters, the API, and the worker. ADR-0002 deliberately deferred selection of a Python resolver until dependencies existed. Clean installations now require one cross-platform lock and workspace-aware editable installs.

## Decision drivers

- One authoritative lock across all Python packages.
- Reproducible Windows and Linux developer/CI environments.
- First-class local workspace dependencies without publishing packages.
- Frozen/locked CI operation.
- Python 3.13 support.

## Considered options

1. uv workspace with a committed universal `uv.lock`.
2. Hand-maintained pinned requirements files.
3. Poetry workspace/path dependencies.
4. Independent virtual environments and lockfiles per package.

## Decision

Use uv 0.11.x as the Python workspace, environment, and lockfile tool. Commit one root `uv.lock`. Each executable/shared package owns a `pyproject.toml`, while the root owns development tooling and workspace membership. CI and documented developer commands use `uv sync --locked --all-packages` and `uv run --locked`.

## Consequences

### Positive

- Exact transitive versions are captured in a cross-platform lock.
- Workspace packages remain independently declared while sharing one environment.
- Clean setup and CI commands are short and consistent.

### Negative

- uv becomes an additional bootstrap tool.
- `uv.lock` is uv-specific rather than a standard installer format.
- Workspace tooling does not itself enforce import boundaries.

### Risks and mitigations

- Tool drift: constrain `required-version` to the accepted minor line and upgrade through an ADR review or explicit dependency change.
- Undeclared cross-package imports: mypy, tests, package metadata, and later import-boundary checks remain required.
- Vendor/tool lock-in: package metadata stays standard `pyproject.toml`; export is available if migration is needed.

## Validation

A clean environment must resolve from the committed lock without changing it, install all packages, and pass lint, type, and test commands on Windows and Linux CI.

## Revisit triggers

- uv stops supporting a required platform/runtime.
- A standardized lock format satisfies the workspace and editable-package requirements.
- Workspace scale or deployment packaging reveals a material limitation.
