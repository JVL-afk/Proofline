# Services

Long-running APIs and isolated runtimes belong here.

- `api`: authenticated M0-M5 application API and composition root.
- `demo-runtime`: separate-origin M4 declarative simulation runtime with no core credentials.

The API does not run workflow activities in request threads. The demo runtime has only a narrow
capability exchange/event gateway and no database or external-action adapter.
