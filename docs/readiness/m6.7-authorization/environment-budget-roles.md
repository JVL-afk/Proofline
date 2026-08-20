# Phase 1 Environment, Budget, and Role Decision Package

**Status:** `PREFERRED_BASELINE_PENDING_EXACT_ENVIRONMENT_CONFIRMATION`
**Infrastructure created:** None

## Minimum production-like environment recommendation

The project owner selected the following as the preferred baseline on 2026-08-20. It is not yet an
accepted A-03/A-04/A-07 environment because no exact account, resource, identity, policy or evidence
record is bound. It creates no cloud resource or authorization.

| Decision | Recommended reference selection | Mandatory approval/evidence |
|---|---|---|
| Cloud/account | Dedicated AWS account/project for M6.7 Phase 1 only | Exact account ID, owner, billing alert and separation attestation |
| Region | AWS `us-east-2` (Ohio), single US region | Owner/legal/privacy acceptance of exact region and service data flows |
| Compute | One ECS/Fargate research worker, desired concurrency 1, no public ingress | Exact task definition hash, image digest, patch/vulnerability owner and egress policy evidence |
| Control database | Encrypted Amazon RDS PostgreSQL in private subnets | Exact instance/database IDs, no public endpoint, workspace role grants, backup/PITR settings |
| Restricted capture store | Private versioned Amazon S3 bucket with public access blocked | Exact bucket ID, object ownership, lifecycle, access logging and deletion/tombstone integration |
| Encryption/key ownership | TLS in transit; separate customer-managed AWS KMS keys for database, captures, backups and logs | Exact key ARNs, key administrators/users, rotation and break-glass evidence |
| Backups | Encrypted RDS/S3 backup configuration with proposed 30-day maximum overhang | Exact retention, region, restore test, deletion replay and RTO/RPO approval |
| Human identity | Owner-selected OIDC identity provider federated to AWS IAM Identity Center; MFA mandatory | Exact IdP/tenant, MFA policy, session limits, named groups, joiner/mover/leaver and review evidence |
| Operator access | No shared accounts; short-lived federated sessions; restricted-data access separately granted and audited | Exact role policies, approvers, access-review interval and break-glass procedure |
| Research egress | Dedicated workload identity through an allowlisting egress control; only exact A-09 hosts/ports | Workload role ARN, DNS/redirect/SSRF enforcement evidence, flow logs, kill-switch linkage |
| Secrets | AWS workload identity first; Secrets Manager only if a selected source later requires a permitted secret | Exact secret owner and scope; no application, AI, browser, M6, sender or delivery credential |
| Logs | CloudWatch or approved equivalent containing IDs/hashes/states only | Exact groups, KMS key, 90/365-day classes, alarms and proof page/contact values are absent |

An owner may select another provider, but must supply an equivalent exact matrix and a successor
environment revision. The environment cannot be inferred from this recommendation. No Terraform,
account, bucket, database, identity, key, secret or network route is created by this package.

## Owner-approved A-18 monetary hard cap

**Owner-approved Phase 1 cohort hard cap: USD 250.00.** This is a maximum authorization ceiling, not
expected spend, a forecast or a representation of current AWS pricing. Before any paid operation,
the security/environment owner must attach a current provider-calculator snapshot for the selected
region/services and confirm the staged pilot fits. If it cannot, the owner must reduce scope or
approve a versioned replacement; the system cannot increase the cap automatically.

| Sub-budget | Recommended hard cap | Treatment |
|---|---:|---|
| Discovery/source operations | USD 10 | Offline seed is USD 0; any government/API charge requires an exact price/version and explicit reservation |
| HTTP research compute/egress | USD 40 | Covers the 120 logical fetch/360 attempt ceiling; missing/stale unit pricing fails closed |
| Storage, backups and logging | USD 50 | Bound to approved retention and measured synthetic size multipliers |
| Shared environment/security overhead | USD 150 | Dedicated compute/database/network/monitoring during the approved pilot window only |
| AI | USD 0 | No eligible route and no provider call |
| Total | **USD 250** | Exactly equals sub-budgets; no automatic transfer or increase |

Additional controls:

