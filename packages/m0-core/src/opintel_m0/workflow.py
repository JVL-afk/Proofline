"""Deterministic M0 workflow orchestration over replaceable ports."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from opintel_m0.application import M0ApplicationService
from opintel_m0.domain import (
    ActivityAttempt,
    AttemptStatus,
    AuditEvent,
    EvidenceItem,
    FixtureFetchError,
    InvalidFixtureUriError,
    Operation,
    PermanentFixtureFetchError,
)
from opintel_m0.ports import (
    Clock,
    EvidenceExtractor,
    FixtureFetcher,
    IdentifierFactory,
    M0Repository,
)


class M0WorkflowRunner:
    workflow_name = "m0.fixture_fetch"
    workflow_version = "1"
    activity_name = "m0.fetch_fixture"
    activity_version = "1"

    def __init__(
        self,
        repository: M0Repository,
        fetcher: FixtureFetcher,
        extractor: EvidenceExtractor,
        clock: Clock,
        identifiers: IdentifierFactory,
        lease_duration: timedelta = timedelta(seconds=30),
    ) -> None:
        self._repository = repository
        self._fetcher = fetcher
        self._extractor = extractor
        self._clock = clock
        self._identifiers = identifiers
        self._lease_duration = lease_duration

    def recover_stale(self) -> int:
        return self._repository.recover_stale_operations(self._clock.now())

    def run_once(self) -> bool:
        now = self._clock.now()
        operation = self._repository.claim_next_operation(now, self._lease_duration)
        if operation is None:
            return False

        campaign = self._repository.get_campaign(operation.workspace_id, operation.campaign_id)
        if campaign is None:
            self._fail_without_fetch(operation, "campaign_missing", "campaign no longer exists")
            return True

        attempt_number = operation.attempt_count + 1
        attempt = ActivityAttempt(
            id=self._identifiers.new(),
            operation_id=operation.id,
            activity_name=self.activity_name,
            activity_version=self.activity_version,
            idempotency_key=(
                f"{operation.id}:{self.activity_name}:{self.activity_version}:{attempt_number}"
            ),
            attempt_number=attempt_number,
            status=AttemptStatus.RUNNING,
            started_at=now,
        )
        if self._repository.begin_attempt(attempt) is None:
            return True

        try:
            fetched = self._fetcher.fetch(campaign.fixture_uri, attempt_number)
            title, excerpt, locator = self._extractor.extract(fetched)
            completed_at = self._clock.now()
            evidence = EvidenceItem(
                id=self._identifiers.new(),
                workspace_id=operation.workspace_id,
                campaign_id=campaign.id,
                operation_id=operation.id,
                source_type="CONTROLLED_FIXTURE",
                source_uri=fetched.source_uri,
                final_uri=fetched.final_uri,
                captured_at=fetched.captured_at,
                content_sha256=hashlib.sha256(fetched.content).hexdigest(),
                mime_type=fetched.mime_type,
                title=title,
                excerpt=excerpt,
                fragment_locator=locator,
                extractor_name=self._extractor.name,
                extractor_version=self._extractor.version,
                fixture_version=fetched.fixture_version,
                created_at=completed_at,
            )
            audit = self._audit(
                operation.workspace_id,
                operation.id,
                operation.trace_id,
                "operation.succeeded",
                completed_at,
            )
            self._repository.complete_operation(
                operation.id, attempt.id, evidence, audit, completed_at
            )
        except (FixtureFetchError, InvalidFixtureUriError) as error:
            self._handle_expected_failure(operation, attempt, error)
        except Exception:
            self._handle_expected_failure(
                operation,
                attempt,
                PermanentFixtureFetchError("unexpected fixture activity failure"),
                code="unexpected_activity_failure",
            )
        return True

    def _handle_expected_failure(
        self,
        operation: Operation,
        attempt: ActivityAttempt,
        error: Exception,
        code: str | None = None,
    ) -> None:
        now = self._clock.now()
        error_code = str(code or getattr(error, "code", "fixture_fetch_failed"))
        retryable = bool(getattr(error, "retryable", False))
        safe_message = "controlled fixture activity failed"
        if retryable and attempt.attempt_number < operation.max_attempts:
            audit = self._audit(
                operation.workspace_id,
                operation.id,
                operation.trace_id,
                "operation.retry_scheduled",
                now,
            )
            self._repository.schedule_retry(
                operation.id,
                attempt.id,
                error_code,
                safe_message,
                now + M0ApplicationService.retry_delay(attempt.attempt_number),
                audit,
            )
            return
        audit = self._audit(
            operation.workspace_id,
            operation.id,
            operation.trace_id,
            "operation.failed",
            now,
        )
        self._repository.fail_operation(
            operation.id, attempt.id, error_code, safe_message, audit, now
        )

    def _fail_without_fetch(self, operation: Operation, code: str, message: str) -> None:
        now = self._clock.now()
        attempt = ActivityAttempt(
            id=self._identifiers.new(),
            operation_id=operation.id,
            activity_name=self.activity_name,
            activity_version=self.activity_version,
            idempotency_key=f"{operation.id}:{self.activity_name}:{self.activity_version}:missing",
            attempt_number=operation.attempt_count + 1,
            status=AttemptStatus.RUNNING,
            started_at=now,
        )
        if self._repository.begin_attempt(attempt) is None:
            return
        audit = self._audit(
            operation.workspace_id,
            operation.id,
            operation.trace_id,
            "operation.failed",
            now,
        )
        self._repository.fail_operation(operation.id, attempt.id, code, message, audit, now)

    def _audit(
        self,
        workspace_id: UUID,
        target_id: UUID,
        trace_id: UUID,
        event_type: str,
        now: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            id=self._identifiers.new(),
            workspace_id=workspace_id,
            subject="m0-worker",
            event_type=event_type,
            target_type="operation",
            target_id=target_id,
            trace_id=trace_id,
            occurred_at=now,
        )
