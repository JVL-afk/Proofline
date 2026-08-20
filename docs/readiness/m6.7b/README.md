# M6.7B Live Research Readiness Design

**Status:** Design complete; all permissions remain `NOT_AUTHORIZED`
**Milestone type:** Policy, environment, operating, and approval readiness only
**Authority granted:** None

## 1. Authority boundary

M6.7B prepares the prerequisites for two independent capabilities:

```text
REAL_BUSINESS_DISCOVERY != REAL_PUBLIC_RESEARCH
```

It does not select a company, fetch a business site, resolve a person, store/verify a contact,
calculate shadow eligibility, produce `SHADOW_READY`, invoke AI, or communicate externally.
M1-M6 remain authoritative. M6.6 stays closed and unavailable to this milestone.

## 2. Browser policy

Phase 1 is `HTTP_FIRST`. Browser fallback is `DISABLED`. A future browser proposal must be a new
independent capability with exact sources, isolated network/container controls, no secrets or
sessions, a separate budget, and explicit approval. HTTP failure cannot automatically trigger a
browser.

## 3. Minimum Phase 1 environment and access

This is an architectural recommendation, not an approved cloud selection.

| Control | Phase 1 requirement |
|---|---|
| Tenancy (A-03) | One dedicated workspace and one cohort/run boundary. Workspace ID is mandatory on every record/query; no cross-workspace administration path. No external customer tenancy. |
| Environment (A-04) | Dedicated production-like environment in one owner-approved US region. Exact provider and region remain required approval fields. No developer workstation or shared test database for real captures. |
| Network | Private control/API surfaces; research worker is the only egress identity. DNS/IP/redirect pinning and SSRF controls remain. Egress is exact approved source host/port only. No inbound public endpoint is required. |
| Storage | Encrypted relational control store plus encrypted restricted capture store, separated by role. Backups encrypted and expiry-bound. Exact products remain unselected. |
| Transport | TLS for service/storage traffic; only ordinary HTTPS/HTTP website access under source policy. No mail, telephony, CRM, calendar, form, chat, booking, AI, or browser egress. |
| Secrets | Managed workload identity/secret store only. Research worker receives no application, AI, M6, sender, delivery, browser-session, or user credential. |
| Identity (A-07) | Standards-based OIDC, MFA for humans, workload identities for services, short sessions, named role grants, access review, and no shared operator account. Exact IdP remains unselected. |
| Audit | Append-protected authentication, policy decision, restricted-data access, permission, kill-switch, deletion, and configuration events. Never log page/contact values. |
| Least privilege | Research worker reads one run capability and writes M1 results/restricted captures only. Shadow control plane reads projections and writes only M6.7 records. |
| Kill switch | Named operator can atomically suspend discovery/research permissions and revoke egress leases. Incident owner controls restart review; project owner cannot bypass a safety stop. |

The environment cannot be approved until cloud/provider/region, IdP, encryption/key ownership,
backup/restore, log destination, vulnerability/patch ownership, monitoring, and kill-switch evidence
are selected and tested. Delivery infrastructure is neither needed nor permitted.

## 4. Durable-workflow decision

**Recommendation:** `BOUNDED_DB_BACKED_PHASE1_ORCHESTRATOR`; do not introduce Temporal for the
24-company pilot.

The existing small-run pattern is sufficient if its live successor implements:

- idempotency keys for cohort/run/company/stage commands;
- append-only stage attempts and exact input/output revision hashes;
- transactional claim leases with owner, attempt, heartbeat, and expiry;
- bounded retry classes and no blind retry after ambiguous state-changing operation (none are
  permitted in this milestone);
- checkpoint/resume at company and M1 page boundaries;
- permission/kill-switch check before claim, DNS, request, redirect, retry, and persistence;
- cohort pause and run termination that stop new claims and safely expire leases;
- preflight cost/work reservations and atomic reconciliation;
- deterministic capture replay from immutable snapshots.

One research worker is the default. Parallelism is an explicit run value and begins at one. Temporal
would add hosting/region/vendor/operations decisions without material benefit at this scale. Revisit
only when multiple long-running workers, multi-day schedules, cross-service signals, or measured
failure/recovery evidence exceeds the database orchestrator's safe operating envelope. A-05 should
accept this bounded exception; A-06 remains deferred because Temporal is not selected.

## 5. Exact Phase 1 cohort approval package

The future project-owner approval must contain:

