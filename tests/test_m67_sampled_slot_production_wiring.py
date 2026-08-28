from __future__ import annotations

import hashlib
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from opintel_audit.domain import AuditKind, AuditOperation, AuditOperationStatus
from opintel_audit_local import SqlAlchemyAuditRepository
from opintel_demo.domain import DemoOperation, DemoOperationStatus
from opintel_demo_local import SqlAlchemyDemoRepository
from opintel_intelligence_worker.controlled_egress_lifecycle import (
    BoundedControlledEgressLifecycle,
)
from opintel_intelligence_worker.coordinator_persistence import (
    CoordinatorRunBinding,
    SqlAlchemyCoordinatorRepository,
)
from opintel_intelligence_worker.execution import BoundedSampledSlotExecution
from opintel_intelligence_worker.orchestration import (
    BoundedSampledSlotCoordinator,
    ShadowStage,
)
from opintel_intelligence_worker.production_runtime import StageResult
from opintel_opportunity.domain import AnalysisStatus, OpportunityAnalysisRun
from opintel_opportunity_local import SqlAlchemyOpportunityRepository
from opintel_outreach.domain import OutreachOperation, OutreachOperationStatus
from opintel_outreach_local import SqlAlchemyOutreachRepository
from opintel_research.domain import CrawlPolicy, ResearchRun, ResearchRunStatus
from opintel_research_worker.activation import (
    FrozenA09DecisionRegistry,
)
from opintel_research_worker.egress_lease import (
    EGRESS_LEASE_LOCK_SENTINEL,
    CanonicalNotAuthorizedEgressLease,
    ControlledEgressLease,
    build_egress_lease,
    parse_stored_egress_lease,
)
from opintel_research_worker.release_application import (
    LEGACY_LOCK_RELEASE_ID,
    LEGACY_LOCK_SENTINEL,
    LEGACY_LOCK_SENTINEL_SHA256,
    SAMPLED_APPROVAL_LOCK_SENTINEL,
    BoundedSampledSlotReleaseApplicator,
    CanonicalNotAuthorizedResearchRelease,
    CanonicalNotAuthorizedSampledSlotApproval,
    SampledSlotExecutionApproval,
    SampledSlotExecutionApprovalEnvelope,
    canonical_sha256,
    parse_stored_research_release,
    parse_stored_sampled_slot_execution_approval,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json"
A09 = ROOT / "infra/container/phase1-worker/phase1-a09-decision-registry.json"
WORKSPACE = UUID("10000000-0000-4000-8000-000000000001")
CURRENT_RELEASE = UUID("10000000-0000-4000-8000-000000000010")
AUTHORIZED_RELEASE = UUID("10000000-0000-4000-8000-000000000011")
SOURCE_REGISTRY = UUID("30000000-0000-4000-8000-000000000001")
RETENTION_POLICY = UUID("30000000-0000-4000-8000-000000000002")
ENVIRONMENT = UUID("30000000-0000-4000-8000-000000000003")
COHORT_POLICY = UUID("30000000-0000-4000-8000-000000000004")
KILL_SWITCH = UUID("30000000-0000-4000-8000-000000000005")
NOW = datetime(2026, 8, 26, 15, 0, tzinfo=UTC)
RUNTIME = "sha256:" + "9" * 64
HASHES = tuple(character * 64 for character in "abcdef")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch):
    calls: list[object] = []

    def deny(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("all wiring denials and synthetic execution must precede DNS")

    monkeypatch.setattr(socket, "getaddrinfo", deny)
    yield
    assert calls == []


def _current_release() -> LiveResearchPermissionRelease:
    return LiveResearchPermissionRelease(
        id=CURRENT_RELEASE,
        workspace_id=WORKSPACE,
        version="m67.slot01.locked@1",
        configuration_hash="0" * 64,
        created_at=NOW - timedelta(days=1),
        activity=PermissionActivity.REAL_PUBLIC_RESEARCH,
        state=PermissionState.NOT_AUTHORIZED,
        source_registry_id=SOURCE_REGISTRY,
        source_registry_hash="1" * 64,
        retention_policy_id=RETENTION_POLICY,
        retention_policy_hash="2" * 64,
        environment_id=ENVIRONMENT,
        environment_hash="3" * 64,
        cohort_policy_id=COHORT_POLICY,
        cohort_or_run_restriction="LOCKED",
        starts_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=1),
        approval_ids=(),
        kill_switch_id=KILL_SWITCH,
    )


