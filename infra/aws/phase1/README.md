# M6.7 Phase 1 AWS Provisioning Boundary

This directory contains a non-executable target specification and an actual-deployment evidence
template. It contains no Terraform/OpenTofu module, provider block, state backend, credential,
deployment command, or live resource identifier.

Executable infrastructure remains blocked until A-03/A-04/A-07, the final A-08 policy, A-17, the
IaC tool/state/backend policy, exact operators, and accountable environment approvals are accepted.
The target specification is not infrastructure evidence and cannot satisfy any environment gate.

After a separately authorized deployment, an operator records observed resource identifiers and
control evidence in an immutable successor of `deployed-environment-evidence.template.json`. The
record must identify an AWS control-plane export, observation time and opaque observer, immutable
raw-evidence hashes, and a separate security/environment-owner approval. The configuration hash
covers the canonical evidence payload. A-03/A-04/A-07 may become accepted only after the
security/environment owner verifies that actual evidence; intended configuration is insufficient.

No deployment or live business access is authorized by any file in this directory.
