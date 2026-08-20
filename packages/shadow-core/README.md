# Shadow Validation Core

M6.7A owns synthetic cohort policies, frozen selections, shadow runs, canonical M1-M5 stage
lineage, outcome projections, review/QA assignments, metrics, costs, safety stops, and immutable
M6.8 evidence packages.

It consumes existing M1-M5 statuses through a declared canonical-pipeline port. It does not own or
mutate their canonical records. It contains no real-data, person/contact, AI, sender, delivery,
provider, network, or M6 command port. Phase 1 cannot progress beyond
`CONTACT_PHASE_NOT_AUTHORIZED`.

Public interfaces are the immutable domain contracts, `ShadowValidationService`, and narrow
repository/canonical-pipeline ports.
