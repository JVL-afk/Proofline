# Research Core

Owner: research and evidence bounded context.

Responsibilities: M1 business/research-run contracts, URL policy, bounded crawl orchestration,
observational HTML extraction, snapshot/evidence provenance, and infrastructure ports.

Forbidden: provider/framework persistence models, opportunity or ROI interpretation, public
network I/O, authenticated scraping, form submission, and AI execution.

Public interface: `opintel_research` domain objects, contracts, ports, policies, and services.

Data access: none directly. Dependencies: M0 principal/clock primitives and Pydantic contracts.
