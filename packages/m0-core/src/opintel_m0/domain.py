"""Framework-free domain types for the M0 walking skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    OPERATOR = "operator"
    VIEWER = "viewer"


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED}


class AttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    workspace_id: UUID
    roles: frozenset[Role]

    def can_operate(self) -> bool:
        return Role.OPERATOR in self.roles


@dataclass(frozen=True, slots=True)
class Campaign:
    id: UUID
    workspace_id: UUID
    name: str
    fixture_uri: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Operation:
    id: UUID
    workspace_id: UUID
    campaign_id: UUID
    workflow_name: str
    workflow_version: str
    status: OperationStatus
    idempotency_key: str
    trace_id: UUID
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    created_by: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ActivityAttempt:
    id: UUID
    operation_id: UUID
    activity_name: str
    activity_version: str
    idempotency_key: str
    attempt_number: int
    status: AttemptStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    id: UUID
    workspace_id: UUID
    campaign_id: UUID
    operation_id: UUID
    source_type: str
    source_uri: str
    final_uri: str
    captured_at: datetime
    content_sha256: str
    mime_type: str
    title: str
    excerpt: str
    fragment_locator: str
    extractor_name: str
    extractor_version: str
    fixture_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    workspace_id: UUID
    subject: str
    event_type: str
    target_type: str
    target_id: UUID
    trace_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class FetchedFixture:
    source_uri: str
    final_uri: str
    content: bytes
    mime_type: str
    captured_at: datetime
    fixture_version: str


class M0Error(Exception):
    """Base class for expected M0 application failures."""


class NotFoundError(M0Error):
    pass


class AuthorizationError(M0Error):
    pass


class InvalidFixtureUriError(M0Error):
    pass


class FixtureFetchError(M0Error):
    code = "fixture_fetch_failed"
    retryable = False


class TransientFixtureFetchError(FixtureFetchError):
    code = "fixture_transient_failure"
    retryable = True


class PermanentFixtureFetchError(FixtureFetchError):
    code = "fixture_permanent_failure"
    retryable = False
