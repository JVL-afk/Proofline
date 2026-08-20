from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from opintel_m0_local import UuidFactory
from opintel_shadow.domain import PermissionActivity, PermissionState, stable_hash
from opintel_shadow.gate_application import (
    BoundedPhaseOneOrchestrator,
    ControlledEgressService,
    LiveResearchGateService,
    all_preflight_evidence,
    fake_response,
)
from opintel_shadow.gate_domain import (
    ApprovalState,
    BackupHandling,
    BudgetExceeded,
    BudgetPolicyRevision,
    CheckState,
    DataHandlingPolicyRevision,
    DeletionBehavior,
    EgressRequest,
    EnvironmentAttestationRevision,
    GovernedDataClass,
    KillSwitchRecord,
    KillSwitchState,
    LegalHold,
    LegalHoldBehavior,
    LiveResearchNotAuthorized,
    LiveResearchPermissionRelease,
    LiveResearchPolicyError,
    LiveResearchStopped,
    OperationalRole,
    ReadinessState,
    RetentionDecision,
    RetentionPolicyRevision,
    RoleAssignment,
    RoleAssignmentRevision,
    Sensitivity,
    SourceAccessMethod,
    SourceInstance,
    SourceKind,
    SourceRegistryRevision,
    StageProgression,
    SyntheticStoredArtifact,
    TermsReviewState,
    WorkStage,
    WorkState,
)
from opintel_shadow_local import (
    FakeHttpTransport,
    FakeResolver,
    InMemorySyntheticArtifactStore,
    SqlAlchemyGateRepository,
)
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000067")


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def gate_repository(tmp_path: Path) -> SqlAlchemyGateRepository:
    value = SqlAlchemyGateRepository(f"sqlite:///{(tmp_path / 'gate.db').as_posix()}")
    value.initialize()
    return value


@pytest.fixture
def artifact_store() -> InMemorySyntheticArtifactStore:
    return InMemorySyntheticArtifactStore()


@pytest.fixture
def gate_service(
    gate_repository: SqlAlchemyGateRepository,
    artifact_store: InMemorySyntheticArtifactStore,
    clock: MutableClock,
) -> LiveResearchGateService:
    return LiveResearchGateService(gate_repository, artifact_store, clock, UuidFactory())


def _data_policy(clock: MutableClock) -> DataHandlingPolicyRevision:
    return DataHandlingPolicyRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-data-policy@1",
        configuration_hash="data-policy-hash",
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-privacy-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
    )


def _retention(clock: MutableClock, seconds: int = 60) -> RetentionPolicyRevision:
    decisions = tuple(
        RetentionDecision(
            data_class=data_class,
            purpose=f"synthetic-{data_class.value}-test",
            sensitivity=(
                Sensitivity.CONFIDENTIAL
                if data_class
                in {
                    GovernedDataClass.RESTRICTED_SOURCE_CAPTURE,
                    GovernedDataClass.EXTRACTED_TEXT,
                    GovernedDataClass.EVIDENCE,
                    GovernedDataClass.REVIEW_ARTIFACT,
                    GovernedDataClass.ACCESS_AUDIT_LOG,
                    GovernedDataClass.BACKUP,
                }
                else Sensitivity.INTERNAL
            ),
            retention_seconds=seconds,
            deletion_behavior=(
                DeletionBehavior.EXPIRE_LOG_RECORD
                if data_class
                in {
                    GovernedDataClass.OPERATIONAL_LOG,
                    GovernedDataClass.ACCESS_AUDIT_LOG,
                }
                else DeletionBehavior.DELETE_CONTENT_RETAIN_TOMBSTONE
            ),
            backup_handling=(
                BackupHandling.ENCRYPTED_EXPIRY_BOUND
                if data_class is GovernedDataClass.BACKUP
                else BackupHandling.SAME_OR_SHORTER_EXPIRY
            ),
            legal_hold_behavior=(
                LegalHoldBehavior.NOT_ELIGIBLE_FOR_HOLD
                if data_class is GovernedDataClass.DELETION_TOMBSTONE
                else LegalHoldBehavior.BLOCK_DELETION_WHILE_ACTIVE
            ),
            allowed_consumers=(OperationalRole.PRIVACY_DATA_OWNER,),
        )
        for data_class in GovernedDataClass
    )
    return RetentionPolicyRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-retention@1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in decisions]),
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-retention-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        decisions=decisions,
    )


