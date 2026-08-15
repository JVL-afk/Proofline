"""M0 application use cases."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from opintel_m0.contracts import CampaignCreate
from opintel_m0.domain import (
    AuditEvent,
    AuthorizationError,
    Campaign,
    EvidenceItem,
    NotFoundError,
    Operation,
    OperationStatus,
    Principal,
)
from opintel_m0.ports import Clock, IdentifierFactory, M0Repository


class M0ApplicationService:
    def __init__(
        self,
        repository: M0Repository,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers

    def create_campaign(self, principal: Principal, command: CampaignCreate) -> Campaign:
        self._require_operator(principal)
        now = self._clock.now()
        campaign = Campaign(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            name=command.name,
            fixture_uri=command.fixture_uri,
            created_by=principal.subject,
            created_at=now,
        )
        audit_event = AuditEvent(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            subject=principal.subject,
            event_type="campaign.created",
            target_type="campaign",
            target_id=campaign.id,
            trace_id=self._identifiers.new(),
            occurred_at=now,
        )
        return self._repository.create_campaign(campaign, audit_event)

    def get_campaign(self, principal: Principal, campaign_id: UUID) -> Campaign:
        campaign = self._repository.get_campaign(principal.workspace_id, campaign_id)
        if campaign is None:
            raise NotFoundError("campaign not found")
        return campaign

    def start_operation(
        self,
        principal: Principal,
        campaign_id: UUID,
        idempotency_key: str,
    ) -> tuple[Operation, bool]:
        self._require_operator(principal)
        campaign = self.get_campaign(principal, campaign_id)
        now = self._clock.now()
        operation = Operation(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            campaign_id=campaign.id,
            workflow_name="m0.fixture_fetch",
            workflow_version="1",
            status=OperationStatus.PENDING,
            idempotency_key=idempotency_key,
            trace_id=self._identifiers.new(),
            attempt_count=0,
            max_attempts=3,
            next_attempt_at=now,
            created_by=principal.subject,
            created_at=now,
            updated_at=now,
        )
        audit_event = AuditEvent(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            subject=principal.subject,
            event_type="operation.requested",
            target_type="operation",
            target_id=operation.id,
            trace_id=operation.trace_id,
            occurred_at=now,
        )
        return self._repository.create_or_get_operation(operation, audit_event)

    def get_operation(self, principal: Principal, operation_id: UUID) -> Operation:
        operation = self._repository.get_operation(principal.workspace_id, operation_id)
        if operation is None:
            raise NotFoundError("operation not found")
        return operation

    def get_evidence(self, principal: Principal, evidence_id: UUID) -> EvidenceItem:
        evidence = self._repository.get_evidence(principal.workspace_id, evidence_id)
        if evidence is None:
            raise NotFoundError("evidence not found")
        return evidence

    @staticmethod
    def retry_delay(attempt_number: int) -> timedelta:
        return timedelta(seconds=min(2 ** (attempt_number - 1), 4))

    @staticmethod
    def _require_operator(principal: Principal) -> None:
        if not principal.can_operate():
            raise AuthorizationError("operator role required")
