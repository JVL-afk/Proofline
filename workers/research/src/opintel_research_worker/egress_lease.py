"""Single-work-item authority for the dormant Phase 1 controlled-egress service."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_research.domain import ResearchRun
from opintel_shadow import LiveResearchPermissionRelease
from pydantic import BaseModel, ConfigDict, model_validator

from opintel_research_worker.release_store import SsmReadWriteClient

EGRESS_LEASE_SCHEMA = "m67.phase1.controlled-egress-lease@1"
EGRESS_LEASE_LOCK_SENTINEL = '{"state":"NOT_AUTHORIZED"}'


class CanonicalNotAuthorizedEgressLease(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    state: Literal["NOT_AUTHORIZED"]


class ControlledEgressLease(BaseModel):
    """Exact live capability; it carries no authority beyond one immutable M1 work item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["m67.phase1.controlled-egress-lease@1"]
    state: Literal["AUTHORIZED"]
    lease_id: UUID
    authorization_release_id: UUID
    authorization_configuration_hash: str
    ordered_package_semantic_sha256: str
    slot_number: int
    business_identity: str
    exact_hostname: str
    work_item_id: UUID
    work_item_identity_sha256: str
    activation_sha256: str
    execution_ceilings_sha256: str
    starts_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_exact_shape(self) -> ControlledEgressLease:
        hashes = (
            self.authorization_configuration_hash,
            self.ordered_package_semantic_sha256,
            self.work_item_identity_sha256,
            self.activation_sha256,
            self.execution_ceilings_sha256,
        )
        if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise ValueError("controlled-egress lease hashes must be lowercase SHA-256")
        if self.slot_number < 1 or not self.business_identity or not self.exact_hostname:
            raise ValueError("controlled-egress lease identity is incomplete")
        if self.starts_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("controlled-egress lease times must be timezone-aware")
        if self.starts_at >= self.expires_at:
            raise ValueError("controlled-egress lease interval is invalid")
        if self.lease_id != self.expected_lease_id():
            raise ValueError("controlled-egress lease identity is not canonical")
        return self

    def expected_lease_id(self) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            "m67.phase1.controlled-egress-lease@1:"
            f"{self.authorization_release_id}:{self.work_item_id}:"
            f"{self.work_item_identity_sha256}:{self.execution_ceilings_sha256}",
        )

    def capability_payload(self) -> dict[str, object]:
        return {
            "activation_sha256": self.activation_sha256,
            "authorization_configuration_hash": self.authorization_configuration_hash,
            "authorization_release_id": str(self.authorization_release_id),
            "business_identity": self.business_identity,
            "exact_hostname": self.exact_hostname,
            "execution_ceilings_sha256": self.execution_ceilings_sha256,
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
            "lease_id": str(self.lease_id),
            "ordered_package_semantic_sha256": self.ordered_package_semantic_sha256,
            "slot_number": self.slot_number,
            "starts_at": self.starts_at.astimezone(UTC).isoformat(),
            "work_item_id": str(self.work_item_id),
            "work_item_identity_sha256": self.work_item_identity_sha256,
        }


def parse_stored_egress_lease(
    raw: str,
) -> CanonicalNotAuthorizedEgressLease | ControlledEgressLease:
    """Accept only the exact historical lock or the complete current live schema."""
    if raw == EGRESS_LEASE_LOCK_SENTINEL:
        return CanonicalNotAuthorizedEgressLease(state="NOT_AUTHORIZED")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema_version") != EGRESS_LEASE_SCHEMA:
        raise ValueError("controlled-egress lease is neither the exact lock nor current schema")
    return ControlledEgressLease.model_validate(value)


class EgressLeaseStore(Protocol):
    def read(self) -> str: ...
    def write(self, value: str) -> None: ...


class SsmControlledEgressLeaseStore:
    def __init__(
        self,
        parameter_name: str,
        region: str,
        client: SsmReadWriteClient | None = None,
    ) -> None:
        if not parameter_name.startswith("/m67-phase1/"):
            raise ValueError("controlled-egress lease requires an exact Phase 1 parameter")
        if client is None:
            import boto3  # type: ignore[import-untyped]

            client = boto3.client("ssm", region_name=region)
        self._client = client
        self._parameter = parameter_name

    def read(self) -> str:
        response = self._client.get_parameter(Name=self._parameter, WithDecryption=False)
        if not isinstance(response, dict):
            raise ValueError("controlled-egress lease parameter response is invalid")
        value = response.get("Parameter", {}).get("Value")
        if not isinstance(value, str):
            raise ValueError("controlled-egress lease parameter is unavailable")
        return value

    def write(self, value: str) -> None:
        self._client.put_parameter(Name=self._parameter, Value=value, Type="String", Overwrite=True)


def build_egress_lease(
    release: LiveResearchPermissionRelease, run: ResearchRun
) -> ControlledEgressLease:
    identity = run.sampled_slot_identity
    activation = run.sampled_slot_activation
    if identity is None or activation is None:
        raise ValueError("controlled egress requires immutable sampled-slot identity")
    if (
        release.slot_number != identity.slot_number
        or release.business_identity != identity.business_identity
        or release.exact_hostname != identity.exact_hostname
        or release.ordered_package_sha256 != identity.ordered_package_semantic_sha256
        or release.id != activation.authorization_release_id
        or release.configuration_hash != activation.authorization_configuration_hash
        or run.id != identity.work_item_id
        or run.permitted_host != identity.exact_hostname
    ):
        raise ValueError("controlled-egress lease identity is outside exact release/work item")
    values = {
        "schema_version": EGRESS_LEASE_SCHEMA,
        "state": "AUTHORIZED",
        "lease_id": uuid5(
            NAMESPACE_URL,
            "m67.phase1.controlled-egress-lease@1:"
            f"{release.id}:{run.id}:{identity.identity_sha256}:"
            f"{activation.execution_ceilings_sha256}",
        ),
        "authorization_release_id": release.id,
        "authorization_configuration_hash": release.configuration_hash,
        "ordered_package_semantic_sha256": identity.ordered_package_semantic_sha256,
        "slot_number": identity.slot_number,
        "business_identity": identity.business_identity,
        "exact_hostname": identity.exact_hostname,
        "work_item_id": run.id,
        "work_item_identity_sha256": identity.identity_sha256,
        "activation_sha256": activation.activation_sha256,
        "execution_ceilings_sha256": activation.execution_ceilings_sha256,
        "starts_at": release.starts_at,
        "expires_at": release.expires_at,
    }
    return ControlledEgressLease.model_validate(values)


def lease_value_sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "EGRESS_LEASE_LOCK_SENTINEL",
    "CanonicalNotAuthorizedEgressLease",
    "ControlledEgressLease",
    "SsmControlledEgressLeaseStore",
    "build_egress_lease",
    "parse_stored_egress_lease",
]