def _approval(**changes: object) -> SampledSlotExecutionApproval:
    samples = FrozenPhaseOneSampleRegistry(SAMPLES)
    decision = FrozenA09DecisionRegistry(A09).require_approved(1, "903 HVAC", "903hvac.com")
    values: dict[str, object] = {
        "schema_version": "m67.phase1.sampled-slot-execution-approval@3",
        "state": "OWNER_APPROVED",
        "approval_id": UUID("20000000-0000-4000-8000-000000000001"),
        "owner_statement_sha256": "f" * 64,
        "owner_signature_state": "APPROVED_IN_THREAD",
        "current_release_id": CURRENT_RELEASE,
        "authorized_release_id": AUTHORIZED_RELEASE,
        "workspace_id": WORKSPACE,
        "legacy_lock_sentinel_sha256": LEGACY_LOCK_SENTINEL_SHA256,
        "permission_type": "REAL_PUBLIC_RESEARCH",
        "source_registry_id": SOURCE_REGISTRY,
        "source_registry_hash": "1" * 64,
        "retention_policy_id": RETENTION_POLICY,
        "retention_policy_hash": "2" * 64,
        "environment_id": ENVIRONMENT,
        "environment_hash": "3" * 64,
        "cohort_policy_id": COHORT_POLICY,
        "kill_switch_id": KILL_SWITCH,
        "ordered_package_file_sha256": samples.ordered_package_file_sha256,
        "ordered_package_semantic_sha256": samples.ordered_package_semantic_sha256,
        "slot_registry_file_sha256": samples.registry_file_sha256,
        "slot_registry_semantic_sha256": samples.registry_sha256,
        "slot_number": 1,
        "business_identity": "903 HVAC",
        "exact_hostname": "903hvac.com",
        "a09_decision_sha256": decision.decision_sha256,
        "research_runtime_revision": RUNTIME,
        "release_applicator_sha256": HASHES[0],
        "activation_adapter_sha256": HASHES[1],
        "activation_entry_point_sha256": HASHES[2],
        "stage_coordinator_sha256": HASHES[3],
        "m1_runtime_sha256": HASHES[4],
        "m2_m5_runtime_sha256": HASHES[5],
        "starts_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(minutes=14),
        "max_logical_requests": 8,
        "max_attempts": 8,
        "max_response_bytes": 250_000,
        "max_total_bytes": 2_000_000,
        "max_duration_seconds": 600,
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": ("903hvac.com",),
        "terminal_rollback_state": "NOT_AUTHORIZED",
    }
    values.update(changes)
    return SampledSlotExecutionApproval(**values)


class _Store:
    def __init__(
        self, approval: SampledSlotExecutionApproval, release_raw: str | None = None
    ) -> None:
        envelope = SampledSlotExecutionApprovalEnvelope(
            approval=approval,
            approval_artifact_sha256=canonical_sha256(approval.model_dump(mode="json")),
        )
        self.approval = envelope.model_dump_json()
        self.release = release_raw or _current_release().model_dump_json()
        self.kill = "TRIPPED"
        self.release_writes = 0

    def read_approval_envelope(self) -> str:
        return self.approval

    def read_release(self) -> str:
        return self.release

    def write_release(self, value: str) -> None:
        self.release = value
        self.release_writes += 1

    def read_kill_switch(self) -> str:
        return self.kill

    def write_kill_switch(self, value: str) -> None:
        self.kill = value


def _applicator(store: _Store) -> BoundedSampledSlotReleaseApplicator:
    return BoundedSampledSlotReleaseApplicator(
        store=store,
        sample_registry=FrozenPhaseOneSampleRegistry(SAMPLES),
        a09_registry=FrozenA09DecisionRegistry(A09),
        runtime_revision=RUNTIME,
        expected_release_applicator_sha256=HASHES[0],
        expected_activation_adapter_sha256=HASHES[1],
        expected_activation_entry_point_sha256=HASHES[2],
        expected_stage_coordinator_sha256=HASHES[3],
        expected_m1_runtime_sha256=HASHES[4],
        expected_m2_m5_runtime_sha256=HASHES[5],
        now=lambda: NOW,
    )