def _source(
    clock: MutableClock,
    kind: SourceKind,
    source_id: str,
    host: str = "synthetic-gate.invalid",
) -> SourceInstance:
    return SourceInstance(
        source_id=source_id,
        kind=kind,
        exact_identity=f"{kind.value}:{host}",
        scheme="https",
        host=host,
        provider="repository-owned-synthetic-fixture",
        purpose="synthetic Phase 1 gate validation",
        access_method=SourceAccessMethod.PUBLIC_HTTP_GET_HEAD,
        terms_review_state=TermsReviewState.APPROVED,
        terms_review_id="fixture-terms-review",
        robots_treatment="required_fail_closed",
        max_logical_fetches=120,
        max_total_attempts=360,
        max_response_bytes=512_000,
        minimum_delay_milliseconds=2_000,
        allowed_data_categories=("public_business_page", "incidental_person_in_capture_only"),
        storage_restrictions=("restricted_immutable_capture",),
        reuse_restrictions=("no_contact_projection",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        accountable_approval_id="fixture-source-approval",
    )


def _registry(clock: MutableClock) -> SourceRegistryRevision:
    sources = (
        _source(clock, SourceKind.DISCOVERY_SOURCE, "fixture-discovery"),
        _source(clock, SourceKind.RESEARCH_SOURCE, "fixture-research"),
    )
    return SourceRegistryRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-source-registry@1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in sources]),
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-source-registry-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        sources=sources,
    )


def _environment(clock: MutableClock) -> EnvironmentAttestationRevision:
    return EnvironmentAttestationRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-environment@1",
        configuration_hash="fixture-environment-hash",
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-security-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        tenancy_boundary_ref="fixture://environment/tenancy",
        environment_identity="synthetic-preflight-only",
        region="synthetic-region-not-live",
        encryption_at_rest_ref="fixture://environment/encryption-at-rest",
        encryption_in_transit_ref="fixture://environment/encryption-in-transit",
        storage_isolation_ref="fixture://environment/storage-isolation",
        research_egress_identity_ref="fixture://environment/egress-identity",
        workload_identity_ref="fixture://environment/workload-identity",
        operator_access_ref="fixture://environment/operator-access",
        mfa_oidc_ref="fixture://environment/mfa-oidc",
        secrets_isolation_ref="fixture://environment/secrets-isolation",
        audit_logging_ref="fixture://environment/audit-logging",
        backup_policy_ref="fixture://environment/backup-policy",
        kill_switch_owner_ref="fixture://environment/kill-owner",
        synthetic_attestation=True,
    )


def _roles(clock: MutableClock, same_reviewers: bool = False) -> RoleAssignmentRevision:
    refs = {
        OperationalRole.PROJECT_OWNER: "fixture-project-owner",
        OperationalRole.OPPORTUNITY_REVIEWER: "fixture-reviewer-one",
        OperationalRole.INDEPENDENT_SECOND_REVIEWER: (
            "fixture-reviewer-one" if same_reviewers else "fixture-reviewer-two"
        ),
        OperationalRole.INCIDENT_OWNER: "fixture-incident-owner",
        OperationalRole.PRIVACY_DATA_OWNER: "fixture-privacy-owner",
        OperationalRole.KILL_SWITCH_OPERATOR: "fixture-kill-operator",
        OperationalRole.SECURITY_ENVIRONMENT_OWNER: "fixture-security-owner",
        OperationalRole.QUALIFIED_LEGAL_REVIEWER: "fixture-legal-reviewer",
    }
    return RoleAssignmentRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-roles@1",
        configuration_hash=stable_hash(refs),
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-role-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        synthetic_assignments=True,
        assignments=tuple(
            RoleAssignment(
                role=role,
                subject_ref=refs[role],
                assignment_approval_id="fixture-role-approval",
            )
            for role in OperationalRole
        ),
    )


def _budget(clock: MutableClock, money: bool = False) -> BudgetPolicyRevision:
    amount = Decimal("25") if money else None
    return BudgetPolicyRevision(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-budget@1",
        configuration_hash="fixture-budget-hash",
        created_at=clock.now(),
        state=ApprovalState.APPROVED,
        approval_ids=("fixture-budget-approval",),
        effective_at=clock.now() - timedelta(hours=1),
        expires_at=clock.now() + timedelta(days=1),
        cohort_hard_cap_usd=(Decimal("100") if money else None),
        discovery_sub_budget_usd=amount,
        research_sub_budget_usd=amount,
        storage_compute_sub_budget_usd=amount,
        shared_overhead_sub_budget_usd=amount,
        max_retries_per_logical_fetch=2,
    )


def _kill(clock: MutableClock, state: KillSwitchState = KillSwitchState.CLEAR) -> KillSwitchRecord:
    return KillSwitchRecord(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version="fixture-kill-switch@1",
        configuration_hash="fixture-kill-hash",
        created_at=clock.now(),
        state=state,
        operator_ref="fixture-kill-operator",
        reason="synthetic baseline" if state is KillSwitchState.CLEAR else "synthetic emergency",
        activated_at=None if state is KillSwitchState.CLEAR else clock.now(),
    )


