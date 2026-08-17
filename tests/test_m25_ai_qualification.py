from __future__ import annotations

import socket
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from conftest import FakeClock
from opintel_m0.domain import Principal, Role
from opintel_m0_local import UuidFactory
from opintel_opportunity_local import SqlAlchemyOpportunityRepository
from opintel_qualification import (
    CASES,
    CORPUS_VERSION,
    POLICY_VERSION,
    TASK_CONTRACTS,
    QualificationApplicationService,
    QualificationRouter,
)
from opintel_qualification.corpus import cases_for
from opintel_qualification.domain import (
    ACTIVE_TASKS,
    BudgetPolicy,
    DataClassification,
    DeploymentRecord,
    GateFailure,
    IntelligenceRequest,
    LiveEvaluationPolicy,
    ProviderKind,
    QualificationAuthorizationError,
    QualificationDecision,
    QualificationKey,
    QualificationStatus,
    RoutingStage,
    TaskClass,
)
from opintel_qualification_local import (
    DeterministicBudgetGuard,
    DeterministicMockProvider,
    DeterministicUsefulnessHook,
    DisabledLiveEvaluationGate,
    InMemoryProviderCatalog,
    MockBehavior,
    SqlAlchemyQualificationRepository,
)
from sqlalchemy import inspect, text


def principal(workspace_id: UUID) -> Principal:
    return Principal("m2.5-operator", workspace_id, frozenset({Role.ADMIN, Role.OPERATOR}))


def live_policy(*, enabled: bool = False) -> LiveEvaluationPolicy:
    return LiveEvaluationPolicy(
        "live-policy@1",
        enabled,
        enabled,
        (),
        tuple(ACTIVE_TASKS),
        (DataClassification.PUBLIC,),
        "approved-test-policy" if enabled else None,
    )


def budget(
    *, invocations: int = 100, tokens: int = 1_000_000, cost: int = 1_000_000
) -> DeterministicBudgetGuard:
    return DeterministicBudgetGuard(BudgetPolicy("test-budget@1", invocations, tokens, cost))


def deployment(
    workspace_id: UUID,
    task: TaskClass,
    *,
    provider_key: str = "mock-provider",
    model_key: str = "mock-model",
    model_version: str = "model@1",
    deployment_version: str = "deployment@1",
    config_hash: str = "a" * 64,
    kind: ProviderKind = ProviderKind.MOCK,
) -> DeploymentRecord:
    return DeploymentRecord(
        uuid4(),
        workspace_id,
        provider_key,
        model_key,
        model_version,
        deployment_version,
        config_hash,
        kind,
        (task,),
        datetime(2026, 8, 17, tzinfo=UTC),
    )


def key_for(
    value: DeploymentRecord,
    task: TaskClass,
    *,
    policy_version: str = POLICY_VERSION,
    corpus_version: str = CORPUS_VERSION,
) -> QualificationKey:
    contract = TASK_CONTRACTS[task]
    return QualificationKey(
        value.id,
        value.deployment_version,
        value.config_hash,
        task,
        contract.task_version,
        contract.output_schema_version,
        policy_version,
        corpus_version,
        DataClassification.PUBLIC,
    )


@pytest.fixture
def qualification_repository(settings) -> SqlAlchemyQualificationRepository:
    value = SqlAlchemyQualificationRepository(settings.database_url)
    value.initialize()
    return value


@pytest.fixture
def qualification_service(
    qualification_repository: SqlAlchemyQualificationRepository, clock: FakeClock
) -> QualificationApplicationService:
    return QualificationApplicationService(
        qualification_repository,
        clock,
        UuidFactory(),
        DisabledLiveEvaluationGate(),
        DeterministicUsefulnessHook(),
    )


def qualify(
    service: QualificationApplicationService,
    repository: SqlAlchemyQualificationRepository,
    workspace_id: UUID,
    behavior: MockBehavior,
    task: TaskClass,
    selected_cases=None,
    *,
    repetitions: int = 1,
) -> tuple[DeploymentRecord, QualificationKey, QualificationDecision, DeterministicMockProvider]:
    value = deployment(workspace_id, task, model_key=f"mock-{behavior.value}-{uuid4()}")
    key = key_for(value, task)
    actor = principal(workspace_id)
    service.register_deployment(actor, value, key)
    provider = DeterministicMockProvider(value.id, behavior)
    decision = service.evaluate(
        actor,
        key,
        tuple(selected_cases or cases_for(task)),
        provider,
        budget(),
        live_policy(),
        repetitions=repetitions,
    )
    assert repository.latest_decision(workspace_id, key) == decision
    return value, key, decision, provider


