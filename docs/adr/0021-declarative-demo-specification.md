# ADR-0021: Declarative demo specification and component registry

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decision owners:** Product owner and architecture owner

## Context

M4 must render a personalized interactive simulation without becoming an arbitrary code-generation
or execution platform.

## Decision drivers

- Make every renderable behavior typed, reviewable, and deterministic.
- Prevent generated HTML, code, URLs, and executable expressions.
- Preserve a narrow, testable runtime attack surface.

## Considered options

1. Vetted immutable components and declarative specifications.
2. Generated HTML and JavaScript in a sandbox.
3. Static screenshots without interaction.

## Decision

M4 specifications may reference only versioned components, events, guards, properties, and actions
from immutable registries. Specifications contain data, never HTML, Markdown, CSS, executable code,
dynamic imports, external URLs, or runtime-compiled expressions. The first registry supports only
the Texas Commercial HVAC inbound lead-response simulation.

## Consequences

Visual freedom is deliberately constrained, while security, accessibility, replay, and QC remain
deterministically testable.

## Validation

Schema, registry, hostile-active-content, unknown-component, and deterministic-render tests apply.

## Revisit triggers

A custom component, arbitrary visual template, generated code, or new opportunity family is proposed.
