# M6.7 authenticated Terraform plan handoff

The protected Terraform-state bootstrap was applied and independently observed on 2026-08-21.
`bootstrap-deployed-evidence-2026-08-21.json` binds the exact approved plan, AWS observations,
policy hashes, remote-backend migration, and pseudonymous owner-actor reconciliation. This deployed
state boundary grants no discovery, research, Slot 1, person/contact, AI, browser, or delivery
authority.

The approved backend-corrected Cloud Map health successor was applied and independently observed.
Terraform now accounts for 82 managed instances and reports no drift. The private PostgreSQL
instance, capture/audit buckets, two zero-count ECS services, controlled-egress boundary, KMS keys,
CloudTrail, alarms, SNS topic, and USD 250 budget exist. The Cloud Map successor has ECS custom
health with threshold one and no registered instance. The immutable observation is recorded in
`phase1-cloud-map-health-backend-successor-deployed-evidence-2026-08-22.json`.

The production minimization gap was remediated in an immutable worker successor. The private
ECR/S3 startup path, kill-switch block, production minimization persistence, and isolated PITR
restore inspection all passed with synthetic data. The restore target was deleted without a final
snapshot, both ECS services returned to zero desired/running/pending tasks, the kill switch is
`TRIPPED`, and Terraform reports `NO_CHANGES` across 84 managed instances. The completed validation
is recorded in `phase1-synthetic-environment-validation-completed-evidence-2026-08-22.json`.

A-03, A-04, A-07, A-08 live effectiveness, and ADR-0071 are separately represented and ready for
one consolidated owner acceptance. Their immutable aggregate is
`phase1-consolidated-environment-evidence-2026-08-22.json`; the unsigned approval object is
`consolidated-environment-acceptance-ready-2026-08-22.json`. PRIMARY_A independent authentication
remains a later discovery-role prerequisite. All discovery, research, person/contact, Slot 1,
communication, AI, and browser permissions remain `NOT_AUTHORIZED`.

The pre-remediation read-only reconciliation is frozen in
`phase1-partial-state-inventory-2026-08-22.json`: 56 managed objects were present in both state and
AWS, 27 objects from the failed plan were absent, and there were no unexpected managed objects or
remote losses. The four narrow source corrections use one shared deterministic S3 identifier
module, exact budget/service-linked-role tag permissions, and native Cloud Map behavior without a
fabricated service-linked role. Corrected source is not deployed evidence and cannot reuse the
consumed application approval.

The exact two-policy control plan is ready only for a separate remediation authorization and is
recorded in `phase1-partial-control-remediation-plan-review-2026-08-22.json`. The subsequent
read-only application review found the existing ECS and RDS service-linked roles tainted in state
and therefore proposed two replacements. That review is frozen as
`phase1-partial-successor-plan-blocked-2026-08-22.json` and must not be applied. The remote roles are
present and must be preserved. Exact IAM-plan authorization plus explicit two-address state
reconciliation must precede a new apply-capable successor plan.

The deployment-preparation state stops at an authenticated saved plan and review package. Phase 1
Terraform apply, business discovery, and public research remain separate authorities.

## Minimum inputs for the plan

1. Approved dedicated AWS account/organization fact, if an account already exists.
2. Approved short-lived AWS CLI v2 IAM Identity Center/SSO profile entry point.

Region `us-east-2`, resource names, role ARNs, backend values, image digest, plan hashes, provider
lock hash, and configuration hashes are system-derived or observed. They are presented in the
bootstrap/application plan records and are not independent owner inputs.

Values AWS can return after authentication are observed rather than requested again. Credentials,
backend files, tfvars, saved plans, and plan JSON stay outside Git.

## Plan sequence

Use the checksum-verified Terraform 1.15.9 binary and the committed provider lock. Confirm caller
identity before initialization. Initialize with the owner-approved partial backend file, validate,
and create a saved plan under the plan role. Render it to JSON, hash the binary and JSON, and copy
only the non-sensitive reviewed results into a successor of the review template.

Any destroy or replacement, account/region mismatch, prohibited infrastructure, missing cost
evidence, spend above USD 250, or unresolved security warning makes apply readiness `NOT_READY`.
Even a clean plan can reach only `READY_FOR_TERRAFORM_APPLY_AUTHORIZATION`; it never constitutes
apply authorization and never changes any real-data permission.