def test_taxonomy_exposes_future_tasks_without_activating_m3_contracts() -> None:
    assert set(TASK_CONTRACTS) == set(ACTIVE_TASKS)
    assert TaskClass.STRUCTURED_AUDIT_COMPOSITION not in TASK_CONTRACTS
    assert TaskClass.VISUAL_WEBSITE_ANALYSIS not in TASK_CONTRACTS
    assert TaskClass.LOW_LATENCY_DEMO_CONVERSATION not in TASK_CONTRACTS
    assert all(not item.authoritative for item in TASK_CONTRACTS.values())


def test_corpus_has_all_partitions_families_and_provenance() -> None:
    families = {item.family for item in CASES}
    assert {
        "strong_opportunity",
        "weak_opportunity",
        "contradicted_opportunity",
        "insufficient_evidence",
        "scoped_absence",
        "misleading_entity_evidence",
        "prompt_injection",
        "unknown_financial_inputs",
        "no_opportunity_supported",
    }.issubset(families)
    assert {item.partition.value for item in CASES} == {
        "development",
        "calibration",
        "hidden_qualification",
        "regression",
        "rotating_challenge",
    }
    assert all(len(item.manifest_hash) == 64 for item in CASES)
    assert all(evidence.untrusted for item in CASES for evidence in item.evidence)


@pytest.mark.parametrize(
    ("behavior", "family", "failure"),
    [
        (
            MockBehavior.FABRICATED_INTERNAL_FACT,
            "strong_opportunity",
            GateFailure.CRITICAL_FABRICATION,
        ),
        (MockBehavior.INVENTED_EVIDENCE_ID, "strong_opportunity", GateFailure.INVENTED_CITATION),
        (
            MockBehavior.OMITTED_CONTRADICTION,
            "contradicted_opportunity",
            GateFailure.HARD_CONTRADICTION_DOWNGRADED,
        ),
        (
            MockBehavior.UNKNOWN_TO_KNOWN,
            "unknown_financial_inputs",
            GateFailure.FALSE_UNKNOWN_RESOLUTION,
        ),
        (
            MockBehavior.PROMPT_INJECTION_COMPLIANCE,
            "prompt_injection",
            GateFailure.PROMPT_INJECTION_COMPLIANCE,
        ),
        (MockBehavior.MALFORMED_SCHEMA, "strong_opportunity", GateFailure.SCHEMA_INVALID),
    ],
)
def test_critical_mock_failures_disqualify_without_aggregate_masking(
    behavior: MockBehavior,
    family: str,
    failure: GateFailure,
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    case = next(item for item in CASES if item.family == family)
    _, _, decision, provider = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        behavior,
        case.task_class,
        (case,),
    )
    assert decision.status == QualificationStatus.DISQUALIFIED
    assert decision.evaluation_run_id is not None
    results = qualification_repository.list_case_results(
        settings.workspace_id, decision.evaluation_run_id
    )
    assert failure in results[0].gate_failures
    if results[0].metrics.schema_valid:
        assert results[0].metrics.reasoning_usefulness == "fixture_hook_recorded"
    if behavior == MockBehavior.MALFORMED_SCHEMA:
        assert provider.invocations == 2


@pytest.mark.parametrize("task", tuple(ACTIVE_TASKS))
def test_valid_mock_qualifies_for_each_active_task_only(
    task: TaskClass,
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    _, _, decision, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        task,
    )
    assert decision.status == QualificationStatus.QUALIFIED


def test_transient_retry_can_qualify_but_timeout_and_inconsistency_are_conditional(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    task = TaskClass.EVIDENCE_INTERPRETATION
    _, _, transient, transient_provider = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.TRANSIENT_FAILURE,
        task,
    )
    assert transient.status == QualificationStatus.QUALIFIED
    assert transient_provider.invocations >= 2
    _, _, timeout, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.TIMEOUT,
        task,
    )
    assert timeout.status == QualificationStatus.CONDITIONAL
    _, _, inconsistent, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.INCONSISTENT_REASONING,
        task,
        repetitions=2,
    )
    assert inconsistent.status == QualificationStatus.CONDITIONAL


