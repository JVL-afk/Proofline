# Phase 1 A-09 Source Approval Package

**Status:** `OWNER_SOURCE_CATEGORY_PREFERENCE_RECORDED_EXACT_INSTANCES_NOT_APPROVED`
**Browser:** `DISABLED`
**Live source operations performed while preparing this package:** 0

The owner-approved source-category preference avoids a general search provider. After discovery
source authority exists, the system constructs a bounded, provenance-backed Texas Commercial HVAC
candidate manifest through the approved mechanism; the system freezes a seeded
selection and uses only each selected business's exact unauthenticated first-party website. Public
government sources remain optional, targeted identity/eligibility validators and are
`NOT_APPROVED_PENDING_SEPARATE_REVIEW` until their exact interface, terms and field treatment are
approved. This category preference does not approve a seed artifact, host or source instance and
does not satisfy A-09.

## Minimum source instances

| Proposed source ID | Kind | Exact identity | Access | Terms review | Robots | Rate/work budget | Storage/reuse | Approval owner | Effective/expiry |
|---|---|---|---|---|---|---|---|---|---|
| `PHASE1_OWNER_SEED_MANIFEST_V1` | `DISCOVERY_SOURCE` | Future immutable signed artifact ID and SHA-256; no URL | Offline read-only CSV/JSON import; no person/contact fields | Owner must attest provenance, permitted reuse and anti-cherry-picking construction | Not applicable; no network | Candidate-frame cap must be approved; zero HTTP attempts | Store exact immutable manifest under restricted access; cohort construction only; no contact reuse | Project owner + privacy/data owner + qualified legal reviewer | Explicit start/expiry required; currently unresolved |
| `FIRST_PARTY_DISCOVERY::<exact-host>` | `DISCOVERY_SOURCE` | One exact lower-case/punycode host for each manifest candidate considered for a slot | HTTPS `HEAD`, or bounded `GET` only if `HEAD` is unavailable; ports 443/80 per M1 policy | Exact site terms/source review required before operation | RFC 9309 plus project fail-closed rule; 5xx/unreachable denies access | Recommended allocation: at most one logical validation per ultimately selected company, max three attempts, one concurrent request/host, minimum two seconds | Store safe status/host/provenance; body only if a GET is necessary and then under restricted snapshot policy; no contact extraction | Privacy/data owner + source/terms reviewer | Exact times required per host; earliest bound expiry wins |
| `FIRST_PARTY_RESEARCH::<exact-host>` | `RESEARCH_SOURCE` | The exact first-party host frozen for each of the 24 selected businesses | Unauthenticated HTTPS GET/HEAD; static public business pages only | Separate research-purpose terms approval required even if discovery host was approved | RFC 9309 plus project fail-closed rule | Recommended maximum four logical page GETs/business after the discovery allocation; max three attempts/logical fetch; one request/host; minimum two seconds | Restricted immutable captures; 90-day proposed raw retention; bounded excerpts/lineage only; no person/contact projection | Privacy/data owner + project owner + source/terms reviewer | Created only after cohort freeze; exact start/expiry required |

The recommended allocation is 24 discovery validations plus at most 96 research page fetches, which
preserves the global 120 logical-fetch, 360-attempt and 36 MB ceilings. A host needing more than four
research pages receives a terminal bounded/partial outcome unless a separately approved successor
budget reduces another allocation; the cohort cap cannot silently increase.

Exact first-party domains cannot be listed before the approved source mechanism constructs the seed
artifact. Each domain must become its own immutable source entry; wildcards such as `*.example.com`
are prohibited. Redirect targets require their own exact source approval or are rejected.

Terms/robots URLs, normalized hosts, retrieval timestamps, accessibility, source hashes, and
technical restrictions are collected automatically after the applicable source authority exists.
The required human conclusion remains explicit per host. One signed batch may bind many separately
enumerated host conclusions, but no blocked, uncertain, expired, or omitted host inherits approval.

The seed artifact must validate against `phase1-owner-seed-manifest-v1.schema.json`, contain no more
than 100 business-level candidates, preserve provenance for every eligibility claim, and contain no
person/contact or opportunity-selection field. Its exact artifact/hash, construction provenance,
storage/reuse terms, accountable approvals, effective time and expiry remain unapproved.

## Optional government validation sources — disabled pending exact review

| Proposed source ID | Kind | Exact official entry point | Intended purpose | Current state | Required review before any system access |
|---|---|---|---|---|---|
| `TX_TDLR_ACR_LICENSE_SEARCH_V1` | `DISCOVERY_SOURCE` only | `https://www.tdlr.texas.gov/LicenseSearch/` on host `www.tdlr.texas.gov` | Targeted Commercial HVAC licensing/identity ambiguity validation | `NOT_APPROVED_PENDING_SEPARATE_REVIEW`; rate budget 0 | Confirm exact automated endpoint, fields, terms, robots, licensee-person exposure, business-only projection, storage/reuse and whether automated access is allowed |
| `TX_COMPTROLLER_ACCOUNT_STATUS_V1` | `DISCOVERY_SOURCE` only | `https://comptroller.texas.gov/taxes/franchise/account-status/` on host `comptroller.texas.gov` | Targeted entity identity/status validation after a candidate is already known | `NOT_APPROVED_PENDING_SEPARATE_REVIEW`; rate budget 0 | Approve exact public API endpoint/version, authentication status, terms, fields, entity matching, storage/reuse, and rate limit |

These government sources are not required if the owner seed and first-party evidence establish
cohort eligibility and identity without material ambiguity. Enabling either consumes the existing
120/360 workload envelope unless an approved successor reallocates it; it does not add capacity.

Official source descriptions were recorded on 2026-08-20 from the Texas Department of Licensing
and Regulation ACR page (`https://www.tdlr.texas.gov/acr/`) and Texas Comptroller account-status page
(`https://comptroller.texas.gov/taxes/franchise/account-status/`). Those descriptions do not approve
automated use.

## Explicitly prohibited source categories

- Social networks and social-profile data.
- Review/rating platforms.
- People databases, professional-person aggregators and contact-enrichment sources.
- Email-finder, pattern-generation or verification services.
- Search/maps APIs or commercial directories unless added through a successor A-09 review.
- Authenticated, account-only, access-controlled, paywalled or CAPTCHA-gated directories.
- Browser fallback, rendered-session reuse or browser credentials.
- Forms, booking, chat, mailbox, calendar or other interactive/state-changing endpoints.
- Archives/caches, robots/rate/access bypass, adversarial access or credential/session borrowing.

## Exact per-source approval record

Every enabled instance must bind:

```text
source_id
source_kind = DISCOVERY_SOURCE | RESEARCH_SOURCE
exact_scheme + exact_host + allowed_paths
purpose
access_method
public_and_unauthenticated = true
terms_uri + terms_hash + reviewer + reviewed_at
robots_policy_version + observed_robots_hash + fail_closed_outcome
logical_fetch_cap + attempt_cap + byte_cap + concurrency + delay
allowed_data_categories
storage_policy + reuse_policy + retention_policy
person_contact_extraction_allowed = false
browser_allowed = false
interactive_operations_allowed = false
accountable_approval_ids
effective_at + expires_at
configuration_hash
```

No unknown source, host, redirect, path class, or expired record is usable.
