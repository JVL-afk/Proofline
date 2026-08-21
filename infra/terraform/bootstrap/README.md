# Phase 1 Terraform Backend Bootstrap

This is a separate state-administration root. It creates only the protected S3/KMS backend,
least-privilege state roles, and the dedicated CloudTrail data-event audit path required by
ADR-0075. It creates no Phase 1 workload, worker, business access, AI, browser, delivery, or
application resource.

For the bounded 24-company pilot, state and workload may use the same dedicated AWS account. The
required separation is an IAM/resource/approval boundary rather than a second-account requirement:
bootstrap, state-plan, state-apply, workload-plan, workload-apply, operator, worker, and kill-switch
roles remain distinct. The state bucket name is derived as
`m67-phase1-tfstate-<account-id>-us-east-2`; it is not an owner decision.

## One-time bootstrap boundary

The backend cannot store the state used to create itself before it exists. An approved bootstrap
operator therefore initializes this root with its local backend, creates and reviews a saved plan,
and may apply that plan only under a separate explicit bootstrap-apply authorization. No such apply
is authorized by M6.7H.

After an authorized bootstrap apply, immediately migrate this root's local state into a distinct
key in the new protected backend (for example `m67/bootstrap/terraform.tfstate`) using
`terraform init -migrate-state`. Verify the remote object, encryption, versioning, lock behavior,
CloudTrail data-event coverage supplied by the state-administration environment, and access roles;
then securely destroy every local state copy. The Phase 1 application root uses
`m67/phase1/terraform.tfstate` and a separately approved partial backend file.

## Required owner inputs

- exact state-administration AWS account and short-lived profile/execution identity;
- exact short-lived plan and apply principal identities, derived from the authenticated SSO session;
- explicit authorization for a future bootstrap apply and its AWS charges.

No credential, generated backend file, tfvars file, plan, or state belongs in Git.
