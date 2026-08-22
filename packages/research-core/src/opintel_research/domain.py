"""M1 research domain objects. Hostile content is represented only as inert data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ResearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.PARTIAL, self.FAILED}


class PageStatus(StrEnum):
    FETCHED = "fetched"
    CACHED = "cached"
    FAILED = "failed"


class CaptureDisposition(StrEnum):
    DURABLE_MINIMIZED_CAPTURE = "DURABLE_MINIMIZED_CAPTURE"
    QUARANTINE_AND_REVIEW = "QUARANTINE_AND_REVIEW"


@dataclass(frozen=True, slots=True)
class CrawlPolicy:
    max_pages: int = 5
    max_depth: int = 1
    max_total_bytes: int = 1_500_000
    max_response_bytes: int = 512_000
    max_compressed_bytes: int = 512_000
    max_duration_seconds: int = 30
    request_timeout_seconds: float = 8.0
    max_redirects: int = 5
    max_attempts: int = 3
    per_domain_delay_seconds: float = 0.25
    cache_ttl_seconds: int = 300
    browser_fallback_enabled: bool = False


@dataclass(frozen=True, slots=True)
class Business:
    id: UUID
    workspace_id: UUID
    name: str
    canonical_url: str
    permitted_host: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchRun:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    operation_id: UUID
    trace_id: UUID
    start_url: str
    permitted_host: str
    policy: CrawlPolicy
    status: ResearchRunStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    pages_attempted: int = 0
    pages_succeeded: int = 0
    bytes_stored: int = 0
    last_error_code: str | None = None
    last_error_message: str | None = None


@dataclass(frozen=True, slots=True)
class FetchAttempt:
    id: UUID
    research_run_id: UUID
    normalized_url: str
    attempt_number: int
    started_at: datetime
    completed_at: datetime
    outcome: str
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """Raw ephemeral page used only while deterministic minimization runs."""

    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    operation_id: UUID
    trace_id: UUID
    source_url: str
    canonical_url: str
    final_url: str
    snapshot_version: str
    captured_at: datetime
    content_sha256: str
    content_type: str
    charset: str
    status_code: int
    content_length: int
    response_headers: tuple[tuple[str, str], ...] = field(repr=False)
    content: bytes = field(repr=False)


_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?1[ .()-]*)?(?:\d[ .()-]*){10}(?!\w)")


def contains_prohibited_contact_value(value: str) -> bool:
    return bool(_EMAIL.search(value) or _PHONE.search(value))


def redact_prohibited_contact_values(value: str) -> str:
    return _PHONE.sub("[PHONE_REDACTED]", _EMAIL.sub("[EMAIL_REDACTED]", value))


@dataclass(frozen=True, slots=True)
class DurableMinimizedCapture:
    source_uri: str
    captured_at: datetime
    raw_content_sha256: str
    minimized_content_sha256: str
    minimized_text: str
    removed_email_count: int
    removed_phone_count: int
    removed_structured_contact_blocks: int
    required_evidence_markers: tuple[str, ...]
    minimizer_version: str
    minimization_event_sha256: str
    disposition: CaptureDisposition = CaptureDisposition.DURABLE_MINIMIZED_CAPTURE

    def __post_init__(self) -> None:
        if self.disposition is not CaptureDisposition.DURABLE_MINIMIZED_CAPTURE:
            raise ValueError("durable capture must have minimized disposition")
        if not self.minimized_text.strip() or not self.minimized_content_sha256:
            raise ValueError("durable capture requires minimized content")
        if contains_prohibited_contact_value(self.minimized_text):
            raise ValueError("durable capture contains prohibited contact data")


@dataclass(frozen=True, slots=True)
class CaptureQuarantine:
    source_uri: str
    captured_at: datetime
    raw_content_sha256: str
    required_evidence_markers: tuple[str, ...]
    quarantine_reasons: tuple[str, ...]
    minimizer_version: str
    minimization_event_sha256: str
    disposition: CaptureDisposition = CaptureDisposition.QUARANTINE_AND_REVIEW

    def __post_init__(self) -> None:
        if self.disposition is not CaptureDisposition.QUARANTINE_AND_REVIEW:
            raise ValueError("quarantine must have quarantine disposition")
        if not self.quarantine_reasons:
            raise ValueError("quarantine requires a safe reason code")


@dataclass(frozen=True, slots=True)
class MinimizedPageSnapshot:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    operation_id: UUID
    trace_id: UUID
    source_url: str
    canonical_url: str
    final_url: str
    snapshot_version: str
    captured_at: datetime
    source_content_sha256: str
    content_sha256: str
    content_type: str
    charset: str
    status_code: int
    content_length: int
    minimized_text: str
    minimizer_version: str
    minimization_event_sha256: str
    removed_email_count: int
    removed_phone_count: int
    removed_structured_contact_blocks: int
    required_evidence_markers: tuple[str, ...]
    disposition: CaptureDisposition = CaptureDisposition.DURABLE_MINIMIZED_CAPTURE

    def __post_init__(self) -> None:
        if self.disposition is not CaptureDisposition.DURABLE_MINIMIZED_CAPTURE:
            raise ValueError("snapshot must be a durable minimized capture")
        if self.content_length != len(self.minimized_text.encode("utf-8")):
            raise ValueError("minimized snapshot length mismatch")
        if contains_prohibited_contact_value(self.minimized_text):
            raise ValueError("minimized snapshot contains prohibited contact data")
        if any(
            contains_prohibited_contact_value(item)
            for item in (self.source_url, self.canonical_url, self.final_url)
        ):
            raise ValueError("minimized snapshot URL contains prohibited contact data")


@dataclass(frozen=True, slots=True)
class ExtractedMaterial:
    id: UUID
    snapshot_id: UUID
    extractor_name: str
    extractor_version: str
    title: str | None
    metadata: tuple[tuple[str, str], ...]
    headings: tuple[tuple[int, str, str], ...]
    visible_text: str
    links: tuple[tuple[str, str, str], ...]
    forms: tuple[tuple[str, str, str], ...]
    buttons: tuple[tuple[str, str], ...]
    contacts: tuple[tuple[str, str, str], ...]
    structured_data: tuple[str, ...]
    technology_signals: tuple[tuple[str, str], ...]
    prompt_injection_suspected: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DurablePageBundle:
    snapshot: MinimizedPageSnapshot
    material: ExtractedMaterial
    evidence: tuple[ResearchEvidence, ...]

    def __post_init__(self) -> None:
        if self.material.snapshot_id != self.snapshot.id:
            raise ValueError("material must bind the minimized snapshot")
        if self.material.contacts or self.material.structured_data:
            raise ValueError("durable material cannot contain contact or structured-person data")
        serialized = repr(
            (
                self.material.title,
                self.material.metadata,
                self.material.headings,
                self.material.visible_text,
                self.material.links,
                self.material.forms,
                self.material.buttons,
                self.material.technology_signals,
            )
        )
        if contains_prohibited_contact_value(serialized):
            raise ValueError("durable material contains prohibited contact data")
        for item in self.evidence:
            if item.snapshot_id != self.snapshot.id:
                raise ValueError("evidence must bind the minimized snapshot")
            if item.extracted_fragment not in self.snapshot.minimized_text:
                raise ValueError("evidence must derive from minimized content")
            if contains_prohibited_contact_value(item.extracted_fragment):
                raise ValueError("evidence contains prohibited contact data")


@dataclass(frozen=True, slots=True)
class ResearchPage:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    requested_url: str
    normalized_url: str
    depth: int
    status: PageStatus
    snapshot_id: UUID | None
    material_id: UUID | None
    fetched_at: datetime | None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    id: UUID
    workspace_id: UUID
    business_id: UUID
    research_run_id: UUID
    operation_id: UUID
    trace_id: UUID
    page_id: UUID
    snapshot_id: UUID
    snapshot_version: str
    source_uri: str
    captured_at: datetime
    content_sha256: str
    locator: str
    extracted_fragment: str
    extractor_name: str
    extractor_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    normalized_url: str
    scheme: str
    host: str
    port: int
    request_target: str
    addresses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawHttpResponse:
    status_code: int
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class FetchedDocument:
    source_url: str
    canonical_url: str
    final_url: str
    status_code: int
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    content: bytes = field(repr=False)
    content_type: str
    charset: str
    captured_at: datetime


class ResearchError(Exception):
    code = "research_error"
    retryable = False
    safe_message = "research failed"


class ResearchNotFoundError(ResearchError):
    code = "not_found"
    safe_message = "research resource not found"


class UrlPolicyError(ResearchError):
    code = "url_policy_blocked"
    safe_message = "URL is not permitted by research policy"


class FetchError(ResearchError):
    code = "fetch_failed"
    safe_message = "public page fetch failed"


class TransientFetchError(FetchError):
    code = "fetch_transient"
    retryable = True


class FetchTimeoutError(TransientFetchError):
    code = "fetch_timeout"


class OversizedResponseError(FetchError):
    code = "response_too_large"


class UnsupportedContentError(FetchError):
    code = "unsupported_content"


class MalformedContentError(FetchError):
    code = "malformed_content"


class BrowserFallbackUnavailable(ResearchError):
    code = "browser_fallback_unavailable"
    safe_message = "browser fallback is unavailable in this environment"