def _release(
    clock: MutableClock,
    registry: SourceRegistryRevision,
    retention: RetentionPolicyRevision,
    environment: EnvironmentAttestationRevision,
    kill: KillSwitchRecord,
    activity: PermissionActivity,
    state: PermissionState = PermissionState.AUTHORIZED,
) -> LiveResearchPermissionRelease:
    payload_hash = stable_hash((activity, registry.id, retention.id, environment.id, state))
    return LiveResearchPermissionRelease(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        version=f"fixture-{activity.value}@1",
        configuration_hash=payload_hash,
        created_at=clock.now(),
        activity=activity,
        state=state,
        source_registry_id=registry.id,
        source_registry_hash=stable_hash(registry.model_dump(mode="json")),
        retention_policy_id=retention.id,
        retention_policy_hash=stable_hash(retention.model_dump(mode="json")),
        environment_id=environment.id,
        environment_hash=stable_hash(environment.model_dump(mode="json")),
        cohort_policy_id=uuid4(),
        cohort_or_run_restriction="fixture-frozen-cohort-24",
        starts_at=clock.now() - timedelta(minutes=1),
        expires_at=clock.now() + timedelta(hours=1),
        approval_ids=("fixture-simulated-live-release",),
        kill_switch_id=kill.id,
        suspended_reason=("fixture suspension" if state is PermissionState.SUSPENDED else None),
    )


def _request(release: LiveResearchPermissionRelease, source_id: str) -> EgressRequest:
    return EgressRequest(
        workspace_id=WORKSPACE_ID,
        activity=release.activity,
        source_id=source_id,
        url="https://synthetic-gate.invalid/public",
        expected_release_id=release.id,
        expected_configuration_hash=release.configuration_hash,
    )


def _preflight(
    service: LiveResearchGateService,
    clock: MutableClock,
    evidence: dict[str, tuple[str, ...]],
    workspace_id: UUID = WORKSPACE_ID,
):
    return service.build_preflight(
        workspace_id,
        evidence,
        data_policy=_data_policy(clock),
        retention=_retention(clock),
        source_registry=_registry(clock),
        environment=_environment(clock),
        roles=_roles(clock),
        budget=_budget(clock),
        kill_switch=_kill(clock),
    )


def test_data_policy_structurally_prohibits_every_person_contact_projection(
    clock: MutableClock,
) -> None:
    policy = _data_policy(clock)
    assert policy.restricted_captures_immutable
    assert policy.incidental_public_person_data_capture_only
    assert not policy.person_contact_domain_extraction_allowed
    assert not policy.person_contact_indexing_allowed
    assert not policy.person_contact_search_allowed
    assert not policy.m6_projection_allowed
    assert not policy.contact_values_in_ordinary_logs_allowed
    assert not policy.person_contact_metrics_allowed


def test_retention_policy_requires_every_data_class_and_no_default_duration(
    clock: MutableClock,
) -> None:
    complete = _retention(clock)
    assert tuple(item.data_class for item in complete.decisions) == tuple(GovernedDataClass)
    payload = complete.model_dump()
    payload["decisions"] = payload["decisions"][:-1]
    with pytest.raises(ValidationError):
        RetentionPolicyRevision.model_validate(payload)
    with pytest.raises(ValidationError):
        RetentionDecision.model_validate(
            {
                "data_class": GovernedDataClass.EVIDENCE,
                "purpose": "fixture",
                "sensitivity": Sensitivity.CONFIDENTIAL,
                "deletion_behavior": DeletionBehavior.DELETE_CONTENT_RETAIN_TOMBSTONE,
                "backup_handling": BackupHandling.SAME_OR_SHORTER_EXPIRY,
                "legal_hold_behavior": LegalHoldBehavior.BLOCK_DELETION_WHILE_ACTIVE,
                "allowed_consumers": (OperationalRole.PRIVACY_DATA_OWNER,),
            }
        )


def test_source_registry_separates_discovery_and_research_and_disables_browser(
    clock: MutableClock,
) -> None:
    registry = _registry(clock)
    assert tuple(item.kind for item in registry.sources) == (
        SourceKind.DISCOVERY_SOURCE,
        SourceKind.RESEARCH_SOURCE,
    )
    assert registry.browser_policy == "DISABLED"
    assert all(not item.browser_allowed for item in registry.sources)
    assert all(not item.person_contact_extraction_allowed for item in registry.sources)


def test_role_assignments_require_independent_second_reviewer(clock: MutableClock) -> None:
    with pytest.raises(ValidationError, match="different human"):
        _roles(clock, same_reviewers=True)


