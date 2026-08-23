# M6.7 Phase 1 Seed Generator and Source Policy

**Review state:** `READY_FOR_SEED_POLICY_OWNER_APPROVAL`  
**Live businesses accessed:** 0  
**Authority granted:** none

This policy is bound to the accepted Phase 1 environment record at commit
`94c3bfa8f227562239b573533fd033902d1d3282`. It governs a later, separately authorized
construction operation; approving this policy does not authorize that operation.

## Eligibility

An eligible unit must have provenance-backed, business-level evidence for all of:

1. a resolvable public business identity;
2. operation or an explicit commercial service area in Texas (`US-TX`);
3. Commercial HVAC services (not residential-only HVAC and not an unrelated trade);
4. B2B/commercial customer relevance;
5. public operating status; and
6. one candidate exact first-party host.

The construction purpose is limited to identity and cohort eligibility for a later B2B inbound
lead-response analysis. It may not inspect or score opportunity content. Missing evidence is not
negative evidence. Ambiguous identity becomes `REVIEW_REQUIRED` and cannot enter the eligible
frame. Explicit ineligibility is limited to outside Texas, not Commercial HVAC, not B2B,
closed/inactive, or no permitted first-party host.

## Data contract and provenance

The maximum candidate frame is 100 and the cohort target is 24. Allowed fields are public business
name and aliases, Texas city/service area, exact first-party-host candidate, organization/shared-
brand and lead-flow-unit hints, business eligibility observations, business-only evidence refs, and
source provenance. Each provenance item binds a source ID, immutable artifact ref and SHA-256,
locator, and observed time.

Person/contact fields or values, names of natural persons, emails, phones, staff/employee blocks,
decision makers, opportunity/yield/score data, revenue/headcount, CRM, response/lead/conversion
metrics, and inferred internal processes or facts are prohibited. Extra or contact-shaped values
fail closed.

## Deterministic frame, seed and order

The generator normalizes exact hosts and comparison keys, orders candidates by their content-derived
reference, and then deduplicates exact hosts and organization-plus-lead-flow units. The shared-brand
cap is one unless business evidence establishes a distinct public lead-flow unit. The complete
eligible frame and canonical frame hash are frozen before the 32-byte OS-CSPRNG seed is generated.

Ordering uses `m6.7.phase1.seeded-order@1` and exactly:

```text
SHA-256(version || NUL || seed || NUL || frozen_frame_hash || NUL || stable_unit_key)
```

Ascending ordering key, then stable-unit-key collision tie-break, fixes slots 1-24 and the reserve.
The seed is generated once and held in restricted private evidence; the durable package exposes its
commitment. Ordering never changes. Outcome, research failure, cost, yield, or inconvenience never
allows replacement. Only a predeclared cohort-ineligibility finding may consume the next frozen
reserve while preserving attempted-slot lineage.

## A-09 exact-host review

Every enumerated `FIRST_PARTY_DISCOVERY::<exact-host>` record begins `NOT_APPROVED`. It separately
records Terms, robots, access restrictions, automated-access restrictions, capture/storage/reuse,
and copyright/contract review. Robots is a technical control, not legal authorization. Material
prohibition or material unresolved risk becomes `SOURCE_BLOCKED`; ambiguity becomes
`SOURCE_REVIEW_REQUIRED`. A batch signature may bind separately enumerated results, but never a
wildcard, omitted, expired, blocked, or uncertain host. Redirect destinations require independent
authorization.

Only metadata strictly necessary to establish business identity and eligibility may later be
collected under a separate discovery authorization. Research pages, people/contact processing,
opportunity analysis, AI, browser activity, authentication, forms, booking, mailbox interaction,
outreach, and communication are outside this policy. Government registries, social/review sites,
people/email services, authenticated sources, archives, and bypass techniques remain unapproved.

## Mandatory boundary

After a candidate/host package is constructed, execution must stop for owner artifact review.
Construction does not authorize public research, a slot, or any successor permission. All seven
M6.7 permissions remain independent and `NOT_AUTHORIZED`.
