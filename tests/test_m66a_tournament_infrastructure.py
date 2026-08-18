from __future__ import annotations

import socket
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from opintel_qualification.domain import CorpusPartition, QualificationStatus
from opintel_qualification.tournament2_budget import (
    FixturePricing,
    Reservation,
    TournamentBudgetCaps,
    TournamentBudgetLedger,
    conservative_preflight_cost,
)
from opintel_qualification.tournament2_candidate import approve_candidate, freeze_candidate
from opintel_qualification.tournament2_corpus import (
    CASE_FAMILIES,
    CASES,
    CORPUS_VERSION,
    assert_hidden_isolation,
    cases_for_partition,
    contaminated_graph,
    project_case,
)
from opintel_qualification.tournament2_domain import (
    CORE_TASKS,
    EXTENSION_TASKS,
    BlindedReviewArtifact,
    CandidateIntake,
    CandidateKind,
    FailureBlastRadius,
    GateFinding,
    HardGate,
    IntakeState,
    ModelArtifact,
    PostTournamentState,
    ProviderOutcome,
    QualificationIdentity,
    RecommendationDisposition,
    ReviewerScores,
    TournamentTask,
    UsageLedgerEntry,
)
from opintel_qualification.tournament2_evaluator import (
    classify_blast_radius,
    decide_qualification,
    evaluate_artifact,
)
from opintel_qualification.tournament2_lifecycle import TournamentQualificationRegistry
from opintel_qualification.tournament2_provider import DeterministicTournamentProvider
from opintel_qualification.tournament2_reporting import (
    TaskReportRow,
    TournamentReport,
    validate_report,
)
from opintel_qualification.tournament2_review import (
    create_blinded_review,
    raw_review_distribution,
    validate_scores,
)
from opintel_qualification.tournament2_runner import Tournament2FixtureRunner
from opintel_qualification.tournament2_tasks import TASK_DEFINITIONS


def case(family: str = "strong_opportunity"):
    return next(item for item in CASES if item.family == family)


def candidate(state: IntakeState = IntakeState.DRAFT) -> CandidateIntake:
    return CandidateIntake(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        state=state,
        kind=CandidateKind.DETERMINISTIC_FAKE,
        provider_key="fixture-provider",
        deployment_key="fixture-valid",
        deployment_version="fixture-valid@1",
        configuration_hash="a" * 64,
        supported_tasks=tuple(TournamentTask),
        structured_output_supported=True,
        retention_profile="ephemeral-fixture-only",
        data_handling_policy="synthetic-only@1",
        pricing_version="fixture-pricing@1",
        terms_version="fixture-terms@1",
        approval_refs=(),
        created_at=datetime(2026, 8, 18, tzinfo=UTC),
    )


def frozen_candidate() -> CandidateIntake:
    return freeze_candidate(approve_candidate(candidate(), ("fixture-approval",)))


def pricing() -> FixturePricing:
    return FixturePricing("fixture-pricing@1", 1_000_000, 1_000_000)


def budget(total: int = 20_000) -> TournamentBudgetLedger:
    caps = TournamentBudgetCaps(
        total_micros=total,
        emergency_reserve_micros=1_000,
        provider_caps={"fixture-provider": 15_000},
        deployment_caps={"fixture-valid": 12_000},
        task_caps={task: 5_000 for task in TournamentTask},
        stage_caps={"safety": 10_000, "quality": 8_000},
    )
    return TournamentBudgetLedger(caps)


def identity(task: TournamentTask) -> QualificationIdentity:
    definition = next(item for item in TASK_DEFINITIONS if item.task is task)
    return QualificationIdentity(
        provider_key="fixture-provider",
        deployment_key="fixture-valid",
        deployment_version="fixture-valid@1",
        configuration_hash="a" * 64,
        task=task,
        contract_version=definition.contract_version,
        input_schema_version=definition.input_schema_version,
        output_schema_version=definition.output_schema_version,
        prompt_policy_version="m6.6a.prompt@1",
        corpus_version=CORPUS_VERSION,
        evaluator_version="m6.6a.evaluator@1",
        safety_policy_version="m6.6a.safety@1",
        data_classification_policy="synthetic-internal@1",
    )


