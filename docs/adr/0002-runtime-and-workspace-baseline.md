# ADR-0002: Runtime and workspace baseline

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owners:** Architecture owner
- **Related architecture decisions:** Architecture section 4
- **Supersedes:** None

## Context

The repository needs supported runtime baselines and a root workspace before application packages or dependency lockfiles exist. Exact framework and provider dependencies are intentionally deferred to their implementation milestones.

## Decision drivers

- Use maintained production runtime lines.
- Avoid a package-manager dependency before the repository has packages.
- Keep setup cross-platform and compatible with hosted CI.
- Permit implementation packages to pin exact dependencies through committed lockfiles.

## Considered options

1. Node.js 24 LTS with npm workspaces; Python 3.13 with standard `pyproject.toml` metadata.
2. Node.js 22 LTS and Python 3.12.
3. Node.js Current and Python 3.14.
4. pnpm plus uv from the first repository commit.

## Decision

Use Node.js 24 LTS, npm 11 workspaces, and Python 3.13 for M0. The root Node workspace has no runtime dependencies. The Python project has no runtime dependencies until an executable Python package is introduced. Each language must commit its authoritative lockfile when dependencies are added; CI must use frozen/clean installation modes.

## Consequences

### Positive

- Both runtimes are maintained and suitable for production baselines.
- npm ships with Node and avoids an additional bootstrap dependency.
- Python 3.13 has a longer ecosystem adoption window than adopting the newest branch immediately.

### Negative

- Local environments on older runtimes must upgrade.
- npm workspaces offer fewer monorepo features than pnpm.
- Python dependency tooling still needs a decision before dependencies are added.

### Risks and mitigations

- Dependency incompatibility: verify framework/provider support before accepting their lockfiles.
- Runtime drift: CI and version files enforce the selected major versions.
- Tool fragmentation: require a superseding ADR before adopting pnpm, uv, Poetry, or another workspace manager.

## Validation

CI runs on Node.js 24 and Python 3.13. Dependency introduction must demonstrate clean installation from committed lockfiles.

## Revisit triggers

- A required dependency does not support the selected runtime.
- Runtime support status changes.
- Workspace scale demonstrates a measured npm limitation.
- The Python dependency graph requires a dedicated lock/resolution tool.
