# External source-adapter invariants

These invariants apply to every network-backed source adapter.

1. `RESPONSE_METADATA_CAPTURE_BEFORE_SCHEMA_VALIDATION`
   Safe transport and structural metadata must be durably sealed before schema,
   row, eligibility, or business-rule validation. A downstream failure must not
   erase HTTP status, allowlisted headers, declared and actual lengths, body
   SHA-256, JSON parse state, top-level JSON type, content-free key/field names,
   parser result, or failure stage. Raw bodies and field values remain forbidden.
2. `SOURCE_API_CONTRACT_PREFLIGHT`
   A source whose active transport or response contract has not already been
   proven must pass a bounded contract preflight before any one-shot acquisition
   authorization can be consumed.

These controls grant no source, discovery, research, person/contact, or delivery
authority.