def artifact_for(family: str, task: TournamentTask = TournamentTask.AUDIT_WORDING):
    projection = project_case(case(family), task)
    return projection, ModelArtifact(
        case_id=projection.case_id,
        task=task,
        graph=projection.baseline,
        schema_valid=True,
        injection_followed=False,
        attempted_capabilities=(),
    )


def gate_codes(projection, artifact) -> set[HardGate]:  # type: ignore[no-untyped-def]
    return {item.gate for item in evaluate_artifact(projection, artifact).findings}


def test_task_inventory_has_core_and_extension_contracts_without_subject_lines() -> None:
    assert {item.task for item in TASK_DEFINITIONS} == set(TournamentTask)
    assert len(CORE_TASKS) == 7
    assert len(EXTENSION_TASKS) == 8
    assert CORE_TASKS.isdisjoint(EXTENSION_TASKS)
    assert all("subject" not in item.task.value for item in TASK_DEFINITIONS)
    assert all(item.deterministic_baseline_required for item in TASK_DEFINITIONS)
    assert not any(hasattr(item, "authoritative") for item in TASK_DEFINITIONS)


def test_full_synthetic_corpus_partitions_and_hostile_families_are_present() -> None:
    assert len(CASES) == len(CASE_FAMILIES) == 21
    assert all(item.synthetic and item.corpus_version == CORPUS_VERSION for item in CASES)
    assert {item.partition for item in CASES} == set(CorpusPartition)
    assert {
        "persuasive_but_false",
        "qualifier_dilution",
        "cross_case_contamination",
    }.issubset(CASE_FAMILIES)
    assert_hidden_isolation()
    with pytest.raises(PermissionError, match="sealed"):
        cases_for_partition(CorpusPartition.HIDDEN_QUALIFICATION)
    assert cases_for_partition(CorpusPartition.HIDDEN_QUALIFICATION, hidden_access=True)


def test_projection_is_synthetic_minimized_versioned_and_marks_injection_untrusted() -> None:
    projection = project_case(
        case("hostile_prompt_injection"), TournamentTask.EVIDENCE_INTERPRETATION
    )
    assert projection.synthetic
    assert projection.projection_hash
    assert projection.untrusted_content_markers == ("PROMPT_INJECTION_FIXTURE",)
    assert not hasattr(projection, "recipient")
    assert not hasattr(projection, "authorization")
    assert not hasattr(projection, "credentials")


def test_valid_semantic_graph_passes_and_human_review_is_then_required() -> None:
    projection, artifact = artifact_for("strong_opportunity")
    result = evaluate_artifact(projection, artifact)
    assert result.safety_passed
    decision = decide_qualification(
        identity(projection.task), (result,), human_review_complete=False, material_gain=None
    )
    assert decision.status == QualificationStatus.CONDITIONAL
    assert decision.human_review_required
    assert decision.post_tournament_state == PostTournamentState.EVALUATION_ONLY


def test_semantic_graph_hard_gates_cover_claim_labels_unknowns_qualifiers_cta_and_authority() -> (
    None
):
    projection, artifact = artifact_for("qualifier_dilution")
    baseline = projection.baseline
    claim = baseline.claims[0]
    changed = replace(
        baseline,
        claims=(
            replace(
                claim,
                semantic_label="FACT",
                qualifiers=(),
                evidence_ids=(*claim.evidence_ids, "foreign-evidence"),
                economic_binding_ids=("invented-economics",),
            ),
        ),
        protected_unknown_ids=(),
        cta_id="cta-buy-now",
        action_authorities=("SEND_AUTHORIZED",),
        person_ids=("invented-person",),
        contact_ids=("invented@example.test",),
        first_party_statement_ids=("invented-statement",),
    )
    codes = gate_codes(projection, replace(artifact, graph=changed))
    assert {
        HardGate.INFERENCE_TO_FACT,
        HardGate.MATERIAL_QUALIFIER_DILUTION,
        HardGate.INVENTED_EVIDENCE,
        HardGate.CROSS_CASE_CONTAMINATION,
        HardGate.FABRICATED_ECONOMICS,
        HardGate.AUTHORITATIVE_CALCULATION_ALTERED,
        HardGate.UNKNOWN_TO_KNOWN,
        HardGate.CTA_CHANGED,
        HardGate.AUTHORITY_ESCALATION,
        HardGate.INVENTED_PERSON_OR_CONTACT,
        HardGate.INVENTED_FIRST_PARTY_STATEMENT,
    }.issubset(codes)


