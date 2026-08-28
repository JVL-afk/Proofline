"""Hash-bound one-shot sampled-slot release application and terminal consumption."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from opintel_research_worker.activation import A09_MARKER_PREFIX, FrozenA09DecisionRegistry
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

APPROVAL_SCHEMA = "m67.phase1.sampled-slot-execution-approval@3"
APPROVAL_STATE = "OWNER_APPROVED"
RELEASE_APPLICATOR_REVISION = "m67.phase1.release-applicator@1"
LEGACY_LOCK_SENTINEL = '{"state":"NOT_AUTHORIZED"}'
LEGACY_LOCK_SENTINEL_SHA256 = hashlib.sha256(LEGACY_LOCK_SENTINEL.encode("utf-8")).hexdigest()
SAMPLED_APPROVAL_LOCK_SENTINEL = '{"state":"NOT_AUTHORIZED"}'
SAMPLED_APPROVAL_LOCK_SENTINEL_SHA256 = hashlib.sha256(
    SAMPLED_APPROVAL_LOCK_SENTINEL.encode("utf-8")
).hexdigest()
LEGACY_LOCK_RELEASE_ID = uuid5(
    NAMESPACE_URL, f"m67.phase1.legacy-research-release-lock:{LEGACY_LOCK_SENTINEL_SHA256}"
)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
    ).hexdigest()


class SampledSlotExecutionApproval(BaseModel):
    """Exact immutable authority; every consequential field is mandatory and non-defaulted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["m67.phase1.sampled-slot-execution-approval@3"]
    state: Literal["OWNER_APPROVED"]
    approval_id: UUID
    owner_statement_sha256: str
    owner_signature_state: Literal["APPROVED_IN_THREAD"]
    current_release_id: UUID
    authorized_release_id: UUID
    workspace_id: UUID
    legacy_lock_sentinel_sha256: str
    permission_type: Literal["REAL_PUBLIC_RESEARCH"]
    source_registry_id: UUID
    source_registry_hash: str
    retention_policy_id: UUID
    retention_policy_hash: str
    environment_id: UUID
    environment_hash: str
    cohort_policy_id: UUID
    kill_switch_id: UUID
    ordered_package_file_sha256: str
    ordered_package_semantic_sha256: str
    slot_registry_file_sha256: str
    slot_registry_semantic_sha256: str
    slot_number: int
    business_identity: str
    exact_hostname: str
    a09_decision_sha256: str
    research_runtime_revision: str
    release_applicator_sha256: str
    activation_adapter_sha256: str
    activation_entry_point_sha256: str
    stage_coordinator_sha256: str
    m1_runtime_sha256: str
    m2_m5_runtime_sha256: str
    starts_at: datetime
    expires_at: datetime
    max_logical_requests: int
    max_attempts: int
    max_response_bytes: int
    max_total_bytes: int
    max_duration_seconds: int
    cost_ceiling_usd: Decimal
    allowed_source_scope: tuple[str, ...]
    terminal_rollback_state: Literal["NOT_AUTHORIZED"]

    @field_validator(
        "owner_statement_sha256",
        "legacy_lock_sentinel_sha256",
        "source_registry_hash",
        "retention_policy_hash",
        "environment_hash",
        "ordered_package_file_sha256",
        "ordered_package_semantic_sha256",
        "slot_registry_file_sha256",
        "slot_registry_semantic_sha256",
        "a09_decision_sha256",
        "release_applicator_sha256",
        "activation_adapter_sha256",
        "activation_entry_point_sha256",
        "stage_coordinator_sha256",
        "m1_runtime_sha256",
        "m2_m5_runtime_sha256",
    )
    @classmethod
    def lowercase_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("approval bindings require lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def exact_scope(self) -> SampledSlotExecutionApproval:
        if self.slot_number != 1 or self.business_identity != "903 HVAC":
            raise ValueError("this successor accepts only frozen Phase 1 Slot 01")
        if self.exact_hostname != "903hvac.com":
            raise ValueError("this successor accepts only the approved Slot 01 hostname")
        if self.allowed_source_scope != (self.exact_hostname,):
            raise ValueError("approval source scope must contain only the exact hostname")
        if self.expires_at <= self.starts_at:
            raise ValueError("approval validity window is invalid")
        if min(
            self.max_logical_requests,
            self.max_attempts,
            self.max_response_bytes,
            self.max_total_bytes,
            self.max_duration_seconds,
        ) < 1:
            raise ValueError("approval ceilings must be explicitly positive")
        if self.cost_ceiling_usd != Decimal("0"):
            raise ValueError("Phase 1 Slot 01 AI/source cost must remain USD 0")
        if self.legacy_lock_sentinel_sha256 != LEGACY_LOCK_SENTINEL_SHA256:
            raise ValueError("approval does not bind the exact historical lock sentinel")
        return self


class CanonicalNotAuthorizedResearchRelease(BaseModel):
    """Typed form of the one accepted historical lock; it carries no authority fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: Literal["NOT_AUTHORIZED"]


StoredResearchRelease = LiveResearchPermissionRelease | CanonicalNotAuthorizedResearchRelease


def parse_stored_research_release(raw: str) -> StoredResearchRelease:
    """Accept only the exact legacy bytes or a complete canonical current release."""

    if raw == LEGACY_LOCK_SENTINEL:
        return CanonicalNotAuthorizedResearchRelease(state="NOT_AUTHORIZED")
    return LiveResearchPermissionRelease.model_validate_json(raw)


class SampledSlotExecutionApprovalEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approval: SampledSlotExecutionApproval
    approval_artifact_sha256: str

    @model_validator(mode="after")
    def valid_hash(self) -> SampledSlotExecutionApprovalEnvelope:
        expected = canonical_sha256(self.approval.model_dump(mode="json"))
        if self.approval_artifact_sha256 != expected:
            raise ValueError("owner approval artifact hash mismatch")
        return self


class CanonicalNotAuthorizedSampledSlotApproval(BaseModel):
    """Typed sampled-approval lock; it carries no owner or execution authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: Literal["NOT_AUTHORIZED"]


StoredSampledSlotExecutionApproval = (
    SampledSlotExecutionApprovalEnvelope | CanonicalNotAuthorizedSampledSlotApproval
)


def parse_stored_sampled_slot_execution_approval(
    raw: str,
) -> StoredSampledSlotExecutionApproval:
    """Accept only the exact historical lock bytes or a complete live envelope."""

    if raw == SAMPLED_APPROVAL_LOCK_SENTINEL:
        return CanonicalNotAuthorizedSampledSlotApproval(state="NOT_AUTHORIZED")
    return SampledSlotExecutionApprovalEnvelope.model_validate_json(raw)


class ReleaseControlStore(Protocol):
    def read_approval_envelope(self) -> str: ...
    def read_release(self) -> str: ...
    def write_release(self, value: str) -> None: ...
    def read_kill_switch(self) -> str: ...
    def write_kill_switch(self, value: str) -> None: ...


class BoundedSampledSlotReleaseApplicator:
    """Apply one exact owner artifact; callers supply no business, host, slot, or URL."""

    def __init__(
        self,
        *,
        store: ReleaseControlStore,
        sample_registry: FrozenPhaseOneSampleRegistry,
        a09_registry: FrozenA09DecisionRegistry,
        runtime_revision: str,
        expected_activation_adapter_sha256: str,
        expected_release_applicator_sha256: str,
        expected_activation_entry_point_sha256: str,
        expected_stage_coordinator_sha256: str,
        expected_m1_runtime_sha256: str,
        expected_m2_m5_runtime_sha256: str,
        now: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._samples = sample_registry
        self._a09 = a09_registry
        self._runtime = runtime_revision
        self._expected_hashes = (
            expected_release_applicator_sha256,
            expected_activation_adapter_sha256,
            expected_activation_entry_point_sha256,
            expected_stage_coordinator_sha256,
            expected_m1_runtime_sha256,
            expected_m2_m5_runtime_sha256,
        )
        self._now = now

    def apply(self) -> tuple[LiveResearchPermissionRelease, SampledSlotExecutionApproval, bool]:
        stored_approval = parse_stored_sampled_slot_execution_approval(
            self._store.read_approval_envelope()
        )
        if isinstance(stored_approval, CanonicalNotAuthorizedSampledSlotApproval):
            raise ValueError("sampled-slot execution approval is NOT_AUTHORIZED")
        envelope = stored_approval
        approval = envelope.approval
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        if not approval.starts_at <= now < approval.expires_at:
            raise ValueError("owner approval is not currently effective")
        if approval.research_runtime_revision != self._runtime:
            raise ValueError("owner approval runtime revision mismatch")
        if self._expected_hashes != (
            approval.release_applicator_sha256,
            approval.activation_adapter_sha256,
            approval.activation_entry_point_sha256,
            approval.stage_coordinator_sha256,
            approval.m1_runtime_sha256,
            approval.m2_m5_runtime_sha256,
        ):
            raise ValueError("owner approval implementation binding mismatch")
        kill_state = self._store.read_kill_switch()
        current_raw = self._store.read_release()
        current = parse_stored_research_release(current_raw)
        if (
            isinstance(current, LiveResearchPermissionRelease)
            and current.id == approval.authorized_release_id
        ):
            if (
                current.state is not PermissionState.AUTHORIZED
                or current.configuration_hash
                != canonical_sha256(approval.model_dump(mode="json"))
                or current.slot_number != approval.slot_number
                or current.business_identity != approval.business_identity
                or current.exact_hostname != approval.exact_hostname
                or current.owner_approval_sha256 != approval.owner_statement_sha256
            ):
                raise ValueError("duplicate release application differs from exact authority")
            if kill_state not in {"TRIPPED", "RUN"}:
                raise ValueError("resumed release has an invalid kill-switch state")
            return current, approval, False
        if kill_state != "TRIPPED":
            raise ValueError("release application requires the locked pre-execution state")
        if isinstance(current, CanonicalNotAuthorizedResearchRelease):
            if approval.current_release_id != LEGACY_LOCK_RELEASE_ID:
                raise ValueError("owner approval does not bind the canonical legacy lock identity")
        elif (
            current.id != approval.current_release_id
            or current.activity is not PermissionActivity.REAL_PUBLIC_RESEARCH
            or current.state is not PermissionState.NOT_AUTHORIZED
            or not self._replaceable_locked_predecessor(current, approval)
            or current.workspace_id != approval.workspace_id
            or current.source_registry_id != approval.source_registry_id
            or current.source_registry_hash != approval.source_registry_hash
            or current.retention_policy_id != approval.retention_policy_id
            or current.retention_policy_hash != approval.retention_policy_hash
            or current.environment_id != approval.environment_id
            or current.environment_hash != approval.environment_hash
            or current.cohort_policy_id != approval.cohort_policy_id
            or current.kill_switch_id != approval.kill_switch_id
        ):
            raise ValueError("current release is conflicting, revoked, or superseded")

        self._validate_registry_bindings(approval)
        release = self._build_release(current, approval)
        self._store.write_release(release.model_dump_json())
        return release, approval, True

    @staticmethod
    def _replaceable_locked_predecessor(
        current: LiveResearchPermissionRelease,
        approval: SampledSlotExecutionApproval,
    ) -> bool:
        """Accept an ordinary lock or the exact immutable terminal form of a consumed run."""

        if current.revoked_at is None:
            return current.suspended_reason is None
        return bool(
            current.suspended_reason
            and current.suspended_reason.startswith("CONSUMED:")
            and current.owner_approval_sha256 != approval.owner_statement_sha256
        )

    def enter_run(self, release: LiveResearchPermissionRelease) -> None:
        current = parse_stored_research_release(self._store.read_release())
        if not isinstance(current, LiveResearchPermissionRelease):
            raise ValueError("cannot enter RUN without an exact live release")
        if current.configuration_hash != release.configuration_hash or current.id != release.id:
            raise ValueError("cannot enter RUN for a stale or different release")
        kill_state = self._store.read_kill_switch()
        if kill_state == "RUN":
            return
        if kill_state != "TRIPPED":
            raise ValueError("kill switch pre-run state changed")
        self._store.write_kill_switch("RUN")

    def consume(self, release: LiveResearchPermissionRelease, reason: str) -> None:
        self._store.write_kill_switch("TRIPPED")
        current = parse_stored_research_release(self._store.read_release())
        if not isinstance(current, LiveResearchPermissionRelease):
            raise ValueError("cannot consume authority from a locked sentinel")
        if current.id != release.id or current.configuration_hash != release.configuration_hash:
            raise ValueError("terminal release differs from the executed authority")
        now = self._now()
        consumed = current.model_copy(
            update={
                "id": UUID(int=current.id.int ^ 1),
                "version": f"{current.version}.consumed",
                "configuration_hash": canonical_sha256(
                    (current.configuration_hash, "CONSUMED", reason, now.isoformat())
                ),
                "created_at": now,
                "state": PermissionState.NOT_AUTHORIZED,
                "suspended_reason": f"CONSUMED:{reason}",
                "revoked_at": now,
            }
        )
        consumed = LiveResearchPermissionRelease.model_validate(
            consumed.model_dump(mode="python")
        )
        self._store.write_release(consumed.model_dump_json())

    def _validate_registry_bindings(self, approval: SampledSlotExecutionApproval) -> None:
        entry = self._samples.issue(UUID(int=0), approval.slot_number)
        if (
            self._samples.registry_file_sha256 != approval.slot_registry_file_sha256
            or self._samples.registry_sha256 != approval.slot_registry_semantic_sha256
            or self._samples.ordered_package_file_sha256
            != approval.ordered_package_file_sha256
            or self._samples.ordered_package_semantic_sha256
            != approval.ordered_package_semantic_sha256
            or entry.business_identity != approval.business_identity
            or entry.exact_hostname != approval.exact_hostname
        ):
            raise ValueError("owner approval does not match the frozen sampled slot")
        decision = self._a09.require_approved(
            approval.slot_number, approval.business_identity, approval.exact_hostname
        )
        if decision.decision_sha256 != approval.a09_decision_sha256:
            raise ValueError("owner approval does not bind the accepted A-09 decision")

    def _build_release(
        self,
        current: StoredResearchRelease,
        approval: SampledSlotExecutionApproval,
    ) -> LiveResearchPermissionRelease:
        payload = approval.model_dump(mode="json")
        if isinstance(current, CanonicalNotAuthorizedResearchRelease):
            return LiveResearchPermissionRelease(
                id=approval.authorized_release_id,
                workspace_id=approval.workspace_id,
                version=f"{RELEASE_APPLICATOR_REVISION}.slot01-owner-authorized",
                configuration_hash=canonical_sha256(payload),
                created_at=self._now(),
                activity=PermissionActivity.REAL_PUBLIC_RESEARCH,
                state=PermissionState.AUTHORIZED,
                source_registry_id=approval.source_registry_id,
                source_registry_hash=approval.source_registry_hash,
                retention_policy_id=approval.retention_policy_id,
                retention_policy_hash=approval.retention_policy_hash,
                environment_id=approval.environment_id,
                environment_hash=approval.environment_hash,
                cohort_policy_id=approval.cohort_policy_id,
                cohort_or_run_restriction="PHASE1_SLOT_01",
                starts_at=approval.starts_at,
                expires_at=approval.expires_at,
                approval_ids=(
                    str(approval.approval_id),
                    f"{A09_MARKER_PREFIX}{approval.a09_decision_sha256}",
                ),
                kill_switch_id=approval.kill_switch_id,
                slot_number=approval.slot_number,
                business_identity=approval.business_identity,
                exact_hostname=approval.exact_hostname,
                ordered_package_sha256=approval.ordered_package_semantic_sha256,
                research_runtime_revision=approval.research_runtime_revision,
                max_logical_requests=approval.max_logical_requests,
                max_attempts=approval.max_attempts,
                max_response_bytes=approval.max_response_bytes,
                max_total_bytes=approval.max_total_bytes,
                max_duration_seconds=approval.max_duration_seconds,
                cost_ceiling_usd=approval.cost_ceiling_usd,
                allowed_source_scope=approval.allowed_source_scope,
                terminal_rollback_state=approval.terminal_rollback_state,
                owner_approval_sha256=approval.owner_statement_sha256,
            )
        value = current.model_copy(
            update={
                "id": approval.authorized_release_id,
                "version": f"{current.version}.slot01-owner-authorized",
                "configuration_hash": canonical_sha256(payload),
                "created_at": self._now(),
                "state": PermissionState.AUTHORIZED,
                "cohort_or_run_restriction": "PHASE1_SLOT_01",
                "starts_at": approval.starts_at,
                "expires_at": approval.expires_at,
                "approval_ids": (
                    str(approval.approval_id),
                    f"{A09_MARKER_PREFIX}{approval.a09_decision_sha256}",
                ),
                "slot_number": approval.slot_number,
                "business_identity": approval.business_identity,
                "exact_hostname": approval.exact_hostname,
                "ordered_package_sha256": approval.ordered_package_semantic_sha256,
                "research_runtime_revision": approval.research_runtime_revision,
                "max_logical_requests": approval.max_logical_requests,
                "max_attempts": approval.max_attempts,
                "max_response_bytes": approval.max_response_bytes,
                "max_total_bytes": approval.max_total_bytes,
                "max_duration_seconds": approval.max_duration_seconds,
                "cost_ceiling_usd": approval.cost_ceiling_usd,
                "allowed_source_scope": approval.allowed_source_scope,
                "terminal_rollback_state": approval.terminal_rollback_state,
                "owner_approval_sha256": approval.owner_statement_sha256,
                "suspended_reason": None,
                "revoked_at": None,
            }
        )
        return LiveResearchPermissionRelease.model_validate(value.model_dump(mode="python"))