def test_owner_approval_applies_exact_release_once_and_restart_is_idempotent() -> None:
    store = _Store(_approval())
    applicator = _applicator(store)
    release, approval, created = applicator.apply()
    assert created is True
    assert release.id == AUTHORIZED_RELEASE
    assert release.slot_number == approval.slot_number == 1
    assert release.exact_hostname == "903hvac.com"
    applicator.enter_run(release)
    assert store.kill == "RUN"

    resumed, _, duplicate_created = applicator.apply()
    applicator.enter_run(resumed)
    assert duplicate_created is False
    assert store.kill == "RUN"
    assert store.release_writes == 1


def test_exact_legacy_lock_normalizes_to_typed_non_authorized_only() -> None:
    locked = parse_stored_research_release(LEGACY_LOCK_SENTINEL)
    assert isinstance(locked, CanonicalNotAuthorizedResearchRelease)
    assert locked.model_dump() == {"state": "NOT_AUTHORIZED"}
    assert not hasattr(locked, "slot_number")
    assert not hasattr(locked, "exact_hostname")
    assert not hasattr(locked, "starts_at")


def test_canonical_complete_not_authorized_release_remains_accepted() -> None:
    current = _current_release()
    parsed = parse_stored_research_release(current.model_dump_json())
    assert isinstance(parsed, LiveResearchPermissionRelease)
    assert parsed == current
    assert parsed.state is PermissionState.NOT_AUTHORIZED


@pytest.mark.parametrize(
    "raw",
    [
        '{"state":"not_authorized"}',
        '{"state":"NOT_AUTHORIZED","slot_number":1}',
        '{ "state": "NOT_AUTHORIZED" }',
        '{"state":"AUTHORIZED"}',
        '{"state":"NOT_AUTHORIZED"',
        "{}",
    ],
)
def test_nonexact_or_malformed_legacy_lock_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_stored_research_release(raw)


def test_partial_live_release_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_stored_research_release(
            '{"record_kind":"live_research_permission","activity":"real_public_research",'
            '"state":"authorized","slot_number":1,"exact_hostname":"903hvac.com"}'
        )


def test_exact_sampled_approval_lock_normalizes_only_to_typed_non_authorized() -> None:
    locked = parse_stored_sampled_slot_execution_approval(SAMPLED_APPROVAL_LOCK_SENTINEL)
    assert isinstance(locked, CanonicalNotAuthorizedSampledSlotApproval)
    assert locked.model_dump() == {"state": "NOT_AUTHORIZED"}
    assert not hasattr(locked, "approval")
    assert not hasattr(locked, "approval_artifact_sha256")
    assert not hasattr(locked, "slot_number")


def test_canonical_sampled_approval_lock_type_remains_accepted() -> None:
    locked = CanonicalNotAuthorizedSampledSlotApproval(state="NOT_AUTHORIZED")
    assert locked.state == "NOT_AUTHORIZED"


@pytest.mark.parametrize(
    "raw",
    [
        '{"state":"not_authorized"}',
        '{"state":"NOT_AUTHORIZED","approval":{}}',
        '{ "state": "NOT_AUTHORIZED" }',
        '{"state":"AUTHORIZED"}',
        '{"state":"NOT_AUTHORIZED"',
        "{}",
    ],
)
def test_nonexact_or_malformed_sampled_approval_lock_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_stored_sampled_slot_execution_approval(raw)


@pytest.mark.parametrize(
    "raw",
    [
        '{"approval_artifact_sha256":"' + "0" * 64 + '"}',
        '{"approval":{}}',
        '{"approval":{},"approval_artifact_sha256":"' + "0" * 64 + '"}',
    ],
)
def test_partial_sampled_approval_envelope_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_stored_sampled_slot_execution_approval(raw)


def test_sampled_approval_lock_cannot_create_release_or_work_item() -> None:
    store = _Store(_approval())
    store.approval = SAMPLED_APPROVAL_LOCK_SENTINEL
    initial_release = store.release
    with pytest.raises(ValueError, match="approval is NOT_AUTHORIZED"):
        _applicator(store).apply()
    assert store.release == initial_release
    assert store.release_writes == 0
    assert store.kill == "TRIPPED"


def test_legacy_lock_requires_exact_owner_bound_predecessor_and_stays_pre_dns() -> None:
    approval = _approval(current_release_id=CURRENT_RELEASE)
    store = _Store(approval, LEGACY_LOCK_SENTINEL)
    with pytest.raises(ValueError, match="canonical legacy lock identity"):
        _applicator(store).apply()
    assert store.release == LEGACY_LOCK_SENTINEL
    assert store.release_writes == 0
    assert store.kill == "TRIPPED"


