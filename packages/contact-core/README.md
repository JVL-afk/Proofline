# Contact Core

Owns the M6 synthetic identity, verification, eligibility, suppression, exact-send, authorization,
mock-delivery, receipt, reply, and first-party statement contracts. It consumes exact approved M5
revisions read-only and emits re-analysis requests; it cannot mutate M1-M5 truth.

Forbidden responsibilities: live enrichment or verification, real recipient or sender data, provider
credentials, bulk/sequence delivery, autonomous follow-up, live AI, CRM/calendar/telephone/SMS, or
M7 behavior.

Public interfaces are `ContactApplicationService`, immutable domain records, and the ports in
`opintel_contact.ports`. The package depends inward on M0 identity/clock contracts and M5 contracts.
