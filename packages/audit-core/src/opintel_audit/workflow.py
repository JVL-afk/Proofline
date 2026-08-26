"""Leased, bounded-retry local M3 composition runner."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from opintel_m0.ports import Clock

from opintel_audit.composition import DeterministicAuditComposer
from opintel_audit.domain import AuditOperation, AuditQcError, TransientCompositionError
from opintel_audit.ports import AuditRepository, AuditSourceCatalog


class AuditWorkflowRunner:
    def __init__(
        self,
        repository: AuditRepository,
        source: AuditSourceCatalog,
        composer: DeterministicAuditComposer,
        clock: Clock,
        lease: timedelta = timedelta(seconds=30),
    ) -> None:
        self._repository = repository
        self._source = source
        self._composer = composer
        self._clock = clock
        self._lease = lease

    def run_once(self) -> bool:
        operation = self._repository.claim_operation(self._clock.now(), self._lease)
        return self._run_claimed(operation)

    def run_exact(self, operation_id: UUID, expected_created_by: str) -> bool:
        operation = self._repository.claim_exact_operation(
            operation_id, expected_created_by, self._clock.now(), self._lease
        )
        return self._run_claimed(operation)

    def _run_claimed(self, operation: AuditOperation | None) -> bool:
        if operation is None:
            return False
        try:
            source = self._source.get_opportunity_bundle(
                operation.workspace_id, operation.hypothesis_id
            )
            if source is None or source.hypothesis is None:
                raise AuditQcError("canonical opportunity is unavailable")
            if source.hypothesis.id != operation.expected_hypothesis_revision_id:
                raise AuditQcError("canonical opportunity changed before composition")
            evidence = self._source.list_evidence(
                operation.workspace_id, operation.business_id, source.run.research_run_id
            )
            revision_number = (
                len(self._repository.list_revisions(operation.workspace_id, operation.audit_id)) + 1
            )
            revision = self._composer.compose(
                audit_id=operation.audit_id,
                revision_number=revision_number,
                parent_revision_id=operation.parent_revision_id,
                kind=operation.kind,
                source=source,
                evidence=evidence,
                created_by=operation.created_by,
                now=self._clock.now(),
            )
            self._repository.save_revision(operation, revision)
        except TransientCompositionError as error:
            if operation.attempt_count < operation.max_attempts:
                self._repository.retry_operation(operation, error.code, self._clock.now())
            else:
                self._repository.fail_operation(operation, error.code, self._clock.now())
        except Exception as error:
            code = error.code if isinstance(error, AuditQcError) else "composition_failed"
            self._repository.fail_operation(operation, code, self._clock.now())
        return True
