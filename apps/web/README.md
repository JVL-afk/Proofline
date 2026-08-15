# M0 Diagnostic Web UI

## Ownership

Application/web team.

## Responsibilities

- Accept a local development token in session storage.
- Create an M0 fixture campaign and idempotent operation command through the API.
- Poll operation state and display attempts and evidence provenance.

## Forbidden responsibilities

- Database access, provider credentials, workflow execution, raw HTML rendering, production identity, or product functionality beyond the M0 path.

## Public interface

Static HTML/CSS/JavaScript served on a separate local origin.

## Data access

Authenticated HTTP calls to the API only.

## Dependencies

None. The UI uses browser platform APIs and is intentionally replaced or superseded before product UI work.
