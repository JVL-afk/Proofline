"""M1 research domain objects. Hostile content is represented only as inert data."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
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
    # --- PHASE1_M1_V2_BOUNDED_SITE_CRAWL additive ceilings (v1-safe defaults) ---
    # `max_pages` remains the successful-capture ceiling ("useful page fetches").
    max_total_http_requests: int = 15
    max_discovery_fetches: int = 1
    max_sitemap_entries_parsed: int = 2_000
    max_query_variants_per_path: int = 3
    max_path_segments: int = 6
    max_pages_per_category: int = 4
    no_progress_window: int = 3
    low_relevance_floor: int = 20
    crawl_protocol_version: str = "phase1-m1@1-homepage"


class SemanticCategory(StrEnum):
    """Deterministic business page-purpose taxonomy for M1 v2 relevance scoring.

    Matched semantically on tokens (path segments, query keys, anchor text, title,
    h1) -- never by exact URL name.
    """

    HOMEPAGE = "homepage"
    SERVICES = "services"
    COMMERCIAL_HVAC = "commercial_hvac"
    RESIDENTIAL_HVAC = "residential_hvac"
    HEATING = "heating"
    COOLING_AC = "cooling_ac"
    REPAIR = "repair"
    INSTALLATION = "installation"
    MAINTENANCE = "maintenance"
    EMERGENCY_SERVICE = "emergency_service"
    REQUEST_SERVICE_SCHEDULING = "request_service_scheduling"
    ESTIMATE_QUOTE = "estimate_quote"
    CONTACT_MECHANISM = "contact_mechanism"
    ABOUT = "about"
    SERVICE_AREA_LOCATION = "service_area_location"
    FINANCING = "financing"
    FAQ = "faq"
    UNCLASSIFIED = "unclassified"


# `PagePurpose` is the same closed taxonomy applied to a fetched page.
PagePurpose = SemanticCategory

# Frozen keyword table. Order within each tuple is irrelevant; the dict key order
# defines the deterministic tie-break priority when a URL matches several
# categories (earlier key wins as the primary category).
SEMANTIC_CATEGORIES: dict[SemanticCategory, tuple[str, ...]] = {
    SemanticCategory.COMMERCIAL_HVAC: (
        "commercial hvac",
        "commercial heating",
        "commercial cooling",
        "commercial air",
        "commercial",
        "industrial",
        "business",
    ),
    SemanticCategory.RESIDENTIAL_HVAC: (
        "residential hvac",
        "residential heating",
        "residential cooling",
        "residential",
        "home comfort",
        "homeowner",
    ),
    SemanticCategory.EMERGENCY_SERVICE: (
        "emergency",
        "24/7",
        "24-7",
        "24 hour",
        "same day",
        "urgent",
        "after hours",
    ),
    SemanticCategory.REQUEST_SERVICE_SCHEDULING: (
        "request service",
        "service request",
        "schedule service",
        "schedule",
        "scheduling",
        "book online",
        "book now",
        "appointment",
        "request an appointment",
    ),
    SemanticCategory.ESTIMATE_QUOTE: (
        "estimate",
        "free estimate",
        "quote",
        "get a quote",
        "request a quote",
        "request an estimate",
        "pricing",
    ),
    SemanticCategory.CONTACT_MECHANISM: (
        "contact us",
        "contact",
        "get in touch",
        "reach us",
        "reach out",
    ),
    SemanticCategory.SERVICE_AREA_LOCATION: (
        "service area",
        "service areas",
        "areas we serve",
        "areas served",
        "locations",
        "service map",
        "cities we serve",
        "coverage area",
    ),
    SemanticCategory.FINANCING: (
        "financing",
        "finance",
        "payment options",
        "payment plans",
        "credit",
        "loan",
    ),
    SemanticCategory.FAQ: (
        "faq",
        "faqs",
        "frequently asked",
        "questions",
    ),
    SemanticCategory.HEATING: (
        "heating",
        "furnace",
        "heat pump",
        "boiler",
        "heater",
    ),
    SemanticCategory.COOLING_AC: (
        "cooling",
        "air conditioning",
        "air conditioner",
        " ac ",
        "ac repair",
        "ac installation",
        "hvac cooling",
        "mini split",
    ),
    SemanticCategory.REPAIR: (
        "repair",
        "repairs",
        "fix",
        "troubleshoot",
        "not working",
    ),
    SemanticCategory.INSTALLATION: (
        "installation",
        "install",
        "replacement",
        "new system",
        "system replacement",
    ),
    SemanticCategory.MAINTENANCE: (
        "maintenance",
        "tune up",
        "tune-up",
        "tuneup",
        "service plan",
        "maintenance plan",
        "preventative",
        "preventive",
    ),
    SemanticCategory.SERVICES: (
        "services",
        "our services",
        "what we do",
        "hvac services",
        "service",
    ),
    SemanticCategory.ABOUT: (
        "about us",
        "about",
        "our story",
        "our company",
        "who we are",
        "our team",
        "meet the team",
    ),
    SemanticCategory.HOMEPAGE: (
        "home",
    ),
}

# Every category that counts toward M1-v2 coverage and M2 relevance (all but the
# catch-all). Homepage is included; it is always captured first as the seed.
HIGH_VALUE_CATEGORIES: frozenset[SemanticCategory] = frozenset(
    category for category in SemanticCategory if category is not SemanticCategory.UNCLASSIFIED
)

_FACT_CLASS_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "public_inbound_path",
        (
            "request service", "request a quote", "service request", "schedule",
            "book online", "appointment", "contact us", "get a quote", "free estimate",
        ),
    ),
    (
        "public_service_area",
        ("service area", "areas we serve", "cities we serve", "locations"),
    ),
    ("public_faq", ("faq", "frequently asked", "questions")),
    ("public_about", ("about us", "our story", "our team", "who we are")),
    (
        "public_service_description",
        (
            "commercial", "residential", "heating", "cooling", "air conditioning",
            "repair", "installation", "maintenance", "hvac",
        ),
    ),
)


def classify_public_fact(fragment: str) -> str:
    """Deterministic public FACT class of an evidence fragment. No inference: a
    pure keyword class of text that is a verified substring of a minimised page.
    """
    lowered = fragment.lower()
    for fact_class, keywords in _FACT_CLASS_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return fact_class
    return "public_other"


class DiscoverySource(StrEnum):
    SEED = "seed"
    ROBOTS_SITEMAP = "robots_sitemap"
    DECLARED_SITEMAP = "declared_sitemap"
    CONVENTIONAL_SITEMAP = "conventional_sitemap"
    SITEMAP_INDEX_CHILD = "sitemap_index_child"
    ON_PAGE_LINK = "on_page_link"


_SITEMAP_DISCOVERY_SOURCES: frozenset[DiscoverySource] = frozenset(
    {
        DiscoverySource.ROBOTS_SITEMAP,
        DiscoverySource.DECLARED_SITEMAP,
        DiscoverySource.CONVENTIONAL_SITEMAP,
        DiscoverySource.SITEMAP_INDEX_CHILD,
    }
)


class CandidateDisposition(StrEnum):
    CAPTURED = "captured"
    QUEUED = "queued"
    EXCLUDED = "excluded"
    ROBOTS_DENIED = "robots_denied"
    TRANSPORT_FAILED = "transport_failed"
    QUARANTINED = "quarantined"
    BUDGET_SKIPPED = "budget_skipped"


class CrawlStopReason(StrEnum):
    USEFUL_PAGE_BUDGET_EXCEEDED = "useful_page_budget_exceeded"
    TOTAL_REQUEST_BUDGET_EXCEEDED = "total_request_budget_exceeded"
    DISCOVERY_BUDGET_EXCEEDED = "discovery_budget_exceeded"
    BYTE_BUDGET_EXCEEDED = "byte_budget_exceeded"
    CRAWL_DURATION_EXCEEDED = "crawl_duration_exceeded"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    MAX_DEPTH_BACKSTOP = "max_depth_backstop"
    HIGH_VALUE_CATEGORIES_SATISFIED = "high_value_categories_satisfied"
    NO_NEW_EVIDENCE = "no_new_evidence"
    FRONTIER_EXHAUSTED = "frontier_exhausted"


@dataclass(frozen=True, slots=True)
class UrlCandidate:
    canonical_url: str
    requested_url: str
    depth: int
    discovery_source: DiscoverySource
    anchor_text: str
    from_page_id: UUID | None
    category: SemanticCategory | None
    matched_categories: tuple[SemanticCategory, ...]
    score: int
    tie_break_key: str


@dataclass(frozen=True, slots=True)
class DiscoveryEdge:
    id: UUID
    workspace_id: UUID
    research_run_id: UUID
    from_page_id: UUID | None
    discovered_url_canonical: str
    discovery_source: DiscoverySource
    category: SemanticCategory | None
    score: int
    disposition: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class M1CoverageRecord:
    """Deterministic, immutable record of what the bounded crawl looked at.

    Absence of a category is *public absence only* -- it must never become an
    internal fact. Enforced by M2 truth rules (unchanged) plus coverage tests.
    """

    research_run_id: UUID
    workspace_id: UUID
    crawl_protocol_version: str
    candidate_urls_discovered: int
    candidate_source_breakdown: tuple[tuple[str, int], ...]
    eligible_urls: int
    duplicate_or_excluded_urls: tuple[tuple[str, str], ...]
    pages_attempted: int
    pages_successfully_captured: int
    captured_pages: tuple[tuple[str, str], ...]
    pages_quarantined: int
    quarantined_pages: tuple[tuple[str, str], ...]
    pages_denied_by_robots: int
    robots_denied_pages: tuple[tuple[str, str], ...]
    transport_failures: int
    transport_failed_pages: tuple[tuple[str, str], ...]
    semantic_categories_searched: tuple[str, ...]
    semantic_categories_found: tuple[str, ...]
    semantic_categories_captured: tuple[str, ...]
    sitemap_documents_fetched: int
    robots_sitemap_directives_seen: int
    stop_reasons: tuple[str, ...]
    byte_budget_used: int
    time_budget_used_seconds: int
    attempts_used: int
    total_http_requests_used: int
    coverage_record_sha256: str = "0" * 64

    def canonical_payload(self) -> dict[str, object]:
        return {
            "attempts_used": self.attempts_used,
            "byte_budget_used": self.byte_budget_used,
            "candidate_source_breakdown": [list(item) for item in self.candidate_source_breakdown],
            "candidate_urls_discovered": self.candidate_urls_discovered,
            "captured_pages": [list(item) for item in self.captured_pages],
            "crawl_protocol_version": self.crawl_protocol_version,
            "duplicate_or_excluded_urls": [list(item) for item in self.duplicate_or_excluded_urls],
            "eligible_urls": self.eligible_urls,
            "pages_attempted": self.pages_attempted,
            "pages_denied_by_robots": self.pages_denied_by_robots,
            "pages_quarantined": self.pages_quarantined,
            "pages_successfully_captured": self.pages_successfully_captured,
            "quarantined_pages": [list(item) for item in self.quarantined_pages],
            "research_run_id": str(self.research_run_id),
            "workspace_id": str(self.workspace_id),
            "robots_denied_pages": [list(item) for item in self.robots_denied_pages],
            "robots_sitemap_directives_seen": self.robots_sitemap_directives_seen,
            "semantic_categories_captured": list(self.semantic_categories_captured),
            "semantic_categories_found": list(self.semantic_categories_found),
            "semantic_categories_searched": list(self.semantic_categories_searched),
            "sitemap_documents_fetched": self.sitemap_documents_fetched,
            "stop_reasons": list(self.stop_reasons),
            "time_budget_used_seconds": self.time_budget_used_seconds,
            "total_http_requests_used": self.total_http_requests_used,
            "transport_failed_pages": [list(item) for item in self.transport_failed_pages],
            "transport_failures": self.transport_failures,
        }

    def computed_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def sealed(self) -> M1CoverageRecord:
        return replace(self, coverage_record_sha256=self.computed_sha256())


@dataclass(frozen=True, slots=True)
class Business:
    id: UUID
    workspace_id: UUID
    name: str
    canonical_url: str
    permitted_host: str
    created_by: str
    created_at: datetime


SAMPLED_WORK_ITEM_REVISION = "m67.phase1.sampled-research-work-item@1"
SAMPLED_ACTIVATION_REVISION = "m67.phase1.sampled-slot-activation@1"


@dataclass(frozen=True, slots=True)
class SampledSlotIdentity:
    """Content-addressed identity of one work item in the frozen Phase 1 sample."""

    ordered_package_file_sha256: str
    ordered_package_semantic_sha256: str
    slot_registry_sha256: str
    slot_number: int
    business_identity: str
    exact_hostname: str
    source_row_sha256: str
    work_item_id: UUID
    work_item_revision: str
    identity_sha256: str

    @classmethod
    def create(
        cls,
        *,
        ordered_package_file_sha256: str,
        ordered_package_semantic_sha256: str,
        slot_registry_sha256: str,
        slot_number: int,
        business_identity: str,
        exact_hostname: str,
        source_row_sha256: str,
        work_item_id: UUID,
    ) -> SampledSlotIdentity:
        payload = {
            "business_identity": business_identity,
            "exact_hostname": exact_hostname,
            "ordered_package_file_sha256": ordered_package_file_sha256,
            "ordered_package_semantic_sha256": ordered_package_semantic_sha256,
            "slot_number": slot_number,
            "slot_registry_sha256": slot_registry_sha256,
            "source_row_sha256": source_row_sha256,
            "work_item_id": str(work_item_id),
            "work_item_revision": SAMPLED_WORK_ITEM_REVISION,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        return cls(
            ordered_package_file_sha256=ordered_package_file_sha256,
            ordered_package_semantic_sha256=ordered_package_semantic_sha256,
            slot_registry_sha256=slot_registry_sha256,
            slot_number=slot_number,
            business_identity=business_identity,
            exact_hostname=exact_hostname,
            source_row_sha256=source_row_sha256,
            work_item_id=work_item_id,
            work_item_revision=SAMPLED_WORK_ITEM_REVISION,
            identity_sha256=digest,
        )

    def __post_init__(self) -> None:
        hashes = (
            self.ordered_package_file_sha256,
            self.ordered_package_semantic_sha256,
            self.slot_registry_sha256,
            self.source_row_sha256,
            self.identity_sha256,
        )
        if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in hashes):
            raise ValueError("sampled slot identity requires lowercase SHA-256 values")
        if not 1 <= self.slot_number <= 24:
            raise ValueError("sampled slot number is outside the frozen Phase 1 slots")
        if not self.business_identity.strip():
            raise ValueError("sampled slot business identity is required")
        if (
            self.exact_hostname != self.exact_hostname.lower()
            or "://" in self.exact_hostname
            or "/" in self.exact_hostname
            or "." not in self.exact_hostname
        ):
            raise ValueError("sampled slot hostname is not an exact normalized hostname")
        if self.work_item_revision != SAMPLED_WORK_ITEM_REVISION:
            raise ValueError("sampled work-item revision is not supported")
        if self.identity_sha256 != self.computed_sha256():
            raise ValueError("sampled slot identity hash mismatch")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "business_identity": self.business_identity,
            "exact_hostname": self.exact_hostname,
            "ordered_package_file_sha256": self.ordered_package_file_sha256,
            "ordered_package_semantic_sha256": self.ordered_package_semantic_sha256,
            "slot_number": self.slot_number,
            "slot_registry_sha256": self.slot_registry_sha256,
            "source_row_sha256": self.source_row_sha256,
            "work_item_id": str(self.work_item_id),
            "work_item_revision": self.work_item_revision,
        }

    def computed_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SampledSlotActivation:
    """Immutable authority binding that creates exactly one sampled research work item."""

    activation_id: UUID
    authorization_release_id: UUID
    authorization_configuration_hash: str
    a09_decision_sha256: str
    research_runtime_revision: str
    execution_ceilings_sha256: str
    activated_at: datetime
    sampled_slot_identity: SampledSlotIdentity
    activation_revision: str
    activation_sha256: str

    @classmethod
    def create(
        cls,
        *,
        activation_id: UUID,
        authorization_release_id: UUID,
        authorization_configuration_hash: str,
        a09_decision_sha256: str,
        research_runtime_revision: str,
        execution_ceilings_sha256: str,
        activated_at: datetime,
        sampled_slot_identity: SampledSlotIdentity,
    ) -> SampledSlotActivation:
        value = cls(
            activation_id=activation_id,
            authorization_release_id=authorization_release_id,
            authorization_configuration_hash=authorization_configuration_hash,
            a09_decision_sha256=a09_decision_sha256,
            research_runtime_revision=research_runtime_revision,
            execution_ceilings_sha256=execution_ceilings_sha256,
            activated_at=activated_at,
            sampled_slot_identity=sampled_slot_identity,
            activation_revision=SAMPLED_ACTIVATION_REVISION,
            activation_sha256="0" * 64,
        )
        return replace(value, activation_sha256=value.computed_sha256())

    def __post_init__(self) -> None:
        hashes = (
            self.authorization_configuration_hash,
            self.a09_decision_sha256,
            self.execution_ceilings_sha256,
            self.activation_sha256,
        )
        if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in hashes):
            raise ValueError("sampled activation requires lowercase SHA-256 values")
        if self.activation_revision != SAMPLED_ACTIVATION_REVISION:
            raise ValueError("sampled activation revision is not supported")
        if self.activation_sha256 != "0" * 64 and self.activation_sha256 != self.computed_sha256():
            raise ValueError("sampled activation hash mismatch")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "activation_id": str(self.activation_id),
            "activation_revision": self.activation_revision,
            "activated_at": self.activated_at.isoformat(),
            "a09_decision_sha256": self.a09_decision_sha256,
            "authorization_configuration_hash": self.authorization_configuration_hash,
            "authorization_release_id": str(self.authorization_release_id),
            "execution_ceilings_sha256": self.execution_ceilings_sha256,
            "research_runtime_revision": self.research_runtime_revision,
            "sampled_slot_identity_sha256": self.sampled_slot_identity.identity_sha256,
        }

    def computed_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


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
    sampled_slot_identity: SampledSlotIdentity | None = None
    sampled_slot_activation: SampledSlotActivation | None = None
    crawl_protocol_version: str = "phase1-m1@1-homepage"
    coverage_record_sha256: str | None = None


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
class RobotsPolicyEvidence:
    """Content-minimized runtime robots decision captured before page fetch."""

    id: UUID
    research_run_id: UUID
    host: str
    requested_path: str
    captured_at: datetime
    http_status: int | None
    body_sha256: str | None
    body_length: int
    decision: str
    reason_code: str
    allowed: bool


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
    page_purpose: str = "unclassified"


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
    fact_class: str = "public_other"


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
