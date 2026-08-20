"""Deterministic M6.7A synthetic control-plane application service."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from uuid import UUID

from opintel_audit.domain import AuditRevisionState
from opintel_demo.domain import DemoRevisionState
from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory
from opintel_opportunity.domain import AnalysisStatus, HypothesisStatus
from opintel_outreach.domain import OutreachRevisionState
from opintel_research.domain import ResearchRunStatus

from opintel_shadow.domain import (
    PERSON_CONTACT_METRICS,
    PREDETERMINED_REPLACEMENT_REASONS,
    RUN_TERMINATING_EVENTS,
    ArtifactReference,
    CanonicalPipelineSnapshot,
    CohortPolicy,
    CohortSelectionManifest,
    CohortSlot,
    CompanyOutcome,
    CompanyOutcomeProjection,
    CostCategory,
    CostEntry,
    CostLedger,
    EligibilityDecisionRecord,
    EligibilityState,
    IneligibilityReason,
    M68EvidencePackage,
    MetricName,
    MetricObservation,
    MetricSnapshot,
    MetricState,
    OrganizationKind,
    PermissionActivity,
    PermissionEntry,
    PermissionState,
    QaPlan,
    QaSelection,
    RealDataPermissionRelease,
    ReleaseState,
    ReplayAssessment,
    ReplayState,
    ReviewAssignment,
    ReviewDecision,
    ReviewKind,
    ReviewState,
    RunState,
    SafetyEventType,
    SafetyIncident,
    SamplingFrame,
    ShadowAuthorizationError,
    ShadowNotFoundError,
    ShadowPhase,
    ShadowRecord,
    ShadowRunManifest,
    ShadowValidationInputError,
    SlotAttempt,
    StopDecision,
    StopScope,
    SyntheticBusinessCandidate,
    stable_hash,
)
from opintel_shadow.ports import CanonicalPipelinePort, ShadowRepository

AI_ZERO_REASON = "NO_M6_6_BINDING_ELIGIBLE_FOR_M6_7"
UNRESOLVED_APPROVALS = (
    "ADR-0071",
    "A-03_TENANCY",
    "A-04_CLOUD_REGION",
    "A-05_A-06_DURABLE_WORKFLOW",
    "A-07_IDENTITY_ACCESS",
    "A-08_RETENTION_PRIVACY",
    "A-09_ALLOWED_SOURCES",
    "A-17_LIVE_RESEARCH_LEGAL_PRIVACY",
    "A-18_OPERATIONS_BUDGETS",
    "PHASE_1_REAL_COHORT_OWNER_APPROVAL",
)
KNOWN_LIMITATIONS = (
    "SYNTHETIC_FIXTURES_ONLY",
    "NO_REAL_SOURCE_POLICY_OR_RETENTION_DURATION",
    "NO_REAL_BUSINESS_DISCOVERY_OR_RESEARCH",
    "NO_PERSON_OR_CONTACT_PHASE",
    "NO_AI_BINDING_ELIGIBLE_FOR_M6_7",
    "NO_DELIVERY_CAPABILITY",
    "PHASE_1_MAXIMUM_OUTCOME_CONTACT_PHASE_NOT_AUTHORIZED",
)


@dataclass(frozen=True, slots=True)
class OutcomeContext:
    projection: CompanyOutcomeProjection
    snapshot: CanonicalPipelineSnapshot


class ShadowValidationService:
    def __init__(
        self,
        repository: ShadowRepository,
        pipeline: CanonicalPipelinePort,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._pipeline = pipeline
        self._clock = clock
        self._ids = identifiers

    def ensure_permission_baseline(self, workspace_id: UUID) -> RealDataPermissionRelease:
        existing = self._repository.list(workspace_id, "real_data_permissions")
        if existing:
            return cast(RealDataPermissionRelease, existing[-1])
        entries = tuple(
            PermissionEntry(activity=activity, state=PermissionState.NOT_AUTHORIZED)
            for activity in PermissionActivity
        )
        value = RealDataPermissionRelease(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7a.real-data-permissions@1",
            configuration_hash=stable_hash(
                {"permissions": [item.model_dump(mode="json") for item in entries]}
            ),
            created_at=self._clock.now(),
            state=ReleaseState.FROZEN,
            phase=ShadowPhase.PHASE_1_COMPANY_ONLY,
            permissions=entries,
        )
        self._repository.save(value)
        return value

    def create_phase_one_policy(self, principal: Principal) -> CohortPolicy:
        self._require_operator(principal)
        payload = {
            "synthetic_only": True,
            "scope": ("US", "US-TX", "commercial_hvac", "b2b"),
            "target_size": 24,
            "franchise_cap": 1,
            "replacement_reasons": [item.value for item in IneligibilityReason],
        }
        value = CohortPolicy(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.phase-1-cohort-policy@1",
            configuration_hash=stable_hash(payload),
            created_at=self._clock.now(),
            state=ReleaseState.FROZEN,
        )
        self._repository.save(value)
        return value

    @staticmethod
    def _unit_key(candidate: SyntheticBusinessCandidate) -> str:
        if candidate.organization_kind is OrganizationKind.MULTI_LOCATION:
            return stable_hash((candidate.organization_group, candidate.lead_flow_key))
        return stable_hash((candidate.canonical_domain, candidate.lead_flow_key))

    def freeze_sampling_frame(
        self,
        principal: Principal,
        policy: CohortPolicy,
        candidates: tuple[SyntheticBusinessCandidate, ...],
        seed: str,
    ) -> SamplingFrame:
        self._require_operator(principal)
        self._same_workspace(principal, policy)
        if not candidates or len({item.id for item in candidates}) != len(candidates):
            raise ShadowValidationInputError("candidate frame must be non-empty and unique")
        if not seed.strip():
            raise ShadowValidationInputError("frozen seed is required")
        decisions: list[EligibilityDecisionRecord] = []
        seen_units: set[str] = set()
        seen_franchise_groups: set[str] = set()
        for candidate in sorted(candidates, key=lambda item: item.fixture_key):
            reasons: list[IneligibilityReason] = []
            if not candidate.in_texas:
                reasons.append(IneligibilityReason.OUTSIDE_TEXAS)
            if not candidate.commercial_hvac:
                reasons.append(IneligibilityReason.NOT_COMMERCIAL_HVAC)
            if not candidate.b2b:
                reasons.append(IneligibilityReason.NOT_B2B)
            if not candidate.operational:
                reasons.append(IneligibilityReason.CLOSED_OR_INACTIVE)
            if not candidate.permitted_public_url:
                reasons.append(IneligibilityReason.NO_PERMITTED_PUBLIC_URL)
            unit_key = self._unit_key(candidate)
            duplicate = unit_key in seen_units or (
                candidate.organization_kind is OrganizationKind.FRANCHISE
                and candidate.organization_group in seen_franchise_groups
            )
            if duplicate:
                reasons.append(IneligibilityReason.DUPLICATE_OR_CLUSTER_CAP)
            state = (
                EligibilityState.REVIEW_REQUIRED
                if candidate.identity_ambiguous
                else EligibilityState.INELIGIBLE
                if reasons
                else EligibilityState.ELIGIBLE
            )
            decisions.append(
                EligibilityDecisionRecord(
                    candidate_id=candidate.id,
                    state=state,
                    reasons=tuple(dict.fromkeys(reasons)),
                    unit_key=unit_key,
                    organization_cluster=candidate.organization_group,
                )
            )
            if state is EligibilityState.ELIGIBLE:
                seen_units.add(unit_key)
                if candidate.organization_kind is OrganizationKind.FRANCHISE:
                    seen_franchise_groups.add(candidate.organization_group)
        frame_payload = {
            "policy_hash": policy.configuration_hash,
            "seed": seed,
            "candidates": [item.model_dump(mode="json") for item in candidates],
            "eligibility": [item.model_dump(mode="json") for item in decisions],
        }
        frame_hash = stable_hash(frame_payload)
        value = SamplingFrame(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.synthetic-sampling-frame@1",
            configuration_hash=frame_hash,
            created_at=self._clock.now(),
            cohort_policy_id=policy.id,
            cohort_policy_hash=policy.configuration_hash,
            frozen_seed=seed,
            candidates=candidates,
            eligibility=tuple(decisions),
            frame_hash=frame_hash,
        )
        self._repository.save(value)
        return value

    def select_cohort(
        self, principal: Principal, policy: CohortPolicy, frame: SamplingFrame
    ) -> CohortSelectionManifest:
        self._require_operator(principal)
        self._same_workspace(principal, policy, frame)
        if frame.cohort_policy_hash != policy.configuration_hash:
            raise ShadowValidationInputError("sampling frame policy hash mismatch")
        decision_map = {item.candidate_id: item for item in frame.eligibility}
        eligible = [
            item
            for item in frame.candidates
            if decision_map[item.id].state is EligibilityState.ELIGIBLE
        ]
        ordered = sorted(
            eligible,
            key=lambda item: stable_hash((frame.frozen_seed, str(item.id), item.fixture_key)),
        )
        if len(ordered) < policy.target_size:
            raise ShadowValidationInputError("fewer than 24 eligible synthetic candidates")
        now = self._clock.now()
        selected = ordered[: policy.target_size]
        slots = tuple(
            CohortSlot(
                slot_number=index,
                selected_candidate_id=candidate.id,
                current_candidate_id=candidate.id,
                attempts=(SlotAttempt(candidate_id=candidate.id, attempted_at=now),),
            )
            for index, candidate in enumerate(selected, start=1)
        )
        reserve = tuple(item.id for item in ordered[policy.target_size :])
        payload = {
            "frame_hash": frame.frame_hash,
            "seed": frame.frozen_seed,
            "slots": [item.model_dump(mode="json") for item in slots],
            "reserve": [str(item) for item in reserve],
        }
        value = CohortSelectionManifest(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.synthetic-selection@1",
            configuration_hash=stable_hash(payload),
            created_at=now,
            frame_id=frame.id,
            frame_hash=frame.frame_hash,
            selection_algorithm_version="seeded-sha256-systematic@1",
            frozen_seed=frame.frozen_seed,
            slots=slots,
            reserve_order=reserve,
        )
        self._repository.save(value)
        return value

    def replace_ineligible_slot(
        self,
        principal: Principal,
        manifest: CohortSelectionManifest,
        slot_number: int,
        reason: IneligibilityReason,
    ) -> CohortSelectionManifest:
        self._require_operator(principal)
        self._same_workspace(principal, manifest)
        if reason not in PREDETERMINED_REPLACEMENT_REASONS:
            raise ShadowValidationInputError("replacement reason is not cohort ineligibility")
        if not manifest.reserve_order:
            raise ShadowValidationInputError("no frozen reserve candidate is available")
        target = next((item for item in manifest.slots if item.slot_number == slot_number), None)
        if target is None:
            raise ShadowValidationInputError("unknown cohort slot")
        if target.attempts[-1].terminal_outcome is not None:
            raise ShadowValidationInputError("pipeline outcome cannot be replaced")
        replacement = manifest.reserve_order[0]
        attempts = list(target.attempts)
        previous = attempts[-1]
        attempts[-1] = previous.model_copy(update={"replacement_reason": reason})
        attempts.append(SlotAttempt(candidate_id=replacement, attempted_at=self._clock.now()))
        updated_slot = target.model_copy(
            update={"current_candidate_id": replacement, "attempts": tuple(attempts)}
        )
        slots = tuple(
            updated_slot if item.slot_number == slot_number else item for item in manifest.slots
        )
        payload = {
            "previous": manifest.configuration_hash,
            "slot": slot_number,
            "reason": reason.value,
            "replacement": str(replacement),
        }
        value = manifest.model_copy(
            update={
                "id": self._ids.new(),
                "version": "m6.7a.synthetic-selection@2",
                "configuration_hash": stable_hash(payload),
                "created_at": self._clock.now(),
                "slots": slots,
                "reserve_order": manifest.reserve_order[1:],
            }
        )
        self._repository.save(value)
        return value

    def record_terminal_slot_outcome(
        self,
        principal: Principal,
        manifest: CohortSelectionManifest,
        slot_number: int,
        outcome: CompanyOutcome,
    ) -> CohortSelectionManifest:
        """Record an attempted company outcome without consuming a reserve candidate."""

        self._require_operator(principal)
        self._same_workspace(principal, manifest)
        target = next((item for item in manifest.slots if item.slot_number == slot_number), None)
        if target is None:
            raise ShadowValidationInputError("unknown cohort slot")
        attempts = list(target.attempts)
        attempts[-1] = attempts[-1].model_copy(update={"terminal_outcome": outcome})
        updated_slot = target.model_copy(update={"attempts": tuple(attempts)})
        slots = tuple(
            updated_slot if item.slot_number == slot_number else item for item in manifest.slots
        )
        value = manifest.model_copy(
            update={
                "id": self._ids.new(),
                "version": "m6.7a.synthetic-selection@terminal-outcome-1",
                "configuration_hash": stable_hash(
                    (manifest.configuration_hash, slot_number, outcome.value)
                ),
                "created_at": self._clock.now(),
                "slots": slots,
            }
        )
        self._repository.save(value)
        return value

    def start_run(
        self,
        principal: Principal,
        selection: CohortSelectionManifest,
        permissions: RealDataPermissionRelease,
    ) -> ShadowRunManifest:
        self._require_operator(principal)
        self._same_workspace(principal, selection, permissions)
        if any(
            item.state is not PermissionState.NOT_AUTHORIZED for item in permissions.permissions
        ):
            raise ShadowValidationInputError("M6.7A requires every real-data permission disabled")
        payload = {
            "selection": selection.configuration_hash,
            "permissions": permissions.configuration_hash,
            "synthetic": True,
        }
        value = ShadowRunManifest(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.synthetic-shadow-run@1",
            configuration_hash=stable_hash(payload),
            created_at=self._clock.now(),
            state=RunState.RUNNING,
            selection_manifest_id=selection.id,
            selection_manifest_hash=selection.configuration_hash,
            permission_release_id=permissions.id,
            permission_release_hash=permissions.configuration_hash,
        )
        self._repository.save(value)
        return value

    @staticmethod
    def required_candidate_reviews(
        candidate: SyntheticBusinessCandidate,
    ) -> tuple[ReviewKind, ...]:
        return (ReviewKind.COHORT_IDENTITY,) if candidate.identity_ambiguous else ()

    @staticmethod
    def required_reviews(snapshot: CanonicalPipelineSnapshot) -> tuple[ReviewKind, ...]:
        result: list[ReviewKind] = []
        if snapshot.entity_ambiguous:
            result.append(ReviewKind.ENTITY_AMBIGUITY)
        if snapshot.contradiction_present:
            result.append(ReviewKind.CONTRADICTION)
        if snapshot.scoped_absence_present:
            result.append(ReviewKind.SCOPED_ABSENCE)
        if snapshot.unsupported_claim_present:
            result.append(ReviewKind.UNSUPPORTED_CLAIM)
        if snapshot.hypothesis_status in {
            HypothesisStatus.READY_FOR_REVIEW,
            HypothesisStatus.ACCEPTED,
        }:
            result.extend((ReviewKind.OPPORTUNITY_ACCEPTANCE, ReviewKind.OPPORTUNITY_SECOND_REVIEW))
        if snapshot.audit_state is AuditRevisionState.APPROVED:
            result.append(ReviewKind.AUDIT_APPROVAL)
        if snapshot.demo_state is DemoRevisionState.APPROVED:
            result.append(ReviewKind.DEMO_APPROVAL)
        if snapshot.outreach_state is OutreachRevisionState.CONTENT_APPROVED:
            result.append(ReviewKind.OUTREACH_APPROVAL)
        return tuple(result)

    def assign_review(
        self,
        principal: Principal,
        run_id: UUID,
        candidate_id: UUID,
        kind: ReviewKind,
        reviewer_pseudonym: str,
        *,
        independent_from_reviewer: str | None = None,
        seeded_qa: bool = False,
        stratum_keys: tuple[str, ...] = (),
    ) -> ReviewAssignment:
        self._require_reviewer(principal)
        if kind is ReviewKind.OPPORTUNITY_SECOND_REVIEW and (
            not independent_from_reviewer or independent_from_reviewer == reviewer_pseudonym
        ):
            raise ShadowValidationInputError("second opportunity review must be independent")
        value = ReviewAssignment(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.review-assignment@1",
            configuration_hash=stable_hash(
                (run_id, candidate_id, kind, reviewer_pseudonym, independent_from_reviewer)
            ),
            created_at=self._clock.now(),
            run_id=run_id,
            candidate_id=candidate_id,
            kind=kind,
            state=ReviewState.ASSIGNED,
            reviewer_pseudonym=reviewer_pseudonym,
            independent_from_reviewer=independent_from_reviewer,
            required=True,
            seeded_qa=seeded_qa,
            stratum_keys=stratum_keys,
        )
        self._repository.save(value)
        return value

    def complete_review(
        self,
        principal: Principal,
        assignment: ReviewAssignment,
        decision: ReviewDecision,
        duration_seconds: int,
        warning_codes: tuple[str, ...] = (),
    ) -> ReviewAssignment:
        self._require_reviewer(principal)
        self._same_workspace(principal, assignment)
        if assignment.state is not ReviewState.ASSIGNED:
            raise ShadowValidationInputError("only assigned reviews may complete")
        state = ReviewState.ESCALATED if warning_codes else ReviewState.COMPLETED
        value = assignment.model_copy(
            update={
                "id": self._ids.new(),
                "version": "m6.7a.review-assignment@2",
                "configuration_hash": stable_hash(
                    (assignment.configuration_hash, decision, duration_seconds, warning_codes)
                ),
                "created_at": self._clock.now(),
                "state": state,
                "decision": decision,
                "duration_seconds": duration_seconds,
                "warning_codes": warning_codes,
            }
        )
        self._repository.save(value)
        return value

    @staticmethod
    def _review_approved(reviews: tuple[ReviewAssignment, ...], kind: ReviewKind) -> bool:
        return any(
            item.kind is kind
            and item.state is ReviewState.COMPLETED
            and item.decision is ReviewDecision.APPROVE
            and item.duration_seconds is not None
            for item in reviews
        )

    @staticmethod
    def _review_completed(reviews: tuple[ReviewAssignment, ...], kind: ReviewKind) -> bool:
        return any(
            item.kind is kind
            and item.state is ReviewState.COMPLETED
            and item.decision is not None
            and item.duration_seconds is not None
            for item in reviews
        )

    @staticmethod
    def _validate_lineage(snapshot: CanonicalPipelineSnapshot) -> None:
        if not snapshot.lineage or snapshot.lineage[0].stage != "M1":
            raise ShadowValidationInputError("canonical lineage must begin with M1")
        prior: ArtifactReference | None = None
        expected_order = ("M1", "M2", "M3", "M4", "M5")
        for index, stage in enumerate(snapshot.lineage):
            if stage.stage != expected_order[index]:
                raise ShadowValidationInputError("canonical stage order changed or bypassed")
            if stage.output.context != stage.stage:
                raise ShadowValidationInputError("stage output context mismatch")
            if prior is not None and prior not in stage.inputs:
                raise ShadowValidationInputError("stage lacks exact upstream revision/hash")
            prior = stage.output

    def _project_outcome(
        self, snapshot: CanonicalPipelineSnapshot, reviews: tuple[ReviewAssignment, ...]
    ) -> CompanyOutcome:
        self._validate_lineage(snapshot)
        if snapshot.ai_assistance_used:
            raise ShadowValidationInputError("M6.7A cannot consume AI assistance")
        if snapshot.m1_status is ResearchRunStatus.FAILED:
            if len(snapshot.lineage) != 1:
                raise ShadowValidationInputError("M1 failure cannot have downstream stages")
            return CompanyOutcome.RESEARCH_FAILED
        if snapshot.m1_status is ResearchRunStatus.PARTIAL:
            if len(snapshot.lineage) != 1:
                raise ShadowValidationInputError("partial M1 review cannot be bypassed")
            return CompanyOutcome.RESEARCH_PARTIAL_REVIEW_REQUIRED
        if snapshot.m1_status is not ResearchRunStatus.SUCCEEDED:
            raise ShadowValidationInputError("M1 must be terminal before projection")
        if snapshot.m2_analysis_status is AnalysisStatus.INSUFFICIENT_DATA:
            if len(snapshot.lineage) != 2:
                raise ShadowValidationInputError("insufficient M2 evidence cannot be bypassed")
            return CompanyOutcome.INSUFFICIENT_EVIDENCE
        if snapshot.m2_analysis_status is not AnalysisStatus.SUCCEEDED:
            raise ShadowValidationInputError("successful M2 analysis is required")
        special_reviews = (
            (snapshot.entity_ambiguous, ReviewKind.ENTITY_AMBIGUITY),
            (snapshot.contradiction_present, ReviewKind.CONTRADICTION),
            (snapshot.scoped_absence_present, ReviewKind.SCOPED_ABSENCE),
            (snapshot.unsupported_claim_present, ReviewKind.UNSUPPORTED_CLAIM),
        )
        if any(
            required and not self._review_completed(reviews, kind)
            for required, kind in special_reviews
        ):
            if len(snapshot.lineage) != 2:
                raise ShadowValidationInputError(
                    "mandatory semantic review cannot be bypassed by a downstream artifact"
                )
            return CompanyOutcome.OPPORTUNITY_REVIEW_REQUIRED
        if snapshot.hypothesis_status in {None, HypothesisStatus.NEEDS_INFORMATION}:
            if len(snapshot.lineage) != 2:
                raise ShadowValidationInputError("unsupported opportunity cannot be bypassed")
            return CompanyOutcome.NO_SUPPORTED_OPPORTUNITY
        if snapshot.hypothesis_status is HypothesisStatus.REJECTED:
            if len(snapshot.lineage) != 2:
                raise ShadowValidationInputError("rejected opportunity cannot be bypassed")
            return CompanyOutcome.OPPORTUNITY_REJECTED
        opportunity_reviews = (
            self._review_approved(reviews, ReviewKind.OPPORTUNITY_ACCEPTANCE),
            self._review_approved(reviews, ReviewKind.OPPORTUNITY_SECOND_REVIEW),
        )
        if snapshot.hypothesis_status is HypothesisStatus.READY_FOR_REVIEW or not all(
            opportunity_reviews
        ):
            if len(snapshot.lineage) != 2:
                raise ShadowValidationInputError("unreviewed opportunity cannot be bypassed")
            return CompanyOutcome.OPPORTUNITY_REVIEW_REQUIRED
        if snapshot.hypothesis_status is not HypothesisStatus.ACCEPTED:
            raise ShadowValidationInputError("accepted opportunity required for M3")
        if snapshot.audit_state in {AuditRevisionState.QC_FAILED, AuditRevisionState.REJECTED}:
            if len(snapshot.lineage) != 3:
                raise ShadowValidationInputError("rejected audit cannot be bypassed")
            return CompanyOutcome.AUDIT_REJECTED
        if snapshot.audit_state is not AuditRevisionState.APPROVED or not self._review_approved(
            reviews, ReviewKind.AUDIT_APPROVAL
        ):
            raise ShadowValidationInputError("approved and reviewed M3 audit required")
        if snapshot.demo_state in {DemoRevisionState.QC_FAILED, DemoRevisionState.REJECTED}:
            if len(snapshot.lineage) != 4:
                raise ShadowValidationInputError("rejected demo cannot be bypassed")
            return CompanyOutcome.DEMO_REJECTED
        if snapshot.demo_state is not DemoRevisionState.APPROVED or not self._review_approved(
            reviews, ReviewKind.DEMO_APPROVAL
        ):
            raise ShadowValidationInputError("approved and reviewed M4 demo required")
        if snapshot.outreach_state in {
            OutreachRevisionState.QC_FAILED,
            OutreachRevisionState.REJECTED,
        }:
            if len(snapshot.lineage) != 5:
                raise ShadowValidationInputError("rejected outreach cannot be bypassed")
            return CompanyOutcome.OUTREACH_REJECTED
        if snapshot.outreach_state is not OutreachRevisionState.CONTENT_APPROVED or not (
            self._review_approved(reviews, ReviewKind.OUTREACH_APPROVAL)
        ):
            raise ShadowValidationInputError("content-approved and reviewed M5 revision required")
        return CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED

    def run_synthetic_company(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        candidate: SyntheticBusinessCandidate,
        reviews: tuple[ReviewAssignment, ...] = (),
    ) -> OutcomeContext:
        self._require_operator(principal)
        self._same_workspace(principal, run, *reviews)
        if run.state is not RunState.RUNNING or not candidate.synthetic:
            raise ShadowValidationInputError("only running synthetic Phase 1 runs are supported")
        if any(item.run_id != run.id or item.candidate_id != candidate.id for item in reviews):
            raise ShadowValidationInputError("review does not bind this run and candidate")
        snapshot = self._pipeline.load(candidate.fixture_key)
        outcome = self._project_outcome(snapshot, reviews)
        determining = snapshot.lineage[-1].output
        replay_hash = stable_hash(
            {
                "source_snapshot_hash": snapshot.source_snapshot.content_hash,
                "source_configuration_version": snapshot.source_configuration_version,
                "deterministic_code_version": snapshot.deterministic_code_version,
                "canonical_snapshot": snapshot.model_dump(mode="json"),
                "outcome": outcome.value,
            }
        )
        value = CompanyOutcomeProjection(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.company-outcome@1",
            configuration_hash=stable_hash(
                (run.configuration_hash, candidate.id, snapshot.model_dump(mode="json"), outcome)
            ),
            created_at=self._clock.now(),
            run_id=run.id,
            candidate_id=candidate.id,
            outcome=outcome,
            determining_reference=determining,
            stage_lineage=snapshot.lineage,
            source_snapshot_hash=snapshot.source_snapshot.content_hash,
            replay_result_hash=replay_hash,
        )
        self._repository.save(value)
        return OutcomeContext(value, snapshot)

    def assess_capture_replay(
        self,
        baseline: OutcomeContext,
        replay: OutcomeContext,
    ) -> ReplayAssessment:
        if (
            baseline.snapshot.source_snapshot.content_hash
            != replay.snapshot.source_snapshot.content_hash
        ):
            state = ReplayState.SOURCE_DRIFT
        elif (
            baseline.snapshot.source_configuration_version
            != replay.snapshot.source_configuration_version
            or baseline.snapshot.deterministic_code_version
            != replay.snapshot.deterministic_code_version
        ):
            state = ReplayState.CONFIGURATION_DRIFT
        elif baseline.projection.replay_result_hash == replay.projection.replay_result_hash:
            state = ReplayState.IDENTICAL
        else:
            raise ShadowValidationInputError(
                "identical capture/config/code produced divergent result"
            )
        return ReplayAssessment(
            state=state,
            baseline_result_hash=baseline.projection.replay_result_hash,
            replay_result_hash=replay.projection.replay_result_hash,
            baseline_snapshot_hash=baseline.snapshot.source_snapshot.content_hash,
            replay_snapshot_hash=replay.snapshot.source_snapshot.content_hash,
        )

    def create_qa_plan(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        outcomes: tuple[CompanyOutcomeProjection, ...],
        strata: dict[UUID, tuple[str, ...]],
        seed: str,
        target_count: int,
    ) -> QaPlan:
        self._require_reviewer(principal)
        self._same_workspace(principal, run, *outcomes)
        negative = tuple(
            item
            for item in outcomes
            if item.outcome
            not in {
                CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED,
                CompanyOutcome.OPPORTUNITY_REVIEW_REQUIRED,
            }
        )
        if target_count < 1 or not negative:
            raise ShadowValidationInputError("negative QA requires cases and a positive target")
        ordered = sorted(
            negative,
            key=lambda item: stable_hash((seed, str(item.candidate_id), item.outcome.value)),
        )
        selected: list[CompanyOutcomeProjection] = []
        covered: set[str] = set()
        for item in ordered:
            if len(selected) >= target_count:
                break
            keys = (item.outcome.value, *strata.get(item.candidate_id, ()))
            if any(key not in covered for key in keys):
                selected.append(item)
                covered.update(keys)
        for item in ordered:
            if len(selected) >= target_count:
                break
            if item not in selected:
                selected.append(item)
        selections = tuple(
            QaSelection(
                candidate_id=item.candidate_id,
                outcome=item.outcome,
                stratum_keys=(item.outcome.value, *strata.get(item.candidate_id, ())),
                order_hash=stable_hash((seed, str(item.candidate_id), item.outcome.value)),
            )
            for item in selected
        )
        value = QaPlan(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.seeded-negative-qa@1",
            configuration_hash=stable_hash(
                {"seed": seed, "selections": [item.model_dump(mode="json") for item in selections]}
            ),
            created_at=self._clock.now(),
            run_id=run.id,
            seed=seed,
            selections=selections,
            observed_strata=tuple(sorted(covered)),
        )
        self._repository.save(value)
        return value

    @staticmethod
    def _metric(
        name: MetricName,
        numerator: int | None,
        denominator: int | None,
        *,
        reason: str | None = None,
        blocked: bool = False,
    ) -> MetricObservation:
        if name in PERSON_CONTACT_METRICS:
            return MetricObservation(
                name=name,
                state=MetricState.NOT_MEASURED,
                numerator=None,
                denominator=None,
                value=None,
                reason="PHASE_1_PERSON_CONTACT_CAPABILITIES_NOT_AUTHORIZED",
            )
        if blocked:
            return MetricObservation(
                name=name,
                state=MetricState.BLOCKED,
                numerator=numerator,
                denominator=denominator,
                value=None,
                reason=reason,
            )
        if numerator is None or denominator is None:
            return MetricObservation(
                name=name,
                state=MetricState.NOT_MEASURED,
                numerator=numerator,
                denominator=denominator,
                value=None,
                reason=reason,
            )
        if denominator == 0:
            return MetricObservation(
                name=name,
                state=MetricState.UNDEFINED_ZERO_DENOMINATOR,
                numerator=numerator,
                denominator=denominator,
                value=None,
                reason="ZERO_DENOMINATOR",
            )
        return MetricObservation(
            name=name,
            state=MetricState.MEASURED,
            numerator=numerator,
            denominator=denominator,
            value=Decimal(numerator) / Decimal(denominator),
            reason=reason,
        )

    def build_metrics(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        outcomes: tuple[CompanyOutcomeProjection, ...],
        reviews: tuple[ReviewAssignment, ...],
        snapshots: tuple[CanonicalPipelineSnapshot, ...],
        incidents: tuple[SafetyIncident, ...] = (),
    ) -> MetricSnapshot:
        self._require_reviewer(principal)
        self._same_workspace(principal, run, *outcomes, *reviews, *incidents)
        total = len(outcomes)
        research_success = sum(
            item.outcome
            not in {
                CompanyOutcome.RESEARCH_FAILED,
                CompanyOutcome.RESEARCH_PARTIAL_REVIEW_REQUIRED,
            }
            for item in outcomes
        )
        evidence_sufficient = sum(
            item.outcome is not CompanyOutcome.INSUFFICIENT_EVIDENCE
            and item.outcome
            not in {
                CompanyOutcome.RESEARCH_FAILED,
                CompanyOutcome.RESEARCH_PARTIAL_REVIEW_REQUIRED,
            }
            for item in outcomes
        )
        opportunity_accepted = sum(
            item.outcome
            in {
                CompanyOutcome.AUDIT_REJECTED,
                CompanyOutcome.DEMO_REJECTED,
                CompanyOutcome.OUTREACH_REJECTED,
                CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED,
            }
            for item in outcomes
        )
        opportunity_reviews = sum(
            item.kind is ReviewKind.OPPORTUNITY_ACCEPTANCE and item.state is ReviewState.COMPLETED
            for item in reviews
        )
        opportunity_rejected = sum(
            item.outcome is CompanyOutcome.OPPORTUNITY_REJECTED for item in outcomes
        )
        audit_submitted = sum(
            item.outcome
            in {
                CompanyOutcome.AUDIT_REJECTED,
                CompanyOutcome.DEMO_REJECTED,
                CompanyOutcome.OUTREACH_REJECTED,
                CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED,
            }
            for item in outcomes
        )
        audit_approved = audit_submitted - sum(
            item.outcome is CompanyOutcome.AUDIT_REJECTED for item in outcomes
        )
        demo_submitted = audit_approved
        demo_approved = demo_submitted - sum(
            item.outcome is CompanyOutcome.DEMO_REJECTED for item in outcomes
        )
        outreach_submitted = demo_approved
        outreach_approved = sum(
            item.outcome is CompanyOutcome.CONTACT_PHASE_NOT_AUTHORIZED for item in outcomes
        )
        observations = (
            self._metric(MetricName.DISCOVERY_SUCCESS, total, total),
            self._metric(MetricName.RESEARCH_SUCCESS, research_success, total),
            self._metric(MetricName.EVIDENCE_SUFFICIENCY, evidence_sufficient, research_success),
            self._metric(MetricName.OPPORTUNITY_YIELD, opportunity_accepted, evidence_sufficient),
            self._metric(
                MetricName.OPPORTUNITY_REJECTION_RATE,
                opportunity_rejected,
                opportunity_reviews,
            ),
            self._metric(
                MetricName.CONTRADICTION_RATE,
                sum(item.contradiction_present for item in snapshots),
                len(snapshots),
            ),
            self._metric(MetricName.AUDIT_APPROVAL_RATE, audit_approved, audit_submitted),
            self._metric(MetricName.DEMO_APPROVAL_RATE, demo_approved, demo_submitted),
            self._metric(MetricName.OUTREACH_APPROVAL_RATE, outreach_approved, outreach_submitted),
            *(self._metric(name, None, None) for name in PERSON_CONTACT_METRICS),
            self._metric(
                MetricName.UNSUPPORTED_CLAIM_INCIDENCE,
                sum(item.unsupported_claim_present for item in snapshots),
                len(snapshots),
            ),
            self._metric(
                MetricName.PRIVACY_SOURCE_VIOLATIONS,
                sum(
                    item.event_type
                    in {
                        SafetyEventType.PROHIBITED_CONTACT_SOURCE_USAGE,
                        SafetyEventType.PRIVACY_OR_SUPPRESSION_VIOLATION,
                        SafetyEventType.UNAPPROVED_DATA_RETENTION,
                    }
                    for item in incidents
                ),
                total,
            ),
            self._metric(
                MetricName.CROSS_BUSINESS_CONTAMINATION,
                sum(
                    item.event_type is SafetyEventType.CROSS_BUSINESS_EVIDENCE_CONTAMINATION
                    for item in incidents
                ),
                total,
            ),
            self._metric(
                MetricName.HUMAN_REVIEW_DURATION_SECONDS,
                sum(item.duration_seconds or 0 for item in reviews),
                sum(item.duration_seconds is not None for item in reviews),
            ),
        )
        value = MetricSnapshot(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.phase-1-metrics@1",
            configuration_hash=stable_hash([item.model_dump(mode="json") for item in observations]),
            created_at=self._clock.now(),
            run_id=run.id,
            observations=observations,
        )
        self._repository.save(value)
        return value

    def build_cost_ledger(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        entries: tuple[CostEntry, ...],
    ) -> CostLedger:
        self._require_operator(principal)
        self._same_workspace(principal, run)
        required = set(CostCategory) - {CostCategory.AI}
        if not required.issubset({item.category for item in entries}):
            raise ShadowValidationInputError("cost ledger lacks a required stage category")
        for entry in entries:
            if entry.category is CostCategory.HUMAN_REVIEW_TIME and (
                entry.duration_seconds is None or entry.monetary_cost is not None
            ):
                raise ShadowValidationInputError(
                    "human review records measured time and no unapproved monetary conversion"
                )
        ai_entry = CostEntry(
            category=CostCategory.AI,
            company_id=None,
            operation_ref="m6.7a:no-qualified-ai-binding",
            monetary_cost=Decimal("0"),
            duration_seconds=None,
            pricing_version=None,
            reason=AI_ZERO_REASON,
        )
        complete_entries = (*entries, ai_entry)
        value = CostLedger(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.cost-ledger@1",
            configuration_hash=stable_hash(
                [item.model_dump(mode="json") for item in complete_entries]
            ),
            created_at=self._clock.now(),
            run_id=run.id,
            entries=complete_entries,
            ai_provider_cost=Decimal("0"),
        )
        self._repository.save(value)
        return value

    def record_safety_incident(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        event_type: SafetyEventType,
        evidence_refs: tuple[str, ...],
        *,
        candidate_id: UUID | None = None,
        requested_scope: StopScope | None = None,
        commercial_performance: Decimal | None = None,
    ) -> tuple[SafetyIncident, StopDecision]:
        self._require_operator(principal)
        self._same_workspace(principal, run)
        if not evidence_refs:
            raise ShadowValidationInputError("zero-tolerance incident requires evidence")
        incident = SafetyIncident(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.safety-incident@1",
            configuration_hash=stable_hash((run.id, event_type, evidence_refs, candidate_id)),
            created_at=self._clock.now(),
            run_id=run.id,
            candidate_id=candidate_id,
            event_type=event_type,
            evidence_refs=evidence_refs,
        )
        minimum_scope = (
            StopScope.RUN_TERMINATION
            if event_type in RUN_TERMINATING_EVENTS
            else StopScope.COHORT_PAUSE
        )
        scope = minimum_scope
        if requested_scope is StopScope.RUN_TERMINATION:
            scope = requested_scope
        if requested_scope is StopScope.COMPANY_QUARANTINE and minimum_scope is (
            StopScope.COHORT_PAUSE
        ):
            scope = StopScope.COHORT_PAUSE
        resulting = RunState.TERMINATED if scope is StopScope.RUN_TERMINATION else RunState.PAUSED
        decision = StopDecision(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.stop-decision@1",
            configuration_hash=stable_hash((incident.id, scope, resulting)),
            created_at=self._clock.now(),
            run_id=run.id,
            incident_id=incident.id,
            scope=scope,
            resulting_run_state=resulting,
        )
        _ = commercial_performance
        self._repository.save(incident)
        self._repository.save(decision)
        return incident, decision

    def quarantine_company(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        candidate_id: UUID,
        reason: str,
    ) -> StopDecision:
        self._require_operator(principal)
        self._same_workspace(principal, run)
        incident = SafetyIncident(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.company-quarantine@1",
            configuration_hash=stable_hash((run.id, candidate_id, reason)),
            created_at=self._clock.now(),
            run_id=run.id,
            candidate_id=candidate_id,
            event_type=SafetyEventType.UNSUPPORTED_FACTUAL_OUTREACH_CLAIM,
            evidence_refs=(reason,),
        )
        decision = StopDecision(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.company-quarantine@1",
            configuration_hash=stable_hash((incident.id, StopScope.COMPANY_QUARANTINE)),
            created_at=self._clock.now(),
            run_id=run.id,
            incident_id=incident.id,
            scope=StopScope.COMPANY_QUARANTINE,
            resulting_run_state=RunState.RUNNING,
        )
        self._repository.save(incident)
        self._repository.save(decision)
        return decision

    def generate_m68_package(
        self,
        principal: Principal,
        run: ShadowRunManifest,
        permissions: RealDataPermissionRelease,
        policy: CohortPolicy,
        frame: SamplingFrame,
        selection: CohortSelectionManifest,
        outcomes: tuple[CompanyOutcomeProjection, ...],
        reviews: tuple[ReviewAssignment, ...],
        metrics: MetricSnapshot,
        costs: CostLedger,
        incidents: tuple[SafetyIncident, ...],
        stops: tuple[StopDecision, ...],
        replays: tuple[ReplayAssessment, ...],
    ) -> M68EvidencePackage:
        self._require_reviewer(principal)
        self._same_workspace(
            principal,
            run,
            permissions,
            policy,
            frame,
            selection,
            *outcomes,
            *reviews,
            metrics,
            costs,
            *incidents,
            *stops,
        )
        permission_states = {item.activity: item.state for item in permissions.permissions}
        if any(state is not PermissionState.NOT_AUTHORIZED for state in permission_states.values()):
            raise ShadowValidationInputError(
                "M6.7A evidence requires all real permissions disabled"
            )
        value = M68EvidencePackage(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7a.synthetic-m68-evidence@1",
            configuration_hash=stable_hash(
                {
                    "run": run.configuration_hash,
                    "permissions": permissions.configuration_hash,
                    "selection": selection.configuration_hash,
                    "outcomes": [item.configuration_hash for item in outcomes],
                    "metrics": metrics.configuration_hash,
                    "costs": costs.configuration_hash,
                }
            ),
            created_at=self._clock.now(),
            run_id=run.id,
            input_manifest=(
                run.configuration_hash,
                permissions.configuration_hash,
                policy.configuration_hash,
                frame.frame_hash,
                selection.configuration_hash,
            ),
            permission_states=permission_states,
            cohort_policy_hash=policy.configuration_hash,
            sampling_frame_hash=frame.frame_hash,
            selection_manifest_hash=selection.configuration_hash,
            outcome_projection_hashes=tuple(item.configuration_hash for item in outcomes),
            review_record_hashes=tuple(item.configuration_hash for item in reviews),
            metric_snapshot_hash=metrics.configuration_hash,
            cost_ledger_hash=costs.configuration_hash,
            safety_incident_hashes=tuple(item.configuration_hash for item in incidents),
            stop_decision_hashes=tuple(item.configuration_hash for item in stops),
            capture_replay_assessments=replays,
            known_limitations=KNOWN_LIMITATIONS,
            unresolved_approvals=UNRESOLVED_APPROVALS,
        )
        self._repository.save(value)
        return value

    def authorize_shadow(self, principal: Principal, assessment_id: UUID) -> None:
        _ = (principal, assessment_id)
        raise ShadowValidationInputError("SHADOW_READY cannot be authorized or delivered")

    def get_record(self, principal: Principal, record_kind: str, record_id: UUID) -> ShadowRecord:
        value = self._repository.get(principal.workspace_id, record_kind, record_id)
        if value is None:
            raise ShadowNotFoundError()
        return value

    @staticmethod
    def _same_workspace(principal: Principal, *records: object) -> None:
        if any(getattr(item, "workspace_id", None) != principal.workspace_id for item in records):
            raise ShadowAuthorizationError()

    @staticmethod
    def _require_operator(principal: Principal) -> None:
        if not principal.can_operate():
            raise ShadowAuthorizationError()

    @staticmethod
    def _require_reviewer(principal: Principal) -> None:
        if not principal.can_review():
            raise ShadowAuthorizationError()
