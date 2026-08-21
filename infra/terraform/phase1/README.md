# M6.7 Phase 1 Terraform Package

This root module implements the owner-selected AWS baseline under ADR-0075. It was initialized
locally with its remote backend disabled only to resolve and lock the signed provider, and it passed
`terraform validate`; it has not been initialized against an AWS backend, planned against AWS,
applied, or treated as evidence of an environment. No AWS CLI/session authority or AWS charge
authorization has been supplied.

The dedicated workload account and protected S3/KMS state backend must be created through an
account-administration process before this package can run. This module deliberately does not use
AWS Organizations management-account authority to create an account.

## Required owner package

Supply outside Git:

- `backend.hcl` based on the example, containing only approved state resource references;
- `terraform.tfvars` with the exact account, final A-08 values, immutable image digest, and approved
  operator principal ARNs;
- short-lived plan/apply credentials for the exact target account;
- explicit AWS charge authorization bounded to USD 250;
- approved plan/apply actors and an expiring apply approval.

## Exact execution procedure

Run from this directory only after every prerequisite is recorded:

```text
terraform version
terraform init -backend-config=backend.hcl
terraform providers lock -platform=windows_amd64 -platform=linux_amd64
terraform fmt -check -recursive
terraform validate
terraform plan -input=false -lock=true -out=phase1.tfplan
terraform show -json phase1.tfplan > phase1.tfplan.json
```

Hash the configuration, `.terraform.lock.hcl`, binary plan, and JSON plan. Perform security and cost
review. Only after the project owner and security/environment owner approve those exact hashes may
an authorized operator run:

```text
terraform apply -input=false -lock=true phase1.tfplan
```

The plan/apply package contains no discovery, research, person/contact, AI, browser, sender, M6, or
delivery authorization. The service defaults to zero running tasks. After apply, record actual AWS
control-plane observations in the deployed-environment evidence record; do not copy planned values
as observations.
