# TDLR live seed-roster source analysis

**State:** `BLOCKED_PENDING_TDLR_EXACT_SOURCE_REVIEW_HOST_LOCATOR_SOURCE_REVIEW_AND_PRIMARY_A_AUTHENTICATION`

This review used only official-source descriptions already captured in the repository. It made no
DNS, HTTP, browser, provider, AWS or other live request. That constraint matters: the repository
does not contain the exact Texas Open Data **TDLR - All Licenses** dataset URL/resource identifier,
schema, field dictionary, API/export contract, reuse terms, or a verified discriminator between a
business entity and a natural-person licensee. Those omissions are material under A-09 and the
attorney-required field-limited/minimized capture design, so the source is blocked rather than
presumed reusable.

## What captured TDLR evidence can and cannot prove

| Approved roster dimension | Current support | Reason |
|---|---|---|
| `public_business_name` | Not verified | No captured exact dataset schema or business-entity discriminator. |
| Texas location/service area | Not verified | Regulator jurisdiction does not prove a location field or an asserted service area. |
| HVAC contractor/license evidence | Program-level relevance only | The captured ACR page establishes licensing relevance, but not exact license class/status fields for the proposed dataset. |
| Operational evidence | Not supported | A license status, even if later verified, is not equivalent to current business operation. |
| Organization/franchise grouping | Not supported | No captured source field supports it. |
| First-party host | Not supported | No captured TDLR field or reviewed locator source provides it. |
| B2B evidence | Not supported | Licensing alone does not establish B2B market focus. |
| Commercial-HVAC evidence | Not supported beyond general ACR relevance | Exact commercial scope needs another approved source. |

The primary source therefore cannot presently produce a schema-complete roster. The narrowest
candidate route, after review, is: one exact TDLR Open Data dataset instance as the primary identity
anchor; targeted official TDLR verification only for predeclared ambiguities; one exact reviewed
host-locator source if the dataset lacks a verified first-party URL; and separately reviewed exact
first-party hosts for only the missing business-level eligibility dimensions. A generic search
engine, maps search, directory wildcard or “public web” grant is prohibited.

## Frozen acquisition rule after blockers close

The exact dataset revision, query/export parameters and observation cutoff are frozen before record
content is classified. Natural-person and unclassifiable records are rejected before durable
projection. The system filters only verified ACR-license, Texas, business-entity and permitted
status fields, sorts on an approved immutable source record identifier, considers at most 500
predeclared records, and takes at most 100 complete eligible business observations. It preserves
all exclusions and ambiguities. Host evidence may be filled only through one exact approved locator
source and separately reviewed exact hosts.

No website quality, lead handling, value, contactability, opportunity, revenue, headcount, customer
complaint or outcome signal may affect inclusion or ordering. There is no outcome-based replacement.
The live substage ends after sealing exactly:

- `local-data/m6.7/seed-source-acquisition/input/offline-business-roster.json`
- `local-data/m6.7/seed-source-acquisition/input/offline-business-roster-attestation.json`

Network access then stops. Neither the already-authorized offline acquisition grant nor the bounded
seed-construction grant is consumed automatically.

## Privacy and execution boundary

Every response follows `EPHEMERAL_RAW_FETCH -> DETERMINISTIC_MINIMIZATION -> DURABLE_BUSINESS_ONLY_ROSTER`.
Names of natural people, individual-license records, emails, telephone numbers, staff/contact blocks
and every prohibited opportunity/internal-process field are excluded from roster records, logs,
metrics and review artifacts. Unsafe or unprovable minimization produces only a content-free audit
and quarantine outcome. It never falls back to raw durable storage.

After source approval, the proposed maximum is 500 source records considered, 120 logical HTTP
requests, 360 attempts, 36,000,000 aggregate response bytes, three attempts per logical request,
concurrency one, and at least two seconds between requests to the same host. AI and browser sessions
remain zero; paid sources are blocked and the monetary source cost is USD 0. The recommended release
validity is seven days. The kill switch must begin and end `TRIPPED` and blocks new requests and
retries immediately.

## Authority and remaining blockers

Live acquisition from TDLR or another public business source has `REAL_BUSINESS_DISCOVERY`
semantics under ADR-0069. A temporary substage cannot be used to evade that permission. If all
source blockers are cleared, one exact release may authorize only this one terminal roster attempt;
`REAL_PUBLIC_RESEARCH` and the other five successor permissions remain `NOT_AUTHORIZED`.

Because this is the previously frozen discovery-role release gate, PRIMARY_A must independently
authenticate and reconcile to `INDEPENDENT_SECOND_REVIEWER` before the live release is signed.
OWNER_ACTOR cannot substitute.

The package is not approvable until all of the following are complete:

1. Capture and review the exact TDLR dataset resource ID/URL, schema, export/API method, terms,
   license/reuse rules and field definitions.
2. Prove the business-entity discriminator and reliable pre-durable exclusion of natural-person
   license records.
3. Select and review one exact first-party-host locator source, unless a reviewed TDLR field supplies
   that host.
4. Complete the exact per-source terms, robots, access, storage/reuse and copyright/contract reviews.
5. Complete PRIMARY_A independent authentication and reconciliation.
6. Generate a new immutable, hash-bound `REAL_BUSINESS_DISCOVERY` release.

No owner approval phrase is emitted while those material blockers remain.