```text
jurisdiction = US-TX
vertical = COMMERCIAL_HVAC
business_model = B2B_RELEVANT
opportunity = INBOUND_LEAD_RESPONSE_QUALIFICATION
target_size = 24
public_business_web_presence_required = true
unit_of_analysis = ONE_DISTINCT_BUSINESS_LEAD_FLOW
shared_brand_franchise_cap = 1
multi_location_split = ONLY_IF_DISTINCT_PUBLIC_LEAD_FLOW_IS_VERIFIED
sampling = FROZEN_SEEDED_SYSTEMATIC_RANDOM_ORDER
reserve_order = FROZEN_BEFORE_RESEARCH
replacement = PREDETERMINED_COHORT_INELIGIBILITY_ONLY
research_failure_replacement = false
insufficient_evidence_replacement = false
no_supported_opportunity_replacement = false
opportunity_based_replacement = false
source_policy_version = REQUIRED
discovery_permission_release_id = REQUIRED
owner_approval = REQUIRED
```

Selection occurs only after source permissions and the real sampling frame are approved. Eligibility,
deduplication, clustering, exclusions, and reserve order are frozen before opportunity outcomes are
known. The manifest records every attempted slot and replacement reason.

## 6. Phase 1 financial and capacity envelope

No external discovery/provider or cloud product is selected, so assigning provider prices would be
fabrication. The preflight therefore separates measurable workload from owner-supplied monetary
rates.

| Stage | Conservative measurable reservation | Monetary treatment |
|---|---|---|
| Discovery | Candidate-frame maximum is an owner-approved input; one approved source operation per candidate plus bounded retry | Direct/public source cost USD 0 only if contract/API is actually free; otherwise price version and sub-budget required |
| HTTP research | 24 companies × max 5 pages = 120 page attempts; max 3 attempts/page; 24 robots checks with bounded retry; max 36 MB response bytes before storage overhead | Compute/egress price version required from selected environment; no dollar estimate yet |
| Storage/compute | At least raw restricted bytes, extracted text, evidence, indexes, logs, and backups; reserve from measured synthetic compression/index multipliers | Provider calculator and retention values required before monetary cap |
| Human review | Every proposed M2 acceptance, independent second review, M3/M4/M5 approval, escalations, and owner-approved negative QA sample | Record actual seconds; no conversion to money without an approved hourly-rate assumption |
| Shared overhead | Environment, monitoring, backup, source/terms review, incident readiness | Selected environment and allocation rule required |
| AI | No eligible M6.6 binding | Exactly USD 0 |

The current M1 ceilings imply at most 120 logical page fetches, at most 360 total page attempts
including initial attempts, up to 72 total robots attempts if the same three-attempt bound is
approved, and 36 MB of uncompressed per-run
response ceilings across 24 businesses before replicas, indexes, logs, and backups. If all 24
businesses advance, mandatory opportunity/M3/M4/M5 review creates up to 120 review events before
identity ambiguity, escalation, or negative QA. These are capacity bounds, not forecasts.

`COHORT_HARD_CAP_USD` must equal the sum of approved discovery, research/compute, storage/backup,
and shared-overhead sub-budgets. Human time remains a separate capacity ledger; AI remains USD 0.

Required A-18 fields before execution:

- overall cohort hard cap in USD;
- separate discovery, research/compute, storage/backup, and shared-overhead sub-budgets;
- human-review capacity in events/time, separate from money;
- 100% reservation before each paid operation, atomic usage reconciliation, no oversubscription;
- an owner-approved candidate-frame cap and negative-QA sample size;
- architectural recommendation: warn at 80% and fail closed at 100% of the approved hard cap, with
  no automatic increase; the owner must explicitly accept or replace the warning threshold;
- stop on missing/stale price, unknown billable unit, unreserved operation, or reconciliation drift;
- AI sub-budget fixed at USD 0.

## 7. Human ownership and separation

| Role | Required responsibility | Separation requirement |
|---|---|---|
| Project owner | Scope, cohort, budget, staged continuation | Cannot act as independent second opportunity reviewer for own first review; cannot override safety stop |
| Opportunity reviewer | Review every proposed M2 acceptance and semantic warnings | Distinct from second reviewer on the same opportunity |
| Independent second reviewer | Independent accepted-opportunity check | Must be a different human; no self-approval |
| Incident owner | Classify safety events, quarantine/pause/terminate, coordinate response | Cannot unilaterally erase incident evidence; restart needs recorded review |
| Privacy/data owner | Source, incidental-data, access, retention, deletion, request handling | Must approve A-08/A-09; cannot be replaced by project-owner convenience approval |
| Kill-switch operator | Exercise and test suspension/revocation | May also be incident owner; must have independent, audited emergency access and a backup operator |
| Qualified legal reviewer | Record scoped legal/terms/applicability conclusions | Must be competent and independent of product pressure where legal interpretation is required |
| Security/environment owner | Environment attestation, identities, egress, encryption, logs, backup | Cannot attest controls without evidence |

