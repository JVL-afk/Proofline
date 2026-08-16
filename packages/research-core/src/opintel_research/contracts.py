"""Typed API contracts for M1 research resources."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from opintel_research.domain import (
    Business,
    CrawlPolicy,
    ExtractedMaterial,
    FetchAttempt,
    PageSnapshot,
    ResearchEvidence,
    ResearchPage,
    ResearchRun,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class BusinessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    public_url: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2048)
    ]


class CrawlPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_pages: int = Field(default=5, ge=1, le=10)
    max_depth: int = Field(default=1, ge=0, le=2)
    max_total_bytes: int = Field(default=1_500_000, ge=1, le=5_000_000)
    max_response_bytes: int = Field(default=512_000, ge=1, le=1_000_000)
    max_duration_seconds: int = Field(default=30, ge=1, le=120)
    per_domain_delay_seconds: float = Field(default=0.25, ge=0.0, le=10.0)
    browser_fallback_enabled: bool = False

    def to_domain(self) -> CrawlPolicy:
        return CrawlPolicy(**self.model_dump())


class ResearchRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: CrawlPolicyInput = Field(default_factory=CrawlPolicyInput)


class BusinessView(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    canonical_url: str
    permitted_host: str
    created_at: datetime
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: Business) -> BusinessView:
        return cls(
            id=value.id,
            workspace_id=value.workspace_id,
            name=value.name,
            canonical_url=value.canonical_url,
            permitted_host=value.permitted_host,
            created_at=value.created_at,
            links={
                "self": f"/api/v1/businesses/{value.id}",
                "research_runs": f"/api/v1/businesses/{value.id}/research-runs",
            },
        )


class ResearchRunView(BaseModel):
    id: UUID
    business_id: UUID
    operation_id: UUID
    trace_id: UUID
    start_url: str
    permitted_host: str
    policy: dict[str, object]
    status: str
    pages_attempted: int
    pages_succeeded: int
    bytes_stored: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ResearchRun) -> ResearchRunView:
        return cls(
            id=value.id,
            business_id=value.business_id,
            operation_id=value.operation_id,
            trace_id=value.trace_id,
            start_url=value.start_url,
            permitted_host=value.permitted_host,
            policy={
                field: getattr(value.policy, field) for field in value.policy.__dataclass_fields__
            },
            status=value.status,
            pages_attempted=value.pages_attempted,
            pages_succeeded=value.pages_succeeded,
            bytes_stored=value.bytes_stored,
            created_at=value.created_at,
            updated_at=value.updated_at,
            started_at=value.started_at,
            completed_at=value.completed_at,
            last_error_code=value.last_error_code,
            last_error_message=value.last_error_message,
            links={
                "self": f"/api/v1/research-runs/{value.id}",
                "business": f"/api/v1/businesses/{value.business_id}",
                "pages": f"/api/v1/research-runs/{value.id}/pages",
                "attempts": f"/api/v1/research-runs/{value.id}/attempts",
                "evidence": f"/api/v1/research-runs/{value.id}/evidence",
            },
        )


class FetchAttemptView(BaseModel):
    id: UUID
    research_run_id: UUID
    normalized_url: str
    attempt_number: int
    started_at: datetime
    completed_at: datetime
    outcome: str
    error_code: str | None

    @classmethod
    def from_domain(cls, value: FetchAttempt) -> FetchAttemptView:
        return cls(**{field: getattr(value, field) for field in cls.model_fields})


class PageView(BaseModel):
    id: UUID
    research_run_id: UUID
    requested_url: str
    normalized_url: str
    depth: int
    status: str
    snapshot_id: UUID | None
    material_id: UUID | None
    fetched_at: datetime | None
    error_code: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ResearchPage) -> PageView:
        links = {"run": f"/api/v1/research-runs/{value.research_run_id}"}
        if value.snapshot_id:
            links["snapshot"] = f"/api/v1/page-snapshots/{value.snapshot_id}"
        if value.material_id:
            links["material"] = f"/api/v1/extracted-material/{value.material_id}"
        return cls(
            **{field: getattr(value, field) for field in cls.model_fields if field != "links"},
            links=links,
        )


class SnapshotView(BaseModel):
    id: UUID
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
    response_headers: dict[str, str]

    @classmethod
    def from_domain(cls, value: PageSnapshot) -> SnapshotView:
        return cls(
            **{
                field: getattr(value, field)
                for field in cls.model_fields
                if field != "response_headers"
            },
            response_headers=dict(value.response_headers),
        )


class MaterialView(BaseModel):
    id: UUID
    snapshot_id: UUID
    extractor_name: str
    extractor_version: str
    title: str | None
    metadata: list[list[object]]
    headings: list[list[object]]
    visible_text: str
    links: list[list[object]]
    forms: list[list[object]]
    buttons: list[list[object]]
    contacts: list[list[object]]
    structured_data: list[str]
    technology_signals: list[list[object]]
    prompt_injection_suspected: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, value: ExtractedMaterial) -> MaterialView:
        data = {field: getattr(value, field) for field in cls.model_fields}
        return cls(**data)


class ResearchEvidenceView(BaseModel):
    id: UUID
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
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ResearchEvidence) -> ResearchEvidenceView:
        return cls(
            **{field: getattr(value, field) for field in cls.model_fields if field != "links"},
            links={
                "self": f"/api/v1/research-evidence/{value.id}",
                "run": f"/api/v1/research-runs/{value.research_run_id}",
                "snapshot": f"/api/v1/page-snapshots/{value.snapshot_id}",
            },
        )
