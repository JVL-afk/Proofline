# M6.7 owner-interaction consolidation

The owner decisions are frozen in `consolidated-owner-approval-2026-08-21.json`. External facts,
system-derived values, and post-deployment observations are not re-presented as owner choices.

## Six interactions before initial discovery, seven through cohort continuation

1. Configure the approved dedicated AWS account and short-lived AWS CLI v2 SSO entry point.
2. Sign `APPROVE_BOOTSTRAP_APPLY` over the exact authenticated bootstrap plan record.
3. Sign `APPROVE_PHASE1_APPLY` over the exact authenticated application plan record.
4. Sign one consolidated environment acceptance whose five explicit child decisions remain
   separately represented: A-03, A-04, A-07, A-08 live effectiveness, and ADR-0071.
5. Approve the exact seed/source generator policy and source mechanism. This grants no live access.
6. Sign `AUTHORIZE_REAL_BUSINESS_DISCOVERY` for the seed-construction substage, which must pause as
   soon as the immutable candidate/source package is generated.
7. Sign the generated seed/source package to permit the remainder of discovery. Every seed artifact
   and host conclusion is separately enumerated; blocked or uncertain hosts cannot be hidden by the
   batch signature.

The system derives resource names, role ARNs, backend values, image digest, plan/configuration/lock
hashes, timestamps, seed commitment, candidate/source references, evidence hashes, manifest hash,
and the seven-day release expiry. AWS identifiers and control evidence are observed after deployment.

Research authorization and slot authorization remain later, separate signature events.

The requested order—approve a generated real-business artifact and then authorize the first access
used to generate it—is circular while no offline artifact exists. Six interactions reach the first
bounded discovery substage; a seventh continuation approval is required after the artifact exists.
Alternatively, a separately lawful provenance-backed offline artifact present before interaction 5
would permit the originally requested six-step order. None currently exists, and the system will not
invent one.
