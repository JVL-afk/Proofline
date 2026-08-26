"""M5 application ports; no delivery or recipient port exists."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from opintel_outreach.domain import (
    OutreachBundle,
    OutreachCanonicalInputs,
    OutreachInvalidation,
    OutreachOperation,
    OutreachReviewDecision,
    OutreachRevision,
)


class OutreachSourceCatalog(Protocol):
    def get_inputs(
        self, workspace_id: UUID, demo_revision_id: UUID
    ) -> OutreachCanonicalInputs | None: ...


class OutreachRepository(Protocol):
    def initialize(self) -> None: ...
    def create_or_get_operation(
        self, operation: OutreachOperation
    ) -> tuple[OutreachOperation, bool]: ...
    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> OutreachOperation | None: ...
    def claim_operation(self, now: datetime, lease: timedelta) -> OutreachOperation | None: ...
    def claim_exact_operation(
        self, operation_id: UUID, expected_created_by: str, now: datetime, lease: timedelta
    ) -> OutreachOperation | None: ...
    def retry_operation(
        self, operation: OutreachOperation, error_code: str, now: datetime
    ) -> None: ...
    def fail_operation(
        self, operation: OutreachOperation, error_code: str, now: datetime
    ) -> None: ...
    def save_revision(self, operation: OutreachOperation, revision: OutreachRevision) -> None: ...
    def get_revision(self, workspace_id: UUID, revision_id: UUID) -> OutreachBundle | None: ...
    def list_revisions(
        self, workspace_id: UUID, package_id: UUID
    ) -> tuple[OutreachBundle, ...]: ...
    def save_review(
        self, bundle: OutreachBundle, decision: OutreachReviewDecision
    ) -> OutreachBundle: ...
    def save_invalidation(
        self, bundle: OutreachBundle, invalidation: OutreachInvalidation
    ) -> OutreachBundle: ...


class OutreachWordingPort(Protocol):
    """Future wording-only port. No implementation or route is authorized in M5."""

    def propose_wording(
        self,
        *,
        projection_ids: tuple[UUID, ...],
        required_qualifiers: tuple[str, ...],
        prohibited_policy_version: str,
        maximum_words: int,
    ) -> tuple[str, ...]: ...
