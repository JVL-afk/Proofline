"""Authorized M3 commands and queries."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory
from opintel_opportunity.domain import HypothesisStatus

from opintel_audit.domain import (
    AuditAuthorizationError,
    AuditBundle,
    AuditKind,
    AuditNotFoundError,
    AuditOperation,
    AuditOperationStatus,
    AuditReviewDecision,
    AuditReviewDecisionType,
    AuditValidationError,
    AuditValidity,
)
from opintel_audit.ports import AuditRepository, AuditSourceCatalog


class AuditApplicationService:
    def __init__(
        self,
        repository: AuditRepository,
        source: AuditSourceCatalog,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._source = source
        self._clock = clock
        self._ids = identifiers

    def start_generation(
        self,
        principal: Principal,
        hypothesis_id: UUID,
        expected_hypothesis_revision_id: UUID,
        idempotency_key: str,
        parent_revision_id: UUID | None = None,
    ) -> tuple[AuditOperation, bool]:
        if not principal.can_operate():
            raise AuditAuthorizationError()
        source = self._source.get_opportunity_bundle(principal.workspace_id, hypothesis_id)
        if source is None or source.hypothesis is None:
            raise AuditNotFoundError()
        hypothesis = source.hypothesis
        if hypothesis.id != expected_hypothesis_revision_id:
            raise AuditValidationError("hypothesis revision precondition failed")
        if hypothesis.status == HypothesisStatus.ACCEPTED and source.review_valid:
            kind = AuditKind.FULL
        elif hypothesis.status == HypothesisStatus.READY_FOR_REVIEW:
            kind = AuditKind.INTERNAL_DIAGNOSTIC
        else:
            raise AuditValidationError("opportunity state is not eligible for audit generation")
        audit_id = self._ids.new()
        if parent_revision_id is not None:
            parent = self.get_revision(principal, parent_revision_id)
            if parent.revision.hypothesis_id != hypothesis_id:
                raise AuditValidationError("parent revision belongs to another opportunity")
            audit_id = parent.revision.audit_id
        now = self._clock.now()
        operation = AuditOperation(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=hypothesis.business_id,
            hypothesis_id=hypothesis.logical_id,
            expected_hypothesis_revision_id=hypothesis.id,
            audit_id=audit_id,
            parent_revision_id=parent_revision_id,
            kind=kind,
            status=AuditOperationStatus.PENDING,
            idempotency_key=idempotency_key,
            trace_id=self._ids.new(),
            attempt_count=0,
            max_attempts=3,
            created_by=principal.subject,
            created_at=now,
            updated_at=now,
        )
        return self._repository.create_or_get_operation(operation)

    def get_operation(self, principal: Principal, operation_id: UUID) -> AuditOperation:
        value = self._repository.get_operation(principal.workspace_id, operation_id)
        if value is None:
            raise AuditNotFoundError()
        return value

    def get_revision(self, principal: Principal, revision_id: UUID) -> AuditBundle:
        value = self._repository.get_revision(principal.workspace_id, revision_id)
        if value is None:
            raise AuditNotFoundError()
        current = self._source.get_opportunity_bundle(
            principal.workspace_id, value.revision.hypothesis_id
        )
        if (
            current is None
            or current.hypothesis is None
            or current.hypothesis.id != value.revision.manifest.hypothesis_revision_id
            or current.hypothesis.manifest_checksum
            != value.revision.manifest.hypothesis_manifest_checksum
        ):
            if value.latest_review is not None:
                self._repository.invalidate_review(
                    value.latest_review.id,
                    current.hypothesis.id
                    if current is not None and current.hypothesis is not None
                    else value.revision.manifest.hypothesis_revision_id,
                    "canonical_audit_input_changed",
                    self._clock.now(),
                )
            return replace(
                value,
                revision=replace(value.revision, validity=AuditValidity.STALE_INPUTS),
                review_valid=False,
            )
        return value

    def list_revisions(self, principal: Principal, audit_id: UUID) -> tuple[AuditBundle, ...]:
        return self._repository.list_revisions(principal.workspace_id, audit_id)

    def review(
        self,
        principal: Principal,
        revision_id: UUID,
        expected_revision_hash: str,
        expected_manifest_hash: str,
        decision_type: AuditReviewDecisionType,
        reason: str,
        acknowledged_qc_codes: tuple[str, ...],
    ) -> AuditBundle:
        if not principal.can_review():
            raise AuditAuthorizationError()
        bundle = self.get_revision(principal, revision_id)
        revision = bundle.revision
        if (
            revision.revision_hash != expected_revision_hash
            or revision.manifest.checksum != expected_manifest_hash
        ):
            raise AuditValidationError("audit revision precondition failed")
        if revision.validity != AuditValidity.CURRENT:
            raise AuditValidationError("stale audit inputs require a new revision")
        if not revision.hard_qc_passed:
            raise AuditValidationError("semantic QC failures cannot be overridden")
        required_acknowledgments = {
            finding.code for finding in revision.qc_findings if finding.acknowledgment_required
        }
        if not required_acknowledgments.issubset(acknowledged_qc_codes):
            raise AuditValidationError("required freshness warning acknowledgment is missing")
        source = self._source.get_opportunity_bundle(principal.workspace_id, revision.hypothesis_id)
        if source is None or source.hypothesis is None:
            raise AuditValidationError("canonical opportunity is unavailable")
        if decision_type == AuditReviewDecisionType.APPROVE:
            if revision.kind != AuditKind.FULL:
                raise AuditValidationError("internal diagnostic audits cannot be approved")
            if source.hypothesis.status != HypothesisStatus.ACCEPTED or not source.review_valid:
                raise AuditValidationError("the opportunity is not currently accepted")
        decision = AuditReviewDecision(
            id=self._ids.new(),
            audit_revision_id=revision.id,
            revision_hash=revision.revision_hash,
            manifest_hash=revision.manifest.checksum,
            decision=decision_type,
            actor=principal.subject,
            actor_roles=tuple(sorted(role.value for role in principal.roles)),
            reason=reason,
            self_review=principal.subject == revision.created_by,
            acknowledged_qc_codes=tuple(sorted(set(acknowledged_qc_codes))),
            created_at=self._clock.now(),
        )
        return self._repository.save_review(bundle, decision)