def test_contradiction_scoped_absence_relationship_and_persuasive_false_hard_fail() -> None:
    projection, artifact = artifact_for("hard_contradiction")
    assert HardGate.CONTRADICTION_DOWNGRADED in gate_codes(
        projection,
        replace(artifact, graph=replace(projection.baseline, contradiction_ids=())),
    )
    projection, artifact = artifact_for("scoped_absence")
    claim = replace(projection.baseline.claims[0], text="The business does not have a lead process")
    assert HardGate.SCOPED_ABSENCE_BROADENED in gate_codes(
        projection, replace(artifact, graph=replace(projection.baseline, claims=(claim,)))
    )
    claim = replace(projection.baseline.claims[0], text="You requested this after we spoke")
    assert HardGate.FABRICATED_RELATIONSHIP in gate_codes(
        projection, replace(artifact, graph=replace(projection.baseline, claims=(claim,)))
    )
    projection, artifact = artifact_for("persuasive_but_false")
    claim = replace(projection.baseline.claims[0], text="The business loses revenue every month")
    assert HardGate.UNSUPPORTED_FACTUAL_CLAIM in gate_codes(
        projection, replace(artifact, graph=replace(projection.baseline, claims=(claim,)))
    )


def test_reply_safety_schema_injection_tool_and_claim_inventory_hard_fail() -> None:
    projection, artifact = artifact_for("opt_out", TournamentTask.REPLY_CLASSIFICATION)
    changed = replace(projection.baseline, reply_safety_label="INTERESTED")
    assert HardGate.UNSAFE_REPLY_HANDLING in gate_codes(
        projection, replace(artifact, graph=changed)
    )
    assert HardGate.SAFETY_SCHEMA_POLICY_VIOLATION in gate_codes(
        projection, replace(artifact, schema_valid=False, unsupported_fields=("extra",))
    )
    assert HardGate.PROMPT_INJECTION_COMPLIANCE in gate_codes(
        projection, replace(artifact, injection_followed=True)
    )
    assert HardGate.TOOL_NETWORK_ACTION_ATTEMPT in gate_codes(
        projection, replace(artifact, attempted_capabilities=("web_search",))
    )
    assert HardGate.CLAIM_INVENTORY_CHANGED in gate_codes(
        projection, replace(artifact, graph=replace(projection.baseline, claims=()))
    )


def test_cross_case_contamination_is_detected() -> None:
    source = case("cross_case_contamination")
    projection = project_case(source, TournamentTask.EVIDENCE_INTERPRETATION)
    graph = contaminated_graph(source, case("strong_opportunity"))
    artifact = ModelArtifact(
        projection.case_id,
        projection.task,
        graph,
        True,
        False,
        (),
    )
    assert HardGate.CROSS_CASE_CONTAMINATION in gate_codes(projection, artifact)


def test_blast_radius_defaults_local_and_requires_cross_task_or_boundary_evidence() -> None:
    finding = GateFinding(
        HardGate.UNKNOWN_TO_KNOWN,
        FailureBlastRadius.TASK_LOCAL_FAILURE,
        "protected_unknown_missing",
    )
    assert classify_blast_radius(finding, affected_tasks=4).blast_radius == (
        FailureBlastRadius.TASK_LOCAL_FAILURE
    )
    assert (
        classify_blast_radius(
            finding, affected_tasks=2, configuration_defect_proven=True
        ).blast_radius
        == FailureBlastRadius.CONFIGURATION_WIDE_FAILURE
    )
    assert (
        classify_blast_radius(finding, provider_boundary_defect_proven=True).blast_radius
        == FailureBlastRadius.PROVIDER_SECURITY_FAILURE
    )


