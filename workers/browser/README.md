# Browser Worker Boundary

Owner: research and evidence bounded context security boundary.

Responsibilities: accept a minimal JSON job over standard input and provide a disposable browser
fallback protocol. M1 ships fail-closed unless a separately isolated Playwright runtime is
configured.

Forbidden: application secrets/database access, persistent profiles, downloads, credentials,
forms, internal-network access, and arbitrary side effects.

Public interface: `opintel-browser-worker` stdin/stdout protocol. Data access: none.
