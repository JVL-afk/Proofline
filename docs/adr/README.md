# Architecture Decision Records

ADRs capture decisions that constrain implementation or are expensive to reverse.

## Status values

- `Proposed`: under review; must not be treated as approved.
- `Accepted`: current decision.
- `Superseded`: replaced by a later ADR.
- `Rejected`: considered and deliberately not selected.
- `Deprecated`: still present but scheduled for removal.

## Process

1. Copy `0000-template.md` to the next four-digit number and a short kebab-case title.
2. State context and constraints without presenting a preferred option as fact.
3. Record alternatives and material tradeoffs.
4. Name the accountable approver in the decision metadata.
5. Merge implementation only after the ADR reaches `Accepted`, unless a documented exception exists.
6. Never edit an accepted ADR to change its decision. Add a superseding ADR.

## Index

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-modular-monolith-monorepo.md) | Accepted | Modular monolith in a polyglot monorepo with isolated hostile-content deployables |
| [ADR-0002](0002-runtime-and-workspace-baseline.md) | Accepted | Node.js 24 LTS, npm workspaces, and Python 3.13 baseline for M0 |
| [ADR-0003](0003-python-workspace-and-locking.md) | Accepted | uv workspace and universal lockfile for Python packages |
| [ADR-0004](0004-m0-local-walking-skeleton-adapters.md) | Accepted | Local-only auth, SQLite workflow, fixture fetch, and diagnostic UI adapters for M0 |
| [ADR-0005](0005-m1-bounded-local-research.md) | Accepted | Bounded local M1 research adapters without closing production source/retention decisions |
| [ADR-0006](0006-m2-semantic-lineage-and-review.md) | Accepted | Separate semantic lineage with mandatory hypothesis review |
| [ADR-0007](0007-commercial-hvac-lead-response-definition.md) | Accepted | Texas Commercial HVAC inbound lead-response definition |
| [ADR-0008](0008-m2-deterministic-economics-and-hypotheticals.md) | Accepted | Deterministic potential-incremental-revenue scenarios |
| [ADR-0009](0009-m2-uncalibrated-factor-bands.md) | Accepted | Heuristic factor bands until calibration exists |
| [ADR-0010](0010-m2-rule-based-reasoning.md) | Accepted | Rule-based M2 reasoning and temporary local adapters |
| [ADR-0011](0011-provider-neutral-intelligence-contracts.md) | Accepted | Provider-neutral task contracts and versioned deployment qualification |
| [ADR-0012](0012-fixture-model-qualification-gates.md) | Accepted | Fixture-based qualification metrics and hard safety gates |
| [ADR-0013](0013-deterministic-baseline-ai-routing.md) | Accepted | Advisory-only routing with deterministic M2 fallback |
| [ADR-0014](0014-live-evaluation-isolation-and-budgets.md) | Accepted | Disabled live boundary, budgets, provenance, and data controls |
| [ADR-0015](0015-controlled-live-model-tournament.md) | Accepted | Synthetic-only, budget-capped live model qualification tournament |
| [ADR-0016](0016-structured-audit-claims-and-manifests.md) | Accepted | Structured audit claims and immutable input manifests |
| [ADR-0017](0017-audit-lineage-and-qc.md) | Accepted | Audit lineage and non-overridable semantic QC |
| [ADR-0018](0018-deterministic-audit-composition.md) | Accepted | Deterministic audit composition and disabled wording-only AI port |
| [ADR-0019](0019-audit-review-and-invalidation.md) | Accepted | Exact revision review and invalidation lifecycle |
| [ADR-0020](0020-audit-eligibility-and-publication-boundary.md) | Accepted | Opportunity eligibility and no-publication M3 boundary |
| [ADR-0021](0021-declarative-demo-specification.md) | Accepted | Declarative demo specifications and immutable component registry |
| [ADR-0022](0022-deterministic-demo-state-machine.md) | Accepted | Deterministic state machine and structurally mock-only actions |
| [ADR-0023](0023-demo-personalization-and-disclosure.md) | Accepted | Evidence-bound personalization, synthetic data, and disclosure |
| [ADR-0024](0024-demo-runtime-isolation.md) | Accepted | Separate runtime, capability sessions, CSP, and minimal telemetry |
| [ADR-0025](0025-demo-eligibility-review-and-revocation.md) | Accepted | Exact eligibility, review, invalidation, and revocation |
| [ADR-0026](0026-authenticated-demo-access.md) | Accepted | Authenticated-only demo access with no public sharing |
| [ADR-0027](0027-outreach-packages-and-exact-manifests.md) | Accepted | Immutable M5 packages and exact approved M1-M4 manifests |
| [ADR-0028](0028-outreach-claim-projection-and-economics.md) | Accepted | Typed claim projection and internal-only economics |
| [ADR-0029](0029-deterministic-outreach-templates.md) | Accepted | Deterministic templates and disabled wording AI port |
| [ADR-0030](0030-outreach-artifact-separation-and-qc.md) | Accepted | Internal/external separation and non-overridable hard QC |
| [ADR-0031](0031-outreach-content-review-no-delivery.md) | Accepted | Content-only review, invalidation, and no-delivery boundary |
| [ADR-0032](0032-functional-role-targeting.md) | Accepted | Functional-role targeting without people or impersonation |
| [ADR-0033](0033-independent-contact-and-send-stages.md) | Accepted | Six independent contact and send stages |
| [ADR-0034](0034-proof-scoped-contact-verification.md) | Accepted | Acquisition origin and proof-scoped verification stay separate |
| [ADR-0035](0035-fixture-eligibility-and-a17-live-gate.md) | Accepted | Fixture-only eligibility and mandatory A-17 live gate |
| [ADR-0036](0036-suppression-cadence-and-time-precedence.md) | Accepted | Suppression, cadence, time, and kill-switch precedence |
| [ADR-0037](0037-typed-m5-delivery-slots.md) | Accepted | Typed M5 delivery/compliance slots without prose mutation |
| [ADR-0038](0038-exact-manifest-and-one-send-authorization.md) | Accepted | Exact manifests and one-message human authorization |
| [ADR-0039](0039-mock-only-single-message-delivery.md) | Accepted | Zero-network mock-only single-message delivery |
| [ADR-0040](0040-receipts-replies-and-first-party-assertions.md) | Accepted | Separate receipts/replies and first-party assertions |
| [ADR-0041](0041-referrals-and-controlled-reanalysis.md) | Accepted | Referral restart and request-only upstream re-analysis |
| [ADR-0042](0042-isolated-mock-delivery-security.md) | Accepted | Synthetic data, strict message QC, and isolation boundary |
| [ADR-0043](0043-narrow-first-production-launch-envelope.md) | Accepted | Texas-only one-message plain-text launch envelope |
| [ADR-0044](0044-deterministic-live-activation-readiness.md) | Accepted | Deterministic fail-closed activation-readiness projection |
| [ADR-0045](0045-versioned-production-outreach-policy.md) | Accepted | Accountable production policy release mechanics |
| [ADR-0046](0046-contact-source-and-proof-governance.md) | Accepted | Inactive source proposal and atomic proof governance |
| [ADR-0047](0047-sender-and-external-presence-lifecycle.md) | Accepted | Independent domain, website, sender, and delivery attestations |
| [ADR-0048](0048-version-specific-provider-certification.md) | Accepted | Version-specific one-message provider certification |
| [ADR-0049](0049-production-separation-of-duties.md) | Accepted | Strict separation of duties and step-up authorization |
| [ADR-0050](0050-contact-data-lifecycle-and-tombstones.md) | Accepted | Per-category lifecycle and suppression tombstone governance |
| [ADR-0051](0051-isolated-production-delivery-boundary.md) | Accepted | Attested isolated future delivery and webhook boundaries |
| [ADR-0052](0052-operational-readiness-and-suspension.md) | Accepted | Operational ownership, runbooks, and emergency suspension |
| [ADR-0053](0053-m67-shadow-ready-boundary.md) | Accepted | Mandatory non-send M6.7 SHADOW_READY boundary |
| [ADR-0054](0054-tournament-ii-task-authority.md) | Accepted | Tournament II task authority and inclusion policy |
| [ADR-0055](0055-end-to-end-synthetic-corpus.md) | Accepted | Synthetic end-to-end corpus and minimum-data projections |
| [ADR-0056](0056-semantic-evaluation-and-blast-radius.md) | Accepted | Semantic hard gates with evidence-scoped failure blast radius |
| [ADR-0057](0057-blinded-usefulness-and-material-gain.md) | Accepted | Blinded usefulness review and material-gain dispositions |
| [ADR-0058](0058-immutable-candidate-intake.md) | Accepted | Just-in-time immutable candidate intake |
| [ADR-0059](0059-tournament-no-route-lifecycle.md) | Accepted | Tournament lifecycle with no route activation |
| [ADR-0060](0060-tournament-budget-ledger.md) | Accepted | Hierarchical tournament budget reservation and reconciliation |
| [ADR-0061](0061-m67-ai-advisory-isolation.md) | Accepted | M6.7 AI advisory isolation |
| [ADR-0062](0062-tournament-security-and-retention.md) | Accepted | Tournament security and safe result retention |
| [ADR-0063](0063-tournament-ii-run-bound-identity.md) | Accepted | Pinned and run-bound identity for synthetic Tournament II only |
| [ADR-0064](0064-synthetic-tournament-retention-and-reviewer-release.md) | Accepted | Synthetic retention approval and reviewer assignment at package release |

The product/compliance decisions A-01 through A-20 are tracked separately in `docs/decisions/README.md` until they become ADRs.
