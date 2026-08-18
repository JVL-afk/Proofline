"""Authorized M4 commands plus the narrow capability-scoped runtime service."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from opintel_audit.domain import (
    AuditKind,
    AuditReviewDecisionType,
    AuditRevisionState,
    AuditValidity,
)
from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory
from opintel_opportunity.domain import HypothesisStatus, ReviewDecisionType

from opintel_demo.composition import APPROVED_DEFINITION
from opintel_demo.domain import (
    DemoAuthorizationError,
    DemoBundle,
    DemoCanonicalInputs,
    DemoNotFoundError,
    DemoOperation,
    DemoOperationStatus,
    DemoReviewDecision,
    DemoReviewDecisionType,
    DemoRevisionState,
    DemoRevocation,
    DemoSessionError,
    DemoValidationError,
    DemoValidity,
    RuntimeSession,
    RuntimeSessionView,
    SessionIssuance,
    SessionState,
    TelemetryEvent,
)
from opintel_demo.policy import CSP
from opintel_demo.ports import CapabilityFactory, DemoRepository, DemoSourceCatalog
from opintel_demo.runtime import DeterministicDemoRuntime

ISSUANCE_LIFETIME = timedelta(minutes=15)
RUNTIME_SESSION_LIFETIME = timedelta(minutes=60)
ALLOWED_TELEMETRY_EVENTS = frozenset(
    {
        "session_start",
        "session_end",
        "state_entered",
        "transition_outcome",
        "mock_action_outcome",
        "safe_error",
    }
)


class DemoApplicationService:
    def __init__(
        self,
        repository: DemoRepository,
        source: DemoSourceCatalog,
        clock: Clock,
        identifiers: IdentifierFactory,
        capabilities: CapabilityFactory,
        *,
        issuance_enabled: bool = True,
        runtime_origin: str = "http://127.0.0.1:8100",
    ) -> None:
        self._repository = repository
        self._source = source
        self._clock = clock
        self._ids = identifiers
        self._capabilities = capabilities
        self._issuance_enabled = issuance_enabled
        self.runtime_origin = runtime_origin

    def start_generation(
        self,
        principal: Principal,
        audit_revision_id: UUID,
        expected_audit_revision_hash: str,
        idempotency_key: str,
        parent_revision_id: UUID | None = None,
    ) -> tuple[DemoOperation, bool]:
        if not principal.can_operate():
            raise DemoAuthorizationError()
        source = self._source.get_inputs(principal.workspace_id, audit_revision_id)
        if source is None:
            raise DemoNotFoundError()
        self._require_eligible(source)
        if source.audit.revision.revision_hash != expected_audit_revision_hash:
            raise DemoValidationError("audit revision precondition failed")
        demo_id = self._ids.new()
        if parent_revision_id is not None:
            parent = self.get_revision(principal, parent_revision_id)
            if parent.revision.audit_id != source.audit.revision.audit_id:
                raise DemoValidationError("parent revision belongs to another audit")
            demo_id = parent.revision.demo_id
        now = self._clock.now()
        operation = DemoOperation(
            self._ids.new(),
            principal.workspace_id,
            source.audit.revision.business_id,
            audit_revision_id,
            expected_audit_revision_hash,
            demo_id,
            parent_revision_id,
            DemoOperationStatus.PENDING,
            idempotency_key,
            self._ids.new(),
            0,
            3,
            principal.subject,
            now,
            now,
        )
        return self._repository.create_or_get_operation(operation)

    def get_operation(self, principal: Principal, operation_id: UUID) -> DemoOperation:
        value = self._repository.get_operation(principal.workspace_id, operation_id)
        if value is None:
            raise DemoNotFoundError()
        return value

    def get_revision(self, principal: Principal, revision_id: UUID) -> DemoBundle:
        value = self.get_current_bundle(principal.workspace_id, revision_id)
        if value is None:
            raise DemoNotFoundError()
        return value

    def get_current_bundle(self, workspace_id: UUID, revision_id: UUID) -> DemoBundle | None:
        value = self._repository.get_revision(workspace_id, revision_id)
        if value is None:
            return None
        if value.revocation is not None:
            return replace(value, revision=replace(value.revision, validity=DemoValidity.REVOKED))
        source = self._source.get_inputs(workspace_id, value.revision.manifest.audit_revision_id)
        if source is None or not self._matches_manifest(value, source):
            return replace(
                value,
                revision=replace(value.revision, validity=DemoValidity.STALE_INPUTS),
                review_valid=False,
            )
        try:
            self._require_eligible(source)
        except DemoValidationError:
            return replace(
                value,
                revision=replace(value.revision, validity=DemoValidity.STALE_INPUTS),
                review_valid=False,
            )
        return value

    def list_revisions(self, principal: Principal, demo_id: UUID) -> tuple[DemoBundle, ...]:
        return self._repository.list_revisions(principal.workspace_id, demo_id)

    def review(
        self,
        principal: Principal,
        revision_id: UUID,
        expected_revision_hash: str,
        expected_manifest_hash: str,
        expected_specification_hash: str,
        decision_type: DemoReviewDecisionType,
        reason: str,
    ) -> DemoBundle:
        if not principal.can_review():
            raise DemoAuthorizationError()
        bundle = self.get_revision(principal, revision_id)
        revision = bundle.revision
        if (
            revision.revision_hash != expected_revision_hash
            or revision.manifest.checksum != expected_manifest_hash
            or revision.specification_hash != expected_specification_hash
        ):
            raise DemoValidationError("demo revision precondition failed")
        if revision.validity != DemoValidity.CURRENT:
            raise DemoValidationError("demo inputs are not current")
        if not revision.hard_qc_passed:
            raise DemoValidationError("demo hard QC failures cannot be overridden")
        if revision.state not in {
            DemoRevisionState.REVIEW_REQUIRED,
            DemoRevisionState.APPROVED,
            DemoRevisionState.REJECTED,
            DemoRevisionState.REVISION_REQUESTED,
        }:
            raise DemoValidationError("demo revision is not reviewable")
        decision = DemoReviewDecision(
            self._ids.new(),
            revision.id,
            revision.revision_hash,
            revision.manifest.checksum,
            revision.specification_hash,
            decision_type,
            principal.subject,
            tuple(sorted(role.value for role in principal.roles)),
            reason,
            principal.subject == revision.created_by,
            self._clock.now(),
        )
        return self._repository.save_review(bundle, decision)

    def revoke_revision(self, principal: Principal, revision_id: UUID, reason: str) -> DemoBundle:
        if not principal.can_review():
            raise DemoAuthorizationError()
        bundle = self.get_revision(principal, revision_id)
        if bundle.revocation is not None:
            return bundle
        revocation = DemoRevocation(
            self._ids.new(), revision_id, principal.subject, reason, self._clock.now()
        )
        return self._repository.save_revocation(bundle, revocation)

    def issue_session(
        self, principal: Principal, revision_id: UUID, expected_revision_hash: str
    ) -> tuple[SessionIssuance, str]:
        if not (principal.can_operate() or principal.can_review()):
            raise DemoAuthorizationError()
        if not self._issuance_enabled:
            raise DemoSessionError("global demo issuance kill switch is active")
        bundle = self.get_revision(principal, revision_id)
        if (
            bundle.revision.revision_hash != expected_revision_hash
            or bundle.revision.state != DemoRevisionState.APPROVED
            or bundle.revision.validity != DemoValidity.CURRENT
            or not bundle.review_valid
            or bundle.revocation is not None
        ):
            raise DemoSessionError("approved current demo revision required")
        raw = self._capabilities.issue()
        now = self._clock.now()
        issuance = SessionIssuance(
            self._ids.new(),
            revision_id,
            principal.workspace_id,
            principal.subject,
            self._capabilities.digest(raw),
            SessionState.ISSUED,
            now,
            now + ISSUANCE_LIFETIME,
        )
        self._repository.create_issuance(issuance)
        return issuance, raw

    def revoke_session(self, principal: Principal, session_id: UUID) -> None:
        if not (principal.can_operate() or principal.can_review()):
            raise DemoAuthorizationError()
        session = self._repository.get_session(principal.workspace_id, session_id)
        if session is None:
            raise DemoNotFoundError()
        self._repository.revoke_session(session.id, principal.subject, self._clock.now())

    @staticmethod
    def _require_eligible(source: DemoCanonicalInputs) -> None:
        audit = source.audit.revision
        audit_review = source.audit.latest_review
        opportunity = source.opportunity.hypothesis
        opportunity_review = source.opportunity.latest_review
        if opportunity is None or opportunity_review is None or audit_review is None:
            raise DemoValidationError("complete reviewed M2/M3 lineage is required")
        if (
            opportunity.status != HypothesisStatus.ACCEPTED
            or not source.opportunity.review_valid
            or opportunity_review.decision != ReviewDecisionType.ACCEPT
            or opportunity_review.hypothesis_revision_id != opportunity.id
            or opportunity_review.manifest_checksum != opportunity.manifest_checksum
            or opportunity.definition_version != APPROVED_DEFINITION
        ):
            raise DemoValidationError("exact accepted Commercial HVAC opportunity required")
        if (
            audit.kind != AuditKind.FULL
            or audit.state != AuditRevisionState.APPROVED
            or audit.validity != AuditValidity.CURRENT
            or not audit.hard_qc_passed
            or not source.audit.review_valid
            or audit_review.decision != AuditReviewDecisionType.APPROVE
            or audit_review.audit_revision_id != audit.id
            or audit_review.revision_hash != audit.revision_hash
            or audit_review.manifest_hash != audit.manifest.checksum
        ):
            raise DemoValidationError("exact approved full audit revision required")
        if (
            audit.manifest.hypothesis_revision_id != opportunity.id
            or audit.manifest.hypothesis_manifest_checksum != opportunity.manifest_checksum
            or audit.workspace_id != opportunity.workspace_id
            or audit.business_id != opportunity.business_id
        ):
            raise DemoValidationError("M2/M3 entity or revision lineage mismatch")

    @staticmethod
    def _matches_manifest(bundle: DemoBundle, source: DemoCanonicalInputs) -> bool:
        manifest = bundle.revision.manifest
        opportunity = source.opportunity.hypothesis
        audit = source.audit.revision
        return bool(
            opportunity
            and audit.id == manifest.audit_revision_id
            and audit.revision_hash == manifest.audit_revision_hash
            and audit.manifest.checksum == manifest.audit_manifest_hash
            and opportunity.id == manifest.opportunity_revision_id
            and opportunity.manifest_checksum == manifest.opportunity_manifest_hash
            and source.business_profile_hash == manifest.business_profile_hash
        )


class DemoRuntimeService:
    """Narrow runtime gateway; callers possess only a one-time/session capability."""

    def __init__(
        self,
        repository: DemoRepository,
        application: DemoApplicationService,
        clock: Clock,
        identifiers: IdentifierFactory,
        capabilities: CapabilityFactory,
        runtime: DeterministicDemoRuntime | None = None,
    ) -> None:
        self._repository = repository
        self._application = application
        self._clock = clock
        self._ids = identifiers
        self._capabilities = capabilities
        self._runtime = runtime or DeterministicDemoRuntime()

    def exchange(
        self, capability: str, persona_id: str, seed: str
    ) -> tuple[RuntimeSessionView, str]:
        now = self._clock.now()
        issuance = self._repository.get_issuance_by_capability_hash(
            self._capabilities.digest(capability)
        )
        if (
            issuance is None
            or issuance.state != SessionState.ISSUED
            or issuance.used_at is not None
            or issuance.revoked_at is not None
            or now >= issuance.expires_at
        ):
            raise DemoSessionError("issuance capability is invalid, used, revoked, or expired")
        bundle = self._application.get_current_bundle(
            issuance.workspace_id, issuance.demo_revision_id
        )
        if (
            bundle is None
            or bundle.revision.state != DemoRevisionState.APPROVED
            or bundle.revision.validity != DemoValidity.CURRENT
            or not bundle.review_valid
            or bundle.revocation is not None
        ):
            raise DemoSessionError("demo revision is not currently available")
        specification = bundle.revision.specification
        if persona_id not in {item.id for item in specification.personas}:
            raise DemoSessionError("synthetic persona is not registered")
        token = self._capabilities.issue()
        session = RuntimeSession(
            self._ids.new(),
            issuance.id,
            bundle.revision.id,
            issuance.workspace_id,
            issuance.audience,
            self._capabilities.digest(token),
            SessionState.ACTIVE,
            specification.initial_state,
            persona_id,
            seed,
            0,
            (),
            (),
            now,
            now + RUNTIME_SESSION_LIFETIME,
        )
        self._repository.consume_issuance(issuance, session, now)
        self._record_telemetry(session, specification.scenario_id, "session_start", "started", None)
        return (
            RuntimeSessionView(
                session,
                specification,
                self._runtime.disclosure(specification.business_display_name),
                CSP,
            ),
            token,
        )

    def apply_event(
        self, session_token: str, event: str, value: str | None, duration_ms: int | None
    ) -> RuntimeSessionView:
        now = self._clock.now()
        session = self._repository.get_session_by_token_hash(
            self._capabilities.digest(session_token)
        )
        if session is None:
            raise DemoSessionError()
        if session.state == SessionState.REVOKED:
            raise DemoSessionError("runtime session is revoked")
        if now >= session.expires_at:
            self._repository.save_session(
                replace(session, state=SessionState.EXPIRED, ended_at=now)
            )
            raise DemoSessionError("runtime session expired")
        bundle = self._application.get_current_bundle(
            session.workspace_id, session.demo_revision_id
        )
        if (
            bundle is None
            or bundle.revision.state != DemoRevisionState.APPROVED
            or bundle.revision.validity != DemoValidity.CURRENT
            or not bundle.review_valid
            or bundle.revocation is not None
        ):
            raise DemoSessionError("demo revision became unavailable")
        updated = self._runtime.advance(session, bundle.revision.specification, event, value)
        if updated.state == SessionState.ENDED:
            updated = replace(updated, ended_at=now)
        self._repository.save_session(updated)
        outcome = f"entered:{updated.current_state}"
        self._record_telemetry(
            updated,
            bundle.revision.specification.scenario_id,
            "transition_outcome",
            outcome,
            duration_ms,
        )
        if updated.state == SessionState.ENDED:
            self._record_telemetry(
                updated,
                bundle.revision.specification.scenario_id,
                "session_end",
                updated.current_state,
                None,
            )
        return RuntimeSessionView(
            updated,
            bundle.revision.specification,
            self._runtime.disclosure(bundle.revision.specification.business_display_name),
            CSP,
        )

    def _record_telemetry(
        self,
        session: RuntimeSession,
        scenario_id: str,
        event_type: str,
        outcome: str,
        duration_ms: int | None,
    ) -> None:
        if event_type not in ALLOWED_TELEMETRY_EVENTS:
            raise DemoValidationError("telemetry event type is not allowed")
        self._repository.save_telemetry(
            TelemetryEvent(
                self._ids.new(),
                session.id,
                session.demo_revision_id,
                scenario_id,
                event_type,
                session.current_state,
                outcome,
                session.persona_id,
                duration_ms,
                self._clock.now(),
            )
        )
