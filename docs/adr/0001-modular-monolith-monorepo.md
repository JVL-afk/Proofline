# ADR-0001: Modular monolith in a polyglot monorepo

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owners:** Architecture owner
- **Related architecture decisions:** Architecture sections 3, 4.1, and 6
- **Supersedes:** None

## Context

The platform needs a TypeScript dashboard and Python-heavy API/research/AI workloads. It also needs strong isolation for hostile public-web content and demos, but has no evidence that independent product microservices are justified.

## Decision drivers

- Preserve a simple transactional model during the greenfield/MVP phase.
- Allow atomic API/schema changes across Python and TypeScript.
- Create enforceable domain boundaries before code volume grows.
- Isolate hostile-content and demo workloads for security and scaling.
- Avoid Kubernetes and microservice release choreography without measured need.

## Considered options

1. Polyglot monorepo with modular-monolith domain packages and multiple process types.
2. TypeScript-only monorepo.
3. Python-only repository with a separate frontend repository.
4. Independent microservices and repositories from day one.

## Decision

Use one monorepo containing TypeScript and Python workspaces. Product domain logic begins as a modular monolith with explicit ports/adapters and module dependency rules. Web, API, workflow/intelligence workers, research/browser workers, and demo runtimes are separate deployable process boundaries. They do not become independent product microservices until measured isolation, scaling, ownership, or release-cadence needs justify extraction.

## Consequences

### Positive

- One review and CI context for cross-language contracts.
- Fewer distributed transactions and compatibility problems.
- Security boundaries can still be deployed independently.
- Later extraction begins from declared ports rather than arbitrary imports.

### Negative

- Tooling must support two languages.
- Module boundaries require automated enforcement and review discipline.
- A shared release repository can increase CI scope if not partitioned.

### Risks and mitigations

- Accidental coupling: enforce ownership and dependency rules; add import checks when source packages exist.
- Oversized CI: use path-aware jobs and shared caches after packages are introduced.
- Premature service extraction: require a superseding ADR with measured evidence.

## Validation

Review dependency direction in CI and architecture review. Track whether any process needs materially independent availability, scaling, security, ownership, or release behavior.

## Revisit triggers

- A bounded context needs independent data ownership or deployment cadence.
- Workload scaling materially penalizes unrelated modules.
- Security review requires a stronger isolation boundary.
- Team ownership makes coordinated releases a sustained bottleneck.