def test_all_live_releases_created_by_m67c_remain_not_authorized(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    discovery, research = gate_service.create_not_authorized_releases(
        WORKSPACE_ID,
        _registry(clock),
        _retention(clock),
        _environment(clock),
        uuid4(),
        _kill(clock),
    )
    assert discovery.state is PermissionState.NOT_AUTHORIZED
    assert research.state is PermissionState.NOT_AUTHORIZED
    assert discovery.activity is PermissionActivity.REAL_BUSINESS_DISCOVERY
    assert research.activity is PermissionActivity.REAL_PUBLIC_RESEARCH


def test_unauthorized_egress_rejects_before_dns_or_transport(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock,
        registry,
        retention,
        environment,
        kill,
        PermissionActivity.REAL_PUBLIC_RESEARCH,
        PermissionState.NOT_AUTHORIZED,
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchNotAuthorized):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert resolver.calls == []
    assert transport.calls == []


def test_future_simulated_authorized_release_allows_only_exact_registered_source(
    clock: MutableClock,
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock,
        registry,
        retention,
        environment,
        kill,
        PermissionActivity.REAL_PUBLIC_RESEARCH,
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200, b"fixture-public-page"),))
    receipt = ControlledEgressService(resolver, transport, clock).fetch(
        _request(release, "fixture-research"),
        release,
        registry,
        retention,
        environment,
        kill,
    )
    assert receipt.response_bytes == len(b"fixture-public-page")
    assert receipt.transport_calls == 1
    assert not receipt.live_provider


@pytest.mark.parametrize(
    ("activity", "source_id"),
    [
        (PermissionActivity.REAL_BUSINESS_DISCOVERY, "fixture-research"),
        (PermissionActivity.REAL_PUBLIC_RESEARCH, "fixture-discovery"),
    ],
)
def test_discovery_and_research_authority_never_inherit(
    clock: MutableClock, activity: PermissionActivity, source_id: str
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(clock, registry, retention, environment, kill, activity)
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchPolicyError, match="unregistered"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, source_id),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert resolver.calls == []