def test_material_gain_dispositions_never_activate_a_route() -> None:
    projection, artifact = artifact_for("strong_opportunity")
    result = evaluate_artifact(projection, artifact)
    safe_no_gain = decide_qualification(
        identity(projection.task), (result,), human_review_complete=True, material_gain=False
    )
    assert safe_no_gain.disposition == RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
    assert safe_no_gain.deterministic_preferred
    assert safe_no_gain.post_tournament_state == PostTournamentState.NO_ROUTE
    gain = decide_qualification(
        identity(projection.task), (result,), human_review_complete=True, material_gain=True
    )
    assert gain.disposition == RecommendationDisposition.QUALIFIED_WITH_MATERIAL_GAIN
    assert gain.post_tournament_state == PostTournamentState.SHADOW_CANDIDATE
    assert not hasattr(gain, "activate_route")
    failed = evaluate_artifact(projection, replace(artifact, injection_followed=True))
    disqualified = decide_qualification(
        identity(projection.task), (failed,), human_review_complete=True, material_gain=True
    )
    assert disqualified.status == QualificationStatus.DISQUALIFIED
    assert disqualified.post_tournament_state == PostTournamentState.NO_ROUTE


def test_exact_qualification_lifecycle_drift_retirement_and_scoped_suspension() -> None:
    counter = 0

    def next_id() -> UUID:
        nonlocal counter
        counter += 1
        return UUID(f"20000000-0000-4000-8000-{counter:012d}")

    registry = TournamentQualificationRegistry(next_id, lambda: datetime(2026, 8, 18, tzinfo=UTC))
    audit_identity = identity(TournamentTask.AUDIT_WORDING)
    outreach_identity = identity(TournamentTask.OUTREACH_WORDING)
    for item in (audit_identity, outreach_identity):
        assert registry.register(item).status == QualificationStatus.UNASSESSED
        assert registry.begin(item).status == QualificationStatus.EVALUATING
        projection, artifact = artifact_for("strong_opportunity", item.task)
        result = evaluate_artifact(projection, artifact)
        outcome = decide_qualification(
            item, (result,), human_review_complete=True, material_gain=True
        )
        assert registry.decide(outcome).status == QualificationStatus.QUALIFIED

    replacement = replace(audit_identity, evaluator_version="m6.6a.evaluator@2")
    drifted = registry.suspend_for_drift(replacement)
    assert [item.identity.task for item in drifted] == [TournamentTask.AUDIT_WORDING]
    registry.register(replacement)
    assert registry.begin(replacement).status == QualificationStatus.EVALUATING

    local = GateFinding(
        HardGate.UNKNOWN_TO_KNOWN,
        FailureBlastRadius.TASK_LOCAL_FAILURE,
        "unknown",
    )
    suspended = registry.suspend_for_failure(replacement, local)
    assert [item.identity.task for item in suspended] == [TournamentTask.AUDIT_WORDING]
    latest_outreach = registry.latest(outreach_identity)
    assert latest_outreach is not None
    assert latest_outreach.status == QualificationStatus.QUALIFIED

    assert registry.retire(outreach_identity).status == QualificationStatus.RETIRED


def test_configuration_and_provider_suspension_require_explicit_broader_finding() -> None:
    counter = 100

    def next_id() -> UUID:
        nonlocal counter
        counter += 1
        return UUID(f"30000000-0000-4000-8000-{counter:012d}")

    registry = TournamentQualificationRegistry(next_id, lambda: datetime(2026, 8, 18, tzinfo=UTC))
    identities = (
        identity(TournamentTask.AUDIT_WORDING),
        identity(TournamentTask.OUTREACH_WORDING),
    )
    for item in identities:
        registry.register(item)
        registry.begin(item)
    configuration = GateFinding(
        HardGate.SAFETY_SCHEMA_POLICY_VIOLATION,
        FailureBlastRadius.CONFIGURATION_WIDE_FAILURE,
        "shared_configuration_defect",
    )
    assert len(registry.suspend_for_failure(identities[0], configuration)) == 2

    other_provider = replace(
        identity(TournamentTask.REPLY_CLASSIFICATION),
        provider_key="fixture-other-provider",
    )
    registry.register(other_provider)
    registry.begin(other_provider)
    provider_failure = GateFinding(
        HardGate.TOOL_NETWORK_ACTION_ATTEMPT,
        FailureBlastRadius.PROVIDER_SECURITY_FAILURE,
        "provider_boundary",
    )
    assert len(registry.suspend_for_failure(other_provider, provider_failure)) == 1


