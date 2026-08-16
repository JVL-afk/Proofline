"""Typed M2 API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from opintel_opportunity.domain import (
    OpportunityAnalysisRun,
    OpportunityBundle,
    ReviewDecisionType,
)


class OpportunityRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_run_id: UUID


class AssumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal[
        "monthly_inbound_leads",
        "affected_share",
        "conversion_lift",
        "average_customer_value",
    ]
    value_state: Literal["known", "proposed", "unknown"]
    decimal_value: str | None = Field(default=None, max_length=80)
    source_kind: str | None = Field(default=None, max_length=80)
    provenance: str | None = Field(default=None, max_length=500)


class RecalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_hypothesis_revision_id: UUID
    assumptions: list[AssumptionInput] = Field(min_length=4, max_length=4)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_hypothesis_revision_id: UUID
    decision: ReviewDecisionType
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class InferenceRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_id: UUID
    expected_hypothesis_revision_id: UUID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class AnalysisRunView(BaseModel):
    id: UUID
    business_id: UUID
    research_run_id: UUID
    operation_id: UUID
    trace_id: UUID
    definition_version: str
    status: str
    hypothesis_id: UUID | None
    current_hypothesis_revision_id: UUID | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: OpportunityAnalysisRun) -> AnalysisRunView:
        return cls(
            **{field: getattr(value, field) for field in cls.model_fields if field != "links"},
            links={
                "self": f"/api/v1/opportunity-analysis-runs/{value.id}",
                "result": f"/api/v1/opportunity-analysis-runs/{value.id}/result",
            },
        )


class OpportunityBundleView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: dict[str, object]
    observations: list[dict[str, object]]
    inference: dict[str, object] | None
    hypothesis: dict[str, object] | None
    information_gaps: list[dict[str, object]]
    assumptions: list[dict[str, object]]
    economic_run: dict[str, object] | None
    score_snapshot: dict[str, object] | None
    latest_review: dict[str, object] | None
    review_valid: bool

    @classmethod
    def from_domain(cls, bundle: OpportunityBundle) -> OpportunityBundleView:
        from dataclasses import asdict

        return cls(
            run=asdict(bundle.run),
            observations=[asdict(item) for item in bundle.observations],
            inference=asdict(bundle.inference) if bundle.inference else None,
            hypothesis=asdict(bundle.hypothesis) if bundle.hypothesis else None,
            information_gaps=[asdict(item) for item in bundle.gaps],
            assumptions=[asdict(item) for item in bundle.assumptions],
            economic_run=asdict(bundle.economic_run) if bundle.economic_run else None,
            score_snapshot=asdict(bundle.score_snapshot) if bundle.score_snapshot else None,
            latest_review=asdict(bundle.latest_review) if bundle.latest_review else None,
            review_valid=bundle.review_valid,
        )
