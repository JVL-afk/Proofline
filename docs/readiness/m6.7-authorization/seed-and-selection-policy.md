# PHASE1_OWNER_SEED_MANIFEST_V1 and Frozen Selection

**Policy state:** `OWNER_PARAMETERS_FROZEN_SOURCE_ARTIFACT_NOT_APPROVED`
**Authority:** ADR-0070 cohort mechanics; ADR-0074 fail-closed gate mechanics
**Real candidates present:** 0

## Business-only seed contract

The normative schema is `phase1-owner-seed-manifest-v1.schema.json`; the repository template is
empty. The maximum raw frame is exactly 100. Every candidate must contain only the business-level
fields necessary for:

- identity: public business name/aliases and provenance-backed identity evidence references;
- Texas eligibility: public business location/service-area evidence references;
- Commercial HVAC eligibility: public business-service evidence references;
- B2B relevance: public business-market/service evidence references;
- first-party host candidacy: one exact host plus evidence that it is first party;
- organization clustering: organization/shared-brand hint and lead-flow unit hint;
- provenance: source ID, immutable artifact reference/hash, locator, and observation time.

Person names, personal or professional contact values, people/contact fields, employee data,
opportunity/yield/score fields, inferred internal processes, revenue, CRM, conversion, response-time,
and lead-volume fields are prohibited. Extra schema fields fail validation.

## Eligibility and deduplication

1. Validate the exact schema, manifest source approval, provenance, and maximum frame before reading
   any candidate into the cohort controller.
2. Normalize business names for comparison without replacing the source value. Normalize the host
   using the existing M1 URL/host rules. Preserve exact original values and evidence references.
3. Require evidence for Texas scope, Commercial HVAC relevance, B2B relevance, operational/public
   business status, and a permitted first-party host. Ambiguity becomes mandatory identity review;
   it is not silently resolved.
4. Cluster candidates by exact normalized host, public identity evidence, shared organization/brand,
   and lead-flow unit. An exact host or the same organization plus the same public lead flow is one
   unit.
5. Apply the shared-brand/franchise cap of one. A location becomes a separate unit only when public
   evidence establishes a distinct public lead flow. Absence of evidence cannot establish one.
6. Freeze the complete eligible unit list and its canonical frame hash before seed generation.
   Opportunity-related content is never inspected for eligibility or selection.

## Seed ceremony and deterministic ordering

After the eligible frame hash is frozen, the assigned security/environment owner generates exactly
32 random bytes once using an approved operating-system cryptographic random generator. The seed is
encoded as 64 lowercase hexadecimal characters. The ceremony records the generator class, time,
opaque operator subject, frame hash, seed commitment `SHA-256(seed)`, and immutable approval ID.
Regeneration is prohibited; a failed ceremony invalidates the frame and requires an explicit
successor, never an unnoticed retry.

For every unit, calculate:

```text
ordering_key = SHA-256(
  "m6.7.phase1.seeded-order@1" + NUL +
  seed + NUL +
  frozen_frame_hash + NUL +
  stable_unit_key
)
```

Sort ascending by `ordering_key`, then by `stable_unit_key` as a collision tie-breaker. The first 24
units become slots 1-24. All remaining eligible units become the reserve order. Freeze the seed,
commitment, algorithm version, frame hash, selected order, reserve order, and configuration hash in
one immutable manifest before any opportunity research.

## Replacement

Replacement may consume the next frozen reserve only when a selected candidate is subsequently
proven cohort-ineligible under the pre-frozen reasons: outside Texas, not Commercial HVAC, not B2B,
closed/inactive, no permitted first-party host, or duplicate/shared-brand cap. Preserve the original
slot attempt, evidence, reason, reviewer, and replacement lineage.

Research failure, partial research, insufficient evidence, no supported opportunity, rejection,
cost, inconvenience, or commercial yield never permits replacement or reordering.

## Negative-outcome QA

Let `N` be the number of terminal negative outcomes. The review target is:

```text
0                                 when N = 0
N                                 when 1 <= N < 3
min(N, max(3, ceil(0.25 * N)))    when N >= 3
```

Use a separately frozen QA seed and the accepted M6.7A stratum-covering deterministic procedure.
The QA selection and seed are frozen before reviewer results are visible.
