# Module and Dependency Boundaries

## Repository boundaries

```text
apps/       user-facing applications
services/   public/private APIs and isolated runtimes
workers/    workflow, intelligence, HTTP research, and browser workers
packages/   shared contracts/configuration; no deployable process
infra/      local and cloud infrastructure definitions
```

Each child deployable/package must contain a README declaring ownership, responsibilities, forbidden responsibilities, public interfaces, data access, and dependencies before source code is added.

## Layer rule inside a bounded context

```text
domain <- application <- ports <- adapters
```

- `domain` contains entities, value objects, policies, and state machines; it imports no framework/provider adapter.
- `application` contains commands, queries, use cases, authorization, and transaction boundaries; it depends on domain and declared ports.
- `ports` declare repository, clock, identity, provider, artifact, and event interfaces.
- `adapters` implement ports using frameworks, databases, SDKs, or external services.

Dependencies point inward. Adapters are composed at process entry points.

## Cross-module rules

- A module may consume another module only through its declared application API, contract, or domain event.
- No module imports another module’s persistence model or adapter.
- Shared packages may contain stable contracts/configuration primitives, not miscellaneous business logic.
- There is one owner for every canonical concept; avoid duplicate `Business`, `User`, `Evidence`, or `Approval` models.
- Cross-language contracts use versioned JSON Schema/OpenAPI once M1 begins.
- Database access does not make the database an integration API.
- Temporal orchestrates durable work; domain state remains in application persistence.
- External-provider payloads are normalized at adapter boundaries.

## Security boundaries

- Hostile-content fetch/browser processes receive no application/user/provider credentials beyond minimal job-specific capability.
- The content interpreter has no tools or arbitrary network access.
- The demo origin/runtime has no core application cookies or real side-effect integrations.
- The outreach context consumes exact M1-M4 contracts read-only and has no person, recipient,
  copy/export, delivery, channel, provider, or external-side-effect port.
- The M6 contact context consumes exact CONTENT_APPROVED M5 contracts read-only. Its only delivery
  adapter is a zero-network, single-message mock. It emits re-analysis requests but cannot mutate
  M1-M5 canonical records. A future live provider must run in an isolated capability-scoped worker.
- The M6.5 activation context consumes no M1-M6 persistence or delivery interface. It owns only
  immutable governance/readiness records and non-send shadow assessments. `SHADOW_READY` cannot
  create M6 `SEND_READY`, authorize, or reach a delivery worker.
- The M6.6A qualification context owns only synthetic task projections, evaluation artifacts,
  qualification evidence, review artifacts, budgets, and reports. Its runner accepts deterministic
  fixture providers only and has no M6/M6.7 state, real-data, credential, route, or delivery port.
- The M6.7 shadow-validation context consumes M1-M5 only through declared canonical contracts and
  owns synthetic cohort/control-plane records. It has no M6 command, person/contact, AI, sender,
  delivery, provider, or network port. Phase 1 terminates at `CONTACT_PHASE_NOT_AUTHORIZED`.
- Approval state can only be changed through the authorized application service.
- No model output is executed as code or trusted configuration.

## Enforcement plan

M0 establishes these rules. When Python/TypeScript source packages are introduced, CI must add import/dependency graph checks appropriate to the actual package layout. Until then, code review and the per-package README contract are authoritative.