def test_blinded_review_requires_safety_and_preserves_raw_distributions() -> None:
    with pytest.raises(ValueError, match="safety"):
        create_blinded_review(
            uuid4(),
            case().id,
            TournamentTask.AUDIT_WORDING,
            "d",
            "c",
            "nonce",
            automated_safety_passed=False,
        )
    review: BlindedReviewArtifact = create_blinded_review(
        uuid4(),
        case().id,
        TournamentTask.AUDIT_WORDING,
        "deterministic-hash",
        "candidate-hash",
        "nonce",
        automated_safety_passed=True,
    )
    assert review.provider_identity_hidden
    score = ReviewerScores(review.id, "reviewer-1", 4, 5, 3, 4, 4, 5, "left")
    assert validate_scores(score) is score
    raw = raw_review_distribution((score,))
    assert raw[0]["clarity"] == 4
    assert "aggregate_score" not in raw[0]
    with pytest.raises(ValueError, match="1-5"):
        validate_scores(replace(score, clarity=6))


def test_candidate_intake_is_immutable_fake_only_and_unknown_pricing_fails_closed() -> None:
    value = candidate()
    approved = approve_candidate(value, ("approval-fixture",))
    frozen = freeze_candidate(approved)
    assert value.state == IntakeState.DRAFT
    assert approved.state == IntakeState.APPROVED
    assert frozen.state == IntakeState.FROZEN
    with pytest.raises(ValueError, match="fixture provider"):
        approve_candidate(replace(value, provider_key="named-live-provider"), ("approval",))
    with pytest.raises(ValueError, match="pricing"):
        freeze_candidate(replace(approved, pricing_version=None))


@pytest.mark.parametrize(
    ("behavior", "attempts", "expected_gate", "failure"),
    [
        (ProviderOutcome.VALID, 1, None, None),
        (ProviderOutcome.MALFORMED_SCHEMA, 2, HardGate.SAFETY_SCHEMA_POLICY_VIOLATION, None),
        (ProviderOutcome.TIMEOUT, 2, None, "timeout"),
        (ProviderOutcome.TRANSIENT_FAILURE, 2, None, None),
        (ProviderOutcome.REFUSAL, 1, None, "provider_refusal"),
        (ProviderOutcome.SAFETY_FILTERED, 1, None, "provider_safety_filtered"),
        (ProviderOutcome.UNSUPPORTED_FIELD, 1, HardGate.SAFETY_SCHEMA_POLICY_VIOLATION, None),
        (ProviderOutcome.HARD_GATE_VIOLATION, 1, HardGate.UNKNOWN_TO_KNOWN, None),
        (
            ProviderOutcome.PROMPT_INJECTION_COMPLIANCE,
            1,
            HardGate.PROMPT_INJECTION_COMPLIANCE,
            None,
        ),
    ],
)
def test_fake_provider_behaviors_are_bounded_and_ledgered(
    behavior: ProviderOutcome,
    attempts: int,
    expected_gate: HardGate | None,
    failure: str | None,
) -> None:
    ledger = budget()
    projection = project_case(
        case("hostile_prompt_injection"), TournamentTask.EVIDENCE_INTERPRETATION
    )
    provider = DeterministicTournamentProvider(behavior)
    result = Tournament2FixtureRunner(ledger).execute(
        frozen_candidate(), provider, projection, pricing()
    )
    assert result.attempts == attempts == provider.invocations
    assert len(ledger.entries) == attempts
    assert all(
        item.input_tokens and item.output_tokens and item.latency_ms for item in ledger.entries
    )
    if expected_gate is not None:
        assert expected_gate in {gate.gate for gate in result.evaluations[-1].findings}
    if failure is not None:
        assert result.evaluations[-1].provider_failure == failure


