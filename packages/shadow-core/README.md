# Shadow Validation Core

M6.7A owns synthetic cohort policies, frozen selections, shadow runs, canonical M1-M5 stage
lineage, outcome projections, review/QA assignments, metrics, costs, safety stops, and immutable
M6.8 evidence packages.

M6.7C adds immutable policy, retention, exact-source, environment, role, budget, permission, kill,
deletion, cohort-gate, staged-execution, and preflight contracts plus a bounded database-orchestrator
application layer. It exposes no command that can authorize live use. Its egress interface is
implemented only by synthetic fakes and reuses the M1 public URL/DNS/SSRF policy.

It consumes existing M1-M5 statuses through a declared canonical-pipeline port. It does not own or
mutate their canonical records. It contains no real-data, person/contact, AI, sender, delivery,
provider, production-network, or M6 command port. Phase 1 cannot progress beyond
`CONTACT_PHASE_NOT_AUTHORIZED`.

Public interfaces are the immutable domain contracts, `ShadowValidationService`, and narrow
repository/canonical-pipeline ports.
