# M6.7 Phase 1 A-17 Counsel Review Form

**State:** `BLOCKED_PENDING_QUALIFIED_LEGAL_REVIEW`
**Jurisdiction:** `US-TX`
**Scope:** 24 Commercial HVAC businesses; B2B inbound lead-response analysis; company-level public
research only; no person/contact projection or communication
**Legal conclusions recorded:** None

This form requests qualified legal review. Repository analysis and project-owner preferences are not
legal advice or approval. Counsel must validate the authority register and its currency as of the
review effective date.

## Questions

1. Does the exact operator and Phase 1 processing fall within TDPSA controller/processor scope, and
   which entity-only, public-information, small-business, processor or other exclusions apply by
   data class?
2. How is incidental public person/contact content inside restricted immutable source captures
   classified, and does preservation for source fidelity affect that classification?
3. Which notice, rights-request, correction, deletion, appeal, processor-contract or assessment
   duties, if any, apply before capture?
4. Is the no-extraction/index/search/projection design sufficient data minimization; if not, what
   exact control is required?
5. Do the provisionally approved 30/90/180/365/730-day periods, maximum 30-day backup overhang,
   tombstones or scoped renewable legal holds require changes or additional obligations?
6. Does Texas Business & Commerce Code Chapter 521 apply to any captured field or selected system;
   if so, which security, destruction, incident or notification control changes the design?
7. Does the Texas Data Broker Act or another Texas statute apply despite no sale, enrichment,
   person/contact record or communication; what factual trigger controls the answer?
8. May a future separately reviewed TDLR source be used for business eligibility, and under what
   field, person-exposure, terms, storage, reuse and automation restrictions?
9. May a future separately reviewed Texas Comptroller interface be used for targeted entity
   validation, and under what endpoint, terms, attribution, field, matching, storage and rate rules?
10. What exact terms, robots, copyright, access, capture, excerpt and reuse review is required for
    each first-party business host?
11. Does retaining source HTML/text for 90 days and evidence excerpts for 180 days require narrower
    capture, excerpt, access or licensing controls?
12. Do the preferred AWS region/services, subprocessors, backups, access model or incident process
    create notice, contract, transfer, breach-response or retention obligations?
13. Confirm the resulting research approval cannot authorize recipient discovery, commercial email,
    calling, forms, booking or other outreach, and identify the separate future review required.
14. What effective date, assumptions, exact policy/source/environment versions, expiry/review date
    and drift events bind or invalidate the opinion?

The supporting processing description and primary authority register are in
`legal-review-package.md`.

## Required response for every material issue

Counsel must create one immutable response record per material issue:

```text
issue_id
conclusion
authority_relied_on = [{citation, official_uri, version_or_access_date, proposition}]
assumptions
required_project_controls
unresolved_uncertainty
effective_at
review_expires_at_or_review_trigger
reviewer_opaque_identity
reviewer_credential_record_as_appropriate
state = APPROVED | APPROVED_WITH_CONTROLS | REJECTED | UNRESOLVED
recorded_at
record_hash
```

An answer such as “legal” or “approved” without the required issue records is insufficient. A-17
remains `BLOCKED_PENDING_QUALIFIED_LEGAL_REVIEW` until every material issue is resolved or explicitly
rejected and all required controls are bound to exact policy/source/environment revisions.
