"""Focused tests for the deterministic Window 2 sampled-slot approval materializer."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.authority_materialization import (
    AuthorityMaterializationError,
    ConsumedLiveBudget,
    MaterializationInputs,
    RepairImageSuccessor,
    materialize,
)
from opintel_research_worker.release_application import (
    SAMPLED_APPROVAL_LOCK_SENTINEL,
    parse_stored_sampled_slot_execution_approval,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

ROOT = Path(__file__).resolve().parents[1]
SLOT_REGISTRY = ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json"
A09_REGISTRY = ROOT / "infra/container/phase1-worker/phase1-a09-decision-registry.json"

NOW = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
APPROVAL_ID = "ab76cb09-b0dc-5842-8d13-57a9b65a39a3"
AUTHORIZED_RELEASE_ID = "375a88da-da88-5ebf-9daf-cb09934e02b8"
EXPERIMENT_ID = "2efaeb57-0a43-5dd2-b649-3ba320246325"
PREDECESSOR_RELEASE_ID = UUID("02873c16-90de-53cc-ae43-b6e325e268d1")
WORKSPACE_ID = UUID("7bb45ae7-dc2c-5529-a31c-82b157bc958d")
SOURCE_REGISTRY_ID = UUID("2fccda0c-bc4c-5563-a523-0047c1a4d89d")
RETENTION_POLICY_ID = UUID("089c05e0-0e51-51cb-97af-668b5c7baf12")
ENVIRONMENT_ID = UUID("f3720f10-c7ee-502d-884c-6e6188c98719")
COHORT_POLICY_ID = UUID("1741cc1c-6896-55e0-b06d-528ce4214b67")
KILL_SWITCH_ID = UUID("774aeb09-f2af-542a-bc09-6715d38658f9")
RUNTIME_REVISION = "sha256:770d4248bbd7b5f915861331663dc68f5107cf87782a86bde5b7105488e16e50"
PREDECESSOR_OWNER_SHA = "72401ddabc44b37cc4d98e76c8d66021e3ed7fc0f29a87f41c05080f0694249b"

_SAMPLES = FrozenPhaseOneSampleRegistry(SLOT_REGISTRY)
_A09 = FrozenA09DecisionRegistry(A09_REGISTRY).require_approved(1, "903 HVAC", "903hvac.com")

RUNTIME_ENV = {
    "OPINTEL_RESEARCH_RUNTIME_REVISION": RUNTIME_REVISION,
    "OPINTEL_RELEASE_APPLICATOR_SHA256": (
        "f7ffdf0cd47abec5e7627ef529d486ed71f09649dc41ffe3a642469ce9fcd420"
    ),
    "OPINTEL_ACTIVATION_ADAPTER_SHA256": (
        "95a0355637800d6e1309755bcb342a990ed8c506d6bbe1de28982c10f0e7cf7c"
    ),
    "OPINTEL_ACTIVATION_ENTRY_POINT_SHA256": (
        "12eaf66bf6dc491c4376d1d42ee6bd794a38636d8c9ce93e4b13b1c6db0b6bf5"
    ),
    "OPINTEL_STAGE_COORDINATOR_SHA256": (
        "fe0f34c9ef67c1aa5158aad8cf21206a31f167093f1aaa6350e9ba8f1cc54801"
    ),
    "OPINTEL_M1_RUNTIME_SHA256": (
        "884b1f271b21f9d0ff4e73557be0ec8c01fda30969fa256f1e555afb4d7f2a99"
    ),
    "OPINTEL_M2_M5_RUNTIME_SHA256": (
        "40e6511a00738980a7604a7d60c1c3419b396e049748f06ec0dae8116a5ebed3"
    ),
}


def _statement(
    *,
    starts: str = "2026-08-28T11:00:00Z",
    expires: str = "2026-09-04T11:00:00Z",
    approval_id: str = APPROVAL_ID,
    authorized_release_id: str = AUTHORIZED_RELEASE_ID,
    experiment_id: str = EXPERIMENT_ID,
    logical: int = 8,
    attempts: int = 8,
    response_bytes: int = 250000,
    total_bytes: int = 2000000,
    authority_seconds: int = 600,
    revision: str = RUNTIME_REVISION,
) -> str:
    return (
        "I approve AUTHORIZE_SLOT01_BOUNDED_REPAIR_WINDOW_2_AND_M1_M5_EXECUTION for AWS account "
        "785072247535 in us-east-2. It binds frozen ordered-package file/semantic SHA-256 "
        f"{_SAMPLES.ordered_package_file_sha256} and {_SAMPLES.ordered_package_semantic_sha256}, "
        f"frozen slot-registry file/semantic SHA-256 {_SAMPLES.registry_file_sha256} and "
        f"{_SAMPLES.registry_sha256}, accepted Slot 01 A-09 decision SHA-256 "
        f"{_A09.decision_sha256} for 903 HVAC at 903hvac.com. It binds the exact activator "
        f"image digest {revision}. The Window 2 experiment ID is {experiment_id}, approval "
        f"ID {approval_id}, initial authorized release ID {authorized_release_id}. This "
        f"authorizes one bounded continuation between {starts} and {expires} limited to "
        f"{logical} logical requests, {attempts} authorization attempts, 3 transport "
        f"attempts, {response_bytes} bytes per response, {total_bytes} cumulative bytes, "
        f"{authority_seconds} authority seconds, 120 "
        "operation seconds, 8-second request timeout, two-second minimum delay and USD 0 research "
        "cost."
    )


def _record(statement: str, *, state: str = "ACCEPTED_UNCONSUMED") -> dict[str, object]:
    return {
        "record_type": "M67_SLOT01_BOUNDED_REPAIR_WINDOW_2_OWNER_AUTHORIZATION",
        "state": state,
        "event": "AUTHORIZE_SLOT01_BOUNDED_REPAIR_WINDOW_2_AND_M1_M5_EXECUTION",
        "account_id": "785072247535",
        "region": "us-east-2",
        "exact_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "approval_id": APPROVAL_ID,
        "experiment_id": EXPERIMENT_ID,
        "initial_release_id": AUTHORIZED_RELEASE_ID,
    }


def _predecessor(**changes: object) -> str:
    values: dict[str, object] = {
        "id": PREDECESSOR_RELEASE_ID,
        "workspace_id": WORKSPACE_ID,
        "version": "m67.phase1.release-applicator@1.slot01-owner-authorized.consumed",
        "configuration_hash": "a" * 64,
        "created_at": NOW - timedelta(hours=8),
        "activity": PermissionActivity.REAL_PUBLIC_RESEARCH,
        "state": PermissionState.NOT_AUTHORIZED,
        "source_registry_id": SOURCE_REGISTRY_ID,
        "source_registry_hash": "b" * 64,
        "retention_policy_id": RETENTION_POLICY_ID,
        "retention_policy_hash": "c" * 64,
        "environment_id": ENVIRONMENT_ID,
        "environment_hash": "d" * 64,
        "cohort_policy_id": COHORT_POLICY_ID,
        "cohort_or_run_restriction": "PHASE1_SLOT_01",
        "starts_at": NOW - timedelta(days=1),
        "expires_at": NOW + timedelta(days=1),
        "approval_ids": ("0938582d-7241-583c-809d-482096010089",),
        "kill_switch_id": KILL_SWITCH_ID,
        "owner_approval_sha256": PREDECESSOR_OWNER_SHA,
        "suspended_reason": "CONSUMED:M1_RESEARCH_FAILED",
        "revoked_at": NOW - timedelta(hours=7),
    }
    values.update(changes)
    return LiveResearchPermissionRelease(**values).model_dump_json()


def _inputs(**changes: object) -> MaterializationInputs:
    statement = changes.pop("statement", None) or _statement()
    record = changes.pop("record", None) or _record(statement)
    base: dict[str, object] = {
        "owner_authorization_statement": statement,
        "owner_authorization_record": record,
        "sample_registry": FrozenPhaseOneSampleRegistry(SLOT_REGISTRY),
        "a09_registry": FrozenA09DecisionRegistry(A09_REGISTRY),
        "current_research_release_raw": _predecessor(),
        "kill_switch_state": "TRIPPED",
        "stored_sampled_slot_approval_raw": SAMPLED_APPROVAL_LOCK_SENTINEL,
        "deployed_activator_environment": dict(RUNTIME_ENV),
        "now": NOW,
    }
    base.update(changes)
    return MaterializationInputs(**base)


def test_exact_authoritative_inputs_produce_valid_envelope() -> None:
    result = materialize(_inputs())
    approval = result.envelope.approval
    assert approval.schema_version == "m67.phase1.sampled-slot-execution-approval@3"
    assert str(approval.approval_id) == APPROVAL_ID
    assert str(approval.authorized_release_id) == AUTHORIZED_RELEASE_ID
    assert approval.current_release_id == PREDECESSOR_RELEASE_ID
    assert approval.workspace_id == WORKSPACE_ID
    assert approval.source_registry_id == SOURCE_REGISTRY_ID
    assert approval.source_registry_hash == "b" * 64
    assert approval.retention_policy_hash == "c" * 64
    assert approval.environment_hash == "d" * 64
    assert approval.cohort_policy_id == COHORT_POLICY_ID
    assert approval.kill_switch_id == KILL_SWITCH_ID
    assert approval.exact_hostname == "903hvac.com"
    assert approval.allowed_source_scope == ("903hvac.com",)
    assert approval.research_runtime_revision == RUNTIME_REVISION
    assert approval.max_logical_requests == 8
    assert approval.max_total_bytes == 2_000_000
    assert result.diagnostics["applicator_release_state"] == "authorized"
    assert result.diagnostics["applicator_release_id"] == AUTHORIZED_RELEASE_ID
    assert result.already_present is False


def test_construction_is_deterministic() -> None:
    first = materialize(_inputs()).envelope.model_dump_json()
    second = materialize(_inputs()).envelope.model_dump_json()
    assert first == second


def test_constructed_envelope_passes_production_consumer_validator() -> None:
    result = materialize(_inputs())
    # The dry run inside materialize() *is* the production applicator; assert its verdict.
    assert result.diagnostics["applicator_configuration_hash"] == result.approval_artifact_sha256
    assert result.diagnostics["release_write_count"] == 1


def test_wrong_owner_statement_hash_fails() -> None:
    statement = _statement()
    bad_record = _record(statement)
    bad_record["exact_statement_sha256"] = "0" * 64
    with pytest.raises(AuthorityMaterializationError, match="does not hash"):
        materialize(_inputs(statement=statement, record=bad_record))


def test_altered_statement_body_fails_against_record_hash() -> None:
    honest = _statement()
    record = _record(honest)
    tampered = honest.replace("USD 0 research cost", "USD 5 research cost")
    with pytest.raises(AuthorityMaterializationError):
        materialize(_inputs(statement=tampered, record=record))


def test_statement_and_record_identifier_disagreement_fails() -> None:
    statement = _statement(approval_id="00000000-0000-4000-8000-000000000000")
    record = _record(statement)
    record["approval_id"] = APPROVAL_ID
    with pytest.raises(AuthorityMaterializationError, match="approval_id disagrees"):
        materialize(_inputs(statement=statement, record=record))


def test_non_accepted_record_state_fails() -> None:
    statement = _statement()
    with pytest.raises(AuthorityMaterializationError, match="ACCEPTED_UNCONSUMED"):
        materialize(_inputs(statement=statement, record=_record(statement, state="CONSUMED")))


def test_expired_authorization_window_fails() -> None:
    with pytest.raises(AuthorityMaterializationError, match="outside the accepted Window 2"):
        materialize(_inputs(now=datetime(2026, 9, 5, tzinfo=UTC)))


def test_not_yet_effective_authorization_window_fails() -> None:
    with pytest.raises(AuthorityMaterializationError, match="outside the accepted Window 2"):
        materialize(_inputs(now=datetime(2026, 8, 28, 10, 0, tzinfo=UTC)))


def test_kill_switch_not_tripped_fails() -> None:
    with pytest.raises(AuthorityMaterializationError, match="kill switch is not TRIPPED"):
        materialize(_inputs(kill_switch_state="RUN"))


def test_predecessor_legacy_sentinel_fails() -> None:
    with pytest.raises(AuthorityMaterializationError, match="legacy sentinel"):
        materialize(_inputs(current_research_release_raw='{"state":"NOT_AUTHORIZED"}'))


def test_predecessor_not_consumed_fails() -> None:
    raw = _predecessor(suspended_reason=None, revoked_at=None)
    with pytest.raises(AuthorityMaterializationError, match="consumed terminal predecessor"):
        materialize(_inputs(current_research_release_raw=raw))


def test_predecessor_already_binding_this_window_fails() -> None:
    statement = _statement()
    record = _record(statement)
    raw = _predecessor(owner_approval_sha256=record["exact_statement_sha256"])
    with pytest.raises(AuthorityMaterializationError, match="authority consumed"):
        materialize(_inputs(statement=statement, record=record, current_research_release_raw=raw))


def test_missing_activator_runtime_binding_fails() -> None:
    env = dict(RUNTIME_ENV)
    del env["OPINTEL_M1_RUNTIME_SHA256"]
    with pytest.raises(AuthorityMaterializationError, match="missing OPINTEL_M1_RUNTIME_SHA256"):
        materialize(_inputs(deployed_activator_environment=env))


def test_activator_revision_not_bound_by_statement_or_repair_chain_fails() -> None:
    env = dict(RUNTIME_ENV)
    env["OPINTEL_RESEARCH_RUNTIME_REVISION"] = "sha256:" + "9" * 64
    with pytest.raises(
        AuthorityMaterializationError,
        match="neither bound by the owner statement nor backed by a sealed",
    ):
        materialize(_inputs(deployed_activator_environment=env))


SUCCESSOR_REVISION = "sha256:" + "a1" * 32


def _repair_link(**changes: object) -> RepairImageSuccessor:
    base: dict[str, object] = {
        "repair_number": 1,
        "predecessor_image_digest": RUNTIME_REVISION,
        "successor_image_digest": SUCCESSOR_REVISION,
        "registry_evidence_sha256": "1" * 64,
        "deployment_evidence_sha256": "2" * 64,
        "representation_equivalent_proven": True,
        "ecr_scan_critical": 0,
        "ecr_scan_high": 0,
        "ecr_scan_blocking": 0,
    }
    base.update(changes)
    return RepairImageSuccessor(**base)  # type: ignore[arg-type]


def _repair_env() -> dict[str, str]:
    env = dict(RUNTIME_ENV)
    env["OPINTEL_RESEARCH_RUNTIME_REVISION"] = SUCCESSOR_REVISION
    return env


def test_sealed_repair_successor_chain_admits_deployed_digest() -> None:
    result = materialize(
        _inputs(
            deployed_activator_environment=_repair_env(),
            repair_image_successor_chain=(_repair_link(),),
        )
    )
    assert result.envelope.approval.research_runtime_revision == SUCCESSOR_REVISION


def test_consumed_live_budget_binds_the_remaining_m1_allowance() -> None:
    result = materialize(
        _inputs(
            consumed_live_budget=ConsumedLiveBudget(
                logical_requests=2,
                authorization_attempts=1,
                total_bytes=872,
                authority_seconds=1,
                transport_attempts=1,
            )
        )
    )
    approval = result.envelope.approval
    assert approval.max_logical_requests == 8 - 2
    assert approval.max_attempts == 8 - 1
    assert approval.max_total_bytes == 2_000_000 - 872
    assert approval.max_duration_seconds == 600 - 1
    assert approval.max_response_bytes == 250_000  # per-response, not cumulative


def test_consumed_budget_exhausting_a_ceiling_fails_closed() -> None:
    with pytest.raises(AuthorityMaterializationError, match="cannot fit inside the remaining"):
        materialize(_inputs(consumed_live_budget=ConsumedLiveBudget(total_bytes=2_000_000)))


def test_consumed_budget_exceeding_transport_attempt_ceiling_fails_closed() -> None:
    with pytest.raises(AuthorityMaterializationError, match="cannot fit inside the remaining"):
        materialize(_inputs(consumed_live_budget=ConsumedLiveBudget(transport_attempts=4)))


def test_consumed_budget_with_non_zero_cost_fails_closed() -> None:
    with pytest.raises(AuthorityMaterializationError, match="research cost is non-zero"):
        materialize(_inputs(consumed_live_budget=ConsumedLiveBudget(cost_usd="1")))


def test_no_consumed_budget_keeps_full_statement_ceilings() -> None:
    approval = materialize(_inputs()).envelope.approval
    assert approval.max_logical_requests == 8
    assert approval.max_total_bytes == 2_000_000
    assert approval.max_duration_seconds == 600


def test_repair_attempt_lineage_is_deterministic_and_distinguishes_successors() -> None:
    from opintel_research_worker.activation import ORIGINAL_ATTEMPT_LINEAGE_SHA256
    from opintel_research_worker.authority_materialization import _repair_attempt_lineage_sha256

    assert _repair_attempt_lineage_sha256(()) == ORIGINAL_ATTEMPT_LINEAGE_SHA256
    one = (_repair_link(),)
    assert _repair_attempt_lineage_sha256(one) == _repair_attempt_lineage_sha256(one)
    assert _repair_attempt_lineage_sha256(one) != ORIGINAL_ATTEMPT_LINEAGE_SHA256
    two = (
        _repair_link(repair_number=1, successor_image_digest="sha256:" + "b2" * 32),
        _repair_link(
            repair_number=2,
            predecessor_image_digest="sha256:" + "b2" * 32,
            successor_image_digest="sha256:" + "c3" * 32,
        ),
    )
    assert _repair_attempt_lineage_sha256(two) != _repair_attempt_lineage_sha256(one)
    # a different sealed evidence identity for the same digits changes the lineage
    altered = (_repair_link(registry_evidence_sha256="9" * 64),)
    assert _repair_attempt_lineage_sha256(altered) != _repair_attempt_lineage_sha256(one)


def test_materialized_envelope_binds_the_repair_attempt_lineage() -> None:
    from opintel_research_worker.authority_materialization import _repair_attempt_lineage_sha256

    env = dict(RUNTIME_ENV)
    env["OPINTEL_RESEARCH_RUNTIME_REVISION"] = SUCCESSOR_REVISION
    chain = (_repair_link(),)
    result = materialize(
        _inputs(deployed_activator_environment=env, repair_image_successor_chain=chain)
    )
    assert result.envelope.approval.repair_attempt_lineage_sha256 == _repair_attempt_lineage_sha256(
        chain
    )


def test_original_attempt_envelope_uses_the_original_lineage() -> None:
    from opintel_research_worker.activation import ORIGINAL_ATTEMPT_LINEAGE_SHA256

    approval = materialize(_inputs()).envelope.approval
    assert approval.repair_attempt_lineage_sha256 == ORIGINAL_ATTEMPT_LINEAGE_SHA256


def test_two_link_sealed_repair_chain_admits_final_deployed_digest() -> None:
    mid = "sha256:" + "b2" * 32
    final = "sha256:" + "c3" * 32
    env = dict(RUNTIME_ENV)
    env["OPINTEL_RESEARCH_RUNTIME_REVISION"] = final
    result = materialize(
        _inputs(
            deployed_activator_environment=env,
            repair_image_successor_chain=(
                _repair_link(repair_number=1, successor_image_digest=mid),
                _repair_link(
                    repair_number=2,
                    predecessor_image_digest=mid,
                    successor_image_digest=final,
                ),
            ),
        )
    )
    assert result.envelope.approval.research_runtime_revision == final


def test_repair_chain_must_start_from_owner_bound_digest() -> None:
    with pytest.raises(AuthorityMaterializationError, match="does not start from the image digest"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=(
                    _repair_link(predecessor_image_digest="sha256:" + "b" * 64),
                ),
            )
        )


def test_repair_chain_final_successor_must_equal_deployed_digest() -> None:
    with pytest.raises(AuthorityMaterializationError, match="not the final sealed"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=(
                    _repair_link(successor_image_digest="sha256:" + "c" * 64),
                ),
            )
        )


def test_repair_chain_rejects_unproven_representation() -> None:
    with pytest.raises(AuthorityMaterializationError, match="not representation-equivalent proven"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=(
                    _repair_link(representation_equivalent_proven=False),
                ),
            )
        )


def test_repair_chain_rejects_dirty_scan() -> None:
    with pytest.raises(AuthorityMaterializationError, match="ECR scan is not COMPLETE"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=(_repair_link(ecr_scan_high=2),),
            )
        )


def test_repair_chain_must_be_contiguous() -> None:
    mid = "sha256:" + "d" * 64
    with pytest.raises(AuthorityMaterializationError, match="not contiguous"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=(
                    _repair_link(repair_number=1, successor_image_digest=mid),
                    _repair_link(
                        repair_number=2,
                        predecessor_image_digest="sha256:" + "e" * 64,
                        successor_image_digest=SUCCESSOR_REVISION,
                    ),
                ),
            )
        )


def test_repair_chain_cannot_exceed_five_links() -> None:
    links = tuple(
        _repair_link(
            repair_number=i + 1,
            predecessor_image_digest=RUNTIME_REVISION if i == 0 else f"sha256:{i:064d}",
            successor_image_digest=(
                SUCCESSOR_REVISION if i == 5 else f"sha256:{i + 1:064d}"
            ),
        )
        for i in range(6)
    )
    with pytest.raises(AuthorityMaterializationError, match="exceeds the five-repair"):
        materialize(
            _inputs(
                deployed_activator_environment=_repair_env(),
                repair_image_successor_chain=links,
            )
        )


def test_synthetic_registry_not_bound_by_statement_fails() -> None:
    # A statement that omits the frozen ordered-package hash cannot admit the real registry.
    statement = _statement().replace(_SAMPLES.ordered_package_file_sha256, "e" * 64)
    record = _record(statement)
    with pytest.raises(AuthorityMaterializationError, match="ordered-package file SHA-256"):
        materialize(_inputs(statement=statement, record=record))


def test_already_present_identical_envelope_is_idempotent_without_write() -> None:
    envelope = materialize(_inputs()).envelope
    result = materialize(_inputs(stored_sampled_slot_approval_raw=envelope.model_dump_json()))
    assert result.already_present is True
    assert result.envelope.approval == envelope.approval
    parsed = parse_stored_sampled_slot_execution_approval(envelope.model_dump_json())
    assert parsed == envelope


def test_different_staged_envelope_fails_safely() -> None:
    other = materialize(_inputs()).envelope
    mutated = other.approval.model_copy(update={"max_attempts": 7})
    from opintel_research_worker.release_application import (
        SampledSlotExecutionApprovalEnvelope,
        canonical_sha256,
    )

    staged = SampledSlotExecutionApprovalEnvelope(
        approval=mutated,
        approval_artifact_sha256=canonical_sha256(mutated.model_dump(mode="json")),
    ).model_dump_json()
    with pytest.raises(AuthorityMaterializationError, match="different sampled-slot approval"):
        materialize(_inputs(stored_sampled_slot_approval_raw=staged))
