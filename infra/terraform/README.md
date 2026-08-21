# Terraform/OpenTofu Boundary

ADR-0075 accepts Terraform for the Phase 1 provisioning package and its protected remote-state
policy. `phase1/` contains the reviewable root module, but it cannot be initialized, planned, or
applied until the exact backend, account, identity, retention, recovery, legal, role, cost, and apply
approvals exist.

The package does not create an AWS account or state backend, and no deployment evidence may be
derived from configuration alone.
