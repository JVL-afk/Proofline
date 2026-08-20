# M6.7B A-09 Discovery and Research Source Policy Matrix

**Status:** `DRAFT_NOT_AUTHORIZED`
**Version:** `m67b-source-policy@draft-1`

`DISCOVERY_SOURCE` identifies candidate businesses. `RESEARCH_SOURCE` captures pages for M1
evidence. A source approved for one purpose is not approved for the other. Every source instance
must bind its exact host/API, terms-review evidence, robots result where applicable, data fields,
retention class, review date, expiry, rate budget, and accountable approval.

## Proposed categories

| Category | Class | Proposed state | Purpose/data | Access/authentication | Robots and terms | Crawl/rate budget | Browser | Storage/reuse | Person/contact extraction |
|---|---|---|---|---|---|---|---|---|---|
| Owner-approved seed manifest | Discovery input only | Conditional proposal | Candidate business name, Texas locality, public business URL, source provenance | Local immutable import; no network itself | Every row's upstream source must independently be approved | Maximum frame size and import count set in cohort release | Disabled | Store manifest/lineage under cohort policy | Prohibited |
| Texas Comptroller public Franchise Tax Account Status API | Discovery verification only | Proposed; endpoint/API terms review required | Entity name and right-to-transact status | Exact official public API only; no screen scraping or authenticated taxpayer functions | Official API documentation/terms must be reviewed and versioned | One bounded lookup per candidate plus approved retry; exact quota required | Disabled | Business verification fields only; restricted raw response | Prohibited |
| TDLR ACR public license search | Discovery/vertical verification | Hold pending counsel, terms, and business-only field mapping | ACR license/business relevance; source may expose licensee individuals | Public search only if exact automated access method is approved; no login | Per-site terms and field-level privacy review mandatory | Not set; therefore disabled | Disabled | No individual-license record may enter cohort/domain records | Prohibited |
| Ordinary first-party business website | Research | Candidate for Phase 1 approval | Public business pages needed for M1 evidence | Unauthenticated HTTP/HTTPS, ports 80/443, approved exact host | Per-domain terms review; RFC 9309 policy below | Max 5 pages, depth 1, 1.5 MB/run, 512 KB/response, 30 seconds/run, max 3 attempts, one request at a time/domain, minimum 2 seconds between requests | Disabled | Restricted immutable captures and approved derivatives only | Prohibited |
| Linked first-party subdomain | Research | Disabled initially | Potentially relevant first-party content | Would require separate exact-host release | Separate terms/robots/security review | None while disabled | Disabled | None | Prohibited |
| First-party public PDF/document | Research | Disabled initially | Static brochure/service information | Would require content-type and copyright review | Separate source/version approval | None while disabled | Disabled | None | Prohibited |
| Search-engine or maps API | Discovery | Disabled; provider unselected | Candidate URLs/business metadata | Contracted API only; never consumer-page scraping | Provider contract, data use, retention, region, and cost approval | None until A-10/A-18 approval | Disabled | Per-provider restrictions | Prohibited |
| Commercial business directory/API | Discovery | Disabled; provider unselected | Candidate business metadata | Contracted API only | Provider terms, provenance, correction, retention, and data-sale review | None until approved | Disabled | Per-provider restrictions | Prohibited |
| Trade-association/member directory | Discovery | Disabled initially | Candidate business/member data | Public page/API only after source-specific review | Terms, copyright, robots, and member-data purpose review | None until approved | Disabled | None | Prohibited |
| Social network, review platform, forum, or user-generated profile | Either | Prohibited Phase 1 | Third-party/UGC claims | None | Not approved | Zero | Disabled | None | Prohibited |
| Web archive, cache, mirror, or data broker dump | Either | Prohibited Phase 1 | Historical/copied content | None | Not approved | Zero | Disabled | None | Prohibited |
| Authenticated, paywalled, access-controlled, or session-only content | Either | Prohibited | Any | No login, credential, token, or session use | Access restriction is a hard block | Zero | Disabled | None | Prohibited |
| CAPTCHA-bypassed, rate-limit-bypassed, obfuscated, or adversarially obtained content | Either | Prohibited | Any | No bypass | Hard block and safety incident | Zero | Disabled | None | Prohibited |
| Form, chat, booking, mailbox, `mailto:`, telephone, SMS, or submission endpoint | Research action | Prohibited | Would create external side effect | No state-changing request | Hard block | Zero | Disabled | None | Prohibited |

## Robots and terms policy

- Use a declared crawler product token and truthful User-Agent describing purpose and operator
  contact page. Do not impersonate a browser.
- Fetch `/robots.txt` for an already source-approved host. Follow parseable rules for the product
  token and `*` group under RFC 9309.
- A robots 5xx/network failure is complete disallow. A 4xx/no-file response does not itself grant
  source approval; access proceeds only if the domain's separate terms/source review is approved.
- Malformed or ambiguous policy fails closed for that host pending review. Cache no longer than 24
  hours unless the standard's unreachable-server exception and project policy both allow it.
- Robots permission is a machine-use signal, not legal authorization or access control. Site terms,
  copyright, privacy, and contractual restrictions remain separately reviewed.
- Terms/source review expires on the release's review interval or immediately upon detected terms,
  robots, ownership, purpose, or access-method drift.

## Source-instance approval record

Each enabled instance requires:

```text
source_instance_id
source_class = DISCOVERY_SOURCE | RESEARCH_SOURCE
category
exact_authority_or_api
permitted_paths_or_operations
prohibited_paths_or_operations
data_fields
purpose
terms_uri + terms_hash + reviewed_at + reviewer
robots_policy_version + robots_result_hash
retention_policy_version
rate_budget
start_at + expires_at
approvals
configuration_hash
state = PROPOSED | APPROVED | SUSPENDED | EXPIRED | REVOKED
```

No category or instance in this draft is approved. The first cohort cannot be selected until enough
discovery instances are approved and the first website cannot be researched until its research
instance is approved.
