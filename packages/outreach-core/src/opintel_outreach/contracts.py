"""Typed M5 API contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from opintel_outreach.domain import (
    OutreachBundle,
    OutreachOperation,
    OutreachReviewDecisionType,
)


class OutreachCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_demo_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    parent_revision_id: UUID | None = None


class OutreachReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_manifest_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    decision: OutreachReviewDecisionType
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class OutreachOperationView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: dict[str, object]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: OutreachOperation) -> OutreachOperationView:
        return cls(
            operation=asdict(value),
            links={
                "self": f"/api/v1/outreach-package-operations/{value.id}",
                "revision": f"/api/v1/outreach-package-revisions/{value.outreach_revision_id}"
                if value.outreach_revision_id
                else "",
            },
        )


class OutreachBundleView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: dict[str, object]
    latest_review: dict[str, object] | None
    review_valid: bool
    invalidation: dict[str, object] | None
    authority_notice: str

    @classmethod
    def from_domain(cls, value: OutreachBundle) -> OutreachBundleView:
        return cls(
            revision=asdict(value.revision),
            latest_review=asdict(value.latest_review) if value.latest_review else None,
            review_valid=value.review_valid,
            invalidation=asdict(value.invalidation) if value.invalidation else None,
            authority_notice=(
                "CONTENT_APPROVED is wording approval only. It does not authorize contact, copy, "
                "export, sending, publication, scheduling, recipient discovery, or integration."
            ),
        )
