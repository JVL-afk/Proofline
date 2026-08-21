# M6.7 Phase 1 AWS Provisioning Boundary

This directory contains the target specification and actual-deployment evidence template. The
reviewable Terraform root module is under `infra/terraform/phase1/`; neither directory contains a
credential, initialized backend, state, plan, deployment receipt, or live resource identifier.

ADR-0075 selects Terraform and the S3/KMS state policy. Initialization, planning and apply remain
blocked until the exact backend/account, A-03/A-04/A-07 inputs, final A-08 policy, A-17, exact
operators, AWS charge authorization, and accountable environment approvals are present. The target
specification and Terraform code are not infrastructure evidence and cannot satisfy an environment
gate.

After a separately authorized deployment, an operator records observed resource identifiers and
control evidence in an immutable successor of `deployed-environment-evidence.template.json`. The
record must identify an AWS control-plane export, observation time and opaque observer, immutable
raw-evidence hashes, and a separate security/environment-owner approval. The configuration hash
covers the canonical evidence payload. A-03/A-04/A-07 may become accepted only after the
security/environment owner verifies that actual evidence; intended configuration is insufficient.

No deployment or live business access is authorized by any file in this directory.