def test_fake_provider_cross_case_contamination_attempt_hard_fails() -> None:
    source = case("cross_case_contamination")
    projection = project_case(source, TournamentTask.EVIDENCE_INTERPRETATION)
    provider = DeterministicTournamentProvider(
        ProviderOutcome.CROSS_CASE_CONTAMINATION,
        contaminated_graph=contaminated_graph(source, case("weak_opportunity")),
    )
    result = Tournament2FixtureRunner(budget()).execute(
        frozen_candidate(), provider, projection, pricing()
    )
    assert HardGate.CROSS_CASE_CONTAMINATION in {
        finding.gate for finding in result.evaluations[0].findings
    }


def test_runner_rejects_pricing_drift_from_frozen_candidate() -> None:
    projection = project_case(case(), TournamentTask.EVIDENCE_INTERPRETATION)
    provider = DeterministicTournamentProvider(
        ProviderOutcome.VALID, pricing_version="fixture-pricing@2"
    )
    with pytest.raises(ValueError, match="pricing version"):
        Tournament2FixtureRunner(budget()).execute(
            frozen_candidate(), provider, projection, pricing()
        )


def test_budget_reservation_reconciliation_caps_and_unknown_pricing_fail_closed() -> None:
    assert conservative_preflight_cost(pricing(), 100, 50) == 150
    with pytest.raises(ValueError, match="unknown pricing"):
        conservative_preflight_cost(None, 1, 1)
    ledger = budget(total=2_000)
    reservation = Reservation(
        "r1",
        "fixture-provider",
        "fixture-valid",
        TournamentTask.AUDIT_WORDING,
        "safety",
        500,
    )
    ledger.reserve(reservation)
    ledger.reconcile(
        "r1",
        UsageLedgerEntry(
            frozen_candidate().id,
            TournamentTask.AUDIT_WORDING,
            "safety",
            case().id,
            1,
            100,
            50,
            4,
            500,
            250,
            "fixture-pricing@1",
            "passed",
        ),
    )
    assert ledger.actual_total_micros == 250
    with pytest.raises(ValueError, match="budget exhausted"):
        ledger.reserve(replace(reservation, id="r2", amount_micros=1_000))


def test_task_report_has_no_global_best_model_and_enforces_deterministic_preference() -> None:
    row = TaskReportRow(
        TournamentTask.AUDIT_WORDING,
        frozen_candidate().id,
        "fixture-valid",
        RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN,
        PostTournamentState.NO_ROUTE,
        True,
        True,
        (),
        (),
        ("deterministic",),
        100,
        50,
        5,
        2,
    )
    report = TournamentReport(
        uuid4(),
        datetime(2026, 8, 18, tzinfo=UTC),
        "m6.6a@1",
        CORPUS_VERSION,
        "evaluator@1",
        "safety@1",
        "synthetic@1",
        "fixture-budget@1",
        ("a" * 64,),
        (row,),
        (),
        4,
        2,
        True,
    )
    assert validate_report(report) is report
    assert not hasattr(report, "best_model")
    assert report.route_activation_count == report.canonical_mutation_count == 0
    with pytest.raises(ValueError, match="deterministic preference"):
        validate_report(replace(report, task_rows=(replace(row, deterministic_preferred=False),)))


def test_normal_m66a_ci_has_no_network_or_live_candidate_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("M6.6A attempted external network access")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    projection = project_case(case(), TournamentTask.EVIDENCE_INTERPRETATION)
    runner = Tournament2FixtureRunner(budget())
    result = runner.execute(
        frozen_candidate(),
        DeterministicTournamentProvider(ProviderOutcome.VALID),
        projection,
        pricing(),
    )
    assert result.evaluations[0].safety_passed
    assert CandidateKind.__members__ == {"DETERMINISTIC_FAKE": CandidateKind.DETERMINISTIC_FAKE}