def test_exact_owner_approval_can_replace_legacy_lock_once() -> None:
    approval = _approval(current_release_id=LEGACY_LOCK_RELEASE_ID)
    store = _Store(approval, LEGACY_LOCK_SENTINEL)
    release, accepted, created = _applicator(store).apply()
    assert created is True
    assert accepted == approval
    assert release.state is PermissionState.AUTHORIZED
    assert release.slot_number == 1
    assert release.exact_hostname == "903hvac.com"
    assert release.source_registry_id == approval.source_registry_id
    assert release.retention_policy_id == approval.retention_policy_id
    assert release.environment_id == approval.environment_id
    assert release.cohort_policy_id == approval.cohort_policy_id
    assert release.kill_switch_id == approval.kill_switch_id
    assert store.release_writes == 1
    assert store.kill == "TRIPPED"


@pytest.mark.parametrize(
    "change",
    [
        {"slot_number": 2},
        {"business_identity": "Forged"},
        {"exact_hostname": "forged.example", "allowed_source_scope": ("forged.example",)},
        {"ordered_package_semantic_sha256": "1" * 64},
        {"slot_registry_file_sha256": "1" * 64},
        {"slot_registry_semantic_sha256": "2" * 64},
        {
            "slot_registry_file_sha256": FrozenPhaseOneSampleRegistry(SAMPLES).registry_sha256,
            "slot_registry_semantic_sha256": FrozenPhaseOneSampleRegistry(
                SAMPLES
            ).registry_file_sha256,
        },
        {"permission_type": "REAL_BUSINESS_DISCOVERY"},
        {"a09_decision_sha256": "2" * 64},
        {"research_runtime_revision": "sha256:" + "8" * 64},
    ],
)
def test_invalid_owner_artifact_creates_no_release(change: dict[str, object]) -> None:
    try:
        approval = _approval(**change)
    except ValueError:
        return
    store = _Store(approval)
    with pytest.raises(ValueError):
        _applicator(store).apply()
    assert (
        LiveResearchPermissionRelease.model_validate_json(store.release).state
        is PermissionState.NOT_AUTHORIZED
    )
    assert store.kill == "TRIPPED"
    assert store.release_writes == 0


@pytest.mark.parametrize(
    "missing",
    ["slot_registry_file_sha256", "slot_registry_semantic_sha256"],
)
def test_live_approval_requires_both_registry_identity_levels(missing: str) -> None:
    values = _approval().model_dump(mode="python")
    values.pop(missing)
    with pytest.raises(ValueError):
        SampledSlotExecutionApproval.model_validate(values)


def test_registry_identity_levels_are_distinct_and_exact() -> None:
    registry = FrozenPhaseOneSampleRegistry(SAMPLES)
    approval = _approval()
    assert registry.registry_file_sha256 == (
        "63428deed639059c40dd1e851c658f25ca421892e6155d0b239c4a8020d534d2"
    )
    assert registry.registry_sha256 == (
        "aaacf237fad2acf91db5a4741cdbc4401dd2a6b757b91bf9a039f7d7b3a454f2"
    )
    assert approval.slot_registry_file_sha256 == registry.registry_file_sha256
    assert approval.slot_registry_semantic_sha256 == registry.registry_sha256
    assert approval.slot_registry_file_sha256 != approval.slot_registry_semantic_sha256
    entry = registry.issue(UUID(int=0), 1)
    assert (entry.business_identity, entry.exact_hostname) == ("903 HVAC", "903hvac.com")


def _coordinator_binding() -> CoordinatorRunBinding:
    return CoordinatorRunBinding(
        coordinator_run_id=UUID("30000000-0000-4000-8000-000000000001"),
        authorization_release_id=AUTHORIZED_RELEASE,
        ordered_package_sha256="3" * 64,
        slot_number=1,
        business_identity="903 HVAC",
        exact_hostname="903hvac.com",
        work_item_identity_sha256="4" * 64,
        activation_sha256="5" * 64,
        runtime_revision=RUNTIME,
        created_at=NOW,
    )


