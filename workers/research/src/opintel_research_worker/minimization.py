"""Production composition adapter for counsel-required Phase 1 minimization."""

from __future__ import annotations

import hashlib
import json
import re

from opintel_research.domain import (
    CaptureQuarantine,
    DurableMinimizedCapture,
    PageSnapshot,
    redact_prohibited_contact_values,
)
from opintel_shadow.compliance_application import PhaseOneMinimizer
from opintel_shadow.compliance_domain import CaptureDisposition

_MARKER_CANDIDATES = (
    "texas",
    "commercial",
    "hvac",
    "business",
    "businesses",
    "company",
    "facility",
    "service",
    "request",
    "quote",
    "estimate",
    "inquiry",
    "form",
    "heating",
    "cooling",
    "air conditioning",
)


def _present(text: str, marker: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text, re.IGNORECASE))


def _event_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ProductionPhaseOneCaptureMinimizer:
    """Adapts the accepted M6.7 minimizer to the M1 durable-capture port."""

    def __init__(self, minimizer: PhaseOneMinimizer | None = None) -> None:
        self._minimizer = minimizer or PhaseOneMinimizer()

    def minimize(
        self, snapshot: PageSnapshot, business_name: str, observed_visible_text: str
    ) -> DurableMinimizedCapture | CaptureQuarantine:
        candidates = (business_name, *_MARKER_CANDIDATES)
        markers = tuple(
            dict.fromkeys(item for item in candidates if _present(observed_visible_text, item))
        )
        if not markers:
            markers = ("PHASE1_REQUIRED_BUSINESS_EVIDENCE",)
        result = self._minimizer.minimize(
            source_uri=snapshot.final_url,
            captured_at=snapshot.captured_at,
            raw_body=snapshot.content,
            required_evidence_markers=markers,
        )
        event_payload: dict[str, object] = {
            "disposition": result.disposition.value,
            "minimized_content_sha256": result.minimized_content_sha256,
            "minimizer_version": result.minimizer_version,
            "quarantine_reasons": result.quarantine_reasons,
            "raw_content_sha256": result.raw_content_sha256,
            "removed_email_count": result.removed_email_count,
            "removed_phone_count": result.removed_phone_count,
            "removed_structured_contact_blocks": result.removed_structured_contact_blocks,
            "required_evidence_markers": result.required_evidence_markers,
            "snapshot_id": str(snapshot.id),
        }
        event_hash = _event_hash(event_payload)
        if result.disposition is CaptureDisposition.QUARANTINE_AND_REVIEW:
            return CaptureQuarantine(
                source_uri=redact_prohibited_contact_values(result.source_uri),
                captured_at=result.captured_at,
                raw_content_sha256=result.raw_content_sha256,
                required_evidence_markers=result.required_evidence_markers,
                quarantine_reasons=result.quarantine_reasons,
                minimizer_version=result.minimizer_version,
                minimization_event_sha256=event_hash,
            )
        if result.minimized_text is None or result.minimized_content_sha256 is None:
            raise ValueError("minimizer returned an invalid durable result")
        return DurableMinimizedCapture(
            source_uri=redact_prohibited_contact_values(result.source_uri),
            captured_at=result.captured_at,
            raw_content_sha256=result.raw_content_sha256,
            minimized_content_sha256=result.minimized_content_sha256,
            minimized_text=result.minimized_text,
            removed_email_count=result.removed_email_count,
            removed_phone_count=result.removed_phone_count,
            removed_structured_contact_blocks=result.removed_structured_contact_blocks,
            required_evidence_markers=result.required_evidence_markers,
            minimizer_version=result.minimizer_version,
            minimization_event_sha256=event_hash,
        )


__all__ = ["ProductionPhaseOneCaptureMinimizer"]
