"""Ports implemented by transport and infrastructure adapters."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from opintel_m0.domain import (
    ActivityAttempt,
    AuditEvent,
    Campaign,
    EvidenceItem,
    FetchedFixture,
    Operation,
    Principal,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class Authenticator(Protocol):
    def authenticate(self, token: str) -> Principal | None: ...


class FixtureFetcher(Protocol):
    def fetch(self, fixture_uri: str, attempt_number: int) -> FetchedFixture: ...


class EvidenceExtractor(Protocol):
    name: str
    version: str

    def extract(self, fixture: FetchedFixture) -> tuple[str, str, str]: ...


class M0Repository(Protocol):
    def initialize(self) -> None: ...

    def create_campaign(self, campaign: Campaign, audit_event: AuditEvent) -> Campaign: ...

    def get_campaign(self, workspace_id: UUID, campaign_id: UUID) -> Campaign | None: ...

    def create_or_get_operation(
        self, operation: Operation, audit_event: AuditEvent
    ) -> tuple[Operation, bool]: ...

    def get_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation | None: ...

    def list_attempts(self, operation_id: UUID) -> list[ActivityAttempt]: ...

    def list_evidence(self, workspace_id: UUID, operation_id: UUID) -> list[EvidenceItem]: ...

    def get_evidence(self, workspace_id: UUID, evidence_id: UUID) -> EvidenceItem | None: ...

    def recover_stale_operations(self, now: datetime) -> int: ...

    def claim_next_operation(
        self, now: datetime, lease_duration: timedelta
    ) -> Operation | None: ...

    def begin_attempt(self, attempt: ActivityAttempt) -> ActivityAttempt | None: ...

    def complete_operation(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        evidence: EvidenceItem,
        audit_event: AuditEvent,
        now: datetime,
    ) -> EvidenceItem: ...

    def schedule_retry(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        error_code: str,
        safe_message: str,
        next_attempt_at: datetime,
        audit_event: AuditEvent,
    ) -> None: ...

    def fail_operation(
        self,
        operation_id: UUID,
        attempt_id: UUID,
        error_code: str,
        safe_message: str,
        audit_event: AuditEvent,
        now: datetime,
    ) -> None: ...
