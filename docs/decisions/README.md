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
| A-01 | Initial industry and geography | Commercial HVAC in Texas/US | Open | Unassigned | ADR |
| A-02 | Initial opportunity plugins | Lead response plus qualification/booking, narrowly scoped | Open | Unassigned | ADR |
| A-03 | Tenancy | Workspace/tenant boundary from day one | Open | Unassigned | ADR and threat model |
| A-04 | Cloud and regions | AWS reference deployment; exact regions after residency review | Open | Unassigned | ADR and data-flow review |
| A-05 | Durable workflow engine | Temporal from the first vertical slice | Open | Unassigned | ADR/spike evidence |
| A-06 | Temporal hosting | Managed Temporal for production | Open | Unassigned | ADR/vendor review |
| A-07 | Identity provider and governance | Standards-based OIDC; explicit role/self-approval rules | Open | Unassigned | ADR and authorization matrix |
| A-08 | Evidence retention/privacy | Encrypted versioned artifacts; defer full WORM pending legal decision | Open | Unassigned | ADR and retention schedule |
| A-09 | Allowed data sources | Approve each provider/source class, terms, geography, retention, and cost | Open | Unassigned | Source-policy register |
| A-10 | Model/search providers | Approve vendors, regions, data terms, budgets, and fallbacks | Open | Unassigned | ADR/vendor/data review |
| A-11 | Demo generation boundary | Vetted declarative components only in MVP | Open | Unassigned | ADR and demo threat model |
| A-12 | Demo sharing | Authenticated-only initially | Open | Unassigned | ADR/access policy |
| A-13 | ROI semantics | Approve formulas, sources, scenarios, currency, and value meaning | Open | Unassigned | Product/finance ADR |
| A-14 | Score calibration | Approve rubrics, weights, thresholds, and heuristic labels | Open | Unassigned | Product/data ADR |
| A-15 | Human approval policy | Define permissions, warning overrides, duties, and reapproval triggers | Open | Unassigned | Governance ADR/state matrix |
| A-16 | Outreach in MVP | Manual copy/export of drafts only | Open | Unassigned | Product/legal ADR |
| A-17 | Legal/privacy/compliance review | Name accountable jurisdictional owners before live research | Open | Unassigned | Signed review record |
| A-18 | SLO/DR/cost limits | Approve SLOs, RTO/RPO, budgets, alerts, and ownership | Open | Unassigned | Operations ADR/runbook baseline |
| A-19 | Acceptance criteria | Set quantitative thresholds after a labeled baseline exists | Open | Unassigned | Evaluation plan/ADR |
| A-20 | Audit/demo exports | Web first; separately approve download/share formats and retention | Open | Unassigned | Product/security ADR |

## Blocking rule

Per architecture section 25, implementation beyond disposable technical spikes must not begin until A-03 through A-11, A-13, and A-15 through A-18 have accountable owners and initial decisions. M1 entry additionally requires that no unresolved foundation decision can force a redesign.

## Updating this register

1. Assign a named role/person as owner.
2. Change status to `In review`.
3. Create an ADR or the required review artifact using the repository template.
4. Obtain the accountable approval.
5. Link the artifact in the final column and set `Accepted`.
6. Never replace an open decision by implementing a convenient default.
