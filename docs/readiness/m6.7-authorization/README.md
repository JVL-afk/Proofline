# M6.7 Phase 1 Final Authorization Package

**Status:** `LEGAL_AND_RETENTION_CONTROLS_RECORDED_AWAITING_IDENTITY_ENVIRONMENT_SOURCE_APPROVALS`
**Prepared:** 2026-08-20
**M6.7C closure:** `8cc38bd19cc45ae3712d6a106b982e3faf75d431`
**Authority granted:** None

This package is the complete known approval surface before the first real-business operation. It
contains recommendations and draft records, not decisions. No real source was accessed while
preparing it. If a new material prerequisite is discovered, it must be added through an immutable
successor blocker record; it cannot remain an implicit or hidden gate.

## Consolidated owner decisions

`consolidated-owner-approval-2026-08-21.json` records every discretionary owner decision in one
immutable artifact. It explicitly separates `OWNER_DECISION`, `EXTERNAL_FACT`,
`SYSTEM_DERIVED_VALUE`, and `POST_DEPLOYMENT_EVIDENCE`. Random pre-deployment actor pseudonyms are
recorded in `role-assignments.predeployment.json`; the private reconciliation salt remains outside
Git, and live discovery still requires reconciliation to the deployed OIDC identity.

The owner is not asked to invent AWS resource names, ARNs, image/plan/configuration/provider hashes,
candidate references, source references, timestamps, seed commitments, or manifest hashes. Those
are generated or observed and included in bounded approval artifacts.

## State separation

```text
READY_FOR_REAL_RESEARCH_AUTHORIZATION
  != REAL_BUSINESS_DISCOVERY_AUTHORIZED
  != REAL_PUBLIC_RESEARCH_AUTHORIZED
  != READY_TO_RUN_SLOT_1
```

- `READY_FOR_REAL_RESEARCH_AUTHORIZATION` means the synthetic technical controls passed.
- `REAL_BUSINESS_DISCOVERY_AUTHORIZED` requires a signed discovery release and permits only the
  approved discovery sources needed to freeze the frame.
- `REAL_PUBLIC_RESEARCH_AUTHORIZED` requires a later, independent signed research release bound to
  the frozen cohort and exact first-party hosts.
- `READY_TO_RUN_SLOT_1` requires a third run authorization naming the exact frozen slot-one business
  ID and permits exactly one staged company run followed by a mandatory pause.

No state, approval, or activity implies the next.

## Final blocker matrix

| Blocker | Current state | Decision/evidence required | Who must approve | Can remain blocked? |
|---|---|---|---|---|
| ADR-0071 | `PROPOSED_IMPLEMENTED_NOT_LIVE_ACCEPTED` | Accept after deployed storage/environment evidence and opaque owner bindings exist | Project, privacy/data and security owners | Yes; blocks both permissions |
| Owner scope | `OWNER_APPROVED` | Recorded in `owner-decisions.md`; no company or source selected | Resolved for scope only | No hidden scope blocker remains |
| A-08 | `APPROVED_POLICY_NOT_LIVE_EFFECTIVE` | Bind to deployed environment and opaque owner identities | Privacy/data and security owner actor bindings | Policy resolved; live gate remains blocked |
| A-09 | `APPROVED_WITH_PER_HOST_REVIEW_EXACT_INSTANCES_NOT_APPROVED` | Approve exact seed artifact and, after cohort freeze, every exact first-party host | Privacy/data owner and accountable per-host reviewer | Yes; blocks matching activity |
| A-17 | `APPROVE_WITH_CONTROLS` | Attorney result recorded; controls implemented; attorney identity/credential record remains to be bound | External attorney record plus project acceptance | Conclusion resolved; identity release gate remains |
| A-03 | `BLOCKED` | Select the exact single-workspace tenancy boundary and accountable operator | Project and security owners | Yes; blocks live environment |
| A-04 | `BLOCKED` | Select cloud, US region, storage, encryption/key ownership, backups and recovery evidence | Security/environment and project owners | Yes; blocks live environment |
| A-07 | `BLOCKED` | Select OIDC/MFA, workload identity, operator roles, access review and audit behavior | Security/environment and privacy/data owners | Yes; blocks live environment |
| A-18 | `OWNER_HARD_CAP_APPROVED` | USD 250 ceiling and USD 0 AI are fixed; selected-environment price evidence and reservation configuration remain operational preflight inputs | Security/environment owner | Paid work still fails closed until exact prices/configuration exist |
| Named operational roles | `BLOCKED` | Supply stable opaque subject identifiers for all eight roles and attest reviewer separation | Project, privacy/data and security owners | Yes; blocks releases |
| 24-company cohort scope | `OWNER_APPROVED` | Privacy/data and incident acknowledgements plus exact frame/seed/source artifact remain required | Privacy/data and incident owners | Scope is resolved; discovery release remains blocked |
| Discovery authorization | `NOT_AUTHORIZED` | Immutable release after all discovery prerequisites above are satisfied | Project, privacy/data, legal, security and kill-switch owners | Yes; must occur first |
| Research authorization | `NOT_AUTHORIZED` | Immutable successor after discovery finishes and exact cohort/source hosts are frozen | Same accountable owners through a separate approval event | Yes; cannot be combined with discovery |

