# OSM Nominatim first-party-host locator review

**State:** `READY_FOR_COMPLIANT_HOST_LOCATOR_OWNER_ACCEPTANCE`

## Selected exact source

The preferred locator is the OpenStreetMap Foundation public Nominatim Search API at the exact
endpoint `https://nominatim.openstreetmap.org/search`, using OpenStreetMap data under ODbL 1.0.
The endpoint receives only a frozen candidate's public business name and Texas city/service-area
binding. It may return at most three POI results. The deterministic projector considers only the
business name, Texas state markers, OSM type/ID and `extratags.website`; it retains only a safe
hostname plus content-free provenance.

This is preferable to an ordinary search API because OSM expressly licenses database use and its
public Nominatim policy permits small one-time bulk geocoding when limited to one thread/machine,
at no more than one request per second, with results cached. Internal use does not require external
publication of the derived database. Attribution remains mandatory. The project adopts a stricter
two-second delay, one attempt per frozen candidate, 100-request/5 MB ceilings and no retry.

There is no account, credential, subscription or paid plan. The owner acceptance is a governance
acceptance of ODbL 1.0, the OSMF Terms of Use and the Nominatim Usage Policy for this exact bounded
use. It is not a generic public-web authorization. Nominatim is a switchable community service with
no completeness or availability guarantee; an incomplete result remains `NOT_FOUND` and cannot be
silently replaced through another source.

## Rights, access and A-09

- **Persistent storage:** permitted for the internal hostname/provenance projection subject to
  ODbL and attribution. The public service policy requires caching, rather than transient-only use.
- **Attribution:** every sealed roster/source package must preserve “Copyright OpenStreetMap
  contributors; data available under ODbL 1.0” and the exact endpoint/access timestamp.
- **Share-alike:** private internal use does not itself require publishing the derived database.
  Any later public distribution or external transfer requires a fresh ODbL analysis.
- **Retention/deletion:** only the approved business-host projection and provenance enter governed
  Phase 1 stores. A-08 retention/destruction applies. Raw API bodies stay ephemeral.
- **Robots:** not applicable to this documented API endpoint. The Usage Policy is the controlling
  technical access rule.
- **A-09:** `APPROVABLE_WITH_CONTROLS_PENDING_OWNER_SOURCE_ACCEPTANCE`. The locator result does not
  approve a destination host; every projected hostname remains separately
  `PENDING_EXACT_HOST_A09_REVIEW`.
- **Qualified review:** not required by the frozen source-governance model because the written ODbL
  license, geocoding guideline and public API policy expressly cover this internal cached use. A
  qualified review is required if the project later publishes/transfers the database or changes
  the source/access method.

## Deterministic anti-cherry-picking algorithm

Process the complete frozen TDLR business frame in source order. Submit exactly one request for
each record, whether or not earlier candidates already provide 24 hosts. Normalize only punctuation,
case and a terminal legal-entity suffix for name comparison. Require Texas in the returned address.
Project `extratags.website` only when exactly one safe distinct hostname survives. Multiple hosts,
no host, social profiles, IP literals, credential-bearing URLs and malformed URLs remain
`AMBIGUOUS` or `NOT_FOUND`. Preserve those results in position; never replace them based on site
quality, contactability, opportunity, sales value or expected outcome.

The locator does not fetch the projected host. It performs no DNS lookup, Terms/robots review or
first-party content research. Those operations remain later exact-host gates.

## Privacy/minimization boundary

`EPHEMERAL_NOMINATIM_RESPONSE -> DETERMINISTIC_FIELD_LIMITED_PROJECTION -> DURABLE_BUSINESS_HOST_EVIDENCE`

The response may contain addresses, phone/email/contact tags or natural-person material. The
projector ignores every field except the enumerated business identity, state, OSM ID and
`extratags.website`. It stores neither the raw response nor `display_name`, address, contact tags,
URL path/query, logs, metrics or error payloads. Invalid/unsafe input yields only a content-free
quarantine or ambiguity state. Synthetic tests exercise contact-shaped responses and prove that
email, phone, staff data and URL paths cannot enter the durable projection.

## Manual versus automated route

| Criterion | Controlled human generic-web locator | Exact Nominatim projector |
|---|---|---|
| Contract clarity | Poor: each search/directory/site has separate or ambiguous storage terms | Strong: ODbL plus a published one-time-use policy |
| Time to authorization | Slow because each source needs review | Immediate after one owner source acceptance |
| Reproducibility | Lower; reviewer judgment and result ordering vary | Frozen query, ordering and projection |
| Provenance | Heterogeneous URLs/screenshots | Stable OSM type/ID, response hash and timestamp |
| Privacy exposure | High; pages commonly expose people/contact fields | Field-limited API projection |
| Cost | Usually zero but labor intensive | USD 0 |
| Engineering | Manual form and reviewer controls | Small deterministic projector already tested |

A human may later review an `AMBIGUOUS` outcome only through a separately approved exact source;
generic manual browsing is not a fallback. The automated Nominatim route is therefore selected.

## References captured for owner review

- OSMF Nominatim Usage Policy: `https://operations.osmfoundation.org/policies/nominatim/`
- OpenStreetMap copyright and ODbL notice: `https://www.openstreetmap.org/copyright`
- OSMF geocoding guideline: `https://osmfoundation.org/wiki/Licence/Community_Guidelines/Geocoding_-_Guideline`
- Nominatim Search API: `https://nominatim.org/release-docs/latest/api/Search/`
- Nominatim output fields: `https://nominatim.org/release-docs/latest/api/Output/`
- OSM `website=*` field definition: `https://wiki.openstreetmap.org/wiki/Key:website`

No candidate, Nominatim, TDLR, DNS, website or other live source request was made during this
review. Brave remains rejected and is not a fallback.
