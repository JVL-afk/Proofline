# Human-Approval Decision Register

This register transcribes A-01 through A-20 from section 25 of the accepted architecture. Architecture acceptance approves the design process and recommendations; it does **not** silently decide these product, compliance, vendor, or operating choices.

## Status vocabulary

- `Open`: needs an accountable owner and decision.
- `In review`: owner assigned; evidence/options under review.
- `Accepted`: decision captured in a linked ADR.
- `Deferred`: explicitly time-bounded with a documented constraint/exception.
- `Superseded`: replaced by another decision.

## Register

| ID | Decision | Architecture recommendation | Status | Owner | Required artifact |
|---|---|---|---|---|---|
| A-01 | Initial industry and geography | Commercial HVAC in Texas/US | Accepted | Product/architecture owners | ADR-0007 |
| A-02 | Initial opportunity plugins | Lead response plus qualification/booking, narrowly scoped | Accepted | Product/architecture owners | ADR-0007 |
| A-03 | Tenancy | Workspace/tenant boundary from day one | Open | Unassigned | ADR and threat model |
| A-04 | Cloud and regions | AWS reference deployment; exact regions after residency review | Open | Unassigned | ADR and data-flow review |
| A-05 | Durable workflow engine | Temporal from the first vertical slice | Open | Unassigned | ADR/spike evidence |
| A-06 | Temporal hosting | Managed Temporal for production | Open | Unassigned | ADR/vendor review |
| A-07 | Identity provider and governance | Standards-based OIDC; explicit role/self-approval rules | Open | Unassigned | ADR and authorization matrix |
| A-08 | Evidence retention/privacy | Encrypted versioned artifacts; defer full WORM pending legal decision | Open | Unassigned | ADR and retention schedule |
| A-09 | Allowed data sources | Approve each provider/source class, terms, geography, retention, and cost | Open | Unassigned | Source-policy register |
| A-10 | Model/search providers | Approve vendors, regions, data terms, budgets, and fallbacks | Deferred | Product/architecture owners | ADR-0015 records the closed synthetic Tournament Run 1; production selection remains unresolved and no route is approved |
| A-11 | Demo generation boundary | Vetted declarative components only in MVP | Accepted | Product/architecture owners | ADR-0021 through ADR-0025 |
| A-12 | Demo sharing | Authenticated-only initially | Accepted | Product/architecture owners | ADR-0026; public access remains unapproved |
| A-13 | ROI semantics | Approve formulas, sources, scenarios, currency, and value meaning | Accepted | Product/architecture owners | ADR-0008 initial M2 formula only |
| A-14 | Score calibration | Approve rubrics, weights, thresholds, and heuristic labels | Deferred | Product/architecture owners | Uncalibrated M2 bands only under ADR-0009 |
| A-15 | Human approval policy | Define permissions, warning overrides, duties, and reapproval triggers | Accepted | Product/architecture owners | ADR-0049 accepts strict initial separation, step-up, no self-authorization, and no hard-gate override; A-07 identity values remain open |
| A-16 | Outreach in MVP | Manual copy/export of drafts only | Accepted | Product/architecture owners | ADR-0043 accepts only the Texas one-to-one no-link/no-attachment envelope; delivery remains disabled pending all other gates |
| A-17 | Legal/privacy/compliance review | Name accountable jurisdictional owners before live research | Open | Unassigned | ADR-0035 requires a signed scoped live-activation release; no real rule is encoded |
| A-18 | SLO/DR/cost limits | Approve SLOs, RTO/RPO, budgets, alerts, and ownership | Open | Unassigned | Operations ADR/runbook baseline |
| A-19 | Acceptance criteria | Set quantitative thresholds after a labeled baseline exists | Deferred | Product/architecture owners | No numeric M2 thresholds under ADR-0009 |
| A-20 | Audit/demo exports | Web first; separately approve download/share formats and retention | Open | Unassigned | ADR-0043 excludes links/attachments/exports from the initial live envelope; broader distribution remains unresolved |

## Blocking rule

Per architecture section 25, production implementation must not begin until A-03 through A-11,
A-13, and A-15 through A-18 have accountable owners and initial decisions. Accepted ADR-0004,
ADR-0005, and ADR-0010 authorize only their bounded local milestone adapters; they do not waive
these production gates or silently accept the open decisions.

## Updating this register

1. Assign a named role/person as owner.
2. Change status to `In review`.
3. Create an ADR or the required review artifact using the repository template.
4. Obtain the accountable approval.
5. Link the artifact in the final column and set `Accepted`.
6. Never replace an open decision by implementing a convenient default.
