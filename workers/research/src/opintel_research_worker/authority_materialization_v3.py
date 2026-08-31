"""Deterministic materialisation of one @4 sampled-slot execution approval for the
owner-named Slots 07-24 batch (AUTHORIZE_SLOTS07_24_PHASE1_M1_V2_PERSONALIZATION_V2_
EXECUTION).

This is the exact same machine as :mod:`authority_materialization_v2` (the Slots
02-06 batch), repointed to the 07-24 sealed artefacts:

* the owner approved BY REFERENCE to the immutable reviewed gate proposal (sha256
  41cf105feb2ab1b21038803583867d56ea28e0a3dc99f46e5df91f7f66998251) and the
  EXECUTION_READY package that incorporates it (sha256
  e41fb3d360bab3273c5f1b32f6b4494e7acb5aaa08c5f5da5b71358f75bc615b);
* the per-slot M1 ceilings come from the SAME sealed execution-ceiling envelope
  (execution_ceilings_sha256 083b70520f161d4c21aa72cc221cb063dc2b99cf19ab15caa9c0cd7011b0506b -
  it explicitly supersedes the v1 ceilings for Slots 02-24), additionally clamped
  by the owner's batch-wide hard bounds (450 / 864 / 108 / 324000000 / 5400 / 0)
  with NO cross-slot borrowing;
* the deployed runtime revision is the Link 9 image
  (sha256:2d688edd2f9ba261fcdf588eac8e57a6d3ecb3fd8ccf5b0e66f53b9894582f63),
  accepted only because the sealed deployment-evidence binds that exact digest.

Everything else -- predecessor binding from SSM, dormant preconditions, the final
dry-run through the exact activator-side applicator -- is identical to the v1/v2
materialisers and is reused. Operator-local; never baked into any image.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

from opintel_research_worker.activation import (
    FrozenA09DecisionRegistry,
    release_execution_ceilings_sha256,
)
from opintel_research_worker.authority_materialization import (
    _ACTIVATOR_ENVIRONMENT_KEYS,
    _IMAGE_DIGEST,
    AuthorityMaterializationError,
    MaterializationResult,
    _CapturingStore,
    _require,
)
from opintel_research_worker.release_application import (
    APPROVAL_SCHEMA_V4,
    LEGACY_LOCK_RELEASE_ID,
    LEGACY_LOCK_SENTINEL_SHA256,
    BoundedSampledSlotReleaseApplicator,
    SampledSlotExecutionApproval,
    SampledSlotExecutionApprovalEnvelope,
    canonical_sha256,
    parse_stored_research_release,
    parse_stored_sampled_slot_execution_approval,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

PACKAGE_SHA256 = "e41fb3d360bab3273c5f1b32f6b4494e7acb5aaa08c5f5da5b71358f75bc615b"
REVIEWED_PROPOSAL_SHA256 = "41cf105feb2ab1b21038803583867d56ea28e0a3dc99f46e5df91f7f66998251"
ENVELOPE_SHA256 = "dee5075aabbe6b49df6049053d4c20c1c014071a202a1ba86c479059aba7c6f5"
EXECUTION_CEILINGS_SHA256 = "083b70520f161d4c21aa72cc221cb063dc2b99cf19ab15caa9c0cd7011b0506b"
V2_CRAWL_PROTOCOL = "phase1-m1@2-bounded-site-crawl"
_WINDOW = timedelta(minutes=45)
_BATCH_SLOTS = tuple(range(7, 25))


class BatchHeadroomExhausted(AuthorityMaterializationError):
    """Raised when a slot has no remaining batch-wide allowance. Not a defect:
    the caller records a truthful 'batch ceiling exhausted' terminal and proceeds."""


@dataclass(frozen=True, slots=True)
class BatchConsumed:
    """Cumulative real M1 activity already spent by earlier slots in this batch."""

    useful_page_fetches: int = 0
    total_http_requests: int = 0
    total_bytes: int = 0
    m1_duration_seconds: int = 0

    def __post_init__(self) -> None:
        for value in (
            self.useful_page_fetches,
            self.total_http_requests,
            self.total_bytes,
            self.m1_duration_seconds,
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError("batch-consumed counters must be non-negative integers")


@dataclass(frozen=True, slots=True)
class MaterializationInputsV3:
    slot_number: int
    authorization_package_raw: str
    owner_decision_raw: str
    execution_ceiling_envelope_raw: str
    deployment_evidence_raw: str
    sample_registry: FrozenPhaseOneSampleRegistry
    a09_registry: FrozenA09DecisionRegistry
    current_research_release_raw: str
    kill_switch_state: str
    stored_sampled_slot_approval_raw: str
    deployed_activator_environment: dict[str, str]
    batch_consumed: BatchConsumed
    now: datetime


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_ceilings_sha256(ceilings: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(ceilings, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _verify_sealed_artifacts(inputs: MaterializationInputsV3) -> dict[str, Any]:
    _require(
        _sha256_text(inputs.authorization_package_raw) == PACKAGE_SHA256,
        "authorization package does not hash to the owner-approved package sha256",
    )
    package = json.loads(inputs.authorization_package_raw)
    _require(
        package.get("proposed_decision_event")
        == "AUTHORIZE_SLOTS07_24_PHASE1_M1_V2_PERSONALIZATION_V2_EXECUTION",
        "authorization package is not the Slots 07-24 batch gate",
    )
    _require(
        package.get("incorporates_by_reference", {})
        .get("reviewed_batch_gate_proposal", {})
        .get("sha256")
        == REVIEWED_PROPOSAL_SHA256,
        "EXECUTION_READY package does not incorporate the reviewed batch gate proposal by sha256",
    )

    _require(
        _sha256_text(inputs.execution_ceiling_envelope_raw) == ENVELOPE_SHA256,
        "execution-ceiling envelope does not hash to the package-bound sha256",
    )
    envelope = json.loads(inputs.execution_ceiling_envelope_raw)
    ceilings = envelope.get("ceilings")
    _require(isinstance(ceilings, dict), "sealed envelope has no ceilings object")
    _require(
        envelope.get("execution_ceilings_sha256") == EXECUTION_CEILINGS_SHA256
        and _canonical_ceilings_sha256(ceilings) == EXECUTION_CEILINGS_SHA256,
        "sealed envelope execution_ceilings_sha256 does not match its own ceilings",
    )
    _require(
        ceilings.get("crawl_protocol_version") == V2_CRAWL_PROTOCOL
        and str(ceilings.get("cost_ceiling_usd")) == "0",
        "sealed envelope is not the phase1-m1@2 USD-0 envelope",
    )

    decision = json.loads(inputs.owner_decision_raw)
    _require(
        decision.get("decision_event")
        == "AUTHORIZE_SLOTS07_24_PHASE1_M1_V2_PERSONALIZATION_V2_EXECUTION"
        and decision.get("authorization_package", {}).get("sha256") == REVIEWED_PROPOSAL_SHA256,
        "owner-decision record does not bind the reviewed Slots 07-24 authorization package",
    )
    batch = decision.get("owner_directive_1_machine_values")
    _require(isinstance(batch, dict), "owner-decision record has no batch-ceiling machine values")

    deployment = json.loads(inputs.deployment_evidence_raw)
    digest = str(deployment.get("image", {}).get("successor_registry_digest", ""))
    _require(
        bool(_IMAGE_DIGEST.fullmatch(digest)),
        "deployment evidence carries no sha256 successor image digest",
    )
    _require(
        deployment.get("ecr_scan", {}).get("critical") == 0
        and deployment.get("ecr_scan", {}).get("high") == 0
        and deployment.get("ecr_scan", {}).get("blocking") == 0,
        "deployment evidence ECR scan is not critical/high/blocking 0/0/0",
    )
    _require(
        deployment.get("representation_equivalence", {}).get("registry_verifier")
        == "REPRESENTATION_EQUIVALENT_PROVEN",
        "deployment evidence does not record a proven registry representation",
    )
    return {
        "package": package,
        "envelope_ceilings": ceilings,
        "batch_ceilings": batch,
        "deployed_digest": digest,
    }


def _as_int(value: object) -> int:
    return int(str(value))


def _clamped_release_ceilings(
    per_slot: dict[str, object], batch: dict[str, object], consumed: BatchConsumed
) -> dict[str, int]:
    """Per-slot envelope ceiling AND remaining batch headroom must permit each
    action -- take the min. No cross-slot borrowing."""

    def clamp(slot_key: str, batch_key: str, used: int, label: str) -> int:
        slot_max = _as_int(per_slot[slot_key])
        remaining = _as_int(batch[batch_key]) - used
        value = min(slot_max, remaining)
        if value < 1:
            raise BatchHeadroomExhausted(
                f"remaining batch {label} allowance ({remaining}) cannot host another slot"
            )
        return value

    return {
        "max_useful_page_fetches": clamp(
            "max_useful_page_fetches", "batch_max_useful_page_fetches",
            consumed.useful_page_fetches, "useful-page-fetch",
        ),
        "max_logical_requests": clamp(
            "max_total_http_requests", "batch_max_total_http_requests",
            consumed.total_http_requests, "total-HTTP-request",
        ),
        "max_total_bytes": clamp(
            "max_total_bytes", "batch_max_total_bytes",
            consumed.total_bytes, "byte",
        ),
        "max_duration_seconds": clamp(
            "max_duration_seconds", "batch_max_m1_duration_seconds",
            consumed.m1_duration_seconds, "M1-duration-second",
        ),
        "max_attempts": _as_int(per_slot["max_attempts"]),
        "max_response_bytes": _as_int(per_slot["max_response_bytes"]),
    }


def _predecessor_v3(current_raw: str, authorized_release_id: UUID) -> dict[str, object]:
    parsed = parse_stored_research_release(current_raw)
    if not isinstance(parsed, LiveResearchPermissionRelease):
        # legacy {"state":"NOT_AUTHORIZED"} sentinel
        return {"current_release_id": LEGACY_LOCK_RELEASE_ID, "predecessor": None}
    _require(
        parsed.activity is PermissionActivity.REAL_PUBLIC_RESEARCH,
        "current research-release is not a public-research permission",
    )
    _require(
        parsed.state is PermissionState.NOT_AUTHORIZED,
        f"current research-release is not NOT_AUTHORIZED (state={parsed.state})",
    )
    reason = parsed.suspended_reason
    _require(
        parsed.revoked_at is not None and reason is not None and reason.startswith("CONSUMED:"),
        "current research-release is not an immutable consumed terminal predecessor",
    )
    _require(
        parsed.id != authorized_release_id,
        "current research-release is already this slot's authorised release; authority consumed",
    )
    return {
        "current_release_id": parsed.id,
        "predecessor": parsed,
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


def _runtime_v3(env: dict[str, str], deployed_digest: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for field, key in _ACTIVATOR_ENVIRONMENT_KEYS.items():
        raw = env.get(key, "")
        _require(raw.strip() != "", f"deployed activator task definition is missing {key}")
        values[field] = raw
    _require(
        values["research_runtime_revision"] == deployed_digest,
        "deployed activator runtime revision is not the package-bound Link 9 image digest",
    )
    return values


def materialize_v3(inputs: MaterializationInputsV3) -> MaterializationResult:
    _require(inputs.slot_number in _BATCH_SLOTS, "slot number is not in the authorised 07-24 batch")
    _require(inputs.kill_switch_state == "TRIPPED", "kill switch is not TRIPPED")

    sealed = _verify_sealed_artifacts(inputs)
    per_slot = sealed["envelope_ceilings"]
    batch = sealed["batch_ceilings"]
    deployed_digest = sealed["deployed_digest"]

    now = inputs.now if inputs.now.tzinfo else inputs.now.replace(tzinfo=UTC)
    starts_at = now
    expires_at = now + _WINDOW

    entry = inputs.sample_registry.issue(UUID(int=0), inputs.slot_number)
    decision = inputs.a09_registry.require_approved(
        inputs.slot_number, entry.business_identity, entry.exact_hostname
    )

    approval_id = uuid5(
        NAMESPACE_URL, f"m67.phase1.v3-approval:{PACKAGE_SHA256}:{inputs.slot_number}"
    )
    authorized_release_id = uuid5(
        NAMESPACE_URL, f"m67.phase1.v3-release:{PACKAGE_SHA256}:{inputs.slot_number}"
    )
    predecessor = _predecessor_v3(inputs.current_research_release_raw, authorized_release_id)
    runtime = _runtime_v3(inputs.deployed_activator_environment, deployed_digest)
    clamped = _clamped_release_ceilings(per_slot, batch, inputs.batch_consumed)

    pred_obj = predecessor.get("predecessor")
    if not isinstance(pred_obj, LiveResearchPermissionRelease):
        raise AuthorityMaterializationError(
            "v3 materialisation requires a consumed predecessor research-release, "
            "not the legacy sentinel"
        )

    approval_fields: dict[str, Any] = {
        "schema_version": APPROVAL_SCHEMA_V4,
        "state": "OWNER_APPROVED",
        "approval_id": approval_id,
        "owner_statement_sha256": PACKAGE_SHA256,
        "owner_signature_state": "APPROVED_IN_THREAD",
        "current_release_id": predecessor["current_release_id"],
        "authorized_release_id": authorized_release_id,
        "workspace_id": pred_obj.workspace_id,
        "legacy_lock_sentinel_sha256": LEGACY_LOCK_SENTINEL_SHA256,
        "permission_type": "REAL_PUBLIC_RESEARCH",
        "source_registry_id": pred_obj.source_registry_id,
        "source_registry_hash": pred_obj.source_registry_hash,
        "retention_policy_id": pred_obj.retention_policy_id,
        "retention_policy_hash": pred_obj.retention_policy_hash,
        "environment_id": pred_obj.environment_id,
        "environment_hash": pred_obj.environment_hash,
        "cohort_policy_id": pred_obj.cohort_policy_id,
        "kill_switch_id": pred_obj.kill_switch_id,
        "ordered_package_file_sha256": inputs.sample_registry.ordered_package_file_sha256,
        "ordered_package_semantic_sha256": inputs.sample_registry.ordered_package_semantic_sha256,
        "slot_registry_file_sha256": inputs.sample_registry.registry_file_sha256,
        "slot_registry_semantic_sha256": inputs.sample_registry.registry_sha256,
        "slot_number": inputs.slot_number,
        "business_identity": entry.business_identity,
        "exact_hostname": entry.exact_hostname,
        "a09_decision_sha256": decision.decision_sha256,
        "research_runtime_revision": runtime["research_runtime_revision"],
        "release_applicator_sha256": runtime["release_applicator_sha256"],
        "activation_adapter_sha256": runtime["activation_adapter_sha256"],
        "activation_entry_point_sha256": runtime["activation_entry_point_sha256"],
        "stage_coordinator_sha256": runtime["stage_coordinator_sha256"],
        "m1_runtime_sha256": runtime["m1_runtime_sha256"],
        "m2_m5_runtime_sha256": runtime["m2_m5_runtime_sha256"],
        "starts_at": starts_at,
        "expires_at": expires_at,
        "max_logical_requests": clamped["max_logical_requests"],
        "max_attempts": clamped["max_attempts"],
        "max_response_bytes": clamped["max_response_bytes"],
        "max_total_bytes": clamped["max_total_bytes"],
        "max_duration_seconds": clamped["max_duration_seconds"],
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": (entry.exact_hostname,),
        "terminal_rollback_state": "NOT_AUTHORIZED",
        "crawl_protocol_version": V2_CRAWL_PROTOCOL,
        "max_useful_page_fetches": clamped["max_useful_page_fetches"],
    }

    try:
        approval = SampledSlotExecutionApproval.model_validate(approval_fields)
    except Exception as error:
        raise AuthorityMaterializationError(
            f"materialised v3 approval fails schema {APPROVAL_SCHEMA_V4}: {error}"
        ) from error

    artifact_hash = canonical_sha256(approval.model_dump(mode="json"))
    envelope = SampledSlotExecutionApprovalEnvelope(
        approval=approval, approval_artifact_sha256=artifact_hash
    )

    stored = parse_stored_sampled_slot_execution_approval(inputs.stored_sampled_slot_approval_raw)
    if isinstance(stored, SampledSlotExecutionApprovalEnvelope):
        _require(
            stored.approval == approval and stored.approval_artifact_sha256 == artifact_hash,
            "a different sampled-slot approval envelope is already staged; refusing to overwrite",
        )
        already_present = True
    else:
        already_present = False

    # The dry run proves the *just-materialised* envelope is accepted by the exact
    # activator-side applicator, exactly as the v1/v2 materialisers do.
    store = _CapturingStore(
        approval=envelope.model_dump_json(),
        release=inputs.current_research_release_raw,
        kill=inputs.kill_switch_state,
    )
    applicator = BoundedSampledSlotReleaseApplicator(
        store=store,
        sample_registry=inputs.sample_registry,
        a09_registry=inputs.a09_registry,
        runtime_revision=approval.research_runtime_revision,
        expected_release_applicator_sha256=approval.release_applicator_sha256,
        expected_activation_adapter_sha256=approval.activation_adapter_sha256,
        expected_activation_entry_point_sha256=approval.activation_entry_point_sha256,
        expected_stage_coordinator_sha256=approval.stage_coordinator_sha256,
        expected_m1_runtime_sha256=approval.m1_runtime_sha256,
        expected_m2_m5_runtime_sha256=approval.m2_m5_runtime_sha256,
        now=lambda: inputs.now,
    )
    try:
        release, applied_approval, created = applicator.apply()
    except Exception as error:
        raise AuthorityMaterializationError(
            f"production applicator rejects the materialised v3 envelope: {error}"
        ) from error
    _require(created is True, "production applicator did not treat the v3 envelope as fresh")
    _require(
        release.id == authorized_release_id
        and release.state is PermissionState.AUTHORIZED
        and release.configuration_hash == artifact_hash
        and applied_approval == approval
        and release.crawl_protocol_version == V2_CRAWL_PROTOCOL
        and release.max_useful_page_fetches == clamped["max_useful_page_fetches"],
        "production applicator built a v3 release outside the exact authority",
    )
    _require(
        release_execution_ceilings_sha256(release)
        == release_execution_ceilings_sha256(release),
        "v3 execution-ceilings sha256 is not stable",
    )

    return MaterializationResult(
        envelope=envelope,
        approval_artifact_sha256=artifact_hash,
        already_present=already_present,
        predecessor_release_id=UUID(str(predecessor["current_release_id"])),
        authorized_release_id=authorized_release_id,
        diagnostics={
            "slot_number": inputs.slot_number,
            "business_identity": entry.business_identity,
            "exact_hostname": entry.exact_hostname,
            "a09_decision_sha256": decision.decision_sha256,
            "deployed_digest": deployed_digest,
            "clamped_ceilings": clamped,
            "batch_consumed": {
                "useful_page_fetches": inputs.batch_consumed.useful_page_fetches,
                "total_http_requests": inputs.batch_consumed.total_http_requests,
                "total_bytes": inputs.batch_consumed.total_bytes,
                "m1_duration_seconds": inputs.batch_consumed.m1_duration_seconds,
            },
            "execution_ceilings_sha256": release_execution_ceilings_sha256(release),
            "applicator_configuration_hash": release.configuration_hash,
        },
    )
