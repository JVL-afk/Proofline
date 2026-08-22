# Phase 1 production minimization data flow

Status: implemented and locally validated; deployment requires a separately hash-bound Terraform
successor approval.

## Typed flow

```text
CONTROLLED_EGRESS_RESPONSE.body
  -> FetchedDocument.content                 RAW_EPHEMERAL
  -> PageSnapshot.content                   RAW_EPHEMERAL
  -> deterministic HTML extraction          RAW_EPHEMERAL
  -> CaptureMinimizer.minimize(...)
       -> CaptureQuarantine                 CONTENT-FREE DURABLE RECORD
       -> DurableMinimizedCapture           MINIMIZED_CAPTURE
  -> MinimizedPageSnapshot                  MINIMIZED_CAPTURE
  -> ExtractedMaterial projection           MINIMIZED_CAPTURE
  -> ResearchEvidence                       EVIDENCE_EXCERPT
  -> DurablePageBundle
  -> ResearchRepository.save_page_bundle
  -> PostgreSQL/SQLite rows                  DURABLE MINIMIZED DATA ONLY
  -> later deterministic analysis           ANALYSIS
  -> redacted review projection              HUMAN_REVIEW_ARTIFACT
```

`RawHttpResponse`, `FetchedDocument`, and `PageSnapshot` exist only inside the bounded fetch,
extract, and minimization call chain. Their byte fields are excluded from representations. The
repository port and adapters accept `DurablePageBundle`, whose runtime invariants reject contact
values, structured person/contact data, evidence not derived from minimized text, and any raw
`PageSnapshot` substitution.

## Durable sinks and bypass review

| Sink/path | Result |
| --- | --- |
| `page_snapshots` | Stores minimized text and minimization provenance; no raw body or headers column. |
| `extracted_materials` | Stores only a projection derived from minimized text; contact and structured-data fields must be empty. |
| `research_evidence` | Excerpts must be substrings of the minimized snapshot. |
| quarantine/error rows | Content-free hashes, reason codes, counters, and provenance only. |
| S3 capture path | Not called by the research workflow before minimization; the durable contract contains no raw body. |
| filesystem | No raw-write port or code path exists; production root is read-only. |
| logs/metrics/traces | Worker lifecycle and egress host hashes/status only; raw types hide byte fields from `repr`; caught minimizer errors persist only a stable reason code. |
| review artifacts | Downstream evidence originates from minimized text, so later review cannot recover raw content. |

Cached snapshots are already `MinimizedPageSnapshot` instances and are revalidated by
`DurablePageBundle` before another durable write. A legacy database schema containing the former
raw `content` column fails closed at repository initialization.

## Minimization behavior

The worker composition adapter invokes the existing `PhaseOneMinimizer`. It deterministically
redacts email addresses and telephone numbers, removes recognized structured contact/person/staff
blocks, and preserves only required observed business evidence markers. Unsupported or unsafe
content becomes `QUARANTINE_AND_REVIEW`; raw content is never the fallback. Natural-person-name
detection is not claimed to be perfect.

## Validation boundary

Hostile fixtures combine business facts, emails, phones, staff/contact blocks, malformed content,
and forced minimizer failures. Tests inspect the actual durable schema and values, prove raw-type
rejection by both SQLite and PostgreSQL-configured adapters, scan observability code, and ensure the
quarantine representation contains no source body or contact value. A deployed PostgreSQL execution
and sink inspection remains required after the corrected image/task-definition revision is
separately approved.
