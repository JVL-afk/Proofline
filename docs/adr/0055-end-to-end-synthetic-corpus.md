# ADR-0055: End-to-end synthetic corpus and minimum-data projections

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decision owners:** Product, data governance, and architecture owners

## Context

Tournament II needs representative M1-M6 cases without inspecting businesses or releasing real
contact data.

## Decision drivers

- Measure actual task boundaries.
- Keep evaluation synthetic and data-minimized.
- Prevent hidden-case leakage and cross-case contamination.

## Considered options

1. Versioned synthetic case bundles with task projections.
2. Full aggregate dumps.
3. Real production-adjacent records.

## Decision

Use development, calibration, hidden qualification, regression, and rotating challenge partitions.
Implement all approved families including persuasive-but-false, qualifier dilution, and cross-case
contamination. Models receive only task projections; hidden cases require explicit sealed access.

## Consequences

The corpus requires governed maintenance but normal CI remains deterministic and data-safe.

## Validation

Partition, synthetic-only, hidden-isolation, minimum-projection, and cross-case tests are required.

## Revisit triggers

Real-data evaluation, a new task family, or corpus custody changes are proposed.
