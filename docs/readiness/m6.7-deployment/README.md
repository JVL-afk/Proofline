# M6.7 authenticated Terraform plan handoff

M6.7H stops at an authenticated saved plan and review package. Terraform apply, AWS resource
creation, business discovery, and public research remain separate authorities.

## Minimum inputs for the plan

1. Approved workload AWS account ID and short-lived profile or role used for read/plan calls.
2. Confirmed region `us-east-2`.
3. Pre-created protected backend values: bucket, state key, KMS key ARN, and plan-role ARN.
4. Immutable worker ECR URI pinned by `@sha256:<64 hex>`.
5. Exact approved operator and kill-switch operator principal ARNs.
6. A non-secret globally unique resource-name prefix only if the default cannot be used.

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