def test_unregistered_host_and_redirect_escape_fail_closed(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    direct = _request(release, "fixture-research").model_copy(
        update={"url": "https://unregistered.invalid/public"}
    )
    direct_transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchPolicyError, match="exact source"):
        ControlledEgressService(resolver, direct_transport, clock).fetch(
            direct, release, registry, retention, environment, kill
        )
    redirect_transport = FakeHttpTransport(
        (fake_response(302, location="https://escape.invalid/public"),)
    )
    with pytest.raises(LiveResearchPolicyError, match="M1 public URL policy"):
        ControlledEgressService(resolver, redirect_transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert len(redirect_transport.calls) == 1


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.1.1", "10.1.2.3", "::1"])
def test_m1_ssrf_policy_rejects_non_public_addresses(clock: MutableClock, address: str) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    resolver = FakeResolver({"synthetic-gate.invalid": ((address,),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchPolicyError, match="M1 public URL policy"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert transport.calls == []


def test_dns_rebinding_on_redirect_is_revalidated_and_rejected(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",), ("127.0.0.1",))})
    transport = FakeHttpTransport((fake_response(302, location="/next"), fake_response(200)))
    with pytest.raises(LiveResearchPolicyError, match="M1 public URL policy"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "ftp://synthetic-gate.invalid/public",
        "https://synthetic-gate.invalid:8443/public",
        "https://synthetic-gate.invalid/login",
        "https://synthetic-gate.invalid/booking",
        "https://synthetic-gate.invalid/mailbox",
        "https://synthetic-gate.invalid/submit",
    ],
)
def test_scheme_port_and_interactive_endpoints_are_rejected(clock: MutableClock, url: str) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    request = _request(release, "fixture-research").model_copy(update={"url": url})
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchPolicyError):
        ControlledEgressService(resolver, transport, clock).fetch(
            request, release, registry, retention, environment, kill
        )
    assert transport.calls == []


def test_expired_policy_revision_and_configuration_drift_fail_closed(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    expired = retention.model_copy(
        update={
            "effective_at": clock.now() - timedelta(days=2),
            "expires_at": clock.now() - timedelta(days=1),
        }
    )
    with pytest.raises(LiveResearchPolicyError, match="revision mismatch"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            expired,
            environment,
            kill,
        )
    drifted_request = _request(release, "fixture-research").model_copy(
        update={"expected_configuration_hash": "drift"}
    )
    with pytest.raises(LiveResearchNotAuthorized, match="hash mismatch"):
        ControlledEgressService(resolver, transport, clock).fetch(
            drifted_request, release, registry, retention, environment, kill
        )
    assert transport.calls == []


@pytest.mark.parametrize("state", [PermissionState.SUSPENDED, PermissionState.EXPIRED])
def test_suspended_or_expired_permission_rejects_before_dns(
    clock: MutableClock, state: PermissionState
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    release = _release(
        clock,
        registry,
        retention,
        environment,
        kill,
        PermissionActivity.REAL_PUBLIC_RESEARCH,
        state,
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchNotAuthorized):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert resolver.calls == [] and transport.calls == []


def test_expired_environment_attestation_blocks_after_exact_binding(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    expired = environment.model_copy(
        update={
            "effective_at": clock.now() - timedelta(days=2),
            "expires_at": clock.now() - timedelta(days=1),
        }
    )
    release = _release(
        clock,
        registry,
        retention,
        expired,
        kill,
        PermissionActivity.REAL_PUBLIC_RESEARCH,
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchPolicyError, match="not current"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            expired,
            kill,
        )
    assert resolver.calls == [] and transport.calls == []


def test_oversized_fake_response_is_rejected(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    constrained_source = registry.sources[1].model_copy(update={"max_response_bytes": 4})
    constrained = registry.model_copy(update={"sources": (registry.sources[0], constrained_source)})
    release = _release(
        clock,
        constrained,
        retention,
        environment,
        kill,
        PermissionActivity.REAL_PUBLIC_RESEARCH,
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200, b"oversized"),))
    with pytest.raises(LiveResearchPolicyError, match="response exceeds"):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            constrained,
            retention,
            environment,
            kill,
        )


def test_kill_switch_blocks_egress_before_dns(clock: MutableClock) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock, KillSwitchState.TRIPPED),
    )
    release = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    resolver = FakeResolver({"synthetic-gate.invalid": (("93.184.216.34",),)})
    transport = FakeHttpTransport((fake_response(200),))
    with pytest.raises(LiveResearchStopped):
        ControlledEgressService(resolver, transport, clock).fetch(
            _request(release, "fixture-research"),
            release,
            registry,
            retention,
            environment,
            kill,
        )
    assert resolver.calls == []


def test_kill_switch_operator_is_explicit_and_project_owner_cannot_override(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    roles = _roles(clock)
    with pytest.raises(LiveResearchPolicyError, match="assigned"):
        gate_service.trip_kill_switch(
            _kill(clock), roles, "fixture-project-owner", "project wants to continue"
        )
    tripped = gate_service.trip_kill_switch(
        _kill(clock), roles, "fixture-kill-operator", "synthetic safety event"
    )
    assert tripped.state is KillSwitchState.TRIPPED
    assert tripped.preserves_captured_evidence


def test_budget_reservations_enforce_workload_caps_and_paid_fail_closed(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    budget = _budget(clock)
    gate_service.reserve_budget(WORKSPACE_ID, budget, "fixture-op", 120, 360, 36_000_000, None)
    with pytest.raises(BudgetExceeded):
        gate_service.reserve_budget(WORKSPACE_ID, budget, "overflow", 1, 0, 0, None)
    with pytest.raises(BudgetExceeded, match="monetary"):
        gate_service.reserve_budget(
            uuid4(), budget, "paid-without-approval", 1, 1, 1, Decimal("0.01")
        )
    assert budget.ai_budget_usd == Decimal("0")
    assert not budget.monetary_approval_complete
    assert _budget(clock, money=True).monetary_approval_complete


def test_budget_reconciliation_is_bounded_immutable_and_single_use(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    reservation = gate_service.reserve_budget(
        WORKSPACE_ID, _budget(clock), "reconcile-op", 5, 10, 1_000, None
    )
    with pytest.raises(BudgetExceeded, match="exceeds"):
        gate_service.reconcile_budget(
            reservation,
            actual_logical_fetches=6,
            actual_total_attempts=10,
            actual_response_bytes=1_000,
            actual_monetary_usd=None,
        )
    reconciled = gate_service.reconcile_budget(
        reservation,
        actual_logical_fetches=4,
        actual_total_attempts=8,
        actual_response_bytes=800,
        actual_monetary_usd=None,
    )
    assert reconciled.reconciled
    assert not reservation.reconciled
    with pytest.raises(BudgetExceeded, match="already"):
        gate_service.reconcile_budget(
            reconciled,
            actual_logical_fetches=4,
            actual_total_attempts=8,
            actual_response_bytes=800,
            actual_monetary_usd=None,
        )


def test_orchestrator_is_idempotent_and_uses_transactional_leases(
    gate_repository: SqlAlchemyGateRepository, clock: MutableClock
) -> None:
    orchestrator = BoundedPhaseOneOrchestrator(
        gate_repository, gate_repository, clock, UuidFactory()
    )
    first, created = orchestrator.enqueue(
        WORKSPACE_ID, "fixture-idempotency", WorkStage.RESEARCH, "payload-hash"
    )
    duplicate, duplicate_created = orchestrator.enqueue(
        WORKSPACE_ID, "fixture-idempotency", WorkStage.RESEARCH, "payload-hash"
    )
    assert created and not duplicate_created and duplicate.id == first.id
    claimed = orchestrator.claim(WORKSPACE_ID, "fixture-worker", _kill(clock), lease_seconds=10)
    assert claimed is not None
    assert claimed.state is WorkState.LEASED
    assert claimed.attempt_count == 1
    assert orchestrator.claim(WORKSPACE_ID, "other-worker", _kill(clock)) is None
    completed = orchestrator.complete(claimed, "fixture-worker", "output-hash", _kill(clock))
    assert completed.state is WorkState.SUCCEEDED
    assert len(gate_repository.list(WORKSPACE_ID, "stage_lineage")) == 2


def test_stale_lease_recovery_and_retry_bounds(
    gate_repository: SqlAlchemyGateRepository, clock: MutableClock
) -> None:
    orchestrator = BoundedPhaseOneOrchestrator(
        gate_repository, gate_repository, clock, UuidFactory()
    )
    item, _ = orchestrator.enqueue(
        WORKSPACE_ID, "stale", WorkStage.DISCOVERY, "payload", max_attempts=2
    )
    leased = orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock), lease_seconds=5)
    assert leased is not None and leased.id == item.id
    clock.advance(6)
    assert orchestrator.recover_stale(WORKSPACE_ID) == 1
    recovered = gate_repository.get_work(WORKSPACE_ID, item.id)
    assert recovered is not None and recovered.state is WorkState.QUEUED
    second = orchestrator.claim(WORKSPACE_ID, "worker-2", _kill(clock), lease_seconds=5)
    assert second is not None and second.attempt_count == 2
    terminal = orchestrator.fail_or_retry(second, "worker-2", True, _kill(clock))
    assert terminal.state is WorkState.FAILED


def test_pause_and_kill_checks_block_queued_retry_and_stale_worker(
    gate_repository: SqlAlchemyGateRepository, clock: MutableClock
) -> None:
    orchestrator = BoundedPhaseOneOrchestrator(
        gate_repository, gate_repository, clock, UuidFactory()
    )
    item, _ = orchestrator.enqueue(WORKSPACE_ID, "kill", WorkStage.RESEARCH, "payload")
    with pytest.raises(LiveResearchStopped):
        orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock, KillSwitchState.TRIPPED))
    with pytest.raises(LiveResearchStopped, match="pause"):
        orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock), paused=True)
    leased = orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock))
    assert leased is not None and leased.id == item.id
    with pytest.raises(LiveResearchStopped):
        orchestrator.fail_or_retry(leased, "worker", True, _kill(clock, KillSwitchState.TRIPPED))
    with pytest.raises(LiveResearchStopped):
        orchestrator.complete(leased, "worker", "output", _kill(clock, KillSwitchState.TRIPPED))


