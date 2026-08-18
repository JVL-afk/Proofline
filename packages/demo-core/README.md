# Demo Core

Owns M4 demo manifests, immutable revisions, declarative specifications, component/state registries,
deterministic composition/replay, QC, review, session, revocation, and telemetry contracts.

It may read exact canonical M1-M3 contracts through `DemoSourceCatalog`. It must not mutate those
contexts, execute generated code, perform network I/O, invoke AI, or implement real side effects.
