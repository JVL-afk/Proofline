# Services

Long-running APIs and isolated runtimes belong here.

- `api`: authenticated M0-M6.5 API and composition root; M6 is mock-only and M6.5 is readiness-only.
- `demo-runtime`: separate-origin M4 declarative simulation runtime with no core credentials.

The API does not run workflow activities in request threads. The demo runtime has only a narrow
capability exchange/event gateway and no database or external-action adapter.
