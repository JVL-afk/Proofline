# Security Policy

## Reporting

Do not open a public issue containing credentials, private data, exploitable URLs, or detailed vulnerability reproduction. Report security findings privately to the repository owner or the security contact designated during M0.

## M0 security baseline

- No credentials or personal data may be committed.
- `.env.example` files contain names and safe placeholders only.
- External content is untrusted by definition.
- Research/browser runtimes will be isolated from application credentials and private networks.
- Generated model output will not be executed as code, shell, SQL, HTML, or configuration.
- Human approval and audit events are server-side controls, not UI conventions.
- New external providers, source classes, or data flows require an approved ADR and threat-model update.

The full threat model is in section 18 of `GREENFIELD_ARCHITECTURE.md`.