def _coordinator(
    binding: CoordinatorRunBinding, existing: tuple = ()
) -> BoundedSampledSlotCoordinator:
    return BoundedSampledSlotCoordinator(
        ordered_package_sha256=binding.ordered_package_sha256,
        slot_number=binding.slot_number,
        business_identity=binding.business_identity,
        exact_hostname=binding.exact_hostname,
        work_item_identity_sha256=binding.work_item_identity_sha256,
        activation_sha256=binding.activation_sha256,
        authorization_release_id=binding.authorization_release_id,
        coordinator_run_id=binding.coordinator_run_id,
        runtime_revision=binding.runtime_revision,
        existing=existing,
    )


def test_durable_lineage_survives_restart_and_rejects_substitution(tmp_path: Path) -> None:
    repository = SqlAlchemyCoordinatorRepository(f"sqlite:///{tmp_path / 'coordinator.db'}")
    repository.initialize()
    binding = _coordinator_binding()
    assert repository.create_or_get(binding)[1] is True
    coordinator = _coordinator(binding)
    first, _ = coordinator.accept_stage(
        stage=ShadowStage.M1_MINIMIZED_EVIDENCE,
        revision_id=UUID("40000000-0000-4000-8000-000000000001"),
        output_sha256="6" * 64,
        authority_effective=True,
        kill_switch_tripped=False,
    )
    assert repository.append(first, NOW) is True
    assert repository.append(first, NOW) is False

    resumed = _coordinator(binding, repository.load(binding.coordinator_run_id))
    second, _ = resumed.accept_stage(
        stage=ShadowStage.M2_OPPORTUNITY_ECONOMICS,
        revision_id=UUID("40000000-0000-4000-8000-000000000002"),
        output_sha256="7" * 64,
        authority_effective=True,
        kill_switch_tripped=False,
    )
    forged = replace(second, predecessor_revision_id=uuid4())
    with pytest.raises(ValueError, match="predecessor"):
        repository.append(forged, NOW)
    assert repository.append(second, NOW) is True


class _Activator:
    def __init__(self, release: LiveResearchPermissionRelease) -> None:
        self.release = release
        self.calls = 0
        registry = FrozenPhaseOneSampleRegistry(SAMPLES)
        run_id = uuid5(NAMESPACE_URL, f"test:{release.id}")
        identity = registry.issue(run_id, 1)
        from opintel_research.domain import SampledSlotActivation

        activation = SampledSlotActivation.create(
            activation_id=uuid4(),
            authorization_release_id=release.id,
            authorization_configuration_hash=release.configuration_hash,
            a09_decision_sha256=FrozenA09DecisionRegistry(A09)
            .require_approved(1, "903 HVAC", "903hvac.com")
            .decision_sha256,
            research_runtime_revision=RUNTIME,
            execution_ceilings_sha256="8" * 64,
            activated_at=NOW,
            sampled_slot_identity=identity,
        )
        self.run = ResearchRun(
            id=run_id,
            workspace_id=WORKSPACE,
            business_id=uuid4(),
            operation_id=uuid4(),
            trace_id=uuid4(),
            start_url="https://903hvac.com/",
            permitted_host="903hvac.com",
            policy=CrawlPolicy(),
            status=ResearchRunStatus.PENDING,
            created_by="m67-sampled-slot-activator",
            created_at=NOW,
            updated_at=NOW,
            sampled_slot_identity=identity,
            sampled_slot_activation=activation,
        )

    def activate(self, slot_number: int, release_id: UUID) -> tuple[ResearchRun, bool]:
        assert slot_number == 1 and release_id == self.release.id
        self.calls += 1
        return self.run, self.calls == 1


class _Authority:
    def __init__(self, store: _Store) -> None:
        self.store = store

    def current_release(self) -> LiveResearchPermissionRelease:
        return LiveResearchPermissionRelease.model_validate_json(self.store.release)


class _Stop:
    def __init__(self, store: _Store) -> None:
        self.store = store

    def is_active(self) -> bool:
        return self.store.kill != "RUN"


class _SyntheticStages:
    def __init__(self) -> None:
        self.calls: list[ShadowStage] = []

    def execute(self, stage: ShadowStage, predecessor: object) -> StageResult:
        if stage is not ShadowStage.M1_MINIMIZED_EVIDENCE:
            assert predecessor is not None
        self.calls.append(stage)
        return StageResult(
            uuid5(NAMESPACE_URL, f"synthetic:{stage.value}"),
            hashlib.sha256(stage.value.encode()).hexdigest(),
        )