def test_pause_is_resumable_only_by_an_explicit_successor_command(
    gate_repository: SqlAlchemyGateRepository, clock: MutableClock
) -> None:
    orchestrator = BoundedPhaseOneOrchestrator(
        gate_repository, gate_repository, clock, UuidFactory()
    )
    orchestrator.enqueue(WORKSPACE_ID, "pause", WorkStage.RESEARCH, "payload")
    leased = orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock))
    assert leased is not None
    paused = orchestrator.pause(leased, "worker")
    assert paused.state is WorkState.PAUSED
    assert orchestrator.claim(WORKSPACE_ID, "worker", _kill(clock)) is None


def test_deletion_requires_expiry_and_emits_content_free_tombstone(
    gate_service: LiveResearchGateService,
    artifact_store: InMemorySyntheticArtifactStore,
    clock: MutableClock,
) -> None:
    retention = _retention(clock, seconds=60)
    artifact = SyntheticStoredArtifact(
        artifact_ref="fixture://restricted/capture-1",
        data_class=GovernedDataClass.RESTRICTED_SOURCE_CAPTURE,
        created_at=clock.now(),
        retention_policy_id=retention.id,
        content_hash=stable_hash(b"synthetic page with incidental contact marker"),
        superseded=True,
    )
    artifact_store.put(WORKSPACE_ID, artifact, b"synthetic page with incidental contact marker")
    with pytest.raises(LiveResearchPolicyError, match="not retention-expired"):
        gate_service.delete_expired_artifact(WORKSPACE_ID, artifact, retention, ())
    clock.advance(61)
    audit = gate_service.delete_expired_artifact(WORKSPACE_ID, artifact, retention, ())
    assert not artifact_store.exists(WORKSPACE_ID, artifact.artifact_ref)
    assert audit.content_deleted and audit.superseded_artifact
    assert audit.tombstone_ref.startswith("tombstone:")
    assert "synthetic page" not in audit.model_dump_json()


def test_active_legal_hold_blocks_expired_deletion(
    gate_service: LiveResearchGateService,
    artifact_store: InMemorySyntheticArtifactStore,
    clock: MutableClock,
) -> None:
    retention = _retention(clock, seconds=1)
    artifact = SyntheticStoredArtifact(
        artifact_ref="fixture://evidence/held",
        data_class=GovernedDataClass.EVIDENCE,
        created_at=clock.now() - timedelta(seconds=10),
        retention_policy_id=retention.id,
        content_hash="held-hash",
    )
    artifact_store.put(WORKSPACE_ID, artifact, b"held synthetic evidence")
    hold = LegalHold(
        hold_id="fixture-hold",
        data_class=GovernedDataClass.EVIDENCE,
        reason="synthetic legal-hold test",
        approval_id="fixture-hold-approval",
        effective_at=clock.now() - timedelta(minutes=1),
        expires_at=clock.now() + timedelta(minutes=1),
    )
    with pytest.raises(LiveResearchPolicyError, match="legal hold"):
        gate_service.delete_expired_artifact(WORKSPACE_ID, artifact, retention, (hold,))
    assert artifact_store.exists(WORKSPACE_ID, artifact.artifact_ref)


