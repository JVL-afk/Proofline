"""Typed M6.5 diagnostic API contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from opintel_activation.domain import ActivationRecord, LiveActivationReadiness


class ActivationRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: dict[str, object]
    authority_notice: str = (
        "Governance/readiness evidence only. This record cannot authorize or perform delivery."
    )

    @classmethod
    def from_domain(cls, value: ActivationRecord) -> ActivationRecordView:
        return cls(record=value.model_dump(mode="json"))


class ActivationReadinessView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    readiness: dict[str, object]
    live_delivery_enabled: bool = False
    production_infrastructure_provisioned: bool = False
    current_expected_state: str = "not_ready"

    @classmethod
    def from_domain(cls, value: LiveActivationReadiness) -> ActivationReadinessView:
        return cls(
            readiness=value.model_dump(mode="json"),
            current_expected_state=value.state,
        )