class _Egress:
    def __init__(self) -> None:
        self.active = False

    def activate_and_await_ready(
        self, release: LiveResearchPermissionRelease, run: ResearchRun
    ) -> tuple[ControlledEgressLease, bool]:
        assert not self.active
        self.active = True
        return build_egress_lease(release, run), True

    def deactivate(self, lease: ControlledEgressLease) -> bool:
        assert lease is not None and self.active
        self.active = False
        return True


class _EgressStore:
    def __init__(self) -> None:
        self.value = EGRESS_LEASE_LOCK_SENTINEL
        self.writes: list[str] = []

    def read(self) -> str:
        return self.value

    def write(self, value: str) -> None:
        self.value = value
        self.writes.append(value)


class _ReadyTransport:
    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def await_ready(self, *, timeout_seconds: float, poll_seconds: float = 0.5) -> None:
        del poll_seconds
        assert timeout_seconds <= 60
        self.calls += 1
        if self.fail:
            raise ValueError("synthetic startup failure")


def test_egress_lease_exact_authority_ready_then_m1_boundary_cleanup() -> None:
    store = _Store(_approval())
    release, _, _ = _applicator(store).apply()
    _applicator(store).enter_run(release)
    run = _Activator(release).run
    lease_store = _EgressStore()
    transport = _ReadyTransport()
    lifecycle = BoundedControlledEgressLifecycle(
        store=lease_store,
        authority=_Authority(store),
        stop_signal=_Stop(store),
        transport=transport,  # type: ignore[arg-type]
        readiness_timeout_seconds=5,
    )
    lease, created = lifecycle.activate_and_await_ready(release, run)
    assert created is True
    assert transport.calls == 1
    assert isinstance(parse_stored_egress_lease(lease_store.value), ControlledEgressLease)
    assert lifecycle.deactivate(lease) is True
    assert isinstance(
        parse_stored_egress_lease(lease_store.value),
        CanonicalNotAuthorizedEgressLease,
    )


def test_egress_startup_failure_restores_lock_without_transport_target_access() -> None:
    store = _Store(_approval())
    release, _, _ = _applicator(store).apply()
    _applicator(store).enter_run(release)
    lease_store = _EgressStore()
    lifecycle = BoundedControlledEgressLifecycle(
        store=lease_store,
        authority=_Authority(store),
        stop_signal=_Stop(store),
        transport=_ReadyTransport(fail=True),  # type: ignore[arg-type]
        readiness_timeout_seconds=5,
    )
    with pytest.raises(ValueError, match="startup failure"):
        lifecycle.activate_and_await_ready(release, _Activator(release).run)
    assert lease_store.value == EGRESS_LEASE_LOCK_SENTINEL


def test_egress_denies_kill_switch_and_wrong_work_item_before_readiness() -> None:
    store = _Store(_approval())
    release, _, _ = _applicator(store).apply()
    run = _Activator(release).run
    lease_store = _EgressStore()
    transport = _ReadyTransport()
    lifecycle = BoundedControlledEgressLifecycle(
        store=lease_store,
        authority=_Authority(store),
        stop_signal=_Stop(store),
        transport=transport,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="kill switch"):
        lifecycle.activate_and_await_ready(release, run)
    assert lease_store.writes == []
    store.kill = "RUN"
    forged = replace(run, permitted_host="forged.example")
    with pytest.raises(ValueError, match="outside exact release/work item"):
        lifecycle.activate_and_await_ready(release, forged)
    assert transport.calls == 0
    assert lease_store.writes == []


def test_complete_synthetic_production_chain_consumes_authority(tmp_path: Path) -> None:
    store = _Store(_approval())
    applicator = _applicator(store)
    release, _, _ = applicator.apply()
    # Restore the exact pre-execution state; BoundedSampledSlotExecution owns entering RUN.
    store.release = _current_release().model_dump_json()
    store.release_writes = 0
    activator = _Activator(release)
    repository = SqlAlchemyCoordinatorRepository(f"sqlite:///{tmp_path / 'execution.db'}")
    repository.initialize()
    stages = _SyntheticStages()
    egress = _Egress()
    execution = BoundedSampledSlotExecution(
        release_applicator=applicator,
        activator=activator,
        authority=_Authority(store),
        stop_signal=_Stop(store),
        repository=repository,
        stage_runtime_factory=lambda run: stages,
        controlled_egress=egress,
        now=lambda: NOW,
    )
    receipt = execution.run()
    assert receipt["terminal_reason"] == "CONTACT_PHASE_NOT_AUTHORIZED"
    assert receipt["accepted_stage_count"] == 6
    assert stages.calls == list(ShadowStage)
    assert receipt["controlled_egress_deactivated_after_m1"] is True
    assert egress.active is False
    assert store.kill == "TRIPPED"
    assert (
        LiveResearchPermissionRelease.model_validate_json(store.release).state
        is PermissionState.NOT_AUTHORIZED
    )
    with pytest.raises(ValueError):
        execution.run()
    assert activator.calls == 1


