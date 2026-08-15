"""Typed transport and durable workflow contracts for M0."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from opintel_m0.domain import ActivityAttempt, Campaign, EvidenceItem, Operation

CampaignName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
IdempotencyKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
]


def validate_fixture_uri(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "fixture" or parsed.netloc != "public":
        raise ValueError("fixture_uri must use fixture://public/<name>.html")
    if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError("fixture_uri may not contain credentials, port, query, or fragment")
    path = parsed.path.removeprefix("/")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}\.html", path):
        raise ValueError("fixture_uri path must be one safe lowercase .html filename")
    return value


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CampaignName
    fixture_uri: str

    @field_validator("fixture_uri")
    @classmethod
    def fixture_uri_is_controlled(cls, value: str) -> str:
        return validate_fixture_uri(value)


class CampaignView(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    fixture_uri: str
    created_by: str
    created_at: datetime
    links: dict[str, str]

    @classmethod
    def from_domain(cls, campaign: Campaign) -> CampaignView:
        return cls(
            id=campaign.id,
            workspace_id=campaign.workspace_id,
            name=campaign.name,
            fixture_uri=campaign.fixture_uri,
            created_by=campaign.created_by,
            created_at=campaign.created_at,
            links={
                "self": f"/api/v1/campaigns/{campaign.id}",
                "operations": f"/api/v1/campaigns/{campaign.id}/operations",
            },
        )


class PrincipalView(BaseModel):
    subject: str
    workspace_id: UUID
    roles: list[str]


class AttemptView(BaseModel):
    id: UUID
    activity_name: str
    activity_version: str
    idempotency_key: str
    attempt_number: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None

    @classmethod
    def from_domain(cls, attempt: ActivityAttempt) -> AttemptView:
        return cls(**{field: getattr(attempt, field) for field in cls.model_fields})


class OperationView(BaseModel):
    id: UUID
    campaign_id: UUID
    workflow_name: str
    workflow_version: str
    status: str
    trace_id: UUID
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    attempts: list[AttemptView]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, operation: Operation, attempts: list[ActivityAttempt]) -> OperationView:
        return cls(
            id=operation.id,
            campaign_id=operation.campaign_id,
            workflow_name=operation.workflow_name,
            workflow_version=operation.workflow_version,
            status=operation.status,
            trace_id=operation.trace_id,
            attempt_count=operation.attempt_count,
            max_attempts=operation.max_attempts,
            next_attempt_at=operation.next_attempt_at,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
            started_at=operation.started_at,
            completed_at=operation.completed_at,
            last_error_code=operation.last_error_code,
            last_error_message=operation.last_error_message,
            attempts=[AttemptView.from_domain(item) for item in attempts],
            links={
                "self": f"/api/v1/operations/{operation.id}",
                "campaign": f"/api/v1/campaigns/{operation.campaign_id}",
                "evidence": f"/api/v1/operations/{operation.id}/evidence",
            },
        )


class EvidenceView(BaseModel):
    id: UUID
    campaign_id: UUID
    operation_id: UUID
    source_type: str
    source_uri: str
    final_uri: str
    captured_at: datetime
    content_sha256: str
    mime_type: str
    title: str
    excerpt: str
    fragment_locator: str
    extractor_name: str
    extractor_version: str
    fixture_version: str
    created_at: datetime
    links: dict[str, str]

    @classmethod
    def from_domain(cls, evidence: EvidenceItem) -> EvidenceView:
        data = {field: getattr(evidence, field) for field in cls.model_fields if field != "links"}
        data["links"] = {
            "self": f"/api/v1/evidence/{evidence.id}",
            "operation": f"/api/v1/operations/{evidence.operation_id}",
            "campaign": f"/api/v1/campaigns/{evidence.campaign_id}",
        }
        return cls(**data)


class EvidenceCollection(BaseModel):
    items: list[EvidenceView]
    count: int


class WorkflowCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    workspace_id: UUID
    campaign_id: UUID
    fixture_uri: str
    workflow_name: Literal["m0.fixture_fetch"] = "m0.fixture_fetch"
    workflow_version: Literal["1"] = "1"
    activity_name: Literal["m0.fetch_fixture"] = "m0.fetch_fixture"
    activity_version: Literal["1"] = "1"
    max_attempts: int = Field(default=3, ge=1, le=3)
