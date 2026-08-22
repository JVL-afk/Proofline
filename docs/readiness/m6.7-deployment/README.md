# M6.7 authenticated Terraform plan handoff

The protected Terraform-state bootstrap was applied and independently observed on 2026-08-21.
`bootstrap-deployed-evidence-2026-08-21.json` binds the exact approved plan, AWS observations,
policy hashes, remote-backend migration, and pseudonymous owner-actor reconciliation. This deployed
state boundary grants no discovery, research, Slot 1, person/contact, AI, browser, or delivery
authority.

The production-runtime, PostgreSQL, read-only-container, workload-identity, protected-state trust,
and controlled exact-host egress remediations are complete. The first remediated plan's apply
stopped before any resource call because its saved backend identity was read-only; the immutable
attempt record preserves that result. The corrected successor in
`phase1-remediated-plan-successor-review-2026-08-22.json` passed its exact pre-apply gate and was
applied under the separately approved workload/state apply identities. It stopped after partial
creation because the bounded apply policy and application configuration disagreed on exact S3
names and provider-required tag operations, and because AWS exposes no Cloud Map service-linked
role template for the explicit resource in the configuration. The independently observed partial
state and fail-closed disposition are recorded in
`phase1-successor-apply-attempt-2026-08-22.json`. That saved plan and its approval are consumed and
must not be retried. No ECS service, task, database, capture/audit bucket, or budget exists, and the
kill switch remains `TRIPPED`. Environment acceptance is blocked pending a reviewed remediation
and new successor authorization. Discovery, research, and Slot 1 remain `NOT_AUTHORIZED`.

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