def test_production_entry_point_accepts_no_identity_arguments() -> None:
    source = (
        ROOT / "workers/intelligence/src/opintel_intelligence_worker/sampled_slot_execution_main.py"
    ).read_text(encoding="utf-8")
    assert "len(sys.argv) != 1" in source
    assert "BoundedSampledSlotExecution(" in source
    assert "opintel_intelligence_worker.main" not in source


def test_legacy_pollers_cannot_claim_reserved_sampled_slot_operations(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy-guard.db'}"
    created_by = "m67-bounded-sampled-slot-coordinator"
    common = {
        "id": uuid4(),
        "workspace_id": WORKSPACE,
        "business_id": uuid4(),
        "status": None,
        "idempotency_key": "m67:slot01:exact-stage",
        "trace_id": uuid4(),
        "attempt_count": 0,
        "max_attempts": 1,
        "created_by": created_by,
        "created_at": NOW,
        "updated_at": NOW,
    }

    opportunity = SqlAlchemyOpportunityRepository(database_url)
    opportunity.initialize()
    opportunity_run = OpportunityAnalysisRun(
        id=uuid4(),
        workspace_id=WORKSPACE,
        business_id=uuid4(),
        research_run_id=uuid4(),
        operation_id=uuid4(),
        trace_id=uuid4(),
        definition_version="m67-production-wiring-test",
        status=AnalysisStatus.PENDING,
        created_by=created_by,
        created_at=NOW,
        updated_at=NOW,
    )
    opportunity.create_or_get_run(opportunity_run, str(common["idempotency_key"]))
    assert opportunity.claim_run(NOW, timedelta(seconds=30)) is None
    assert (
        opportunity.claim_exact_run(opportunity_run.id, created_by, NOW, timedelta(seconds=30))
        is not None
    )

    audit = SqlAlchemyAuditRepository(database_url)
    audit.initialize()
    audit_operation = AuditOperation(
        **{
            **common,
            "id": uuid4(),
            "hypothesis_id": uuid4(),
            "expected_hypothesis_revision_id": uuid4(),
            "audit_id": uuid4(),
            "parent_revision_id": None,
            "kind": AuditKind.FULL,
            "status": AuditOperationStatus.PENDING,
        }
    )
    audit.create_or_get_operation(audit_operation)
    assert audit.claim_operation(NOW, timedelta(seconds=30)) is None
    assert (
        audit.claim_exact_operation(audit_operation.id, created_by, NOW, timedelta(seconds=30))
        is not None
    )

    demo = SqlAlchemyDemoRepository(database_url)
    demo.initialize()
    demo_operation = DemoOperation(
        **{
            **common,
            "id": uuid4(),
            "audit_revision_id": uuid4(),
            "expected_audit_revision_hash": "a" * 64,
            "demo_id": uuid4(),
            "parent_revision_id": None,
            "status": DemoOperationStatus.PENDING,
        }
    )
    demo.create_or_get_operation(demo_operation)
    assert demo.claim_operation(NOW, timedelta(seconds=30)) is None
    assert (
        demo.claim_exact_operation(demo_operation.id, created_by, NOW, timedelta(seconds=30))
        is not None
    )

    outreach = SqlAlchemyOutreachRepository(database_url)
    outreach.initialize()
    outreach_operation = OutreachOperation(
        **{
            **common,
            "id": uuid4(),
            "demo_revision_id": uuid4(),
            "expected_demo_revision_hash": "b" * 64,
            "package_id": uuid4(),
            "parent_revision_id": None,
            "status": OutreachOperationStatus.PENDING,
        }
    )
    outreach.create_or_get_operation(outreach_operation)
    assert outreach.claim_operation(NOW, timedelta(seconds=30)) is None
    assert (
        outreach.claim_exact_operation(
            outreach_operation.id, created_by, NOW, timedelta(seconds=30)
        )
        is not None
    )
