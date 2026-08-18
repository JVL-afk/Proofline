"""Leased, bounded-retry deterministic M4 composition runner."""

from __future__ import annotations

from datetime import timedelta

from opintel_m0.ports import Clock

from opintel_demo.composition import DeterministicDemoComposer
from opintel_demo.domain import DemoQcError, TransientDemoCompositionError
from opintel_demo.ports import DemoRepository, DemoSourceCatalog


class DemoWorkflowRunner:
    def __init__(
        self,
        repository: DemoRepository,
        source: DemoSourceCatalog,
        composer: DeterministicDemoComposer,
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
        if operation is None:
            return False
        try:
            source = self._source.get_inputs(operation.workspace_id, operation.audit_revision_id)
            if source is None:
                raise DemoQcError("canonical demo inputs are unavailable")
            if source.audit.revision.revision_hash != operation.expected_audit_revision_hash:
                raise DemoQcError("canonical audit changed before composition")
            revision_number = (
                len(self._repository.list_revisions(operation.workspace_id, operation.demo_id)) + 1
            )
            revision = self._composer.compose(
                demo_id=operation.demo_id,
                revision_number=revision_number,
                parent_revision_id=operation.parent_revision_id,
                source=source,
                created_by=operation.created_by,
                now=self._clock.now(),
            )
            self._repository.save_revision(operation, revision)
        except TransientDemoCompositionError as error:
            if operation.attempt_count < operation.max_attempts:
                self._repository.retry_operation(operation, error.code, self._clock.now())
            else:
                self._repository.fail_operation(operation, error.code, self._clock.now())
        except Exception as error:
            code = error.code if isinstance(error, DemoQcError) else "composition_failed"
            self._repository.fail_operation(operation, code, self._clock.now())
        return True
