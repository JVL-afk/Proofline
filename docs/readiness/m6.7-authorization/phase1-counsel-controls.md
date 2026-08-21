# Phase 1 Counsel-Control Implementation

**Recorded result:** `A-17 = APPROVE_WITH_CONTROLS`

**Counsel classification:** `CURRENT_FACT_BOUND_COUNSEL_CONCLUSION`

**Source policy:** `APPROVED_WITH_PER_HOST_REVIEW`

**Live authority granted:** None

The attorney-provided result is preserved in `a17-attorney-result-2026-08-21.json`. The independent
statutory register verifies only the cited propositions against current official Texas text; it is
not a replacement opinion and does not broaden counsel's conclusion.

## Implemented modifications

1. `EPHEMERAL_RAW_FETCH -> DETERMINISTIC_MINIMIZATION -> DURABLE_MINIMIZED_CAPTURE` replaces
   ordinary durable raw-page storage. Safely identifiable email addresses, telephone numbers,
   structured contact fields, and structured person/staff contact blocks are removed. Human-name
   detection is not represented as complete.
2. Required business evidence markers must survive minimization. If they do not, the output is a
   content-free `QUARANTINE_AND_REVIEW` record.
3. A-08 binds every governed class across primary stores, replicas, object versions, backups, and
   derived stores to an exact retention period, destruction method, and effective maximum including
   backup overhang.
4. The Chapter 521 workflow records detection, sensitive-information assessment, breach
   determination, affected-subject determination, notification decision, verified deadline
   provenance, and an immutable hash. It sends no notification. Missing facts or authority produce
   `LEGAL_REVIEW_REQUIRED`.

## Source boundary

No blanket host approval exists. Each `FIRST_PARTY_RESEARCH::<exact-host>` record must bind a
completed review of terms, robots, access restrictions, automated-access restrictions, intended
capture/storage/reuse, and copyright/contract risk. Robots is a technical input and not legal
authorization. Material prohibition or unresolved material risk produces `SOURCE_BLOCKED`.

## Mandatory re-review

Fresh qualified review is required before person/contact extraction, enrichment, people/email
databases, third-party personal-data sourcing, sale or transfer of personal data, outbound outreach,
material organization-size/revenue/business-structure change, or another material processing change
specified by counsel.

ADR-0071 remains proposed because no deployed environment/storage evidence or opaque identity
binding exists. A-08 is approved as policy but is not live-effective. Discovery and research remain
`NOT_AUTHORIZED`.
