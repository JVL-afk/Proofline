"""Typed M3 API contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from opintel_audit.domain import (
    AuditBundle,
    AuditOperation,
    AuditReviewDecisionType,
)


class AuditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_hypothesis_revision_id: UUID
    parent_revision_id: UUID | None = None


class AuditReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_manifest_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    decision: AuditReviewDecisionType
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    acknowledged_qc_codes: list[str] = Field(default_factory=list, max_length=20)


class AuditOperationView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: dict[str, object]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: AuditOperation) -> AuditOperationView:
        return cls(
            operation=asdict(value),
            links={
                "self": f"/api/v1/audit-operations/{value.id}",
                "revision": f"/api/v1/audit-revisions/{value.audit_revision_id}"
                if value.audit_revision_id
                else "",
            },
        )


class AuditBundleView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: dict[str, object]
    latest_review: dict[str, object] | None
    review_valid: bool

    @classmethod
    def from_domain(cls, value: AuditBundle) -> AuditBundleView:
        return cls(
            revision=asdict(value.revision),
            latest_review=asdict(value.latest_review) if value.latest_review else None,
            review_valid=value.review_valid,
        )
