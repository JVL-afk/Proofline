# Security Policy

## Reporting

Do not open a public issue containing credentials, private data, exploitable URLs, or detailed vulnerability reproduction. Report security findings privately to the repository owner or the security contact designated during M0.

## M2 security baseline

- No credentials or personal data may be committed.
- `.env.example` files contain names and safe placeholders only.
- External content is untrusted by definition.
- Research/browser runtimes are separate credential-free processes; URL policy blocks non-public
  addresses and pins HTTP connections to validated IPs. Production browser network containment
  remains blocked on approved infrastructure.
- Live research and browser fallback are disabled by default and require explicit local enablement.
- Page bodies and public contact details are not logged.
- Generated model output will not be executed as code, shell, SQL, HTML, or configuration.
- Human approval and audit events are server-side controls, not UI conventions.
- Evidence, observations, inferences, hypotheses, assumptions, economic runs, factor snapshots, and
  review decisions remain distinct and revision-bound.
- Live AI is disabled. Deterministic rules and mock reasoning have no public network or tool access.
- Unknown inputs never receive silent defaults; hypothetical economics are visibly labelled and
  cannot be presented as actual loss or realized impact.
- New external providers, source classes, or data flows require an approved ADR and threat-model update.

The full threat model is in section 18 of `GREENFIELD_ARCHITECTURE.md`.
