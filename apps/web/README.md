# M1 Diagnostic Web UI

## Ownership

Application/web team.

## Responsibilities

- Accept a local development token in session storage.
- Create a known-business URL permit and idempotent research command through the API.
- Poll research state and display pages, snapshot links, and evidence provenance.

## Forbidden responsibilities

- Database access, provider credentials, crawling, raw HTML rendering, production identity, or
  product functionality beyond the M1 research path.

## Public interface

Static HTML/CSS/JavaScript served on a separate local origin.

## Data access

Authenticated HTTP calls to the API only.

## Dependencies

None. The UI uses browser platform APIs and is intentionally replaced or superseded before product UI work.
