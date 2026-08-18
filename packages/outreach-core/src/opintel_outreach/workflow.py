"""Leased, bounded-retry deterministic M5 composition runner."""

from __future__ import annotations

from datetime import timedelta

from opintel_m0.ports import Clock

from opintel_outreach.composition import DeterministicOutreachComposer
from opintel_outreach.domain import OutreachQcError, TransientOutreachCompositionError
from opintel_outreach.ports import OutreachRepository, OutreachSourceCatalog


class OutreachWorkflowRunner:
    def __init__(
        self,
        repository: OutreachRepository,
        source: OutreachSourceCatalog,
        composer: DeterministicOutreachComposer,
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
            source = self._source.get_inputs(operation.workspace_id, operation.demo_revision_id)
            if source is None:
                raise OutreachQcError("canonical outreach inputs are unavailable")
            if source.demo.revision.revision_hash != operation.expected_demo_revision_hash:
                raise OutreachQcError("canonical demo changed before composition")
            revision_number = (
                len(self._repository.list_revisions(operation.workspace_id, operation.package_id))
                + 1
            )
            revision = self._composer.compose(
                package_id=operation.package_id,
                revision_number=revision_number,
                parent_revision_id=operation.parent_revision_id,
                source=source,
                created_by=operation.created_by,
                now=self._clock.now(),
            )
            self._repository.save_revision(operation, revision)
        except TransientOutreachCompositionError as error:
            if operation.attempt_count < operation.max_attempts:
                self._repository.retry_operation(operation, error.code, self._clock.now())
            else:
                self._repository.fail_operation(operation, error.code, self._clock.now())
        except Exception as error:
            code = error.code if isinstance(error, OutreachQcError) else "composition_failed"
            self._repository.fail_operation(operation, code, self._clock.now())
        return True
