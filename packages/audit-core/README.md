# Audit Core

Owns M3 audit operations, immutable input manifests, structured sections, atomic claims, lineage,
deterministic composition/QC contracts, and version-bound audit review rules.

It may consume canonical M1/M2 application contracts but cannot create or mutate their truth. It
does not fetch pages, calculate economics, invoke providers, publish artifacts, or perform external
actions. Public interfaces are `opintel_audit` domain, application, contracts, ports, composition,
and workflow modules. Persistence and framework concerns belong to adapters.
