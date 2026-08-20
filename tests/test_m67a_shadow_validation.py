from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from opintel_m0.domain import Principal, Role
from opintel_m0_local import UuidFactory
from opintel_shadow.application import AI_ZERO_REASON, ShadowValidationService
from opintel_shadow.domain import (
    PHASE_1_OUTCOMES,
    CanonicalPipelineSnapshot,
    CompanyOutcome,
    CostCategory,
    CostEntry,
    EligibilityState,
    IneligibilityReason,
    MetricName,
    MetricState,
    OrganizationKind,
    PermissionActivity,
    PermissionEntry,
    PermissionState,
    ReplayState,
    ReviewDecision,
    ReviewKind,
    SafetyEventType,
    ShadowAuthorizationError,
    ShadowValidationInputError,
    StopScope,
    SyntheticBusinessCandidate,
)
from opintel_shadow_local import (
    SqlAlchemyShadowRepository,
    SyntheticCanonicalPipeline,
    build_pipeline_snapshot,
    build_synthetic_candidates,
    build_synthetic_pipeline,
)
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@pytest.fixture
def admin() -> Principal:
    return Principal("m67a-admin", WORKSPACE_ID, frozenset({Role.ADMIN}))


@pytest.fixture
def shadow_repository(tmp_path: Path) -> SqlAlchemyShadowRepository:
    value = SqlAlchemyShadowRepository(f"sqlite:///{(tmp_path / 'shadow.db').as_posix()}")
    value.initialize()
    return value


@pytest.fixture
def candidates() -> tuple[SyntheticBusinessCandidate, ...]:
    return build_synthetic_candidates()