These are the complete known material blockers. Technical preflight is not an additional blocker; it
passed at M6.7C. Owner scope, workload ceilings and the USD 250/AI USD 0 budget are resolved. Slot-one
execution is a separate post-research-authorization run gate rather than a real-data permission.

## Non-negotiable inherited controls

- Jurisdiction `US-TX`; vertical `COMMERCIAL_HVAC`; B2B inbound lead-response analysis only.
- Exactly 24 frozen cohort slots; no opportunity/yield-based replacement.
- HTTP first; browser disabled.
- No person/contact extraction, index, search, M6 projection, metric, or ordinary-log value.
- No social/review/people/email-finder/authenticated source, bypass, form, booking, chat or mailbox.
- No AI route or cost; AI is USD 0.
- No sender, delivery credential, external communication, or M6 state transition.
- Workload ceilings: 120 logical page fetches, 360 total attempts, 36 MB aggregate responses.

## Package contents

- `retention-recommendation.md`: proposed A-08 values requiring owner/legal approval.
- `source-approval-package.md`: minimum A-09 sources and exact source-record requirements.
- `legal-review-package.md`: exact A-17 questions and primary authority register.
- `environment-budget-roles.md`: A-03/A-04/A-07/A-18 recommendation and unassigned roles.
- `phase1-and-authorizations.md`: cohort approval plus three independent draft authorization records.
- `owner-decisions.md`: explicit scope, workload, budget, retention preference and dependency graph.
- `counsel-review-form.md`: concise 14-question A-17 response artifact; no legal conclusions.
- `owner-decisions-successor-2026-08-21.md`: frozen 100-frame, QA and staged-batch decisions.
- `owner-control-package.json`: machine-readable exact owner decisions and disabled permissions.
- `phase1-owner-seed-manifest-v1.schema.json`: business-only seed-manifest contract.
- `seed-and-selection-policy.md`: eligibility, deduplication, seed, ordering and replacement rules.
- `discovery-readiness.md`: unsigned discovery-release scope and current exact blockers.
- `a17-attorney-result-2026-08-21.json`: attorney-provided fact-bound result; not a Codex legal opinion.
- `texas-statutory-provenance-2026-08-21.json`: official Texas proposition-level verification.
- `phase1-retention-policy-v1.json`: approved, non-live-effective minimized-capture schedule.
- `phase1-counsel-controls.md`: implemented minimization, destruction, incident, source, and
  mandatory re-review boundaries.
- `role-assignments.template.json`: immutable opaque-subject assignment shape; every subject remains
  unassigned.
- `a17-qualified-review.template.json`: preserved original qualified-reviewer intake; the completed
  attorney-provided result is a separate immutable successor.
- `discovery-signature.template.json`: exact unsigned discovery-only release shape; it cannot grant
  research or slot authority.
- `../../../infra/terraform/phase1/`: reviewable ADR-0075 Terraform package and locked provider;
  locally validated without an AWS backend, plan, apply, or cloud observation.
