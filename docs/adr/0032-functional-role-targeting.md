# ADR-0032: Functional-role targeting and anti-impersonation

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product owner and architecture owner

## Context

M5 needs a relevant audience without collecting people or fabricating familiarity.

## Decision drivers

- Avoid personal-contact discovery and regulated data.
- Prevent employment assertions and impersonation.
- Keep targeting deterministic and narrow.

## Considered options

1. Approved functional-role taxonomy with `NO_PERSON_IDENTIFIED`.
2. Scraped or enriched individual contacts.
3. Unstructured model-selected personas.

## Decision

Initial priority is service operations, commercial service, dispatch/intake, owner/executive,
business development, then unknown relevant role. Selection expresses functional relevance only
and never asserts that the business employs the role. M5 never discovers or stores a person,
address, phone, email, social profile, relationship, referral, testimonial, or recipient.

## Consequences

Sender identity remains an explicit human-verified slot and production identity governance is
deferred.

## Validation

Role priority, person-marker, PII, fake relationship, testimonial, urgency, request, and
impersonation hostile tests apply.

## Revisit triggers

Individual targeting, enrichment, verified sender profiles, or real recipient data is proposed.
