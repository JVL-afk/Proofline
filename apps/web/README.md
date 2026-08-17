# M3 Diagnostic Web UI

## Ownership

Application/web team.

## Responsibilities

- Accept a local development token in session storage.
- Create a known-business URL permit and idempotent research command through the API.
- Poll research state and display pages, snapshot links, and evidence provenance.
- Start deterministic Commercial HVAC opportunity analysis, inspect lineage/gaps/economics/factors,
  edit visibly proposed assumptions, and record local human review.
- Generate and inspect structured audit manifests, claims, QC, provenance, and exact review state.

## Forbidden responsibilities

- Database access, provider credentials, crawling, raw HTML rendering, live AI, demos, publication,
  outreach, integrations, production identity, or M4 behavior.

## Public interface

Static HTML/CSS/JavaScript served on a separate local origin.

## Data access

Authenticated HTTP calls to the API only.

## Dependencies

None. The UI uses browser platform APIs and is intentionally replaced or superseded before product UI work.
