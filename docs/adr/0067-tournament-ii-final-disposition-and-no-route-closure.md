# ADR-0067: Tournament II final disposition and no-route closure

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Product and architecture owner

## Context

The original Tournament II machine run, its separate human-review recovery, three primary reviews,
and one adjudication review are immutable. The three reasoning comparisons contain 63 genuinely
byte-identical candidate/baseline pairs. Audit wording contains one further identical pair. Two
wording tasks also contain resolved material defects, including the rendered-wording/structured-CTA
gap governed by ADR-0066. The frozen evaluator cannot be amended retrospectively.

## Decision drivers

- Score only task-specific results under the frozen human-review policy.
- Give no AI credit for byte-identical output.
- Preserve resolved material defects without converting them into retrospective machine gates.
- Reveal identity only after every scoring input is locked.
- Keep all Tournament II results outside application routes and canonical authority.

## Considered options

1. Close identical tasks as safe but without material gain and defect-bearing wording tasks as
   conditional/no-route.
2. Qualify wording tasks based on majority preference despite unresolved material defects.
3. Retroactively add a hard evaluator gate and rewrite the machine-stage result.
4. Treat identical output as either a model win or a model failure.

## Decision

Unblind against the exact sealed assignment file only after all four human records are locked. The
unblinding event records the mapping hash, locked-input hash, timestamp, and event hash; no score may
change after reveal.

The Sonnet evidence-interpretation, contradiction-analysis, and opportunity-reasoning bindings are
`SAFE_BUT_NO_MATERIAL_GAIN / NO_ROUTE`: their outputs are byte-identical to the deterministic
baseline. Audit wording is `CONDITIONAL / NO_ROUTE` because adjudication confirmed one material
defect. Outreach wording is `CONDITIONAL / NO_ROUTE` because it contains one adjudicated material
defect plus the mechanically confirmed `RENDERED_CTA_SEMANTIC_CONSISTENCY_GAP`. All seven original
machine disqualifications remain unchanged.

No binding is `QUALIFIED_WITH_MATERIAL_GAIN`, no universal model ranking exists, and no Tournament
II result is an M6.7 shadow candidate. The two wording tasks are
`BLOCKED_PENDING_VALIDATOR_FIX`; the reasoning tasks and machine-disqualified tasks are
`NO_AI_SHADOW_CANDIDATE`. M6.7 remains unstarted.

## Consequences

Deterministic M1-M6 authority remains unchanged. Tournament II closes with zero route activation
and zero canonical mutation. A future evaluator revision must validate rendered wording against the
authoritative structured CTA before wording AI can be reconsidered, but historical Tournament II
results remain under their frozen evaluator.

## Validation

The closure validator recomputes task distributions from exact local immutable locks, assignment
mappings, rendered artifacts, and provider cost ledgers; compares them with the tracked final
report; preserves 194 original and 105 recovery calls; and rejects routes, canonical mutation, or
M6.7 activation.

## Revisit triggers

A separately approved future tournament uses a versioned evaluator containing the missing
rendered-wording/structured-CTA invariant, or M6.7 design is explicitly authorized.