One person may hold project, incident, or kill-switch roles if access policy permits. The privacy/data
approval, legal conclusions, security attestation, and independent second review retain their
distinct evidence even if a small team assigns multiple roles.

## 8. A-17 Texas live-research release design

The signed release must state exactly:

- jurisdiction `US-TX`; Texas businesses only;
- vertical `COMMERCIAL_HVAC`, B2B, inbound lead-response/qualification analysis;
- public business discovery/research under exact A-09 source versions;
- restricted incidental-data handling under exact A-08 policy;
- no person/contact resolution, extraction, indexing, verification, eligibility, or metrics;
- no communication, form/chat/booking/mailbox action, contact with a business, authentication,
  access-control/CAPTCHA/rate-limit bypass, or browser fallback;
- no claim that public accessibility alone authorizes collection/reuse;
- exact operator/controller, purpose, environment, start, expiry, incident owner, and counsel record;
- a statement that research approval does not authorize outreach, CAN-SPAM activity, M6 records, or
  delivery.

Three evidence classes remain distinct:

1. Architectural policy: controls and fail-closed design recorded here.
2. Project-owner approval: acceptance of product scope, cohort, costs, and operational risk.
3. Legal interpretation: counsel's scoped assessment of law, terms, contracts, and obligations.

This repository and its policy review do not provide legal advice.

## 9. Synthetic pre-live safety test

The next implementation milestone must prove:

1. With both permissions `NOT_AUTHORIZED`, discovery adapter construction and every egress request
   fail before DNS/network activity.
2. Discovery authorization enables only approved discovery operations; research still fails.
3. Research authorization enables only exact selected-host HTTP GET/HEAD work for the frozen run;
   discovery outside the frame still fails.
4. Missing/mismatched workspace, scope, source, terms hash, retention, environment, run, start,
   expiry, configuration, budget, or approval fails closed.
5. Browser, person/contact extraction/index/search/projection/metrics, M6 send state, and delivery
   remain absent under every permission combination.
6. Suspension/revocation before claim, before DNS, before request, during retry, and before
   persistence stops or safely checkpoints work; no automatic resume.
7. Emergency kill terminates egress leases, pauses the cohort, and preserves immutable evidence.
8. M6.7 removal or permission-artifact deletion cannot change M1-M6/M6.5 truth.
9. Deterministic CI uses fake transports, zero credentials, and zero network.

## 10. First-real-business procedure

1. After all approvals, construct and freeze the 24-company frame, selection, seed, and reserve.
2. Create the exact run and releases; select slot 1 by frozen order, not operator preference.
3. Run only slot 1 with worker concurrency fixed to one.
4. Pause automatically after its terminal M1-M5/Phase 1 outcome.
5. Review full source/terms record, snapshots, lineage, semantic safety, reviews, outcome, cost,
   logs, and deletion/retention scheduling. Failure remains slot 1's true outcome.
6. Project owner, privacy/data owner, incident owner, and reviewers record continuation or stop.
7. If approved, run the next frozen contiguous small batch; recommended batch size is an explicit
   owner decision in the run release, not an operator choice.
8. Pause and review batch evidence before authorizing the remaining frozen slots.
9. Never reorder, replace for outcome/yield, add a preferred company, or regenerate the seed.

## 11. Exact approvals still required

- Accept ADR-0071 after all fields are completed.
- Accept A-08 retention/privacy/deletion values and procedures.
- Accept A-09 exact discovery and research source instances and terms/robots/rate rules.
- Sign A-17 scoped Texas public-research release with qualified legal record.
- Accept A-03 tenancy/workspace decision.
- Select and accept A-04 provider, exact US region, data flows, encryption/key, backup, and recovery.
- Select and accept A-07 IdP, roles, MFA, workload identities, and access-review policy.
- Accept A-05 bounded database-orchestrator exception; keep A-06 deferred unless Temporal returns.
- Accept A-18 monetary caps, non-monetary limits, alerts, ownership, and recovery objectives.
- Assign every human role and backup kill-switch operator.
- Approve the exact cohort package, candidate-frame cap, negative-QA sample, and staged batch size.
- Implement and pass M6.7C pre-live safety/environment/source/retention tests.
- Create separate immutable discovery and research releases; both remain `NOT_AUTHORIZED` now.

## 12. Recommended next milestone

**M6.7C — Live Research Gate Implementation and Synthetic Preflight** should implement only the
approved policy schemas, source registry, environment attestations, permission checks, bounded
database orchestrator, robots/terms enforcement, deletion controls, cost reservation, kill switch,
and fake-transport tests. It must finish with both live permissions still `NOT_AUTHORIZED`.

Only a later explicitly authorized M6.7D action may populate signed releases and run the staged
first real company. No implementation or live access is authorized by M6.7B.
