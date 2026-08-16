# Workers

Background and hostile-content process boundaries belong here.

- `core`: executable M0 durable operation worker.
- `research`: bounded M1 HTTP-first research worker, disabled for live access by default.
- `browser`: minimal credential-free Playwright subprocess, disabled by default.
- `intelligence`: deterministic M2 opportunity worker with live AI disabled.

The M0 core worker still has no general network fetcher. Only the M1 research/browser processes may
cross the hostile-content boundary under ADR-0005.