- Warn at 80% (USD 200) and fail closed at 100% (USD 250), subject to owner acceptance.
- Reserve before every potentially billable operation and atomically reconcile actual usage.
- Stop on missing/stale price, unknown billing unit, reservation drift or sub-budget exhaustion.
- Preserve 120 logical fetches, 360 attempts and 36 MB even if monetary headroom remains.
- Human review time is recorded in seconds/events and excluded from money. A labor-rate assumption
  requires a separate explicit approval.
- Any paid source or tool not listed in A-09 has a budget of USD 0 and remains unavailable.

## Stable operational role slots

Repository records should contain an opaque stable IdP subject identifier or an approved salted
subject digest plus a non-identifying role pseudonym. Do not store unnecessary names, email
addresses, telephone numbers, employment details or credentials.

| Role | Stable identifier | Current state | Required attestation |
|---|---|---|---|
| Project owner | `UNASSIGNED` | `BLOCKED` | Scope, budget, cohort and staged-continuation authority |
| Opportunity reviewer | `UNASSIGNED` | `BLOCKED` | Primary M2 acceptance review competency |
| Independent second reviewer | `UNASSIGNED` | `BLOCKED` | Must be a different human/IdP subject from opportunity reviewer |
| Incident owner | `UNASSIGNED` | `BLOCKED` | Quarantine/pause/terminate and incident-record responsibility |
| Privacy/data owner | `UNASSIGNED` | `BLOCKED` | Source, retention, deletion and restricted-access responsibility |
| Kill-switch operator | `UNASSIGNED` | `BLOCKED` | Tested emergency access; project owner cannot override activation |
| Security/environment owner | `UNASSIGNED` | `BLOCKED` | Environment/control evidence and workload-identity responsibility |
| Qualified legal reviewer | `UNASSIGNED` | `BLOCKED` | Scoped Texas/source/retention conclusion and review expiry |

Recommended record shape:

```text
role
opaque_subject_id
role_pseudonym
assignment_approval_id
effective_at
expires_at
workspace_id
identity_provider_revision
configuration_hash
```

One person may hold compatible operational roles if approved, but the primary and independent second
opportunity reviewers must always be different humans. Legal, privacy and security conclusions
remain distinct evidence even when a small team assigns multiple roles.

### Minimum human separation

Subject to competence and separate attestations, the project owner may also hold
`OPPORTUNITY_REVIEWER`, `INCIDENT_OWNER`, `PRIVACY_DATA_OWNER`, `KILL_SWITCH_OPERATOR`, and
`SECURITY_ENVIRONMENT_OWNER`. The project owner's continuation authority cannot override an active
safety stop or kill switch.

At least one different human must hold `INDEPENDENT_SECOND_REVIEWER`. The
`QUALIFIED_LEGAL_REVIEWER` must also be independent of project-product approval and therefore cannot
be the project owner; it may be the same second human only if that person separately satisfies both
competency and qualification records. The hard invariant remains:

```text
OPPORTUNITY_REVIEWER != INDEPENDENT_SECOND_REVIEWER
```

### Exact remaining A-03/A-04/A-07 environment inputs

The preferred baseline becomes an accepted environment release only after exact values and evidence
are supplied for:

- AWS account/organization ID, accountable account and billing owners, and separation attestation.
- Explicit `us-east-2` acceptance and a documented service/data-flow inventory.
- VPC, private subnet, route, security-group, DNS and exact-host egress-control identifiers.
- ECS cluster/service/task-definition identifiers, immutable image digest and patch/vulnerability
  owner.
- Private RDS instance/database identifiers, encryption key, role grants, backup/PITR settings and
  restore evidence.
- Restricted S3 bucket identifier, versioning, public-access block, object ownership, lifecycle,
  access logging and deletion replay.
- Separate KMS key ARNs, administrators/users, rotation, recovery and break-glass evidence.
- IAM Identity Center instance and upstream IdP identifiers, MFA/session policy, named access groups,
  joiner/mover/leaver process and review cadence.
- Opaque operator subject IDs, exact policies, restricted-data access approval and break-glass path.
- Research workload role ARN/policy hash and the dedicated egress identity.
- Secrets Manager identifiers and owners only where necessary; no AI, browser, M6, sender or
  delivery secret.
- Audit/log group identifiers, encryption, redaction evidence, alarms and approved retention bindings.
- Backup locations, RTO/RPO, tested restoration and tombstone/deletion reapplication evidence.
- Environment approval IDs, effective/expiry times, kill-switch binding and final configuration hash.