def test_budget_limits_fail_closed_without_calling_provider(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    case = next(item for item in CASES if item.family == "strong_opportunity")
    value = deployment(settings.workspace_id, case.task_class, model_key="budget-model")
    key = key_for(value, case.task_class)
    actor = principal(settings.workspace_id)
    qualification_service.register_deployment(actor, value, key)
    provider = DeterministicMockProvider(value.id, MockBehavior.VALID)
    decision = qualification_service.evaluate(
        actor,
        key,
        (case,),
        provider,
        budget(tokens=999),
        live_policy(),
        repetitions=1,
    )
    assert decision.status == QualificationStatus.CONDITIONAL
    assert provider.invocations == 0
    assert decision.evaluation_run_id is not None
    result = qualification_repository.list_case_results(
        settings.workspace_id, decision.evaluation_run_id
    )[0]
    assert GateFailure.BUDGET_EXCEEDED in result.gate_failures

    cost_value = deployment(settings.workspace_id, case.task_class, model_key="cost-budget-model")
    cost_key = key_for(cost_value, case.task_class)
    qualification_service.register_deployment(actor, cost_value, cost_key)
    cost_provider = DeterministicMockProvider(cost_value.id, MockBehavior.VALID)
    cost_decision = qualification_service.evaluate(
        actor,
        cost_key,
        (case,),
        cost_provider,
        budget(cost=9),
        live_policy(),
        repetitions=1,
    )
    assert cost_decision.status == QualificationStatus.CONDITIONAL
    assert cost_provider.invocations == 0

    token_value = deployment(settings.workspace_id, case.task_class, model_key="token-limit-model")
    token_key = key_for(token_value, case.task_class)
    qualification_service.register_deployment(actor, token_value, token_key)
    token_provider = DeterministicMockProvider(token_value.id, MockBehavior.TOKEN_LIMIT)
    token_decision = qualification_service.evaluate(
        actor,
        token_key,
        (case,),
        token_provider,
        budget(),
        live_policy(),
        repetitions=1,
    )
    assert token_decision.status == QualificationStatus.CONDITIONAL
    assert token_decision.evaluation_run_id is not None
    token_entries = qualification_repository.list_invocations(
        settings.workspace_id, token_decision.evaluation_run_id
    )
    assert token_entries[0].safe_failure_code == "token_limit"


def _routing_request(workspace_id: UUID, case, stage: RoutingStage) -> IntelligenceRequest:
    contract = TASK_CONTRACTS[case.task_class]
    return IntelligenceRequest(
        uuid4(),
        workspace_id,
        uuid4(),
        case.id,
        contract,
        stage,
        case.evidence,
        tuple(item.id for item in case.evidence),
        POLICY_VERSION,
        CORPUS_VERSION,
        DataClassification.PUBLIC,
        "b" * 64,
        "c" * 64,
        100,
        10,
        uuid4(),
    )


def test_unqualified_cannot_route_and_provider_failure_uses_only_qualified_fallback(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    clock: FakeClock,
    settings,
) -> None:
    case = next(item for item in CASES if item.family == "strong_opportunity")
    actor = principal(settings.workspace_id)
    unqualified = deployment(settings.workspace_id, case.task_class, model_key="unqualified")
    qualification_service.register_deployment(
        actor, unqualified, key_for(unqualified, case.task_class)
    )
    unused = DeterministicMockProvider(unqualified.id, MockBehavior.VALID)
    router = QualificationRouter(
        qualification_repository,
        InMemoryProviderCatalog((unused,)),
        budget(),
        DisabledLiveEvaluationGate(),
        clock,
        UuidFactory(),
    )
    blocked = router.route(
        actor, _routing_request(settings.workspace_id, case, RoutingStage.ADVISORY), live_policy()
    )
    assert blocked.deterministic_m2_fallback is True
    assert unused.invocations == 0

    first, _, first_decision, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        case.task_class,
        (case,),
    )
    second, _, second_decision, second_provider = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        case.task_class,
        (case,),
    )
    assert first_decision.status == second_decision.status == QualificationStatus.QUALIFIED
    first_now_fails = DeterministicMockProvider(first.id, MockBehavior.TIMEOUT)
    router = QualificationRouter(
        qualification_repository,
        InMemoryProviderCatalog((unused, first_now_fails, second_provider)),
        budget(),
        DisabledLiveEvaluationGate(),
        clock,
        UuidFactory(),
    )
    routed = router.route(
        actor, _routing_request(settings.workspace_id, case, RoutingStage.ADVISORY), live_policy()
    )
    assert routed.deployment_id == second.id
    assert routed.deterministic_m2_fallback is False
    assert first_now_fails.invocations == 1


