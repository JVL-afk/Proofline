"""Append-only Tournament II qualification lifecycle and scoped suspension."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from opintel_qualification.domain import QualificationStatus
from opintel_qualification.tournament2_domain import (
    FailureBlastRadius,
    GateFinding,
    QualificationIdentity,
    QualificationOutcome,
    RecommendationDisposition,
    TournamentQualificationRecord,
)


class TournamentQualificationRegistry:
    def __init__(
        self,
        id_factory: Callable[[], UUID],
        clock: Callable[[], datetime],
    ) -> None:
        self._id_factory = id_factory
        self._clock = clock
        self._history: list[TournamentQualificationRecord] = []

    @property
    def history(self) -> tuple[TournamentQualificationRecord, ...]:
        return tuple(self._history)

    def latest(self, identity: QualificationIdentity) -> TournamentQualificationRecord | None:
        matches = [item for item in self._history if item.identity == identity]
        return matches[-1] if matches else None

    def register(self, identity: QualificationIdentity) -> TournamentQualificationRecord:
        if self.latest(identity) is not None:
            raise ValueError("qualification identity is already registered")
        return self._append(identity, QualificationStatus.UNASSESSED, None, None, "registered")

    def begin(self, identity: QualificationIdentity) -> TournamentQualificationRecord:
        previous = self._required(identity)
        if previous.status not in {
            QualificationStatus.UNASSESSED,
            QualificationStatus.SUSPENDED,
            QualificationStatus.CONDITIONAL,
            QualificationStatus.DISQUALIFIED,
        }:
            raise ValueError("qualification cannot enter evaluation from current state")
        return self._append(
            identity,
            QualificationStatus.EVALUATING,
            None,
            previous.id,
            "evaluation_started",
        )

    def decide(self, outcome: QualificationOutcome) -> TournamentQualificationRecord:
        previous = self._required(outcome.identity)
        if previous.status is not QualificationStatus.EVALUATING:
            raise ValueError("qualification decision requires EVALUATING state")
        return self._append(
            outcome.identity,
            outcome.status,
            outcome.disposition,
            previous.id,
            "evaluation_completed",
        )

    def suspend_for_drift(
        self, replacement: QualificationIdentity
    ) -> tuple[TournamentQualificationRecord, ...]:
        results: list[TournamentQualificationRecord] = []
        for current in self._latest_active_records():
            same_binding_family = (
                current.identity.provider_key == replacement.provider_key
                and current.identity.deployment_key == replacement.deployment_key
                and current.identity.task == replacement.task
            )
            if same_binding_family and current.identity != replacement:
                results.append(
                    self._append(
                        current.identity,
                        QualificationStatus.SUSPENDED,
                        current.disposition,
                        current.id,
                        "exact qualification identity drifted",
                    )
                )
        return tuple(results)

    def suspend_for_failure(
        self, failed_identity: QualificationIdentity, finding: GateFinding
    ) -> tuple[TournamentQualificationRecord, ...]:
        results: list[TournamentQualificationRecord] = []
        for current in self._latest_active_records():
            target = False
            if finding.blast_radius is FailureBlastRadius.TASK_LOCAL_FAILURE:
                target = current.identity == failed_identity
            elif finding.blast_radius is FailureBlastRadius.CONFIGURATION_WIDE_FAILURE:
                target = (
                    current.identity.provider_key == failed_identity.provider_key
                    and current.identity.deployment_key == failed_identity.deployment_key
                    and current.identity.configuration_hash == failed_identity.configuration_hash
                )
            elif finding.blast_radius is FailureBlastRadius.PROVIDER_SECURITY_FAILURE:
                target = current.identity.provider_key == failed_identity.provider_key
            if target and current.status is not QualificationStatus.SUSPENDED:
                results.append(
                    self._append(
                        current.identity,
                        QualificationStatus.SUSPENDED,
                        current.disposition,
                        current.id,
                        f"{finding.blast_radius.value}:{finding.gate.value}",
                    )
                )
        return tuple(results)

    def retire(self, identity: QualificationIdentity) -> TournamentQualificationRecord:
        previous = self._required(identity)
        if previous.status is QualificationStatus.RETIRED:
            raise ValueError("qualification is already retired")
        return self._append(
            identity,
            QualificationStatus.RETIRED,
            previous.disposition,
            previous.id,
            "retired",
        )

    def _required(self, identity: QualificationIdentity) -> TournamentQualificationRecord:
        result = self.latest(identity)
        if result is None:
            raise ValueError("qualification identity is not registered")
        return result

    def _latest_active_records(self) -> tuple[TournamentQualificationRecord, ...]:
        latest: dict[QualificationIdentity, TournamentQualificationRecord] = {}
        for item in self._history:
            latest[item.identity] = item
        return tuple(
            item
            for item in latest.values()
            if item.status
            in {
                QualificationStatus.EVALUATING,
                QualificationStatus.QUALIFIED,
                QualificationStatus.CONDITIONAL,
            }
        )

    def _append(
        self,
        identity: QualificationIdentity,
        status: QualificationStatus,
        disposition: RecommendationDisposition | None,
        previous_id: UUID | None,
        reason: str,
    ) -> TournamentQualificationRecord:
        record = TournamentQualificationRecord(
            id=self._id_factory(),
            identity=identity,
            status=status,
            disposition=disposition,
            previous_record_id=previous_id,
            reason=reason,
            created_at=self._clock(),
        )
        self._history.append(record)
        return record
