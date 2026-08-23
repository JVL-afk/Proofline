# Bounded Phase 1 Seed Construction Authorization Scope

**State:** `READY_FOR_SEED_CONSTRUCTION_AUTHORIZATION`  
**Successor permission changed by this grant:** none  
**Real candidates currently present:** 0

This is a one-shot execution grant below the `REAL_BUSINESS_DISCOVERY` permission boundary. It may
process live business identities only after the owner signs the exact hash-bound grant. It neither
acquires a source nor permits a website request.

## Exact permitted operations

1. Receive exactly one owner-controlled, provenance-backed offline JSON artifact through the
   restricted Phase 1 input path. The artifact must validate against
   `phase1-seed-construction-input-v1.schema.json`, contain 24-100 business observations, and carry
   a construction/reuse attestation plus an immutable SHA-256 before parsing.
2. Scan keys and values before durable projection. Reject person/contact fields, contact-shaped
   values, opportunity/outcome data, revenue/headcount, internal-process claims, and unsupported
   fields. A rejected input produces content-free audit metadata only.
3. Apply the approved business eligibility, ambiguity, deterministic deduplication, shared-brand
   cap, frame-freeze, post-freeze CSPRNG seed, ordering, slot 1-24, and reserve rules using the exact
   approved generator.
4. Persist only the business-only input artifact, minimized business-only generated package,
   content-free audit hashes, and restricted private seed evidence in the accepted Phase 1 storage
   boundary under A-08/ADR-0071. No raw web response exists in this flow.
5. Emit a separate `FIRST_PARTY_DISCOVERY::<exact-host>` review stub for every selected/reserve
   host. Every stub remains `NOT_APPROVED`; no DNS, HTTP, robots, Terms, or host validation occurs.
6. Stop immediately after sealing the immutable candidate/source package. Owner review of that
   package is a later gate. No discovery, research, cohort execution, or replacement follows.

## Explicitly not permitted

No source search, directory/API query, DNS lookup, HTTP request, redirect, first-party website
access, robots/Terms retrieval, government registry, social/review/people/email source,
authentication, browser, AI, person/contact processing, opportunity analysis, research, Slot 1,
outreach, communication, form, booking, mailbox, CRM, or delivery operation is permitted. The
artifact must be supplied; this grant cannot manufacture provenance or acquire candidates.

This grant may write only bounded business-only artifacts and audit records to already accepted
Phase 1 storage. It cannot create or change AWS infrastructure, credentials, policies, routes,
permissions, or application delivery state. It expires seven days after signature or immediately
after one terminal construction attempt, whichever occurs first. Failed validation consumes the
attempt; retry requires an explicit successor authorization.

All seven M6.7 permissions remain independently `NOT_AUTHORIZED` before, during, and after the
operation. PRIMARY_A authentication remains an independent prerequisite for the later discovery
role gate and is not required or satisfied by this construction grant.
