"""Authorized M5 package commands and content-only review."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from opintel_audit.domain import (
    AuditKind,
    AuditReviewDecisionType,
    AuditRevisionState,
    AuditValidity,
)
from opintel_demo.domain import (
    DemoReviewDecisionType,
    DemoRevisionState,
    DemoValidity,
)
from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory
from opintel_opportunity.domain import HypothesisStatus, ReviewDecisionType

from opintel_outreach.composition import APPROVED_DEFINITION
from opintel_outreach.domain import (
    OutreachAuthorizationError,
    OutreachBundle,
    OutreachCanonicalInputs,
    OutreachInvalidation,
    OutreachNotFoundError,
    OutreachOperation,
    OutreachOperationStatus,
    OutreachReviewDecision,
    OutreachReviewDecisionType,
    OutreachRevisionState,
    OutreachValidationError,
    OutreachValidity,
)
from opintel_outreach.ports import OutreachRepository, OutreachSourceCatalog


class OutreachApplicationService:
    def __init__(
        self,
        repository: OutreachRepository,
        source: OutreachSourceCatalog,
        clock: Clock,
        identifiers: IdentifierFactory,
        *,
        generation_enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._source = source
        self._clock = clock
        self._ids = identifiers
        self._generation_enabled = generation_enabled

    def start_generation(
        self,
        principal: Principal,
        demo_revision_id: UUID,
        expected_demo_revision_hash: str,
        idempotency_key: str,
        parent_revision_id: UUID | None = None,
    ) -> tuple[OutreachOperation, bool]:
        if not principal.can_operate():
            raise OutreachAuthorizationError()
        if not self._generation_enabled:
            raise OutreachValidationError("outreach package generation is disabled")
        source = self._source.get_inputs(principal.workspace_id, demo_revision_id)
        if source is None:
            raise OutreachNotFoundError()
        self._require_eligible(source)
        if source.demo.revision.revision_hash != expected_demo_revision_hash:
            raise OutreachValidationError("demo revision precondition failed")
        package_id = self._ids.new()
        if parent_revision_id is not None:
            parent = self.get_revision(principal, parent_revision_id)
            if parent.revision.demo_id != source.demo.revision.demo_id:
                raise OutreachValidationError("parent revision belongs to another demo")
            package_id = parent.revision.package_id
        now = self._clock.now()
        operation = OutreachOperation(
            self._ids.new(),
            principal.workspace_id,
            source.audit.revision.business_id,
            demo_revision_id,
            expected_demo_revision_hash,
            package_id,
            parent_revision_id,
            OutreachOperationStatus.PENDING,
            idempotency_key,
            self._ids.new(),
            0,
            3,
            principal.subject,
            now,
            now,
        )
        return self._repository.create_or_get_operation(operation)

    def get_operation(self, principal: Principal, operation_id: UUID) -> OutreachOperation:
        value = self._repository.get_operation(principal.workspace_id, operation_id)
        if value is None:
            raise OutreachNotFoundError()
        return value

    def get_revision(self, principal: Principal, revision_id: UUID) -> OutreachBundle:
        value = self._repository.get_revision(principal.workspace_id, revision_id)
        if value is None:
            raise OutreachNotFoundError()
        return self._refresh_validity(value)

    def list_revisions(self, principal: Principal, package_id: UUID) -> tuple[OutreachBundle, ...]:
        return tuple(
            self._refresh_validity(item)
            for item in self._repository.list_revisions(principal.workspace_id, package_id)
        )

    def review(
        self,
        principal: Principal,
        revision_id: UUID,
        expected_revision_hash: str,
        expected_manifest_hash: str,
        expected_content_hash: str,
        decision: OutreachReviewDecisionType,
        reason: str,
    ) -> OutreachBundle:
        if not principal.can_review():
            raise OutreachAuthorizationError()
        bundle = self.get_revision(principal, revision_id)
        revision = bundle.revision
        if (
            revision.revision_hash != expected_revision_hash
            or revision.manifest.checksum != expected_manifest_hash
            or revision.content_hash != expected_content_hash
        ):
            raise OutreachValidationError("outreach review precondition failed")
        if revision.validity != OutreachValidity.CURRENT:
            raise OutreachValidationError("outreach inputs are no longer current")
        if not revision.hard_qc_passed:
            raise OutreachValidationError("hard QC failures cannot be overridden")
        if revision.state not in {
            OutreachRevisionState.READY_FOR_REVIEW,
            OutreachRevisionState.CONTENT_APPROVED,
            OutreachRevisionState.REVISION_REQUESTED,
        }:
            raise OutreachValidationError("outreach revision is not reviewable")
        review = OutreachReviewDecision(
            self._ids.new(),
            revision.id,
            revision.revision_hash,
            revision.manifest.checksum,
            revision.content_hash,
            decision,
            principal.subject,
            tuple(str(role) for role in principal.roles),
            reason,
            principal.subject == revision.created_by,
            self._clock.now(),
        )
        return self._repository.save_review(bundle, review)

    def invalidate(self, principal: Principal, revision_id: UUID, reason: str) -> OutreachBundle:
        if not principal.can_review():
            raise OutreachAuthorizationError()
        bundle = self.get_revision(principal, revision_id)
        invalidation = OutreachInvalidation(
            self._ids.new(), revision_id, reason, principal.subject, self._clock.now()
        )
        return self._repository.save_invalidation(bundle, invalidation)

    @staticmethod
    def _require_eligible(source: OutreachCanonicalInputs) -> None:
        demo = source.demo
        audit = source.audit
        opportunity = source.opportunity
        hypothesis = opportunity.hypothesis
        if (
            hypothesis is None
            or hypothesis.status != HypothesisStatus.ACCEPTED
            or hypothesis.definition_version != APPROVED_DEFINITION
            or not opportunity.review_valid
            or opportunity.latest_review is None
            or opportunity.latest_review.decision != ReviewDecisionType.ACCEPT
        ):
            raise OutreachValidationError("an exact accepted opportunity is required")
        if (
            audit.revision.kind != AuditKind.FULL
            or audit.revision.state != AuditRevisionState.APPROVED
            or audit.revision.validity != AuditValidity.CURRENT
            or not audit.revision.hard_qc_passed
            or not audit.review_valid
            or audit.latest_review is None
            or audit.latest_review.decision != AuditReviewDecisionType.APPROVE
        ):
            raise OutreachValidationError("an exact approved full audit is required")
        if (
            demo.revision.state != DemoRevisionState.APPROVED
            or demo.revision.validity != DemoValidity.CURRENT
            or not demo.revision.hard_qc_passed
            or not demo.review_valid
            or demo.latest_review is None
            or demo.latest_review.decision != DemoReviewDecisionType.APPROVE
            or demo.revocation is not None
        ):
            raise OutreachValidationError("an exact approved non-revoked demo is required")
        if (
            demo.revision.manifest.audit_revision_id != audit.revision.id
            or audit.revision.hypothesis_id != hypothesis.logical_id
            or len(
                {demo.revision.workspace_id, audit.revision.workspace_id, hypothesis.workspace_id}
            )
            != 1
            or len({demo.revision.business_id, audit.revision.business_id, hypothesis.business_id})
            != 1
        ):
            raise OutreachValidationError("upstream entity or revision lineage mismatch")

    def _refresh_validity(self, bundle: OutreachBundle) -> OutreachBundle:
        if bundle.invalidation is not None:
            return OutreachBundle(
                replace(bundle.revision, validity=OutreachValidity.INVALIDATED),
                bundle.latest_review,
                False,
                bundle.invalidation,
            )
        source = self._source.get_inputs(
            bundle.revision.workspace_id, bundle.revision.manifest.demo_revision_id
        )
        try:
            if source is None:
                raise OutreachValidationError()
            self._require_eligible(source)
            manifest = bundle.revision.manifest
            current = (
                source.demo.revision.revision_hash == manifest.demo_revision_hash
                and source.audit.revision.revision_hash == manifest.audit_revision_hash
                and source.opportunity.hypothesis is not None
                and source.opportunity.hypothesis.manifest_checksum
                == manifest.opportunity_manifest_hash
            )
        except OutreachValidationError:
            current = False
        if current:
            return bundle
        return OutreachBundle(
            replace(bundle.revision, validity=OutreachValidity.STALE_INPUTS),
            bundle.latest_review,
            False,
            bundle.invalidation,
        )
