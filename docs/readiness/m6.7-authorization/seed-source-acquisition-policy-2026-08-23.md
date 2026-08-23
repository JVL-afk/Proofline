# M6.7 Phase 1 Offline Seed Source Acquisition

**State:** `READY_FOR_SEED_SOURCE_ACQUISITION_AUTHORIZATION`  
**Source class:** `OWNER_CONTROLLED_FIELD_LIMITED_OFFLINE_BUSINESS_ROSTER_V1`  
**Network source access:** 0

## Acquisition method

The sole permitted source is one owner-controlled offline roster exported or compiled before system
ingestion. It must contain the complete predeclared source frame of 24-100 observations and carry
row-level provenance. The system may receive it through the restricted Phase 1 input boundary,
minimize it, and construct the two approved seed-input files. It may not search for, scrape, query,
or enrich candidates.

The roster may originate only from records the accountable owner is authorized to use and reuse.
Its exact artifact SHA-256, origin, construction method, permitted-use basis, completeness claim,
and accountable source-review conclusion must be recorded before any parse. If those facts cannot
be attested, the source instance is `SOURCE_BLOCKED`.

This is an A-09 `DISCOVERY_SOURCE` substage, but not the `REAL_BUSINESS_DISCOVERY` permission. It is
`READY_PENDING_EXACT_INSTANCE_ATTESTATION`; the signed owner grant activates only the named offline
class and no other source. Terms and robots are `NOT_APPLICABLE` only because the system performs no
network access. Any third-party license, contract, export restriction, or uncertain reuse right
must be recorded and resolved by the accountable privacy/source reviewer; material uncertainty is
`SOURCE_REVIEW_REQUIRED`, not inferred approval.

## Data boundary and minimization

Only public business identity, Texas/Commercial-HVAC/B2B eligibility evidence, candidate
first-party-host string, and provenance may survive. Before durable projection, the transient input
is scanned deterministically for prohibited fields, email/phone shapes, natural-person/staff blocks,
and unsupported structure. Field-limited export is preferred. If incidental person/contact data is
present, it is never indexed, searched, scored, logged, measured, or written to the output. If safe
field projection cannot be proven, the whole attempt stops with content-free audit metadata; raw
content is neither quarantined durably nor copied to review artifacts.

The durable outputs are exactly:

- `local-data/m6.7/seed-construction/input/phase1-seed-input.json`
- `local-data/m6.7/seed-construction/input/phase1-seed-input-attestation.json`

The output artifact must validate against `phase1-seed-construction-input-v1.schema.json`. The
attestation binds its SHA-256 computed before seed-construction parsing, count, acquisition method,
complete provenance, prohibited-field absence, accountable actor, permitted use/reuse, and validity.

## Anti-cherry-picking

The imported roster must be the complete predeclared source frame, capped at 100 before eligibility
filtering. Acquisition and rejection may use only identity, Texas scope, Commercial HVAC, B2B,
operating status, exact-host candidacy, ambiguity, duplicate/shared-brand, and schema/provenance
rules. Website quality, lead handling, value, sales ease, complaints, audit/demo prospects,
opportunity, or any outcome may not be observed or used. Source order and every exclusion are
preserved in the audit lineage. No retry or alternate roster is permitted after results are known.

## Frozen envelope

- Input artifacts: 1; records: 24-100; terminal attempts: 1.
- Maximum input size: 5,000,000 bytes; maximum durable output size: 5,000,000 bytes.
- DNS/HTTP/browser/provider requests: 0; retries: 0; concurrency: 1.
- Rate: one local read and one deterministic projection; no external request rate.
- Monetary cost: USD 0; AI cost: USD 0.
- Effective only after exact owner signature; expires after seven days or the first terminal attempt.
- Existing Phase 1 kill switch or suspension blocks start, parsing, projection, and retry. A trip
  during processing discards transient input, writes content-free audit only, and consumes the grant.

The acquisition stage stops after the two output files are sealed. It does not consume the existing
seed-construction grant, generate a CSPRNG seed, order candidates, approve hosts, run M1-M5, or
authorize any successor permission.

PRIMARY_A independent authentication is not required for this source-acquisition substage or the
subsequent candidate-package owner review. It remains mandatory before the later
`REAL_BUSINESS_DISCOVERY` role release; OWNER_ACTOR cannot satisfy it.
