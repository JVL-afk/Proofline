# Secret Handling Policy — M0 Baseline

## Rules

- Secrets are injected at runtime from an approved managed secret store or an approved local-only mechanism.
- Repository files, images, build logs, test snapshots, provider prompts, browser jobs, and client bundles must not contain secrets.
- `.env.example` documents variable names only. `.env` and key material are ignored.
- Each deployable receives a distinct workload identity and the minimum secrets/permissions it needs.
- Research/browser workers receive no core application, user, AI-provider, or cloud credentials except a narrowly scoped job capability.
- Rotate credentials after suspected disclosure and audit access to production secrets.
- Never place secrets in command-line arguments when a safer file descriptor/environment/workload-identity mechanism exists.

## Local development

The approved local secret mechanism is pending the environment/IaC ADR. Until then, developers may use an ignored local `.env` for non-production placeholders only. Production credentials are prohibited on developer machines unless a separately approved emergency process requires them.

M2.5 has no live-provider adapter and requires no provider credential. Future evaluation credentials
must be scoped to the isolated evaluation runtime and must never be available to research/browser
workers, ordinary CI, the web application, or deterministic M2 workers.

M2.6 credentials may be read only by the explicit local tournament process from an ignored local
secret file. `apikeys.txt`, `.env`, and `.env.local` are excluded from Git. Values must never appear
in command arguments, exceptions, logs, provider metadata, hashes, ledgers, databases, test output,
or tournament reports. The tournament process passes each credential only to its matching adapter.

M4 uses opaque, short-lived local capabilities. Only their SHA-256 digests may be persisted. The
separate demo runtime receives no core cookie, database/provider/research credential, signing key,
or general-purpose application credential. No M4 component requires a live provider secret.

## CI/CD

- Prefer workload identity federation over long-lived repository secrets.
- Environments protect deployment credentials and require review as approved.
- Forked/untrusted workflows never receive secrets.
- Secret scanning and push protection should be enabled when the hosting platform is selected.

## Incident response

If a secret is committed or logged: stop use, revoke/rotate it, preserve the minimum incident evidence, purge/contain exposed artifacts according to the incident procedure, and document the control failure. Deleting only the latest file revision is not remediation.
