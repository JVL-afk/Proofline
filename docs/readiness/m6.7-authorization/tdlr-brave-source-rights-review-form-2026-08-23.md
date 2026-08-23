# M6.7 Phase 1 exact-source rights review

**State:** `BLOCKED_PENDING_QUALIFIED_SOURCE_RIGHTS_REVIEW_AND_LOCATOR_CONTRACT_ACCEPTANCE`

This is a narrow factual review form, not a request for a new product design or a legal conclusion
from Codex. No license row, candidate, business website, DNS record, or search result was acquired
while preparing it.

## Exact source 1 — TDLR All Licenses

- Dataset: `TDLR - All Licenses`, resource `7358-krk7`.
- Publisher: Texas Department of Licensing and Regulation.
- Landing page: `https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7`.
- Documented API: `https://data.texas.gov/api/v3/views/7358-krk7/query.json`.
- Current schema has 18 fields. It includes business name/location/license fields, but also owner
  name, telephone, mailing-address and geospatial/contact-shaped fields.
- The portal describes open data generally as freely usable, reusable and redistributable. The
  Texas ODP publishing guide separately explains that a publisher may leave a dataset with no
  specified license and that a license reduces uncertainty for consumers. No dataset-specific
  license was established for `7358-krk7` in this review.

Proposed field-limited access, if approved, queries only `license_type`, `license_number`,
`business_county`, `business_name`, `business_city_state_zip`,
`license_expiration_date_mmddccyy`, and `license_subtype`. It rejects every natural-person,
sole-proprietor or ambiguous name before durable projection and admits only a high-confidence legal
entity suffix. It never queries or stores owner names, telephone numbers, street/mailing addresses,
or geospatial/contact fields.

Qualified reviewer must record:

1. May this exact dataset be queried and the listed business-only fields stored/reused for the
   bounded Phase 1 seed roster despite the missing/unspecified dataset-specific license?
2. What authority and assumptions support the conclusion?
3. What attribution, retention, or other required control applies?
4. `APPROVED`, `APPROVED_WITH_CONTROLS`, or `REJECTED`.

## Exact source 2 — Brave Search API host locator

- Endpoint: `https://api.search.brave.com/res/v1/web/search`.
- Terms: `https://api-dashboard.search.brave.com/terms-of-service`, observed revision
  11 February 2026.
- Proposed use: one deterministic plain-Web query per admitted TDLR business; no AI/Answers
  endpoint; transiently inspect only the top result to derive one candidate host.
- General terms prohibit non-transitory storage/cache/database creation from Search Results. Brave
  states that storage requires a plan expressly granting storage rights. The API also grants no
  rights to downstream webpage content.
- Proposed bound: at most 120 logical requests, USD 0.60 before any advertised account credit,
  concurrency one, and no snippet/title/result-body persistence.

Qualified reviewer must record:

1. Does storing only the derived exact host plus content-free API provenance comply with the
   applicable plan/order form, or is an express storage-rights plan required?
2. May that derived host be used to perform a later, separately approved exact-host source review?
3. What attribution, deletion, contract, privacy, or other required control applies?
4. `APPROVED`, `APPROVED_WITH_CONTROLS`, or `REJECTED`.

The owner must separately accept the Brave API contract and the maximum USD 0.60 source cost only
after a qualified review permits this use. An API key must then be placed in AWS Secrets Manager;
it must never be pasted into chat or committed to Git.

## Eliminated source

The interactive TDLR License Search interface is not required. The Open Data API supplies the
license fields needed for the primary identity anchor, while the interactive interface adds
natural-person exposure and automated-access uncertainty without a required field.

## Invariants

Every exact first-party host remains independently reviewed. A locator result is not a source
approval. `REAL_PUBLIC_RESEARCH` and the five person/contact/shadow permissions remain
`NOT_AUTHORIZED`. No live roster acquisition can be signed until both source decisions above are
resolved and bound into a successor package.
