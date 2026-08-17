"""M3 application ports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from opintel_opportunity.domain import OpportunityBundle

from opintel_audit.domain import (
    AuditBundle,
    AuditEvidence,
    AuditOperation,
    AuditReviewDecision,
    AuditRevision,
)


class AuditSourceCatalog(Protocol):
    def get_opportunity_bundle(
        self, workspace_id: UUID, hypothesis_id: UUID
    ) -> OpportunityBundle | None: ...

    def list_evidence(
        self, workspace_id: UUID, business_id: UUID, research_run_id: UUID
    ) -> tuple[AuditEvidence, ...]: ...


class AuditRepository(Protocol):
    def initialize(self) -> None: ...
    def create_or_get_operation(self, operation: AuditOperation) -> tuple[AuditOperation, bool]: ...
    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> AuditOperation | None: ...
    def claim_operation(self, now: datetime, lease: timedelta) -> AuditOperation | None: ...
    def retry_operation(
        self, operation: AuditOperation, error_code: str, now: datetime
    ) -> None: ...
    def fail_operation(self, operation: AuditOperation, error_code: str, now: datetime) -> None: ...
    def save_revision(self, operation: AuditOperation, revision: AuditRevision) -> None: ...
    def get_revision(self, workspace_id: UUID, revision_id: UUID) -> AuditBundle | None: ...
    def list_revisions(self, workspace_id: UUID, audit_id: UUID) -> tuple[AuditBundle, ...]: ...
    def save_review(self, bundle: AuditBundle, decision: AuditReviewDecision) -> AuditBundle: ...
    def invalidate_review(
        self, review_id: UUID, changed_input_id: UUID, reason: str, now: datetime
    ) -> None: ...


class ProseComposerPort(Protocol):
    """Future wording-only port. It cannot add claims, bindings, entities, or numbers."""

    def propose_wording(
        self, claim_text_by_id: dict[UUID, str], manifest_hash: str
    ) -> dict[UUID, str]: ...
