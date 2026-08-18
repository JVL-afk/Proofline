"""Typed M4 core and separate-runtime transport contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from opintel_demo.domain import (
    DemoBundle,
    DemoOperation,
    DemoReviewDecisionType,
    RuntimeSessionView,
)


class DemoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    parent_revision_id: UUID | None = None


class DemoReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_manifest_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_specification_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    decision: DemoReviewDecisionType
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class DemoRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SessionIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CapabilityExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: Annotated[str, StringConstraints(min_length=32, max_length=512)]
    persona_id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,64}$")]
    seed: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{1,64}$")]


class RuntimeEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_token: Annotated[str, StringConstraints(min_length=32, max_length=512)]
    event: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.:-]{1,80}$")]
    value: Annotated[str | None, StringConstraints(max_length=80)] = None
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class DemoOperationView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: dict[str, object]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: DemoOperation) -> DemoOperationView:
        return cls(
            operation=asdict(value),
            links={
                "self": f"/api/v1/demo-operations/{value.id}",
                "revision": f"/api/v1/demo-revisions/{value.demo_revision_id}"
                if value.demo_revision_id
                else "",
            },
        )


class DemoBundleView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: dict[str, object]
    latest_review: dict[str, object] | None
    review_valid: bool
    revocation: dict[str, object] | None

    @classmethod
    def from_domain(cls, value: DemoBundle) -> DemoBundleView:
        return cls(
            revision=asdict(value.revision),
            latest_review=asdict(value.latest_review) if value.latest_review else None,
            review_valid=value.review_valid,
            revocation=asdict(value.revocation) if value.revocation else None,
        )


class SessionCapabilityView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issuance_id: UUID
    capability: str
    expires_at: str
    runtime_origin: str


class RuntimeSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime: dict[str, object]
    session_token: str

    @classmethod
    def from_domain(cls, value: RuntimeSessionView, token: str) -> RuntimeSessionResponse:
        return cls(runtime=asdict(value), session_token=token)
