# ADR-0076: Phase 1 controlled research egress

- Status: Accepted
- Date: 2026-08-22
- Decision owners: Project owner / security-environment owner
- Scope: M6.7 Phase 1 production runtime

## Context

The research worker must eventually reach changing, CDN-backed first-party public hosts, so static
IP allowlists are neither correct nor durable. Security groups cannot express an exact-host policy,
and application URL validation alone does not remove the worker's arbitrary-internet capability.
The worker must also reach AWS control and storage services without using a general public path.

## Decision

Run a separate, credential-free controlled-egress task. The research worker's security group permits
only PostgreSQL, VPC DNS, approved private AWS endpoints, and TCP 8080 to that task. It has no direct
public HTTP or HTTPS rule. The controlled-egress task alone has public HTTP/HTTPS network reach and
exposes only a private fetch operation to the worker security group.

At the gateway, every request must bind an exact non-empty source-policy revision and exact hostname.
The gateway repeats URL normalization, DNS resolution and public-address validation, connects to a
validated address, preserves HTTP Host and TLS SNI/certificate verification, enforces GET-only,
timeout and byte ceilings, and records content-free host-digest audit events. Redirects are returned
to the research fetcher and every destination is independently revalidated through both layers.
Private, loopback, link-local, metadata and reserved destinations fail closed. A gateway without a
released non-empty host set cannot start. The gateway receives no application, database, storage,
AI, browser, sender, delivery, or business secret.

Use private VPC endpoints for ECR API/Docker, CloudWatch Logs, Secrets Manager and SSM, plus an S3
gateway endpoint. Security-group rules on the gateway's internet path are not treated as the domain
authorization control; the application-aware gateway is that narrower enforcement boundary. Static
public-IP allowlists are rejected because ordinary first-party hosts may use changing CDN addresses.

The controlled-egress deployment creates no source approval. Exact hosts remain governed by A-09
records and `REAL_PUBLIC_RESEARCH`; both are independently fail-closed. Desired task count remains
zero before later, separate research and slot authorization.

## Consequences and tradeoffs

- A compromised research worker cannot open a direct arbitrary public socket through its ENI.
- The gateway is a small security-critical component and needs versioned tests, logs, patching and
  independent task isolation.
- Generic IaC scanners will continue to identify the gateway's public HTTP/HTTPS security-group
  route. That finding is retained as evidence and mapped to this explicit application-aware boundary;
  it must never be suppressed or misrepresented as worker egress.
- Interface endpoints add recurring cost but keep required AWS service traffic off the research
  internet path.

## Reconsider when

Reconsider if AWS offers a lower-cost, exact-domain egress control that supports dynamic public DNS,
TLS validation, auditability and the same fail-closed redirect/SSRF guarantees, or if the Phase 1
cost envelope cannot accommodate the private endpoint topology.
