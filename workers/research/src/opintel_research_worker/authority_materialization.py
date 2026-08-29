"""Deterministic materialization of the exact single-use sampled-slot approval.

The owner authorizes ``AUTHORIZE_SLOT01_BOUNDED_REPAIR_WINDOW_2_AND_M1_M5_EXECUTION``
with a signed statement plus an immutable acceptance record. That authority names the
experiment, approval, release, lease and work-item identifiers and the exact research
ceilings, but it is *not* a ready-to-consume ``m67.phase1.sampled-slot-execution-approval@3``
envelope: several immutable release-binding fields (workspace, source registry, retention
policy, environment, cohort policy, kill switch) only exist in the current predecessor
research-release object held in AWS SSM.

This module rebuilds the exact envelope deterministically from:

* the accepted owner authorization statement (hash-verified against its record);
* the frozen Phase 1 slot and A-09 registries;
* the exact current predecessor research-release value read from SSM;
* the exact deployed sampled-slot activator task-definition environment.

No field is invented, defaulted or copied from a test fixture. The completed envelope is
validated with the *same* :class:`BoundedSampledSlotReleaseApplicator` the activator uses
before it may be written. Possession of this code alone creates no authority: without the
exact accepted statement, the bound identifiers, the exact predecessor state and the
dormant preconditions, materialization fails before any write.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.release_application import (
    APPROVAL_SCHEMA,
    SAMPLED_APPROVAL_LOCK_SENTINEL,
    BoundedSampledSlotReleaseApplicator,
    SampledSlotExecutionApproval,
    SampledSlotExecutionApprovalEnvelope,
    canonical_sha256,
    parse_stored_research_release,
    parse_stored_sampled_slot_execution_approval,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

WINDOW_2_EVENT = "AUTHORIZE_SLOT01_BOUNDED_REPAIR_WINDOW_2_AND_M1_M5_EXECUTION"
ACCEPTED_STATE = "ACCEPTED_UNCONSUMED"
EXPECTED_ACCOUNT_ID = "785072247535"
EXPECTED_REGION = "us-east-2"
SLOT_NUMBER = 1

_ACTIVATOR_ENVIRONMENT_KEYS = {
    "research_runtime_revision": "OPINTEL_RESEARCH_RUNTIME_REVISION",
    "release_applicator_sha256": "OPINTEL_RELEASE_APPLICATOR_SHA256",
    "activation_adapter_sha256": "OPINTEL_ACTIVATION_ADAPTER_SHA256",
    "activation_entry_point_sha256": "OPINTEL_ACTIVATION_ENTRY_POINT_SHA256",
    "stage_coordinator_sha256": "OPINTEL_STAGE_COORDINATOR_SHA256",
    "m1_runtime_sha256": "OPINTEL_M1_RUNTIME_SHA256",
    "m2_m5_runtime_sha256": "OPINTEL_M2_M5_RUNTIME_SHA256",
}


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_MAX_BOUNDED_REPAIRS = 5


class AuthorityMaterializationError(RuntimeError):
    """Raised when the exact single-use approval cannot be materialized safely."""


@dataclass(frozen=True, slots=True)
class ConsumedLiveBudget:
    """Live M1 activity already spent against the frozen experiment's original
    ceilings once first target transport has occurred.

    The Window 2 statement forbids resetting any request, authorization-attempt,
    transport-attempt, byte, time or cost counter because of a repair. When this
    is supplied, the materialized envelope binds the *remaining* allowance
    (original statement ceiling minus already-consumed live activity), and
    materialization fails closed if the remainder cannot host a further run.
    """

    logical_requests: int = 0
    authorization_attempts: int = 0
    total_bytes: int = 0
    authority_seconds: int = 0
    transport_attempts: int = 0
    cost_usd: str = "0"


@dataclass(frozen=True, slots=True)
class RepairImageSuccessor:
    """One sealed link in the bounded-repair image successor chain.

    The accepted Window 2 statement authorizes at most five sequential eligible
    repairs and requires every repair to immutably seal its registry identity,
    representation equivalence, clean provider scan and deployment. When an
    eligible repair republishes the worker image, the deployed activator runtime
    revision is the repair successor digest rather than the digest inline in the
    owner statement. Each link is derived by
    :mod:`authority_materialization_main` from the committed sealed evidence
    files; the core only checks the chain is contiguous, owner-anchored, within
    the five-repair bound, representation-equivalent and scan-clean.
    """

    repair_number: int
    predecessor_image_digest: str
    successor_image_digest: str
    registry_evidence_sha256: str
    deployment_evidence_sha256: str
    representation_equivalent_proven: bool
    ecr_scan_critical: int
    ecr_scan_high: int
    ecr_scan_blocking: int


def _require(condition: object, message: str) -> None:
    if not condition:
        raise AuthorityMaterializationError(message)


def _uuid(value: object, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as error:
        raise AuthorityMaterializationError(f"authority field is not a UUID: {field}") from error


def _iso_utc(value: str, field: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise AuthorityMaterializationError(f"authority timestamp is invalid: {field}") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _one(pattern: str, text: str, field: str) -> str:
    matches = re.findall(pattern, text)
    _require(matches, f"accepted owner statement does not bind {field}")
    _require(len(set(matches)) == 1, f"accepted owner statement binds {field} inconsistently")
    return str(matches[0])


@dataclass(frozen=True, slots=True)
class MaterializationInputs:
    """Every authoritative input, each from exactly one non-synthetic source."""

    owner_authorization_statement: str
    owner_authorization_record: Mapping[str, object]
    sample_registry: FrozenPhaseOneSampleRegistry
    a09_registry: FrozenA09DecisionRegistry
    current_research_release_raw: str
    kill_switch_state: str
    stored_sampled_slot_approval_raw: str
    deployed_activator_environment: Mapping[str, str]
    now: datetime
    repair_image_successor_chain: tuple[RepairImageSuccessor, ...] = ()
    consumed_live_budget: ConsumedLiveBudget | None = None


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    envelope: SampledSlotExecutionApprovalEnvelope
    approval_artifact_sha256: str
    already_present: bool
    predecessor_release_id: UUID
    authorized_release_id: UUID
    diagnostics: Mapping[str, object]


class _CapturingStore:
    """Read-only-in-effect store: it records writes without side effects for the dry run."""

    def __init__(self, approval: str, release: str, kill: str) -> None:
        self._approval = approval
        self._release = release
        self._kill = kill
        self.release_writes: list[str] = []
        self.kill_writes: list[str] = []

    def read_approval_envelope(self) -> str:
        return self._approval

    def read_release(self) -> str:
        return self._release

    def write_release(self, value: str) -> None:
        self.release_writes.append(value)
        self._release = value

    def read_kill_switch(self) -> str:
        return self._kill

    def write_kill_switch(self, value: str) -> None:
        self.kill_writes.append(value)
        self._kill = value


def _statement_sha256(statement: str) -> str:
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()


def _verify_accepted_authority(inputs: MaterializationInputs) -> Mapping[str, object]:
    record = inputs.owner_authorization_record
    _require(
        record.get("event") == WINDOW_2_EVENT,
        "authorization record is not the Window 2 M1-M5 execution event",
    )
    _require(
        record.get("state") == ACCEPTED_STATE,
        f"authorization record is not {ACCEPTED_STATE} (state={record.get('state')!r})",
    )
    _require(record.get("account_id") == EXPECTED_ACCOUNT_ID, "authorization account mismatch")
    _require(record.get("region") == EXPECTED_REGION, "authorization region mismatch")
    expected_hash = record.get("exact_statement_sha256")
    actual_hash = _statement_sha256(inputs.owner_authorization_statement)
    _require(
        isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash),
        "authorization record has no exact statement hash",
    )
    _require(
        actual_hash == expected_hash,
        "accepted owner statement does not hash to the recorded authorization",
    )
    return record


def _bound_identifiers(inputs: MaterializationInputs) -> dict[str, object]:
    statement = inputs.owner_authorization_statement
    record = inputs.owner_authorization_record

    uuid_re = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    approval_id = _one(
        rf"approval ID ({uuid_re})", statement, "approval_id"
    )
    authorized_release_id = _one(
        rf"initial authorized release ID ({uuid_re})", statement, "authorized_release_id"
    )
    experiment_id = _one(
        rf"experiment ID (?:is )?({uuid_re})", statement, "experiment_id"
    )
    starts_at = _one(
        r"between (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) and \d{4}-\d{2}-\d{2}T",
        statement,
        "starts_at",
    )
    expires_at = _one(
        r"between \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z and (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)",
        statement,
        "expires_at",
    )

    _require(
        approval_id == str(record.get("approval_id")),
        "statement approval_id disagrees with the acceptance record",
    )
    _require(
        authorized_release_id == str(record.get("initial_release_id")),
        "statement authorized release id disagrees with the acceptance record",
    )
    _require(
        experiment_id == str(record.get("experiment_id")),
        "statement experiment id disagrees with the acceptance record",
    )

    ceilings = {
        "max_logical_requests": int(
            _one(r"(\d+) logical requests", statement, "logical requests")
        ),
        "max_attempts": int(
            _one(r"(\d+) authorization attempts", statement, "authorization attempts")
        ),
        "max_response_bytes": int(
            _one(r"(\d+) bytes per response", statement, "response bytes")
        ),
        "max_total_bytes": int(
            _one(r"(\d+) cumulative bytes", statement, "cumulative bytes")
        ),
        "max_duration_seconds": int(
            _one(r"(\d+) authority seconds", statement, "authority seconds")
        ),
    }
    _require(
        "USD 0 research cost" in statement,
        "accepted owner statement does not fix research cost at USD 0",
    )
    transport_attempt_ceiling = int(
        _one(r"(\d+) transport attempts", statement, "transport attempts")
    )
    consumed = inputs.consumed_live_budget
    if consumed is not None:
        for label, value in (
            ("logical_requests", consumed.logical_requests),
            ("authorization_attempts", consumed.authorization_attempts),
            ("total_bytes", consumed.total_bytes),
            ("authority_seconds", consumed.authority_seconds),
            ("transport_attempts", consumed.transport_attempts),
        ):
            _require(
                isinstance(value, int) and value >= 0,
                f"consumed live budget component {label} is not a non-negative integer",
            )
        _require(
            str(consumed.cost_usd) == "0",
            "consumed live research cost is non-zero; the frozen experiment fixes cost at USD 0",
        )
        ceilings["max_logical_requests"] -= consumed.logical_requests
        ceilings["max_attempts"] -= consumed.authorization_attempts
        ceilings["max_total_bytes"] -= consumed.total_bytes
        ceilings["max_duration_seconds"] -= consumed.authority_seconds
        _require(
            ceilings["max_logical_requests"] >= 1
            and ceilings["max_attempts"] >= 1
            and ceilings["max_total_bytes"] >= 1
            and ceilings["max_duration_seconds"] >= 1
            and consumed.transport_attempts <= transport_attempt_ceiling,
            "the repair-resumed run cannot fit inside the remaining authorized "
            "M1 ceilings after already-consumed live activity",
        )
    return {
        "approval_id": _uuid(approval_id, "approval_id"),
        "authorized_release_id": _uuid(authorized_release_id, "authorized_release_id"),
        "owner_statement_sha256": record["exact_statement_sha256"],
        "starts_at": _iso_utc(starts_at, "starts_at"),
        "expires_at": _iso_utc(expires_at, "expires_at"),
        **ceilings,
    }


def _predecessor_bindings(
    inputs: MaterializationInputs, owner_statement_sha256: str
) -> dict[str, object]:
    parsed = parse_stored_research_release(inputs.current_research_release_raw)
    _require(
        isinstance(parsed, LiveResearchPermissionRelease),
        "current research-release is the legacy sentinel; expected a consumed predecessor",
    )
    assert isinstance(parsed, LiveResearchPermissionRelease)
    _require(
        parsed.activity is PermissionActivity.REAL_PUBLIC_RESEARCH,
        "current research-release is not a public-research permission",
    )
    _require(
        parsed.state is PermissionState.NOT_AUTHORIZED,
        f"current research-release is not NOT_AUTHORIZED (state={parsed.state})",
    )
    suspended_reason = parsed.suspended_reason
    _require(
        parsed.revoked_at is not None
        and suspended_reason is not None
        and suspended_reason.startswith("CONSUMED:"),
        "current research-release is not an immutable consumed terminal predecessor",
    )
    _require(
        parsed.owner_approval_sha256 != owner_statement_sha256,
        "current research-release already binds this exact Window 2 statement; authority consumed",
    )
    return {
        "current_release_id": parsed.id,
        "workspace_id": parsed.workspace_id,
        "source_registry_id": parsed.source_registry_id,
        "source_registry_hash": parsed.source_registry_hash,
        "retention_policy_id": parsed.retention_policy_id,
        "retention_policy_hash": parsed.retention_policy_hash,
        "environment_id": parsed.environment_id,
        "environment_hash": parsed.environment_hash,
        "cohort_policy_id": parsed.cohort_policy_id,
        "kill_switch_id": parsed.kill_switch_id,
    }


def _registry_bindings(inputs: MaterializationInputs) -> dict[str, object]:
    samples = inputs.sample_registry
    entry = samples.issue(UUID(int=0), SLOT_NUMBER)
    decision = inputs.a09_registry.require_approved(
        SLOT_NUMBER, entry.business_identity, entry.exact_hostname
    )
    statement = inputs.owner_authorization_statement
    for label, value in (
        ("ordered-package file", samples.ordered_package_file_sha256),
        ("ordered-package semantic", samples.ordered_package_semantic_sha256),
        ("slot-registry file", samples.registry_file_sha256),
        ("slot-registry semantic", samples.registry_sha256),
        ("A-09 decision", decision.decision_sha256),
    ):
        _require(
            value in statement,
            f"frozen {label} SHA-256 is not bound by the accepted owner statement",
        )
    _require(
        entry.business_identity in statement and entry.exact_hostname in statement,
        "frozen slot business/hostname is not bound by the accepted owner statement",
    )
    return {
        "ordered_package_file_sha256": samples.ordered_package_file_sha256,
        "ordered_package_semantic_sha256": samples.ordered_package_semantic_sha256,
        "slot_registry_file_sha256": samples.registry_file_sha256,
        "slot_registry_semantic_sha256": samples.registry_sha256,
        "slot_number": SLOT_NUMBER,
        "business_identity": entry.business_identity,
        "exact_hostname": entry.exact_hostname,
        "a09_decision_sha256": decision.decision_sha256,
    }


def _runtime_bindings(inputs: MaterializationInputs) -> dict[str, object]:
    env = inputs.deployed_activator_environment
    values: dict[str, object] = {}
    for field, key in _ACTIVATOR_ENVIRONMENT_KEYS.items():
        raw = env.get(key)
        _require(
            isinstance(raw, str) and raw.strip() != "",
            f"deployed activator task definition is missing {key}",
        )
        values[field] = raw
    revision = str(values["research_runtime_revision"])
    _require(
        revision.startswith("sha256:") and _IMAGE_DIGEST.fullmatch(revision),
        "deployed activator runtime revision is not a sha256 digest",
    )
    _accept_runtime_revision(revision, inputs)
    return values


def _accept_runtime_revision(revision: str, inputs: MaterializationInputs) -> None:
    """Accept the deployed activator digest only if the owner bound it directly
    or a sealed, owner-anchored bounded-repair chain proves it is the successor."""

    if revision in inputs.owner_authorization_statement:
        return

    chain = inputs.repair_image_successor_chain
    _require(
        bool(chain),
        "deployed activator runtime revision is neither bound by the owner statement "
        "nor backed by a sealed bounded-repair image successor chain",
    )
    _require(
        len(chain) <= _MAX_BOUNDED_REPAIRS,
        "bounded-repair image successor chain exceeds the five-repair authorization",
    )
    _require(
        _digest_in_statement(chain[0].predecessor_image_digest, inputs),
        "the bounded-repair image successor chain does not start from the "
        "image digest bound by the accepted owner statement",
    )
    for index, link in enumerate(chain):
        where = f"bounded-repair image successor {index + 1}"
        _require(link.repair_number == index + 1, f"{where} is not sequentially numbered from one")
        for label, digest in (
            ("predecessor", link.predecessor_image_digest),
            ("successor", link.successor_image_digest),
        ):
            _require(
                isinstance(digest, str) and bool(_IMAGE_DIGEST.fullmatch(digest)),
                f"{where} {label} image digest is not a sha256 digest",
            )
        for label, value in (
            ("registry", link.registry_evidence_sha256),
            ("deployment", link.deployment_evidence_sha256),
        ):
            _require(
                isinstance(value, str) and bool(_SHA256_HEX.fullmatch(value)),
                f"{where} sealed {label} evidence sha256 is missing or malformed",
            )
        _require(
            link.predecessor_image_digest != link.successor_image_digest,
            f"{where} predecessor and successor image digests are identical",
        )
        _require(
            link.representation_equivalent_proven is True,
            f"{where} image is not representation-equivalent proven against its local build",
        )
        _require(
            link.ecr_scan_critical == 0
            and link.ecr_scan_high == 0
            and link.ecr_scan_blocking == 0,
            f"{where} image ECR scan is not COMPLETE with critical/high/blocking 0/0/0",
        )
        if index > 0:
            _require(
                chain[index - 1].successor_image_digest == link.predecessor_image_digest,
                "bounded-repair image successor chain is not contiguous",
            )
    _require(
        chain[-1].successor_image_digest == revision,
        "the deployed activator runtime revision is not the final sealed "
        "bounded-repair image successor",
    )


def _digest_in_statement(digest: str, inputs: MaterializationInputs) -> bool:
    return isinstance(digest, str) and digest in inputs.owner_authorization_statement


def _dry_run_production_validator(
    envelope: SampledSlotExecutionApprovalEnvelope,
    inputs: MaterializationInputs,
    expected_authorized_release_id: UUID,
) -> Mapping[str, object]:
    """Prove the envelope is accepted by the exact activator-side applicator."""

    runtime = envelope.approval
    store = _CapturingStore(
        approval=envelope.model_dump_json(),
        release=inputs.current_research_release_raw,
        kill=inputs.kill_switch_state,
    )
    applicator = BoundedSampledSlotReleaseApplicator(
        store=store,
        sample_registry=inputs.sample_registry,
        a09_registry=inputs.a09_registry,
        runtime_revision=runtime.research_runtime_revision,
        expected_release_applicator_sha256=runtime.release_applicator_sha256,
        expected_activation_adapter_sha256=runtime.activation_adapter_sha256,
        expected_activation_entry_point_sha256=runtime.activation_entry_point_sha256,
        expected_stage_coordinator_sha256=runtime.stage_coordinator_sha256,
        expected_m1_runtime_sha256=runtime.m1_runtime_sha256,
        expected_m2_m5_runtime_sha256=runtime.m2_m5_runtime_sha256,
        now=lambda: inputs.now,
    )
    try:
        release, approval, created = applicator.apply()
    except Exception as error:
        raise AuthorityMaterializationError(
            f"production applicator rejects the materialized envelope: {error}"
        ) from error
    _require(created is True, "production applicator did not treat the envelope as a fresh release")
    _require(
        release.id == expected_authorized_release_id,
        "production applicator built a release id other than the authorized Window 2 id",
    )
    _require(
        release.state is PermissionState.AUTHORIZED,
        "production applicator did not authorize the release",
    )
    _require(
        release.configuration_hash == envelope.approval_artifact_sha256,
        "authorized release configuration hash does not equal the approval artifact hash",
    )
    _require(
        approval == envelope.approval,
        "production applicator parsed a different approval than the one materialized",
    )
    return {
        "applicator_release_id": str(release.id),
        "applicator_release_state": release.state.value,
        "applicator_configuration_hash": release.configuration_hash,
        "release_write_count": len(store.release_writes),
    }


def materialize(inputs: MaterializationInputs) -> MaterializationResult:
    """Deterministically build (and validate) the exact Window 2 approval envelope."""

    record = _verify_accepted_authority(inputs)
    identifiers = _bound_identifiers(inputs)
    owner_statement_sha256 = str(identifiers["owner_statement_sha256"])

    now = inputs.now
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    starts_at = identifiers["starts_at"]
    expires_at = identifiers["expires_at"]
    assert isinstance(starts_at, datetime) and isinstance(expires_at, datetime)
    _require(
        starts_at <= now < expires_at,
        "current time is outside the accepted Window 2 authorization window",
    )

    _require(
        inputs.kill_switch_state == "TRIPPED",
        f"kill switch is not TRIPPED (state={inputs.kill_switch_state!r})",
    )

    predecessor = _predecessor_bindings(inputs, owner_statement_sha256)
    registry = _registry_bindings(inputs)
    runtime = _runtime_bindings(inputs)

    approval_fields: dict[str, Any] = {
        "schema_version": APPROVAL_SCHEMA,
        "state": "OWNER_APPROVED",
        "approval_id": identifiers["approval_id"],
        "owner_statement_sha256": owner_statement_sha256,
        "owner_signature_state": "APPROVED_IN_THREAD",
        "current_release_id": predecessor["current_release_id"],
        "authorized_release_id": identifiers["authorized_release_id"],
        "workspace_id": predecessor["workspace_id"],
        "legacy_lock_sentinel_sha256": hashlib.sha256(
            SAMPLED_APPROVAL_LOCK_SENTINEL.encode("utf-8")
        ).hexdigest(),
        "permission_type": "REAL_PUBLIC_RESEARCH",
        "source_registry_id": predecessor["source_registry_id"],
        "source_registry_hash": predecessor["source_registry_hash"],
        "retention_policy_id": predecessor["retention_policy_id"],
        "retention_policy_hash": predecessor["retention_policy_hash"],
        "environment_id": predecessor["environment_id"],
        "environment_hash": predecessor["environment_hash"],
        "cohort_policy_id": predecessor["cohort_policy_id"],
        "kill_switch_id": predecessor["kill_switch_id"],
        "ordered_package_file_sha256": registry["ordered_package_file_sha256"],
        "ordered_package_semantic_sha256": registry["ordered_package_semantic_sha256"],
        "slot_registry_file_sha256": registry["slot_registry_file_sha256"],
        "slot_registry_semantic_sha256": registry["slot_registry_semantic_sha256"],
        "slot_number": registry["slot_number"],
        "business_identity": registry["business_identity"],
        "exact_hostname": registry["exact_hostname"],
        "a09_decision_sha256": registry["a09_decision_sha256"],
        "research_runtime_revision": runtime["research_runtime_revision"],
        "release_applicator_sha256": runtime["release_applicator_sha256"],
        "activation_adapter_sha256": runtime["activation_adapter_sha256"],
        "activation_entry_point_sha256": runtime["activation_entry_point_sha256"],
        "stage_coordinator_sha256": runtime["stage_coordinator_sha256"],
        "m1_runtime_sha256": runtime["m1_runtime_sha256"],
        "m2_m5_runtime_sha256": runtime["m2_m5_runtime_sha256"],
        "starts_at": starts_at,
        "expires_at": expires_at,
        "max_logical_requests": identifiers["max_logical_requests"],
        "max_attempts": identifiers["max_attempts"],
        "max_response_bytes": identifiers["max_response_bytes"],
        "max_total_bytes": identifiers["max_total_bytes"],
        "max_duration_seconds": identifiers["max_duration_seconds"],
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": (registry["exact_hostname"],),
        "terminal_rollback_state": "NOT_AUTHORIZED",
    }

    try:
        approval = SampledSlotExecutionApproval.model_validate(approval_fields)
    except Exception as error:
        raise AuthorityMaterializationError(
            f"materialized approval fails schema {APPROVAL_SCHEMA}: {error}"
        ) from error

    artifact_hash = canonical_sha256(approval.model_dump(mode="json"))
    envelope = SampledSlotExecutionApprovalEnvelope(
        approval=approval, approval_artifact_sha256=artifact_hash
    )

    diagnostics = _dry_run_production_validator(
        envelope, inputs, approval.authorized_release_id
    )

    stored = parse_stored_sampled_slot_execution_approval(
        inputs.stored_sampled_slot_approval_raw
    )
    if isinstance(stored, SampledSlotExecutionApprovalEnvelope):
        _require(
            stored.approval == approval
            and stored.approval_artifact_sha256 == artifact_hash,
            "a different sampled-slot approval envelope is already staged; refusing to overwrite",
        )
        already_present = True
    else:
        already_present = False

    return MaterializationResult(
        envelope=envelope,
        approval_artifact_sha256=artifact_hash,
        already_present=already_present,
        predecessor_release_id=approval.current_release_id,
        authorized_release_id=approval.authorized_release_id,
        diagnostics={
            "record_approval_id": str(record.get("approval_id")),
            "owner_statement_sha256": owner_statement_sha256,
            **diagnostics,
        },
    )
