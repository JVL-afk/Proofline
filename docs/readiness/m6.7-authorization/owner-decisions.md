# M6.7 Phase 1 Project-Owner Decisions

**Decision record:** `M67_PHASE1_OWNER_DECISIONS_2026-08-20_01`
**Recorded:** 2026-08-20
**Provenance:** Explicit project-owner instruction in the M6.7 authorization task
**Live authority granted:** None

## Approved scope

| Decision | Owner-approved value |
|---|---|
| Cohort target | 24 |
| Jurisdiction | `US-TX` |
| Vertical | `COMMERCIAL_HVAC` |
| Business context | `B2B` |
| Opportunity | `INBOUND_LEAD_RESPONSE` using the existing narrow lead-response/qualification definition |
| Cohort construction | Freeze the complete eligible cohort and reserve order before research outcomes |
| Initial execution | Slot 1 only, concurrency 1 |
| After slot 1 | Mandatory pause; no automatic slot 2 |
| Small batch | Frozen contiguous next slots only after a separate continuation approval |
| After small batch | Mandatory pause |
| Remainder | Only after another separate continuation approval |
| Replacement | Outcome-based replacement prohibited; only pre-frozen cohort-ineligibility rules apply |
| Browser fallback | `DISABLED` |
| Person/contact processing | `NOT_AUTHORIZED` |
| AI routes/cost | Unavailable; USD 0 |
| Delivery | Unavailable |

This is scope approval, not company selection, source approval, permission authorization or run
authorization. It cannot choose a company before discovery is separately authorized.

## Approved workload and monetary ceilings

| Control | Owner-approved hard ceiling |
|---|---:|
| Logical fetches | 120 |
| Total attempts including initial attempts | 360 |
| Aggregate response bytes | 36,000,000 bytes (36 MB decimal) |
| Phase 1 monetary spend | USD 250 |
| AI spend | USD 0 |

USD 250 is the maximum authorization ceiling, not expected spend, a forecast or permission to buy
an unapproved service. Reservations and reconciliation continue to fail closed. The approved
sub-budget recommendation is discovery USD 10, research USD 40, storage/logs/backups USD 50, shared
environment/security USD 150 and AI USD 0. Missing/stale provider pricing or an unknown billable
unit blocks the paid operation even when total headroom remains. Human time remains separate unless
the owner later approves a labor-rate assumption.

## Provisional retention decision

The schedule in `retention-recommendation.md` is:

```text
OWNER_PROVISIONALLY_APPROVED_PENDING_LEGAL_REVIEW
```

It records project architecture preferences, not statutory claims. A-08 is not accepted until the
qualified A-17 reviewer confirms or changes the values and the privacy/data and security owners sign
the resulting exact policy.

## Source-category preference

The owner prefers only:

1. A provenance-backed offline seed manifest for discovery.
2. Exact unauthenticated first-party public business websites for bounded discovery validation and
   research.

Social/review platforms, people/contact databases, email finders, authenticated sources, archives,
browser automation, forms, booking, mailboxes and access-control bypasses remain disabled. TDLR and
Texas Comptroller remain `NOT_APPROVED_PENDING_SEPARATE_REVIEW` and cannot be activated because they
are public government sources.

This preference does not approve an exact seed artifact, business host, terms assessment, robots
result, retention binding or source release. A-09 therefore remains partially blocked.

## Preferred environment baseline

The AWS `us-east-2` reference architecture in `environment-budget-roles.md` is the preferred
baseline pending exact owner/environment confirmation. No account, resource, identity, key, secret,
network route or infrastructure is selected or created by this preference.

## Required state separation

```text
READY_FOR_REAL_RESEARCH_AUTHORIZATION
  != REAL_BUSINESS_DISCOVERY_AUTHORIZED
  != REAL_PUBLIC_RESEARCH_AUTHORIZED
  != READY_TO_RUN_SLOT_1
```

All real-data permissions remain `NOT_AUTHORIZED` after this decision record.

## Final dependency graph

```text
OWNER SCOPE APPROVAL ───────────────┐
ENVIRONMENT APPROVAL ──────────────┤
SOURCE APPROVAL ───────────────────┤
RETENTION APPROVAL ────────────────┤
BUDGET APPROVAL ───────────────────┤
ROLE ASSIGNMENTS ──────────────────┤
LEGAL A-17 APPROVAL ───────────────┘
                   ↓ explicit independent authorization; never automatic
REAL_BUSINESS_DISCOVERY AUTHORIZATION
                   ↓ authorized execution and immutable result
FREEZE 24-COMPANY COHORT
                   ↓ separate source/terms/robots approval
EXACT 24 RESEARCH SOURCES APPROVED
                   ↓ second explicit independent authorization
REAL_PUBLIC_RESEARCH AUTHORIZATION
                   ↓ third explicit run authorization
SLOT-1 AUTHORIZATION
                   ↓ only after every exact binding validates
READY_TO_RUN_SLOT_1
```

No arrow implies automatic approval, inheritance or authority.
