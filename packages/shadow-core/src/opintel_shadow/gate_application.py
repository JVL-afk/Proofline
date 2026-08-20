"""M6.7C deterministic live-research gates and bounded Phase 1 orchestration."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import cast
from urllib.parse import urljoin, urlsplit
from uuid import UUID

from opintel_m0.ports import Clock, IdentifierFactory
from opintel_research.domain import RawHttpResponse, UrlPolicyError
from opintel_research.url_policy import PublicUrlPolicy, normalize_public_url

from opintel_shadow.domain import PermissionActivity, PermissionState, stable_hash
from opintel_shadow.gate_domain import (
    ApprovalState,
    BudgetExceeded,
    BudgetPolicyRevision,
    BudgetReservation,
    CheckState,
    CohortGateResult,
    DataHandlingPolicyRevision,
    DeletionAuditRecord,
    EgressReceipt,
    EgressRequest,
    EnvironmentAttestationRevision,
    KillSwitchRecord,
    KillSwitchState,
    LegalHold,
    LiveResearchNotAuthorized,
    LiveResearchPermissionRelease,
    LiveResearchPolicyError,
    LiveResearchStopped,
    OperationalRole,
    PreflightCheck,
    ReadinessState,
    RetentionPolicyRevision,
    RoleAssignmentRevision,
    SourceInstance,
    SourceKind,
    SourceRegistryRevision,
    StagedExecutionManifest,
    StageLineageRecord,
    StageProgression,
    SyntheticPreflightResult,
    SyntheticStoredArtifact,
    TermsReviewState,
    WorkItem,
    WorkLeaseError,
    WorkStage,
    WorkState,
)
from opintel_shadow.gate_ports import (
    GateRepository,
    HttpTransport,
    Resolver,
    SyntheticArtifactStore,
    WorkRepository,
)

_REDIRECTS = {301, 302, 303, 307, 308}
_INTERACTIVE_PATH_MARKERS = (
    "/login",
    "/signin",
    "/submit",
    "/booking",
    "/book-now",
    "/calendar",
    "/mailbox",
    "/webmail",
    "/chat",
)
_PREFLIGHT_CODES = (
    "POLICY_REVISIONS_PRESENT",
    "ROLES_ASSIGNED_AND_INDEPENDENT",
    "ENVIRONMENT_ATTESTATION_MECHANICS",
    "WORKLOAD_BUDGETS_PRESENT",
    "SOURCE_REGISTRY_VALID",
    "KILL_SWITCH_OPERATIONAL",
    "RETENTION_DELETION_OPERATIONAL",
    "DISCOVERY_RESEARCH_INDEPENDENT",
    "UNAUTHORIZED_REJECTS_BEFORE_DNS",
    "BROWSER_ABSENT",
    "PERSON_CONTACT_PATHS_ABSENT",
    "M6_STATE_PATH_ABSENT",
    "DELIVERY_DEPENDENCY_ABSENT",
    "AI_ROUTE_ABSENT",
    "CAPTURE_REPLAY_DETERMINISTIC",
    "COST_RESERVATION_FAILS_CLOSED",
)
_AUTHORIZATION_BLOCKERS = (
    "ADR_0071_ACCEPTED_POLICY_REQUIRED",
    "A08_RETENTION_VALUES_AND_APPROVAL_REQUIRED",
    "A09_EXACT_SOURCE_INSTANCES_AND_TERMS_APPROVAL_REQUIRED",
    "A17_QUALIFIED_TEXAS_RESEARCH_RELEASE_REQUIRED",
    "A03_TENANCY_APPROVAL_REQUIRED",
    "A04_EXACT_PROVIDER_REGION_KEYS_BACKUP_APPROVAL_REQUIRED",
    "A07_IDENTITY_ACCESS_APPROVAL_REQUIRED",
    "A18_MONETARY_BUDGET_APPROVAL_REQUIRED",
    "NAMED_OPERATIONAL_ROLE_ASSIGNMENTS_REQUIRED",
    "PHASE1_24_COMPANY_COHORT_OWNER_APPROVAL_REQUIRED",
    "SEPARATE_DISCOVERY_PERMISSION_AUTHORIZATION_REQUIRED",
    "SEPARATE_RESEARCH_PERMISSION_AUTHORIZATION_REQUIRED",
)


def _record_hash(record: object) -> str:
    if hasattr(record, "model_dump"):
        return stable_hash(record.model_dump(mode="json"))
    return stable_hash(record)


class LiveResearchGateService:
    """M6.7C policy gate with no command capable of authorizing a live release."""

    def __init__(
        self,
        repository: GateRepository,
        artifact_store: SyntheticArtifactStore,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._artifacts = artifact_store
        self._clock = clock
        self._ids = identifiers

    def create_not_authorized_releases(
        self,
        workspace_id: UUID,
        source_registry: SourceRegistryRevision,
        retention: RetentionPolicyRevision,
        environment: EnvironmentAttestationRevision,
        cohort_policy_id: UUID,
        kill_switch: KillSwitchRecord,
    ) -> tuple[LiveResearchPermissionRelease, LiveResearchPermissionRelease]:
        records: list[LiveResearchPermissionRelease] = []
        for activity in (
            PermissionActivity.REAL_BUSINESS_DISCOVERY,
            PermissionActivity.REAL_PUBLIC_RESEARCH,
        ):
            payload = {
                "activity": activity,
                "source": _record_hash(source_registry),
                "retention": _record_hash(retention),
                "environment": _record_hash(environment),
                "cohort": cohort_policy_id,
                "state": PermissionState.NOT_AUTHORIZED,
            }
            release = LiveResearchPermissionRelease(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version=f"m6.7c.{activity.value}@1",
                configuration_hash=stable_hash(payload),
                created_at=self._clock.now(),
                activity=activity,
                state=PermissionState.NOT_AUTHORIZED,
                source_registry_id=source_registry.id,
                source_registry_hash=_record_hash(source_registry),
                retention_policy_id=retention.id,
                retention_policy_hash=_record_hash(retention),
                environment_id=environment.id,
                environment_hash=_record_hash(environment),
                cohort_policy_id=cohort_policy_id,
                cohort_or_run_restriction="UNRESOLVED_FUTURE_FROZEN_SCOPE",
                starts_at=self._clock.now(),
                expires_at=min(
                    source_registry.expires_at,
                    retention.expires_at,
                    environment.expires_at,
                ),
                approval_ids=(),
                kill_switch_id=kill_switch.id,
            )
            self._repository.save(release)
            records.append(release)
        return records[0], records[1]

    def trip_kill_switch(
        self,
        current: KillSwitchRecord,
        roles: RoleAssignmentRevision,
        operator_ref: str,
        reason: str,
    ) -> KillSwitchRecord:
        assigned = {item.role: item.subject_ref for item in roles.assignments}[
            OperationalRole.KILL_SWITCH_OPERATOR
        ]
        if operator_ref != assigned:
            raise LiveResearchPolicyError("only the assigned kill-switch operator may trip it")
        if not reason.strip():
            raise LiveResearchPolicyError("kill-switch reason is required")
        successor = current.model_copy(
            update={
                "id": self._ids.new(),
                "version": f"{current.version}.trip",
                "configuration_hash": stable_hash(
                    (current.configuration_hash, operator_ref, reason, self._clock.now())
                ),
                "created_at": self._clock.now(),
                "state": KillSwitchState.TRIPPED,
                "operator_ref": operator_ref,
                "reason": reason,
                "activated_at": self._clock.now(),
            }
        )
        self._repository.save(successor)
        return successor

    def suspend_release(
        self,
        release: LiveResearchPermissionRelease,
        reason: str,
    ) -> LiveResearchPermissionRelease:
        if not reason.strip():
            raise LiveResearchPolicyError("suspension reason is required")
        successor = release.model_copy(
            update={
                "id": self._ids.new(),
                "version": f"{release.version}.suspended",
                "configuration_hash": stable_hash(
                    (release.configuration_hash, reason, self._clock.now())
                ),
                "created_at": self._clock.now(),
                "state": PermissionState.SUSPENDED,
                "suspended_reason": reason,
                "revoked_at": self._clock.now(),
            }
        )
        self._repository.save(successor)
        return successor

    def reserve_budget(
        self,
        workspace_id: UUID,
        policy: BudgetPolicyRevision,
        operation_ref: str,
        logical_fetches: int,
        total_attempts: int,
        response_bytes: int,
        monetary_usd: Decimal | None,
    ) -> BudgetReservation:
        if min(logical_fetches, total_attempts, response_bytes) < 0:
            raise BudgetExceeded("negative reservations are invalid")
        latest_by_operation: dict[str, BudgetReservation] = {}
        for value in self._repository.list(workspace_id, "budget_reservation"):
            reservation = cast(BudgetReservation, value)
            latest_by_operation[reservation.operation_ref] = reservation
        existing = tuple(latest_by_operation.values())
        if sum(item.logical_fetches for item in existing) + logical_fetches > 120:
            raise BudgetExceeded("logical fetch capacity exhausted")
        if sum(item.total_attempts for item in existing) + total_attempts > 360:
            raise BudgetExceeded("attempt capacity exhausted")
        if sum(item.response_bytes for item in existing) + response_bytes > 36_000_000:
            raise BudgetExceeded("response-byte capacity exhausted")
        if monetary_usd is not None and not policy.monetary_approval_complete:
            raise BudgetExceeded("paid operation has no approved monetary envelope")
        value = BudgetReservation(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7c.budget-reservation@1",
            configuration_hash=stable_hash(
                (operation_ref, logical_fetches, total_attempts, response_bytes, monetary_usd)
            ),
            created_at=self._clock.now(),
            budget_policy_id=policy.id,
            operation_ref=operation_ref,
            logical_fetches=logical_fetches,
            total_attempts=total_attempts,
            response_bytes=response_bytes,
            monetary_usd=monetary_usd,
        )
        self._repository.save(value)
        return value

    def reconcile_budget(
        self,
        reservation: BudgetReservation,
        *,
        actual_logical_fetches: int,
        actual_total_attempts: int,
        actual_response_bytes: int,
        actual_monetary_usd: Decimal | None,
    ) -> BudgetReservation:
        if reservation.reconciled:
            raise BudgetExceeded("reservation is already reconciled")
        actuals = (actual_logical_fetches, actual_total_attempts, actual_response_bytes)
        reserved = (
            reservation.logical_fetches,
            reservation.total_attempts,
            reservation.response_bytes,
        )
        if any(actual < 0 for actual in actuals) or any(
            actual > limit for actual, limit in zip(actuals, reserved, strict=True)
        ):
            raise BudgetExceeded("actual usage exceeds its reservation")
        if actual_monetary_usd is not None and (
            reservation.monetary_usd is None or actual_monetary_usd > reservation.monetary_usd
        ):
            raise BudgetExceeded("actual monetary usage exceeds its reservation")
        successor = reservation.model_copy(
            update={
                "id": self._ids.new(),
                "version": f"{reservation.version}.reconciled",
                "configuration_hash": stable_hash(
                    (reservation.configuration_hash, actuals, actual_monetary_usd)
                ),
                "created_at": self._clock.now(),
                "logical_fetches": actual_logical_fetches,
                "total_attempts": actual_total_attempts,
                "response_bytes": actual_response_bytes,
                "monetary_usd": actual_monetary_usd,
                "reconciled": True,
            }
        )
        self._repository.save(successor)
        return successor

    def delete_expired_artifact(
        self,
        workspace_id: UUID,
        artifact: SyntheticStoredArtifact,
        policy: RetentionPolicyRevision,
        legal_holds: tuple[LegalHold, ...],
    ) -> DeletionAuditRecord:
        if artifact.retention_policy_id != policy.id:
            raise LiveResearchPolicyError("artifact does not bind this retention policy")
        decision = next(item for item in policy.decisions if item.data_class is artifact.data_class)
        eligible_at = artifact.created_at + timedelta(seconds=decision.retention_seconds)
        if self._clock.now() < eligible_at:
            raise LiveResearchPolicyError("artifact is not retention-expired")
        if any(
            hold.data_class is artifact.data_class
            and hold.effective_at <= self._clock.now() < hold.expires_at
            for hold in legal_holds
        ):
            raise LiveResearchPolicyError("active legal hold blocks deletion")
        if not self._artifacts.exists(workspace_id, artifact.artifact_ref):
            raise LiveResearchPolicyError("artifact is missing")
        self._artifacts.delete(workspace_id, artifact.artifact_ref)
        audit = DeletionAuditRecord(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7c.deletion-audit@1",
            configuration_hash=stable_hash(
                (artifact.artifact_ref, policy.id, eligible_at, self._clock.now())
            ),
            created_at=self._clock.now(),
            data_class=artifact.data_class,
            artifact_ref=artifact.artifact_ref,
            retention_policy_id=policy.id,
            eligible_at=eligible_at,
            deleted_at=self._clock.now(),
            deletion_behavior=decision.deletion_behavior,
            backup_handling=decision.backup_handling,
            tombstone_ref=f"tombstone:{stable_hash(artifact.artifact_ref)}",
            superseded_artifact=artifact.superseded,
        )
        self._repository.save(audit)
        return audit

    def evaluate_cohort_freeze(
        self,
        workspace_id: UUID,
        *,
        cohort_policy_accepted: bool,
        target_owner_approved: bool,
        source_registry: SourceRegistryRevision | None,
        environment: EnvironmentAttestationRevision | None,
        retention: RetentionPolicyRevision | None,
        a17_approved: bool,
        roles: RoleAssignmentRevision | None,
        budget: BudgetPolicyRevision | None,
        discovery_release: LiveResearchPermissionRelease | None,
    ) -> CohortGateResult:
        blockers: list[str] = []
        if not cohort_policy_accepted:
            blockers.append("COHORT_POLICY_NOT_ACCEPTED")
        if not target_owner_approved:
            blockers.append("TARGET_24_NOT_OWNER_APPROVED")
        if source_registry is None or source_registry.state is not ApprovalState.APPROVED:
            blockers.append("SOURCE_REGISTRY_NOT_APPROVED")
        if environment is None or environment.state is not ApprovalState.APPROVED:
            blockers.append("ENVIRONMENT_NOT_APPROVED")
        if retention is None or retention.state is not ApprovalState.APPROVED:
            blockers.append("RETENTION_NOT_APPROVED")
        if not a17_approved:
            blockers.append("A17_NOT_APPROVED")
        if roles is None or roles.state is not ApprovalState.APPROVED:
            blockers.append("ROLES_NOT_APPROVED")
        if budget is None or budget.state is not ApprovalState.APPROVED:
            blockers.append("BUDGET_NOT_APPROVED")
        if (
            discovery_release is None
            or discovery_release.activity is not PermissionActivity.REAL_BUSINESS_DISCOVERY
            or discovery_release.state is not PermissionState.AUTHORIZED
        ):
            blockers.append("DISCOVERY_NOT_AUTHORIZED")
        result = CohortGateResult(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7c.cohort-gate@1",
            configuration_hash=stable_hash(blockers),
            created_at=self._clock.now(),
            can_freeze=not blockers,
            blockers=tuple(blockers),
            discovery_release_id=None if discovery_release is None else discovery_release.id,
        )
        self._repository.save(result)
        return result

    def create_staged_execution(
        self,
        workspace_id: UUID,
        frozen_cohort_hash: str,
        frozen_order: tuple[str, ...],
        small_batch_size: int,
    ) -> StagedExecutionManifest:
        if len(frozen_order) != 24 or len(set(frozen_order)) != 24:
            raise LiveResearchPolicyError("staged execution requires a frozen unique 24-slot order")
        record = StagedExecutionManifest(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7c.staged-execution@1",
            configuration_hash=stable_hash((frozen_cohort_hash, frozen_order, small_batch_size)),
            created_at=self._clock.now(),
            frozen_cohort_hash=frozen_cohort_hash,
            frozen_candidate_order=frozen_order,
            progression=StageProgression.STAGE_0_PREFLIGHT,
            small_batch_size=small_batch_size,
            completed_candidate_ids=(),
            recorded_outcomes={},
            continuation_approval_ids=(),
        )
        self._repository.save(record)
        return record

    def advance_stage(
        self,
        current: StagedExecutionManifest,
        *,
        completed_outcomes: dict[str, str],
        continuation_approval_id: str | None = None,
    ) -> StagedExecutionManifest:
        transitions = {
            StageProgression.STAGE_0_PREFLIGHT: StageProgression.STAGE_1_SLOT_ONE,
            StageProgression.STAGE_1_SLOT_ONE: StageProgression.STAGE_1_PAUSED,
            StageProgression.STAGE_1_PAUSED: StageProgression.STAGE_2_SMALL_BATCH,
            StageProgression.STAGE_2_SMALL_BATCH: StageProgression.STAGE_2_PAUSED,
            StageProgression.STAGE_2_PAUSED: StageProgression.STAGE_3_REMAINDER,
            StageProgression.STAGE_3_REMAINDER: StageProgression.COMPLETE,
        }
        if current.progression is StageProgression.COMPLETE:
            raise LiveResearchPolicyError("staged execution is already complete")
        if (
            current.progression
            in {
                StageProgression.STAGE_1_PAUSED,
                StageProgression.STAGE_2_PAUSED,
            }
            and not continuation_approval_id
        ):
            raise LiveResearchPolicyError("paused stage requires explicit continuation approval")
        if not set(completed_outcomes).issubset(current.frozen_candidate_order):
            raise LiveResearchPolicyError("outcomes cannot alter the frozen cohort")
        for candidate_id, outcome in completed_outcomes.items():
            existing = current.recorded_outcomes.get(candidate_id)
            if existing is not None and existing != outcome:
                raise LiveResearchPolicyError("a recorded cohort outcome is immutable")
        merged = {**current.recorded_outcomes, **completed_outcomes}
        if (
            current.progression is StageProgression.STAGE_1_SLOT_ONE
            and tuple(merged) != current.frozen_candidate_order[:1]
        ):
            raise LiveResearchPolicyError("slot-one stage must record only frozen slot one")
        if current.progression is StageProgression.STAGE_2_SMALL_BATCH:
            expected = current.frozen_candidate_order[: 1 + current.small_batch_size]
            if tuple(merged) != expected:
                raise LiveResearchPolicyError(
                    "small-batch stage must preserve frozen contiguous order"
                )
        if (
            current.progression is StageProgression.STAGE_3_REMAINDER
            and tuple(merged) != current.frozen_candidate_order
        ):
            raise LiveResearchPolicyError(
                "remainder stage must preserve all frozen cohort outcomes"
            )
        successor = current.model_copy(
            update={
                "id": self._ids.new(),
                "version": f"{current.version}.next",
                "configuration_hash": stable_hash(
                    (current.configuration_hash, transitions[current.progression], merged)
                ),
                "created_at": self._clock.now(),
                "progression": transitions[current.progression],
                "completed_candidate_ids": tuple(
                    item for item in current.frozen_candidate_order if item in merged
                ),
                "recorded_outcomes": merged,
                "continuation_approval_ids": current.continuation_approval_ids
                + (() if continuation_approval_id is None else (continuation_approval_id,)),
            }
        )
        self._repository.save(successor)
        return successor

    def build_preflight(
        self,
        workspace_id: UUID,
        passed_evidence: dict[str, tuple[str, ...]],
        *,
        data_policy: DataHandlingPolicyRevision,
        retention: RetentionPolicyRevision,
        source_registry: SourceRegistryRevision,
        environment: EnvironmentAttestationRevision,
        roles: RoleAssignmentRevision,
        budget: BudgetPolicyRevision,
        kill_switch: KillSwitchRecord,
    ) -> SyntheticPreflightResult:
        persisted_releases = self._repository.list(workspace_id, "live_research_permission")
        if any(
            cast(LiveResearchPermissionRelease, item).state is PermissionState.AUTHORIZED
            for item in persisted_releases
        ):
            raise LiveResearchPolicyError(
                "M6.7C preflight refuses a workspace containing an authorized live release"
            )
        effective_evidence = dict(passed_evidence)
        now = self._clock.now()
        records = (
            data_policy,
            retention,
            source_registry,
            environment,
            roles,
            budget,
            kill_switch,
        )
        if any(record.workspace_id != workspace_id for record in records):
            effective_evidence.pop("POLICY_REVISIONS_PRESENT", None)
        if not (
            data_policy.state is ApprovalState.APPROVED
            and retention.state is ApprovalState.APPROVED
            and data_policy.effective_at <= now < data_policy.expires_at
            and retention.effective_at <= now < retention.expires_at
            and data_policy.approval_ids
            and retention.approval_ids
        ):
            effective_evidence.pop("POLICY_REVISIONS_PRESENT", None)
        if not (
            roles.state is ApprovalState.APPROVED
            and roles.effective_at <= now < roles.expires_at
            and roles.approval_ids
            and roles.synthetic_assignments
        ):
            effective_evidence.pop("ROLES_ASSIGNED_AND_INDEPENDENT", None)
        if not (
            environment.state is ApprovalState.APPROVED
            and environment.effective_at <= now < environment.expires_at
            and environment.approval_ids
            and environment.synthetic_attestation
        ):
            effective_evidence.pop("ENVIRONMENT_ATTESTATION_MECHANICS", None)
        if not (
            budget.state is ApprovalState.APPROVED
            and budget.effective_at <= now < budget.expires_at
            and budget.approval_ids
            and budget.ai_budget_usd == Decimal("0")
        ):
            effective_evidence.pop("WORKLOAD_BUDGETS_PRESENT", None)
        if not (
            source_registry.state is ApprovalState.APPROVED
            and source_registry.effective_at <= now < source_registry.expires_at
            and source_registry.approval_ids
            and source_registry.browser_policy == "DISABLED"
            and {source.kind for source in source_registry.sources} == set(SourceKind)
            and all(
                source.terms_review_state is TermsReviewState.APPROVED
                and source.effective_at <= now < source.expires_at
                for source in source_registry.sources
            )
        ):
            effective_evidence.pop("SOURCE_REGISTRY_VALID", None)
        assigned_kill_operator = {item.role: item.subject_ref for item in roles.assignments}.get(
            OperationalRole.KILL_SWITCH_OPERATOR
        )
        if not (
            kill_switch.state is KillSwitchState.CLEAR
            and assigned_kill_operator == kill_switch.operator_ref
        ):
            effective_evidence.pop("KILL_SWITCH_OPERATIONAL", None)
        checks = tuple(
            PreflightCheck(
                code=code,
                state=(CheckState.PASS if effective_evidence.get(code, ()) else CheckState.FAIL),
                evidence_refs=effective_evidence.get(code, ()),
            )
            for code in _PREFLIGHT_CODES
        )
        readiness = (
            ReadinessState.READY_FOR_REAL_RESEARCH_AUTHORIZATION
            if all(item.state is CheckState.PASS for item in checks)
            else ReadinessState.NOT_READY_FOR_REAL_RESEARCH_AUTHORIZATION
        )
        result = SyntheticPreflightResult(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.7c.synthetic-preflight@1",
            configuration_hash=stable_hash({item.code: item.evidence_refs for item in checks}),
            created_at=self._clock.now(),
            checks=checks,
            readiness=readiness,
            authorization_blockers=_AUTHORIZATION_BLOCKERS,
            permission_states={
                activity: PermissionState.NOT_AUTHORIZED for activity in PermissionActivity
            },
        )
        self._repository.save(result)
        return result


class ControlledEgressService:
    """Exact-source HTTP gate using M1 URL/DNS/SSRF policy and a supplied fake transport."""

    def __init__(self, resolver: Resolver, transport: HttpTransport, clock: Clock) -> None:
        self._resolver = resolver
        self._transport = transport
        self._clock = clock

    def fetch(
        self,
        request: EgressRequest,
        release: LiveResearchPermissionRelease,
        source_registry: SourceRegistryRevision,
        retention: RetentionPolicyRevision,
        environment: EnvironmentAttestationRevision,
        kill_switch: KillSwitchRecord,
    ) -> EgressReceipt:
        source = self._preflight(
            request, release, source_registry, retention, environment, kill_switch
        )
        policy = PublicUrlPolicy(self._resolver)
        try:
            current = normalize_public_url(request.url)
        except UrlPolicyError as error:
            raise LiveResearchPolicyError("M1 public URL policy rejected target") from error
        transport_calls = 0
        for redirect_count in range(6):
            try:
                target = policy.validate(current, source.host)
            except UrlPolicyError as error:
                raise LiveResearchPolicyError("M1 public URL policy rejected target") from error
            response = self._transport.request(target, 8.0, source.max_response_bytes)
            transport_calls += 1
            if response.status_code in _REDIRECTS:
                location = dict(response.headers).get("location")
                if not location or redirect_count == 5:
                    raise LiveResearchPolicyError("invalid or excessive redirect")
                current = urljoin(current, location)
                continue
            if not 200 <= response.status_code < 300:
                raise LiveResearchPolicyError("non-success fake response")
            if len(response.body) > source.max_response_bytes:
                raise LiveResearchPolicyError("response exceeds source budget")
            try:
                normalized_url = normalize_public_url(request.url)
                final_url = normalize_public_url(current)
            except UrlPolicyError as error:
                raise LiveResearchPolicyError("M1 public URL policy rejected target") from error
            return EgressReceipt(
                source_id=source.source_id,
                normalized_url=normalized_url,
                final_url=final_url,
                status_code=response.status_code,
                response_bytes=len(response.body),
                transport_calls=transport_calls,
            )
        raise LiveResearchPolicyError("redirect processing failed")

    def _preflight(
        self,
        request: EgressRequest,
        release: LiveResearchPermissionRelease,
        registry: SourceRegistryRevision,
        retention: RetentionPolicyRevision,
        environment: EnvironmentAttestationRevision,
        kill_switch: KillSwitchRecord,
    ) -> SourceInstance:
        now = self._clock.now()
        if kill_switch.state is KillSwitchState.TRIPPED:
            raise LiveResearchStopped("Phase 1 kill switch is active")
        if release.state is not PermissionState.AUTHORIZED:
            raise LiveResearchNotAuthorized("permission is not authorized")
        if request.expected_release_id != release.id or request.activity is not release.activity:
            raise LiveResearchNotAuthorized("request does not bind the exact permission")
        if request.expected_configuration_hash != release.configuration_hash:
            raise LiveResearchNotAuthorized("permission configuration hash mismatch")
        if not release.starts_at <= now < release.expires_at:
            raise LiveResearchNotAuthorized("permission is not currently effective")
        if (
            release.source_registry_id != registry.id
            or release.source_registry_hash != _record_hash(registry)
        ):
            raise LiveResearchPolicyError("source registry revision mismatch")
        if (
            release.retention_policy_id != retention.id
            or release.retention_policy_hash != _record_hash(retention)
        ):
            raise LiveResearchPolicyError("retention revision mismatch")
        if release.environment_id != environment.id or release.environment_hash != _record_hash(
            environment
        ):
            raise LiveResearchPolicyError("environment revision mismatch")
        for record in (registry, retention, environment):
            if record.state is not ApprovalState.APPROVED:
                raise LiveResearchPolicyError("bound control revision is not approved")
            if not record.effective_at <= now < record.expires_at:
                raise LiveResearchPolicyError("bound control revision is not current")
        expected_kind = (
            SourceKind.DISCOVERY_SOURCE
            if request.activity is PermissionActivity.REAL_BUSINESS_DISCOVERY
            else SourceKind.RESEARCH_SOURCE
        )
        source = next(
            (
                item
                for item in registry.sources
                if item.source_id == request.source_id and item.kind is expected_kind
            ),
            None,
        )
        if source is None:
            raise LiveResearchPolicyError("source is unregistered for this activity")
        if not source.effective_at <= now < source.expires_at:
            raise LiveResearchPolicyError("source approval is not current")
        if source.terms_review_state is not TermsReviewState.APPROVED:
            raise LiveResearchPolicyError("source terms review is not approved")
        parsed = urlsplit(request.url)
        if (parsed.hostname or "").lower().rstrip(".") != source.host:
            raise LiveResearchPolicyError("request host does not match exact source")
        if parsed.scheme.lower() != source.scheme:
            raise LiveResearchPolicyError("request scheme does not match exact source")
        path = parsed.path.lower()
        if any(marker in path for marker in _INTERACTIVE_PATH_MARKERS):
            raise LiveResearchPolicyError("interactive endpoint is prohibited")
        return source


class BoundedPhaseOneOrchestrator:
    """Small database-backed orchestrator with leases, replay safety, and immutable lineage."""

    def __init__(
        self,
        work_repository: WorkRepository,
        records: GateRepository,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._work = work_repository
        self._records = records
        self._clock = clock
        self._ids = identifiers

    def enqueue(
        self,
        workspace_id: UUID,
        idempotency_key: str,
        stage: WorkStage,
        payload_hash: str,
        max_attempts: int = 3,
    ) -> tuple[WorkItem, bool]:
        if not idempotency_key.strip() or not payload_hash.strip():
            raise WorkLeaseError("idempotency key and payload hash are required")
        if max_attempts < 1 or max_attempts > 3:
            raise WorkLeaseError("attempt bound must be between one and three")
        item = WorkItem(
            id=self._ids.new(),
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            stage=stage,
            payload_hash=payload_hash,
            state=WorkState.QUEUED,
            attempt_count=0,
            max_attempts=max_attempts,
            version=1,
        )
        return self._work.enqueue(item)

    def claim(
        self,
        workspace_id: UUID,
        worker_ref: str,
        kill_switch: KillSwitchRecord,
        lease_seconds: int = 30,
        paused: bool = False,
    ) -> WorkItem | None:
        if kill_switch.state is KillSwitchState.TRIPPED:
            raise LiveResearchStopped("kill switch blocks new and queued work")
        if paused:
            raise LiveResearchStopped("cohort pause blocks new and queued work")
        if lease_seconds <= 0:
            raise WorkLeaseError("lease must be positive")
        item = self._work.claim(workspace_id, worker_ref, self._clock.now(), lease_seconds)
        if item is not None:
            self._lineage(item, "LEASED", worker_ref, None)
        return item

    def complete(
        self,
        item: WorkItem,
        worker_ref: str,
        output_hash: str,
        kill_switch: KillSwitchRecord,
    ) -> WorkItem:
        self._assert_owner(item, worker_ref)
        if kill_switch.state is KillSwitchState.TRIPPED:
            raise LiveResearchStopped("stale worker cannot persist after kill activation")
        updated = item.model_copy(
            update={
                "state": WorkState.SUCCEEDED,
                "version": item.version + 1,
                "lease_owner": None,
                "lease_expires_at": None,
            }
        )
        saved = self._work.save_work(updated, item.version)
        self._lineage(saved, "SUCCEEDED", worker_ref, output_hash)
        return saved

    def fail_or_retry(
        self,
        item: WorkItem,
        worker_ref: str,
        retryable: bool,
        kill_switch: KillSwitchRecord,
    ) -> WorkItem:
        self._assert_owner(item, worker_ref)
        if kill_switch.state is KillSwitchState.TRIPPED:
            raise LiveResearchStopped("kill switch prevents retry issuance")
        should_retry = retryable and item.attempt_count < item.max_attempts
        updated = item.model_copy(
            update={
                "state": WorkState.QUEUED if should_retry else WorkState.FAILED,
                "version": item.version + 1,
                "lease_owner": None,
                "lease_expires_at": None,
            }
        )
        saved = self._work.save_work(updated, item.version)
        self._lineage(saved, "RETRY_QUEUED" if should_retry else "FAILED", worker_ref, None)
        return saved

    def pause(self, item: WorkItem, worker_ref: str) -> WorkItem:
        self._assert_owner(item, worker_ref)
        updated = item.model_copy(
            update={
                "state": WorkState.PAUSED,
                "version": item.version + 1,
                "lease_owner": None,
                "lease_expires_at": None,
            }
        )
        saved = self._work.save_work(updated, item.version)
        self._lineage(saved, "PAUSED", worker_ref, None)
        return saved

    def recover_stale(self, workspace_id: UUID) -> int:
        return self._work.recover_stale(workspace_id, self._clock.now())

    @staticmethod
    def _assert_owner(item: WorkItem, worker_ref: str) -> None:
        if item.state is not WorkState.LEASED or item.lease_owner != worker_ref:
            raise WorkLeaseError("worker does not hold the active lease")

    def _lineage(
        self, item: WorkItem, event: str, worker_ref: str | None, output_hash: str | None
    ) -> None:
        record = StageLineageRecord(
            id=self._ids.new(),
            workspace_id=item.workspace_id,
            version="m6.7c.stage-lineage@1",
            configuration_hash=stable_hash(
                (item.id, event, item.attempt_count, worker_ref, output_hash)
            ),
            created_at=self._clock.now(),
            work_item_id=item.id,
            event=event,
            input_hash=item.payload_hash,
            output_hash=output_hash,
            attempt_number=item.attempt_count,
            worker_ref=worker_ref,
        )
        self._records.save(record)


def fake_response(
    status_code: int, body: bytes = b"fixture", location: str | None = None
) -> RawHttpResponse:
    headers = () if location is None else (("location", location),)
    return RawHttpResponse(status_code=status_code, headers=headers, body=body)


def all_preflight_evidence() -> dict[str, tuple[str, ...]]:
    """Complete synthetic evidence map; it never represents live approval."""

    return {code: (f"fixture://m6.7c/preflight/{code.lower()}",) for code in _PREFLIGHT_CODES}


__all__ = [
    "BoundedPhaseOneOrchestrator",
    "ControlledEgressService",
    "LiveResearchGateService",
    "all_preflight_evidence",
    "fake_response",
]