def test_routing_stages_remain_non_authoritative_and_retirement_removes_route(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    clock: FakeClock,
    settings,
) -> None:
    case = next(item for item in CASES if item.family == "strong_opportunity")
    value, key, decision, provider = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        case.task_class,
        (case,),
    )
    assert decision.status == QualificationStatus.QUALIFIED
    router = QualificationRouter(
        qualification_repository,
        InMemoryProviderCatalog((provider,)),
        budget(),
        DisabledLiveEvaluationGate(),
        clock,
        UuidFactory(),
    )
    actor = principal(settings.workspace_id)
    for stage in (RoutingStage.EVALUATION_ONLY, RoutingStage.SHADOW):
        result = router.route(
            actor, _routing_request(settings.workspace_id, case, stage), live_policy()
        )
        assert result.deployment_id == value.id
        assert result.deterministic_m2_fallback is True
    advisory = router.route(
        actor,
        _routing_request(settings.workspace_id, case, RoutingStage.ADVISORY),
        live_policy(),
    )
    assert advisory.deployment_id == value.id
    assert advisory.deterministic_m2_fallback is False

    retired = qualification_service.retire(actor, key)
    assert retired.status == QualificationStatus.RETIRED
    after = router.route(
        actor,
        _routing_request(settings.workspace_id, case, RoutingStage.ADVISORY),
        live_policy(),
    )
    assert after.deterministic_m2_fallback is True
    assert after.deployment_id is None


def test_qualification_is_version_specific_and_drift_suspends_active_decisions(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    task = TaskClass.EVIDENCE_INTERPRETATION
    old, _old_key, decision, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        task,
    )
    assert decision.status == QualificationStatus.QUALIFIED
    policy_drift = key_for(old, task, policy_version="m2.semantic_safety@2")
    suspended = qualification_service.suspend_drifted(
        principal(settings.workspace_id), policy_drift
    )
    assert suspended and suspended[0].status == QualificationStatus.SUSPENDED
    old_requalified = qualification_service.evaluate(
        principal(settings.workspace_id),
        _old_key,
        cases_for(task),
        DeterministicMockProvider(old.id, MockBehavior.VALID),
        budget(),
        live_policy(),
        repetitions=1,
    )
    assert old_requalified.status == QualificationStatus.QUALIFIED
    qualification_service.suspend_drifted(principal(settings.workspace_id), policy_drift)
    qualification_service.register_key(principal(settings.workspace_id), policy_drift)
    requalified = qualification_service.evaluate(
        principal(settings.workspace_id),
        policy_drift,
        cases_for(task),
        DeterministicMockProvider(old.id, MockBehavior.VALID),
        budget(),
        live_policy(),
        repetitions=1,
    )
    assert requalified.status == QualificationStatus.QUALIFIED

    corpus_drift = key_for(
        old,
        task,
        policy_version="m2.semantic_safety@2",
        corpus_version="commercial_hvac.ai_qualification.corpus@2",
    )
    qualification_service.suspend_drifted(principal(settings.workspace_id), corpus_drift)
    qualification_service.register_key(principal(settings.workspace_id), corpus_drift)
    # Corpus-v2 fixtures are represented by the same controlled cases with their immutable
    # version changed for this drift/requalification contract test.
    corpus_cases = tuple(
        replace(item, corpus_version=corpus_drift.corpus_version) for item in cases_for(task)
    )
    corpus_requalified = qualification_service.evaluate(
        principal(settings.workspace_id),
        corpus_drift,
        corpus_cases,
        DeterministicMockProvider(old.id, MockBehavior.VALID),
        budget(),
        live_policy(),
        repetitions=1,
    )
    assert corpus_requalified.status == QualificationStatus.QUALIFIED

    replacement = deployment(
        settings.workspace_id,
        task,
        model_key=old.model_key,
        model_version="model@2",
        deployment_version="deployment@2",
        config_hash="d" * 64,
    )
    qualification_service.register_deployment(
        principal(settings.workspace_id), replacement, key_for(replacement, task)
    )
    latest_drifted = qualification_repository.latest_decision(settings.workspace_id, corpus_drift)
    assert latest_drifted is not None
    assert latest_drifted.status == QualificationStatus.SUSPENDED


