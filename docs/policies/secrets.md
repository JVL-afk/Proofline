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

M5 requires no provider, mail, CRM, calendar, telephony, social-network, recipient-enrichment, or
delivery credential. The disabled wording port has no adapter or route. Draft content, sender slots,
reviewer edits, and future recipient data must never be treated as secret-injection mechanisms.

M6 requires no live secret. The deterministic mock uses no credential and its fixture-event marker
is public test data, not a secret. A future isolated delivery worker may receive only its provider
credential and field-protection capability; API, research/browser, demo, AI, and normal CI processes
must not receive them. No real mailbox/domain credential may be stored locally.

M6.5 requires no secret and exposes no secret/provider/identity adapter. Infrastructure and sender
controls are represented only by safe evidence references and hashes. Missing secret isolation or
workload-identity evidence blocks readiness; it is never satisfied by placing credentials locally.

M6.6A requires no secret. Candidate records are deterministic fixtures and the fake runner contains
no credential or network interface. Any future M6.6B credential boundary requires separate
authorization and must not be added to normal application or CI processes.

M6.6B-3 permits the explicit one-shot local certification process to read only OpenAI, Anthropic,
and Gemini credentials from the already ignored `apikeys.txt` boundary. Missing credentials are
provider-local `CREDENTIAL_UNAVAILABLE` outcomes. Values may exist only in process memory and their
matching authorization headers; they are never printed, hashed, persisted, passed as command-line
arguments, or exposed to another provider. The process retains only approved safe metadata and
removes its credential bundle reference after execution. Normal CI never invokes this process.

M6.6B-3R narrows the live boundary to the Gemini credential and exact Google host. The repair runner
does not receive OpenAI or Anthropic credentials and cannot call either provider. Its ignored local
output and committed safe receipt follow the same no-value, no-hash, no-body rules. Normal CI tests
the repair through fake transports only.

M6.6B-4A permits four read-only model-metadata requests through the existing provider-specific
credential boundary and exact HTTPS hosts. These checks submit no prompt, fixture, or inference
request and retain only status, exact returned model ID, approved rate-limit headers when present,
and latency. Raw bodies and credentials remain memory-only. The credential-value audit compares the
local values in memory against tracked working-tree files and reachable Git blobs without placing a
value in process arguments or output. Normal CI uses fake transports and no credential.

M6.7A requires no secret and defines no credential-loading interface. The shadow-validation
bounded context has no live research, person/contact, AI, sender, delivery, CRM, calendar,
messaging, form, booking, or other external provider adapter. Synthetic CI is network-free, and no
M6.6 provider credential or registry is available to M6.7A.

M6.7C adds no credential loader or live transport. Environment and workload identities are modeled
only as immutable evidence references. Fake transport tests receive no secret, and the future
research-egress identity cannot contain AI, M6, sender, delivery, browser-session, or user secrets.

## CI/CD

- Prefer workload identity federation over long-lived repository secrets.
- Environments protect deployment credentials and require review as approved.
- Forked/untrusted workflows never receive secrets.
- Secret scanning and push protection should be enabled when the hosting platform is selected.

## Incident response

If a secret is committed or logged: stop use, revoke/rotate it, preserve the minimum incident evidence, purge/contain exposed artifacts according to the incident procedure, and document the control failure. Deleting only the latest file revision is not remediation.
