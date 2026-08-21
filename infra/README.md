# Infrastructure

Infrastructure-as-code, environment composition, and local platform definitions belong here.

## M0 gate

Executable Terraform/OpenTofu modules and container-compose definitions are intentionally absent until the following are approved:

- A-04 cloud and regions;
- A-05/A-06 workflow engine and hosting;
- A-08 evidence retention posture;
- A-18 SLO, disaster recovery, and cost limits;
- the IaC tool and state/backend policy.

Adding placeholder infrastructure with floating images, invented regions, retention, backup, or network settings would create false decisions. Use ADRs first, then add executable definitions with validation and cost/security review.

## M6.7 Phase 1 preparation

`infra/aws/phase1/` contains a non-executable owner-preferred AWS target specification and an empty
actual-deployment evidence template. These are review/control artifacts, not Terraform, deployment,
cloud authority, or proof that a resource exists. Executable IaC remains blocked on A-03/A-04/A-07,
final A-08/A-17, the IaC tool and remote-state/backend decision, and accountable environment owners.
