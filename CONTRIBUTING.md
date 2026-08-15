# Contributing

## Scope gate

The active milestone is M0 only. Changes may establish repository governance, decision records, module boundaries, CI, dependency policy, environment/data policy, identity/authorization foundations, secret injection, audit logging foundations, local platform definitions, or IaC foundations.

The M0 walking skeleton is limited to local authentication, a fixture campaign command, a durable local operation, one controlled fixture fetch, one stored evidence item, and API/UI traceability.

The following are out of scope until M1 or later:

- product/domain entities or APIs beyond the exact M0 walking-skeleton contracts;
- production discovery, crawling, public-web evidence extraction, opportunities, ROI, scoring, audits, demos, or outreach;
- provider-specific AI/search integrations;
- production database schemas beyond an explicitly approved M0 identity/audit foundation;
- autonomous external side effects.

## Change requirements

1. Link the change to an M0 exit criterion or approved ADR.
2. Keep module dependencies consistent with `docs/engineering/module-boundaries.md`.
3. Add or update automated checks for repository behavior.
4. Do not commit secrets, generated credentials, local data, or provider responses.
5. Update the decision register when an approval is obtained; never infer approval from implementation convenience.
6. Run all validation commands documented in the root README before review.

## Commit and review guidance

- Keep changes small and independently reviewable.
- Explain security and data-handling consequences.
- Include migration and rollback considerations for infrastructure/configuration changes.
- Treat workflow, evidence, authorization, and approval semantics as architecture-level changes requiring an ADR.