def test_ledger_provenance_workspace_isolation_and_zero_network(
    monkeypatch: pytest.MonkeyPatch,
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    def deny_network(*args, **kwargs):
        del args, kwargs
        raise AssertionError("normal CI attempted network access")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    value, key, decision, _ = qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        TaskClass.EVIDENCE_INTERPRETATION,
    )
    assert decision.evaluation_run_id is not None
    entries = qualification_repository.list_invocations(
        settings.workspace_id, decision.evaluation_run_id
    )
    assert entries and all(item.workspace_id == settings.workspace_id for item in entries)
    assert all(item.deployment_id == value.id for item in entries)
    assert all(len(item.prompt_hash) == len(item.config_hash) == 64 for item in entries)
    serialized = str(tuple(asdict(item) for item in entries))
    assert "Commercial HVAC" not in serialized
    other = UUID("00000000-0000-4000-8000-000000000099")
    assert qualification_repository.get_deployment(other, value.id) is None
    assert qualification_repository.latest_decision(other, key) is None
    assert qualification_repository.list_invocations(other, decision.evaluation_run_id) == ()

    viewer = Principal("viewer", settings.workspace_id, frozenset({Role.VIEWER}))
    blocked = deployment(settings.workspace_id, TaskClass.EVIDENCE_INTERPRETATION)
    with pytest.raises(QualificationAuthorizationError):
        qualification_service.register_deployment(
            viewer, blocked, key_for(blocked, TaskClass.EVIDENCE_INTERPRETATION)
        )


def test_evaluation_cannot_mutate_canonical_m2_tables(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    opportunity_repository: SqlAlchemyOpportunityRepository,
    settings,
) -> None:
    inspector = inspect(opportunity_repository.engine)
    opportunity_tables = tuple(
        name for name in inspector.get_table_names() if name.startswith("opportunity_")
    )

    def counts() -> dict[str, int]:
        with opportunity_repository.engine.connect() as connection:
            return {
                table: int(connection.scalar(text(f'SELECT COUNT(*) FROM "{table}"')) or 0)
                for table in opportunity_tables
            }

    before = counts()
    qualify(
        qualification_service,
        qualification_repository,
        settings.workspace_id,
        MockBehavior.VALID,
        TaskClass.OPPORTUNITY_REASONING,
    )
    assert counts() == before
    qualification_tables = inspect(qualification_repository.engine).get_table_names()
    assert qualification_tables
    assert all(
        name.startswith("qualification_")
        for name in qualification_tables
        if "qualification" in name
    )


def test_live_evaluation_boundary_is_disabled_and_fail_closed(
    qualification_service: QualificationApplicationService,
    qualification_repository: SqlAlchemyQualificationRepository,
    settings,
) -> None:
    case = next(item for item in CASES if item.family == "strong_opportunity")
    value = deployment(
        settings.workspace_id,
        case.task_class,
        model_key="future-live-model",
        kind=ProviderKind.LIVE,
    )
    actor = principal(settings.workspace_id)
    key = key_for(value, case.task_class)
    qualification_service.register_deployment(actor, value, key)
    provider = DeterministicMockProvider(value.id, MockBehavior.VALID)
    with pytest.raises(Exception, match="live evaluation policy denied"):
        qualification_service.evaluate(
            actor,
            key,
            (case,),
            provider,
            budget(),
            live_policy(enabled=False),
            repetitions=1,
        )
    assert provider.invocations == 0
