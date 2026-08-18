"""Typed M6 API contracts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from opintel_contact.domain import (
    AcquisitionOrigin,
    ContactPoint,
    InboundReply,
    M6Record,
    ReplyKind,
    SuppressionReason,
)

SafeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class PersonIdentifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
    ]
    functional_role: SafeText
    source_uri: Annotated[str, StringConstraints(pattern=r"^fixture://")]
    source_locator: SafeText


class ContactPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=254)]
    acquisition_origin: AcquisitionOrigin
    source_uri: Annotated[str, StringConstraints(pattern=r"^fixture://")]
    source_locator: SafeText


class EligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = "b2b_first_contact"


class SenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: SafeText
    mailbox: Annotated[str, StringConstraints(pattern=r"^[^\r\n]+@fixture\.invalid$")]
    signature: SafeText
    postal_disclosure: SafeText
    opt_out_instruction: SafeText


class ReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_point_id: UUID
    sender_identity_id: UUID
    artifact_kind: str = "first_contact_email"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_manifest_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_preview_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    reason: SafeText


class SuppressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: SuppressionReason


class FixtureEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: SafeText
    event_type: SafeText
    body: Annotated[str, StringConstraints(max_length=5000)] = ""
    signature: SafeText


class ClassificationCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ReplyKind


class ReanalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement_ids: tuple[UUID, ...]
    reason: SafeText


class ContactRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: dict[str, object]
    authority_notice: str = (
        "Synthetic mock-only M6 record. No live provider, recipient, or message is authorized."
    )

    @classmethod
    def from_domain(cls, value: M6Record) -> ContactRecordView:
        record = value.model_dump(mode="json")
        if isinstance(value, ContactPoint):
            record["value"] = value.redacted_value
        if isinstance(value, InboundReply):
            record["body"] = "[REDACTED; use controlled first-party statement view]"
        return cls(record=record)
