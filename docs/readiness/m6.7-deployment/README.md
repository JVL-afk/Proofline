# M6.7 authenticated Terraform plan handoff

The protected Terraform-state bootstrap was applied and independently observed on 2026-08-21.
`bootstrap-deployed-evidence-2026-08-21.json` binds the exact approved plan, AWS observations,
policy hashes, remote-backend migration, and pseudonymous owner-actor reconciliation. This deployed
state boundary grants no discovery, research, Slot 1, person/contact, AI, browser, or delivery
authority.

M6.7H stops at an authenticated saved plan and review package. Terraform apply, AWS resource
creation, business discovery, and public research remain separate authorities.

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