def test_cohort_freeze_gate_lists_every_missing_live_approval(
    gate_service: LiveResearchGateService,
) -> None:
    result = gate_service.evaluate_cohort_freeze(
        WORKSPACE_ID,
        cohort_policy_accepted=False,
        target_owner_approved=False,
        source_registry=None,
        environment=None,
        retention=None,
        a17_approved=False,
        roles=None,
        budget=None,
        discovery_release=None,
    )
    assert not result.can_freeze
    assert set(result.blockers) == {
        "COHORT_POLICY_NOT_ACCEPTED",
        "TARGET_24_NOT_OWNER_APPROVED",
        "SOURCE_REGISTRY_NOT_APPROVED",
        "ENVIRONMENT_NOT_APPROVED",
        "RETENTION_NOT_APPROVED",
        "A17_NOT_APPROVED",
        "ROLES_NOT_APPROVED",
        "BUDGET_NOT_APPROVED",
        "DISCOVERY_NOT_AUTHORIZED",
    }


def test_cohort_gate_requires_discovery_and_research_remains_separate(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    discovery = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_BUSINESS_DISCOVERY
    )
    result = gate_service.evaluate_cohort_freeze(
        WORKSPACE_ID,
        cohort_policy_accepted=True,
        target_owner_approved=True,
        source_registry=registry,
        environment=environment,
        retention=retention,
        a17_approved=True,
        roles=_roles(clock),
        budget=_budget(clock),
        discovery_release=discovery,
    )
    assert result.can_freeze
    assert result.research_release_required_for_fetch


def test_staged_execution_freezes_order_pauses_and_preserves_failed_outcome(
    gate_service: LiveResearchGateService,
) -> None:
    order = tuple(f"synthetic-slot-{number:02d}" for number in range(1, 25))
    value = gate_service.create_staged_execution(
        WORKSPACE_ID, stable_hash(order), order, small_batch_size=4
    )
    assert value.progression is StageProgression.STAGE_0_PREFLIGHT
    value = gate_service.advance_stage(value, completed_outcomes={})
    value = gate_service.advance_stage(value, completed_outcomes={order[0]: "RESEARCH_FAILED"})
    assert value.progression is StageProgression.STAGE_1_PAUSED
    with pytest.raises(LiveResearchPolicyError, match="continuation"):
        gate_service.advance_stage(value, completed_outcomes={})
    value = gate_service.advance_stage(
        value, completed_outcomes={}, continuation_approval_id="fixture-owner-safety-review"
    )
    assert value.progression is StageProgression.STAGE_2_SMALL_BATCH
    assert value.recorded_outcomes[order[0]] == "RESEARCH_FAILED"
    assert value.frozen_candidate_order == order
    with pytest.raises(LiveResearchPolicyError, match="frozen cohort"):
        gate_service.advance_stage(value, completed_outcomes={"preferred-company": "APPROVED"})


def test_staged_execution_requires_exact_contiguous_batch_and_immutable_outcome(
    gate_service: LiveResearchGateService,
) -> None:
    order = tuple(f"synthetic-slot-{number:02d}" for number in range(1, 25))
    value = gate_service.create_staged_execution(
        WORKSPACE_ID, stable_hash(order), order, small_batch_size=3
    )
    value = gate_service.advance_stage(value, completed_outcomes={})
    with pytest.raises(LiveResearchPolicyError, match="slot-one"):
        gate_service.advance_stage(value, completed_outcomes={order[1]: "RESEARCH_FAILED"})
    value = gate_service.advance_stage(value, completed_outcomes={order[0]: "RESEARCH_FAILED"})
    with pytest.raises(LiveResearchPolicyError, match="immutable"):
        gate_service.advance_stage(
            value,
            completed_outcomes={order[0]: "CONTACT_PHASE_NOT_AUTHORIZED"},
            continuation_approval_id="fixture-review",
        )
    value = gate_service.advance_stage(
        value, completed_outcomes={}, continuation_approval_id="fixture-review"
    )
    with pytest.raises(LiveResearchPolicyError, match="contiguous"):
        gate_service.advance_stage(
            value,
            completed_outcomes={
                order[1]: "RESEARCH_FAILED",
                order[3]: "NO_SUPPORTED_OPPORTUNITY",
            },
        )


