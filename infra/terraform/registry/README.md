# Phase 1 worker registry preparation

This separate Terraform root resolves the worker-image dependency loop without creating the Phase 1
workload. It may create only the exact private `m67-phase1-worker` ECR repository, its rotating KMS
key/alias, and a short-lived least-privilege image-publisher role. Tags are immutable, scan-on-push
is enabled, abandoned untagged layers expire after seven days, and the publisher's
repository-scoped actions cannot target another repository. Tagged immutable release images are not
expired by this lifecycle rule.

The unavoidable `ecr:GetAuthorizationToken` action uses resource `*` because ECR does not support
resource-level permission for that action. It grants no repository mutation by itself.

Planning and applying are separate approvals. A registry plan or apply grants no Phase 1 workload,
business discovery, research, Slot 1, person/contact, AI, browser, sender, or delivery authority.