@pytest.fixture
def service(
    shadow_repository: SqlAlchemyShadowRepository,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> ShadowValidationService:
    return ShadowValidationService(
        shadow_repository,
        build_synthetic_pipeline(candidates),
        FixedClock(),
        UuidFactory(),
    )


def _setup_run(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
):
    permissions = service.ensure_permission_baseline(admin.workspace_id)
    policy = service.create_phase_one_policy(admin)
    frame = service.freeze_sampling_frame(admin, policy, candidates, "frozen-seed-2026-08")
    selection = service.select_cohort(admin, policy, frame)
    run = service.start_run(admin, selection, permissions)
    return permissions, policy, frame, selection, run


def _completed_review(
    service: ShadowValidationService,
    admin: Principal,
    run_id: UUID,
    candidate_id: UUID,
    kind: ReviewKind,
    reviewer: str,
    independent_from: str | None = None,
):
    assigned = service.assign_review(
        admin,
        run_id,
        candidate_id,
        kind,
        reviewer,
        independent_from_reviewer=independent_from,
    )
    return service.complete_review(admin, assigned, ReviewDecision.APPROVE, 61)


def _approval_reviews(
    service: ShadowValidationService,
    admin: Principal,
    run_id: UUID,
    candidate_id: UUID,
    through: str,
):
    reviews = [
        _completed_review(
            service, admin, run_id, candidate_id, ReviewKind.OPPORTUNITY_ACCEPTANCE, "r1"
        ),
        _completed_review(
            service,
            admin,
            run_id,
            candidate_id,
            ReviewKind.OPPORTUNITY_SECOND_REVIEW,
            "r2",
            "r1",
        ),
    ]
    if through in {"M3", "M4", "M5"}:
        reviews.append(
            _completed_review(service, admin, run_id, candidate_id, ReviewKind.AUDIT_APPROVAL, "r3")
        )
    if through in {"M4", "M5"}:
        reviews.append(
            _completed_review(service, admin, run_id, candidate_id, ReviewKind.DEMO_APPROVAL, "r4")
        )
    if through == "M5":
        reviews.append(
            _completed_review(
                service, admin, run_id, candidate_id, ReviewKind.OUTREACH_APPROVAL, "r5"
            )
        )
    return tuple(reviews)


def test_permission_successor_taxonomy_is_exact_independent_and_disabled(
    service: ShadowValidationService, admin: Principal
) -> None:
    release = service.ensure_permission_baseline(admin.workspace_id)
    assert tuple(item.activity for item in release.permissions) == tuple(PermissionActivity)
    assert all(item.state is PermissionState.NOT_AUTHORIZED for item in release.permissions)
    assert release.legacy_real_company_research_grants_successors is False


def test_authorizing_one_permission_does_not_inherit_to_another(
    service: ShadowValidationService, admin: Principal
) -> None:
    release = service.ensure_permission_baseline(admin.workspace_id)
    changed = list(release.permissions)
    changed[0] = PermissionEntry(activity=changed[0].activity, state=PermissionState.AUTHORIZED)
    successor = release.model_copy(update={"permissions": tuple(changed)})
    assert successor.permissions[1].state is PermissionState.NOT_AUTHORIZED


def test_synthetic_run_fails_closed_if_any_real_permission_is_authorized(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    permissions = service.ensure_permission_baseline(admin.workspace_id)
    changed = list(permissions.permissions)
    changed[0] = PermissionEntry(activity=changed[0].activity, state=PermissionState.AUTHORIZED)
    authorized = permissions.model_copy(update={"permissions": tuple(changed)})
    policy = service.create_phase_one_policy(admin)
    frame = service.freeze_sampling_frame(admin, policy, candidates, "permission-seed")
    selection = service.select_cohort(admin, policy, frame)
    with pytest.raises(ShadowValidationInputError):
        service.start_run(admin, selection, authorized)


def test_synthetic_phase_one_policy_has_exact_scope_and_target(
    service: ShadowValidationService, admin: Principal
) -> None:
    policy = service.create_phase_one_policy(admin)
    assert (policy.country, policy.jurisdiction, policy.industry, policy.b2b_only) == (
        "US",
        "US-TX",
        "commercial_hvac",
        True,
    )
    assert policy.target_size == 24
    assert policy.future_real_frame_owner_approval_required is True


def test_sampling_is_frozen_deterministic_and_has_reserves(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    policy = service.create_phase_one_policy(admin)
    first = service.freeze_sampling_frame(admin, policy, candidates, "fixed-seed")
    second = service.freeze_sampling_frame(admin, policy, candidates, "fixed-seed")
    first_selection = service.select_cohort(admin, policy, first)
    second_selection = service.select_cohort(admin, policy, second)
    assert tuple(item.current_candidate_id for item in first_selection.slots) == tuple(
        item.current_candidate_id for item in second_selection.slots
    )
    assert len(first_selection.slots) == 24
    assert len(first_selection.reserve_order) == 12
    assert first_selection.owner_approval_for_future_real_frame is False


def test_dedupe_franchise_cap_and_multi_location_units(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    base = candidates[0]
    duplicate = base.model_copy(
        update={"id": uuid4(), "fixture_key": "synthetic-duplicate", "display_name": "Duplicate"}
    )
    franchise_a = base.model_copy(
        update={
            "id": uuid4(),
            "fixture_key": "synthetic-franchise-a",
            "canonical_domain": "franchise-a.invalid",
            "organization_kind": OrganizationKind.FRANCHISE,
            "organization_group": "shared-franchise",
            "lead_flow_key": "a",
        }
    )
    franchise_b = franchise_a.model_copy(
        update={
            "id": uuid4(),
            "fixture_key": "synthetic-franchise-b",
            "canonical_domain": "franchise-b.invalid",
            "lead_flow_key": "b",
        }
    )
    multi_a = base.model_copy(
        update={
            "id": uuid4(),
            "fixture_key": "synthetic-location-a",
            "organization_kind": OrganizationKind.MULTI_LOCATION,
            "organization_group": "multi-group",
            "lead_flow_key": "flow-a",
        }
    )
    multi_b = multi_a.model_copy(
        update={"id": uuid4(), "fixture_key": "synthetic-location-b", "lead_flow_key": "flow-b"}
    )
    policy = service.create_phase_one_policy(admin)
    frame = service.freeze_sampling_frame(
        admin,
        policy,
        (*candidates, duplicate, franchise_a, franchise_b, multi_a, multi_b),
        "dedupe-seed",
    )
    decisions = {item.candidate_id: item for item in frame.eligibility}
    assert IneligibilityReason.DUPLICATE_OR_CLUSTER_CAP in decisions[duplicate.id].reasons
    assert {
        decisions[franchise_a.id].state,
        decisions[franchise_b.id].state,
    } == {EligibilityState.ELIGIBLE, EligibilityState.INELIGIBLE}
    assert decisions[multi_a.id].unit_key != decisions[multi_b.id].unit_key


def test_ambiguous_identity_requires_review(
    service: ShadowValidationService, candidates: tuple[SyntheticBusinessCandidate, ...]
) -> None:
    ambiguous = candidates[0].model_copy(update={"identity_ambiguous": True})
    assert service.required_candidate_reviews(ambiguous) == (ReviewKind.COHORT_IDENTITY,)


@pytest.mark.parametrize(
    "outcome",
    [
        CompanyOutcome.RESEARCH_FAILED,
        CompanyOutcome.INSUFFICIENT_EVIDENCE,
        CompanyOutcome.NO_SUPPORTED_OPPORTUNITY,
    ],
)
def test_terminal_pipeline_results_never_consume_a_reserve(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
    outcome: CompanyOutcome,
) -> None:
    _, _, _, selection, _ = _setup_run(service, admin, candidates)
    reserve = selection.reserve_order
    successor = service.record_terminal_slot_outcome(admin, selection, 1, outcome)
    assert successor.reserve_order == reserve
    assert successor.slots[0].current_candidate_id == selection.slots[0].current_candidate_id
    assert successor.slots[0].attempts[-1].terminal_outcome is outcome
    with pytest.raises(ShadowValidationInputError):
        service.replace_ineligible_slot(admin, successor, 1, IneligibilityReason.OUTSIDE_TEXAS)


def test_replacement_uses_only_frozen_ineligibility_and_preserves_attempt_lineage(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, selection, _ = _setup_run(service, admin, candidates)
    old_id = selection.slots[0].current_candidate_id
    reserve_id = selection.reserve_order[0]
    successor = service.replace_ineligible_slot(
        admin, selection, 1, IneligibilityReason.OUTSIDE_TEXAS
    )
    assert successor.slots[0].current_candidate_id == reserve_id
    assert successor.slots[0].attempts[0].candidate_id == old_id
    assert successor.slots[0].attempts[0].replacement_reason is IneligibilityReason.OUTSIDE_TEXAS
    assert successor.slots[0].attempts[1].candidate_id == reserve_id


def test_pipeline_outcome_families_project_existing_canonical_states(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    expected = (
        CompanyOutcome.RESEARCH_FAILED,
        CompanyOutcome.RESEARCH_PARTIAL_REVIEW_REQUIRED,
        CompanyOutcome.INSUFFICIENT_EVIDENCE,
        CompanyOutcome.NO_SUPPORTED_OPPORTUNITY,
        CompanyOutcome.OPPORTUNITY_REVIEW_REQUIRED,
        CompanyOutcome.OPPORTUNITY_REJECTED,
        CompanyOutcome.AUDIT_REJECTED,
        CompanyOutcome.DEMO_REJECTED,
        CompanyOutcome.OUTREACH_REJECTED,
    )
    through = ("M2", "M2", "M2", "M2", "M2", "M2", "M2", "M3", "M4")
    actual = []
    for candidate, stage in zip(candidates[:9], through, strict=True):
        reviews = ()
        if stage in {"M2", "M3", "M4"} and candidate.fixture_key.endswith(
            ("audit_rejected", "demo_rejected", "outreach_rejected")
        ):
            reviews = _approval_reviews(service, admin, run.id, candidate.id, stage)
        actual.append(
            service.run_synthetic_company(admin, run, candidate, reviews).projection.outcome
        )
    assert tuple(actual) == expected


def test_approved_pipeline_stops_at_contact_phase_not_authorized(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    candidate = candidates[9]
    reviews = _approval_reviews(service, admin, run.id, candidate.id, "M5")
    result = service.run_synthetic_company(admin, run, candidate, reviews).projection
    assert result.outcome is CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED
    assert result.outcome in PHASE_1_OUTCOMES
    assert not result.can_create_real_person_candidate
    assert not result.can_produce_shadow_ready
    assert not result.can_create_m6_send_ready
    assert not result.can_transition_to_send_authorized
    assert not result.consumable_by_delivery_worker


def test_upstream_rejection_cannot_be_bypassed(
    shadow_repository: SqlAlchemyShadowRepository,
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    base = build_pipeline_snapshot("bypass", "research_failed")
    downstream = build_pipeline_snapshot("bypass", "approved")
    invalid = base.model_copy(update={"lineage": downstream.lineage})
    invalid_service = ShadowValidationService(
        shadow_repository,
        SyntheticCanonicalPipeline((invalid,)),
        FixedClock(),
        UuidFactory(),
    )
    candidate = candidates[0].model_copy(update={"fixture_key": "bypass"})
    with pytest.raises(ShadowValidationInputError):
        invalid_service.run_synthetic_company(admin, run, candidate)


def test_flagged_semantics_require_review_before_downstream_artifacts(
    shadow_repository: SqlAlchemyShadowRepository,
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    flagged = build_pipeline_snapshot("flagged", "approved").model_copy(
        update={
            "contradiction_present": True,
            "entity_ambiguous": True,
            "scoped_absence_present": True,
            "unsupported_claim_present": True,
        }
    )
    flagged_service = ShadowValidationService(
        shadow_repository,
        SyntheticCanonicalPipeline((flagged,)),
        FixedClock(),
        UuidFactory(),
    )
    candidate = candidates[9].model_copy(update={"fixture_key": "flagged"})
    with pytest.raises(ShadowValidationInputError):
        flagged_service.run_synthetic_company(admin, run, candidate)
    reviews = list(_approval_reviews(flagged_service, admin, run.id, candidate.id, "M5"))
    for index, kind in enumerate(
        (
            ReviewKind.CONTRADICTION,
            ReviewKind.ENTITY_AMBIGUITY,
            ReviewKind.SCOPED_ABSENCE,
            ReviewKind.UNSUPPORTED_CLAIM,
        ),
        start=6,
    ):
        reviews.append(
            _completed_review(flagged_service, admin, run.id, candidate.id, kind, f"r{index}")
        )
    result = flagged_service.run_synthetic_company(admin, run, candidate, tuple(reviews))
    assert result.projection.outcome is CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED


def test_unknown_economics_are_preserved(
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    snapshot = build_synthetic_pipeline(candidates).load(candidates[9].fixture_key)
    assert {state.value for state in snapshot.economic_value_states} == {"unknown", "proposed"}
    assert snapshot.economics_engine == "deterministic"


def test_capture_replay_is_deterministic_for_identical_immutable_snapshot(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    candidate = candidates[0]
    first = service.run_synthetic_company(admin, run, candidate)
    second = service.run_synthetic_company(admin, run, candidate)
    assessment = service.assess_capture_replay(first, second)
    assert assessment.state is ReplayState.IDENTICAL
    assert first.projection.replay_result_hash == second.projection.replay_result_hash


def test_changed_web_capture_is_source_drift_not_nondeterminism(
    shadow_repository: SqlAlchemyShadowRepository,
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    candidate = candidates[0]
    baseline = service.run_synthetic_company(admin, run, candidate)
    pipeline = build_synthetic_pipeline(candidates).with_source_drift(candidate.fixture_key)
    drift_service = ShadowValidationService(
        shadow_repository, pipeline, FixedClock(), UuidFactory()
    )
    replay = drift_service.run_synthetic_company(admin, run, candidate)
    assert service.assess_capture_replay(baseline, replay).state is ReplayState.SOURCE_DRIFT


def test_incidental_person_data_cannot_project_or_log(
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    snapshot = build_synthetic_pipeline(candidates).load(candidates[0].fixture_key).source_snapshot
    assert snapshot.storage_class == "restricted_source_snapshot"
    assert snapshot.may_contain_incidental_public_person_data
    assert not snapshot.person_contact_indexing_allowed
    assert not snapshot.m6_projection_allowed
    assert not snapshot.ordinary_log_values_allowed
    assert snapshot.retention_policy_status == "UNRESOLVED_ADR_0071_A08"


def test_second_opportunity_review_must_be_independent(
    service: ShadowValidationService, admin: Principal
) -> None:
    with pytest.raises(ShadowValidationInputError):
        service.assign_review(
            admin,
            uuid4(),
            uuid4(),
            ReviewKind.OPPORTUNITY_SECOND_REVIEW,
            "same-reviewer",
            independent_from_reviewer="same-reviewer",
        )


def test_review_duration_is_measured_and_warnings_escalate(
    service: ShadowValidationService, admin: Principal
) -> None:
    assignment = service.assign_review(
        admin, uuid4(), uuid4(), ReviewKind.UNSUPPORTED_CLAIM, "reviewer"
    )
    completed = service.complete_review(
        admin, assignment, ReviewDecision.REQUEST_INFORMATION, 93, ("DISAGREEMENT",)
    )
    assert completed.duration_seconds == 93
    assert completed.state.value == "escalated"


def test_seeded_negative_qa_is_repeatable_and_covers_strata(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    contexts = tuple(service.run_synthetic_company(admin, run, item) for item in candidates[:4])
    outcomes = tuple(item.projection for item in contexts)
    strata = {item.candidate_id: (f"region-{index % 2}",) for index, item in enumerate(outcomes)}
    first = service.create_qa_plan(admin, run, outcomes, strata, "qa-seed", 3)
    second = service.create_qa_plan(admin, run, outcomes, strata, "qa-seed", 3)
    assert tuple(item.order_hash for item in first.selections) == tuple(
        item.order_hash for item in second.selections
    )
    assert {"region-0", "region-1"}.issubset(first.observed_strata)


def test_metrics_bind_exact_counts_and_person_contact_is_not_measured(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    contexts = tuple(service.run_synthetic_company(admin, run, item) for item in candidates[:4])
    metrics = service.build_metrics(
        admin,
        run,
        tuple(item.projection for item in contexts),
        (),
        tuple(item.snapshot for item in contexts),
    )
    by_name = {item.name: item for item in metrics.observations}
    assert by_name[MetricName.RESEARCH_SUCCESS].numerator == 2
    assert by_name[MetricName.RESEARCH_SUCCESS].denominator == 4
    for name in (
        MetricName.PERSON_RESOLUTION_RATE,
        MetricName.VERIFIED_CONTACT_RATE,
        MetricName.SHADOW_ELIGIBILITY_RATE,
        MetricName.SHADOW_READY_YIELD,
    ):
        assert by_name[name].state is MetricState.NOT_MEASURED
        assert by_name[name].numerator is None


def test_zero_denominator_metric_is_undefined_not_fabricated(
    service: ShadowValidationService,
) -> None:
    value = service._metric(MetricName.RESEARCH_SUCCESS, 0, 0)
    assert value.state is MetricState.UNDEFINED_ZERO_DENOMINATOR
    assert value.value is None


def test_cost_ledger_records_review_time_without_money_and_ai_zero(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    entries = tuple(
        CostEntry(
            category=category,
            company_id=None,
            operation_ref=f"synthetic:{category.value}",
            monetary_cost=None if category is CostCategory.HUMAN_REVIEW_TIME else Decimal("0"),
            duration_seconds=120 if category is CostCategory.HUMAN_REVIEW_TIME else None,
            pricing_version=None,
        )
        for category in (
            CostCategory.DISCOVERY,
            CostCategory.RESEARCH,
            CostCategory.STORAGE_COMPUTE,
            CostCategory.HUMAN_REVIEW_TIME,
            CostCategory.SHARED_COHORT_OVERHEAD,
        )
    )
    ledger = service.build_cost_ledger(admin, run, entries)
    assert ledger.ai_provider_cost == Decimal("0")
    assert ledger.ai_cost_reason == AI_ZERO_REASON
    assert ledger.review_time_converted_to_money is False


@pytest.mark.parametrize("event_type", tuple(SafetyEventType))
def test_every_zero_tolerance_event_stops_at_least_the_cohort(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
    event_type: SafetyEventType,
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    _, stop = service.record_safety_incident(
        admin,
        run,
        event_type,
        ("synthetic-evidence",),
        commercial_performance=Decimal("999999"),
    )
    assert stop.scope in {StopScope.COHORT_PAUSE, StopScope.RUN_TERMINATION}
    assert stop.commercial_performance_considered is False


def test_company_quarantine_does_not_silently_resume_or_replace(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    decision = service.quarantine_company(admin, run, candidates[0].id, "synthetic finding")
    assert decision.scope is StopScope.COMPANY_QUARANTINE
    assert decision.resumable_without_review is False


def test_shadow_authorization_always_fails(
    service: ShadowValidationService, admin: Principal
) -> None:
    with pytest.raises(ShadowValidationInputError):
        service.authorize_shadow(admin, uuid4())


def test_repository_is_append_only_workspace_scoped(
    service: ShadowValidationService,
    shadow_repository: SqlAlchemyShadowRepository,
    admin: Principal,
) -> None:
    policy = service.create_phase_one_policy(admin)
    assert shadow_repository.get(admin.workspace_id, policy.record_kind, policy.id) == policy
    assert shadow_repository.get(uuid4(), policy.record_kind, policy.id) is None
    with pytest.raises(IntegrityError):
        shadow_repository.save(policy)


def test_workspace_authorization_is_enforced(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    policy = service.create_phase_one_policy(admin)
    other = replace(admin, workspace_id=uuid4())
    with pytest.raises(ShadowAuthorizationError):
        service.freeze_sampling_frame(other, policy, candidates, "seed")


def test_m66_artifacts_are_absent_and_cannot_change_results(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    candidate = candidates[0]
    without_m66 = service.run_synthetic_company(admin, run, candidate)
    assert "qualification" not in inspect.getsource(type(service)).lower()
    assert without_m66.snapshot.ai_assistance_used is False


def test_ai_assisted_snapshot_is_rejected_even_if_constructed_unsafely(
    shadow_repository: SqlAlchemyShadowRepository,
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    _, _, _, _, run = _setup_run(service, admin, candidates)
    base = build_pipeline_snapshot("ai-interference", "research_failed")
    invalid = base.model_copy(update={"ai_assistance_used": True})
    ai_service = ShadowValidationService(
        shadow_repository,
        SyntheticCanonicalPipeline((cast(CanonicalPipelineSnapshot, invalid),)),
        FixedClock(),
        UuidFactory(),
    )
    candidate = candidates[0].model_copy(update={"fixture_key": "ai-interference"})
    with pytest.raises(ShadowValidationInputError):
        ai_service.run_synthetic_company(admin, run, candidate)


def test_no_delivery_import_port_sdk_or_m6_table_write_exists() -> None:
    shadow_root = ROOT / "packages" / "shadow-core"
    local_root = ROOT / "packages" / "shadow-local"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (shadow_root, local_root)
        for path in root.rglob("*.py")
    ).lower()
    prohibited = (
        "opintel_contact",
        "send_ready",
        "send_authorized",
        "authorize_delivery",
        "deliver_message",
        "retry_delivery",
        "sendgrid",
        "mailgun",
        "twilio",
        "smtp",
        "calendar_port",
        "crm_port",
        "booking_port",
        "search_person",
        "search_contact",
        "import socket",
        "import httpx",
        "import requests",
        "urllib.request",
        "playwright",
    )
    # False-valued contract field names are allowed; executable command/import spellings are not.
    executable_source = source.replace("can_create_m6_send_ready", "").replace(
        "can_transition_to_send_authorized", ""
    )
    assert all(term not in executable_source for term in prohibited)
    persistence = (local_root / "src/opintel_shadow_local/persistence.py").read_text(
        encoding="utf-8"
    )
    assert "m67_shadow_records" in persistence
    assert "m6_send" not in persistence.lower()


def test_m68_evidence_package_preserves_limitations_and_zero_live_counts(
    service: ShadowValidationService,
    admin: Principal,
    candidates: tuple[SyntheticBusinessCandidate, ...],
) -> None:
    permissions, policy, frame, selection, run = _setup_run(service, admin, candidates)
    context = service.run_synthetic_company(admin, run, candidates[0])
    metrics = service.build_metrics(admin, run, (context.projection,), (), (context.snapshot,))
    entries = tuple(
        CostEntry(
            category=category,
            company_id=None,
            operation_ref=category.value,
            monetary_cost=None if category is CostCategory.HUMAN_REVIEW_TIME else Decimal("0"),
            duration_seconds=1 if category is CostCategory.HUMAN_REVIEW_TIME else None,
            pricing_version=None,
        )
        for category in (
            CostCategory.DISCOVERY,
            CostCategory.RESEARCH,
            CostCategory.STORAGE_COMPUTE,
            CostCategory.HUMAN_REVIEW_TIME,
            CostCategory.SHARED_COHORT_OVERHEAD,
        )
    )
    costs = service.build_cost_ledger(admin, run, entries)
    replay = service.assess_capture_replay(context, context)
    package = service.generate_m68_package(
        admin,
        run,
        permissions,
        policy,
        frame,
        selection,
        (context.projection,),
        (),
        metrics,
        costs,
        (),
        (),
        (replay,),
    )
    assert package.synthetic_only
    assert package.actual_business_count == package.real_web_research_count == 0
    assert package.real_person_count == package.real_contact_count == 0
    assert package.external_communication_count == 0
    assert package.ai_provider_cost_usd == Decimal("0")
    assert "ADR-0071" in package.unresolved_approvals
    assert "NO_DELIVERY_CAPABILITY" in package.known_limitations