def test_complete_synthetic_preflight_is_technically_ready_but_authorizes_nothing(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    result = _preflight(gate_service, clock, all_preflight_evidence())
    assert result.readiness is ReadinessState.READY_FOR_REAL_RESEARCH_AUTHORIZATION
    assert all(item.state is CheckState.PASS for item in result.checks)
    assert len(result.authorization_blockers) == 12
    assert set(result.permission_states) == set(PermissionActivity)
    assert set(result.permission_states.values()) == {PermissionState.NOT_AUTHORIZED}
    assert result.real_businesses_accessed == 0
    assert result.real_business_urls_fetched == 0
    assert result.real_people_processed == 0
    assert result.real_contacts_processed == 0
    assert result.live_source_provider_calls == 0
    assert result.external_communications == 0
    assert result.delivery_capabilities == 0
    assert result.ai_provider_calls == 0


def test_incomplete_synthetic_preflight_is_not_ready(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    evidence = all_preflight_evidence()
    del evidence["KILL_SWITCH_OPERATIONAL"]
    result = _preflight(gate_service, clock, evidence)
    assert result.readiness is ReadinessState.NOT_READY_FOR_REAL_RESEARCH_AUTHORIZATION
    failed = [item.code for item in result.checks if item.state is CheckState.FAIL]
    assert failed == ["KILL_SWITCH_OPERATIONAL"]


def test_preflight_derives_failure_from_expired_environment_record(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    environment = _environment(clock).model_copy(
        update={
            "effective_at": clock.now() - timedelta(days=2),
            "expires_at": clock.now() - timedelta(days=1),
        }
    )
    result = gate_service.build_preflight(
        WORKSPACE_ID,
        all_preflight_evidence(),
        data_policy=_data_policy(clock),
        retention=_retention(clock),
        source_registry=_registry(clock),
        environment=environment,
        roles=_roles(clock),
        budget=_budget(clock),
        kill_switch=_kill(clock),
    )
    assert result.readiness is ReadinessState.NOT_READY_FOR_REAL_RESEARCH_AUTHORIZATION
    failed = {item.code for item in result.checks if item.state is CheckState.FAIL}
    assert failed == {"ENVIRONMENT_ATTESTATION_MECHANICS"}


def test_preflight_cannot_report_ready_if_a_persisted_release_is_authorized(
    gate_repository: SqlAlchemyGateRepository,
    gate_service: LiveResearchGateService,
    clock: MutableClock,
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    gate_repository.save(
        _release(
            clock,
            registry,
            retention,
            environment,
            kill,
            PermissionActivity.REAL_BUSINESS_DISCOVERY,
        )
    )
    with pytest.raises(LiveResearchPolicyError, match="authorized live release"):
        _preflight(gate_service, clock, all_preflight_evidence())


def test_permission_suspension_is_independent_and_immutable(
    gate_service: LiveResearchGateService, clock: MutableClock
) -> None:
    registry, retention, environment, kill = (
        _registry(clock),
        _retention(clock),
        _environment(clock),
        _kill(clock),
    )
    discovery = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_BUSINESS_DISCOVERY
    )
    research = _release(
        clock, registry, retention, environment, kill, PermissionActivity.REAL_PUBLIC_RESEARCH
    )
    suspended = gate_service.suspend_release(discovery, "synthetic source-policy drift")
    assert suspended.state is PermissionState.SUSPENDED
    assert discovery.state is PermissionState.AUTHORIZED
    assert research.state is PermissionState.AUTHORIZED


def test_gate_repository_is_append_only_and_workspace_scoped(
    gate_repository: SqlAlchemyGateRepository,
    gate_service: LiveResearchGateService,
    clock: MutableClock,
) -> None:
    first = _preflight(gate_service, clock, all_preflight_evidence())
    assert gate_repository.get(WORKSPACE_ID, first.record_kind, first.id) == first
    assert gate_repository.get(uuid4(), first.record_kind, first.id) is None
    with pytest.raises(IntegrityError):
        gate_repository.save(first)


def test_no_delivery_ai_person_contact_or_live_transport_dependency_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    source_files = tuple((root / "packages" / "shadow-core").rglob("*.py")) + tuple(
        (root / "packages" / "shadow-local").rglob("*.py")
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    prohibited_imports = (
        "opintel_contact",
        "opintel_activation",
        "opintel_qualification",
        "requests",
        "httpx",
        "boto3",
        "sendgrid",
        "twilio",
    )
    assert not any(
        f"import {name}" in text or f"from {name}" in text for name in prohibited_imports
    )
    assert "class StdlibPinnedTransport" not in text
    assert "authorize_send" not in text
    assert "send_message" not in text
    assert "class PersonContactIndex" not in text
    assert "def search_person" not in text
    assert "M6.7C" in inspect.getdoc(LiveResearchGateService)


def test_m67a_runtime_source_remains_behaviorally_untouched() -> None:
    root = Path(__file__).resolve().parents[1]
    changed_gate_files = {
        path.name
        for path in (root / "packages" / "shadow-core" / "src" / "opintel_shadow").glob("gate_*.py")
    }
    assert changed_gate_files == {"gate_application.py", "gate_domain.py", "gate_ports.py"}
    m67a_application = (
        root / "packages" / "shadow-core" / "src" / "opintel_shadow" / "application.py"
    )
    m67a_persistence = (
        root / "packages" / "shadow-local" / "src" / "opintel_shadow_local" / "persistence.py"
    )
    assert "M6.7A" in m67a_application.read_text(encoding="utf-8")
    assert "M6.7A" in m67a_persistence.read_text(encoding="utf-8")
