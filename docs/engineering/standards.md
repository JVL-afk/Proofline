# Engineering Standards

## General

- Optimize for correctness, evidence integrity, and reversibility before throughput.
- Use typed public interfaces and explicit error categories.
- Keep deterministic policy/calculation code separate from model-generated interpretation.
- Use UTC timestamps and explicit ISO currencies/units.
- Treat external inputs, including provider/model output, as untrusted.
- Do not log secrets, source bodies, prompts/responses, personal contact data, or tokens by default.

## Python

- Python 3.13 baseline.
- Type annotations are required for application code; strict type checking is the goal.
- Ruff is the formatting/lint baseline when the first Python package is introduced.
- Pytest is the test runner when the first Python package is introduced.
- Async I/O is used only for genuinely asynchronous integrations; CPU-bound or blocking work must not occupy API event loops.
- Framework/provider types remain in adapters and transport layers.

## TypeScript

- Node.js 24 LTS baseline with strict TypeScript.
- No implicit `any`; boundary data is schema-validated.
- UI code does not access persistence or provider credentials.
- Generated API types are not manually edited.
- Frontend data fetching must preserve authorization and artifact/config version identifiers.

## Testing

- Unit tests cover policies, state machines, calculations, canonicalization, and authorization.
- Contract tests cover APIs, provider adapters, and cross-language schemas.
- Integration tests use real service engines in isolated environments where behavior matters.
- Workflow changes require replay/determinism tests.
- Research/demo changes require adversarial security fixtures.
- AI prompt/model/config changes require versioned evaluations, not snapshot approval alone.
- Every bug fix includes a failing test when practical.

## Changes and compatibility

- Public contracts and database changes are backward-compatible during rollout.
- Use expand/migrate/contract database evolution.
- Accepted prompts, configs, evidence, audits, demos, scores, and approvals are immutable revisions.
- New dependencies require a purpose, owner, license/security review, and locked version.
- Security controls and human approval gates cannot be disabled by ordinary feature flags.

## Documentation

- Significant and hard-to-reverse decisions require ADRs.
- Every deployable/package README declares its boundary and operation.
- Runbooks accompany production dependencies and alerts.
- Unknown requirements remain documented decisions; they are not filled with assumptions.
