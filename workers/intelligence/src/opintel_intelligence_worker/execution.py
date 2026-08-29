"""Single-use production execution chain for one owner-approved sampled slot."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_research.domain import ResearchRun
from opintel_research_worker.activation import ORIGINAL_ATTEMPT_LINEAGE_SHA256
from opintel_research_worker.egress_lease import ControlledEgressLease
from opintel_research_worker.release_application import (
    BoundedSampledSlotReleaseApplicator,
    SampledSlotExecutionApproval,
)
from opintel_shadow import LiveResearchPermissionRelease

from opintel_intelligence_worker.coordinator_persistence import (
    CoordinatorRunBinding,
    SqlAlchemyCoordinatorRepository,
)
from opintel_intelligence_worker.orchestration import (
    BoundedSampledSlotCoordinator,
    CoordinatedStageArtifact,
    ShadowStage,
)
from opintel_intelligence_worker.production_runtime import StageResult, TruthfulTerminal


class SampledActivator(Protocol):
    def activate(self, slot_number: int, release_id: UUID) -> tuple[ResearchRun, bool]: ...


class CurrentAuthority(Protocol):
    def current_release(self) -> LiveResearchPermissionRelease: ...


class StopSignal(Protocol):
    def is_active(self) -> bool: ...


class StageRuntime(Protocol):
    def execute(
        self, stage: ShadowStage, predecessor: CoordinatedStageArtifact | None
    ) -> StageResult: ...


class ControlledEgressLifecycle(Protocol):
    def activate_and_await_ready(
        self, release: LiveResearchPermissionRelease, run: ResearchRun
    ) -> tuple[ControlledEgressLease, bool]: ...

    def deactivate(self, lease: ControlledEgressLease) -> bool: ...


class BoundedSampledSlotExecution:
    """Apply authority, activate once, advance exact lineage, then consume authority."""

    def __init__(
        self,
        *,
        release_applicator: BoundedSampledSlotReleaseApplicator,
        activator: SampledActivator,
        authority: CurrentAuthority,
        stop_signal: StopSignal,
        repository: SqlAlchemyCoordinatorRepository,
        stage_runtime_factory: Callable[[ResearchRun], StageRuntime],
        controlled_egress: ControlledEgressLifecycle,
        now: Callable[[], datetime],
    ) -> None:
        self._release_applicator = release_applicator
        self._activator = activator
        self._authority = authority
        self._stop = stop_signal
        self._repository = repository
        self._stage_runtime_factory = stage_runtime_factory
        self._controlled_egress = controlled_egress
        self._now = now

    def run(self) -> dict[str, object]:
        release: LiveResearchPermissionRelease | None = None
        approval: SampledSlotExecutionApproval | None = None
        egress_lease: ControlledEgressLease | None = None
        egress_lease_created = False
        egress_deactivated = False
        terminal_reason = "BOUNDED_EXECUTION_FAILED"
        try:
            release, approval, release_created = self._release_applicator.apply()
            self._release_applicator.enter_run(release)
            run, work_item_created = self._activator.activate(approval.slot_number, release.id)
            identity = run.sampled_slot_identity
            activation = run.sampled_slot_activation
            if identity is None or activation is None:
                raise ValueError("sampled activation did not create immutable work-item identity")
            # Attempt-scoped so a prior terminal coordinator (a superseded
            # bounded-repair attempt in the same experiment) never short-circuits
            # a legitimate repaired successor. Stable for an identical sealed
            # authority; distinct per eligible repair successor.
            attempt_lineage = (
                release.repair_attempt_lineage_sha256 or ORIGINAL_ATTEMPT_LINEAGE_SHA256
            )
            coordinator_run_id = uuid5(
                NAMESPACE_URL,
                "m67.sampled-slot-coordinator:"
                f"{release.id}:{identity.identity_sha256}:{attempt_lineage}",
            )
            binding = CoordinatorRunBinding(
                coordinator_run_id=coordinator_run_id,
                authorization_release_id=release.id,
                ordered_package_sha256=identity.ordered_package_semantic_sha256,
                slot_number=identity.slot_number,
                business_identity=identity.business_identity,
                exact_hostname=identity.exact_hostname,
                work_item_identity_sha256=identity.identity_sha256,
                activation_sha256=activation.activation_sha256,
                runtime_revision=activation.research_runtime_revision,
                created_at=activation.activated_at,
                repair_attempt_lineage_sha256=attempt_lineage,
            )
            _, coordinator_created = self._repository.create_or_get(binding)
            existing = self._repository.load(coordinator_run_id)
            coordinator = BoundedSampledSlotCoordinator(
                ordered_package_sha256=binding.ordered_package_sha256,
                slot_number=binding.slot_number,
                business_identity=binding.business_identity,
                exact_hostname=binding.exact_hostname,
                work_item_identity_sha256=binding.work_item_identity_sha256,
                activation_sha256=binding.activation_sha256,
                authorization_release_id=binding.authorization_release_id,
                coordinator_run_id=binding.coordinator_run_id,
                runtime_revision=binding.runtime_revision,
                existing=existing,
            )
            runtime = self._stage_runtime_factory(run)
            stages = tuple(ShadowStage)
            if len(existing) == 0:
                egress_lease, egress_lease_created = (
                    self._controlled_egress.activate_and_await_ready(release, run)
                )
            for stage in stages[len(existing) :]:
                self._require_current_authority(release)
                predecessor = coordinator.artifacts[-1] if coordinator.artifacts else None
                try:
                    result = runtime.execute(stage, predecessor)
                except TruthfulTerminal as outcome:
                    artifact, _ = coordinator.accept_stage(
                        stage=stage,
                        revision_id=outcome.revision_id,
                        output_sha256=outcome.output_sha256,
                        authority_effective=True,
                        kill_switch_tripped=False,
                    )
                    self._repository.append(artifact, self._now())
                    terminal_reason = outcome.reason
                    if stage is ShadowStage.M1_MINIMIZED_EVIDENCE and egress_lease:
                        egress_deactivated = self._controlled_egress.deactivate(egress_lease)
                        egress_lease = None
                    self._release_applicator.consume(release, terminal_reason)
                    self._repository.mark_terminal(coordinator_run_id, terminal_reason, self._now())
                    return self._receipt(
                        release,
                        approval,
                        coordinator_run_id,
                        release_created,
                        work_item_created,
                        coordinator_created,
                        terminal_reason,
                        len(coordinator.artifacts),
                        egress_lease_created,
                        egress_deactivated,
                    )
                artifact, _ = coordinator.accept_stage(
                    stage=stage,
                    revision_id=result.revision_id,
                    output_sha256=result.output_sha256,
                    authority_effective=True,
                    kill_switch_tripped=False,
                )
                self._repository.append(artifact, self._now())
                if stage is ShadowStage.M1_MINIMIZED_EVIDENCE and egress_lease:
                    egress_deactivated = self._controlled_egress.deactivate(egress_lease)
                    egress_lease = None
            terminal_reason = "CONTACT_PHASE_NOT_AUTHORIZED"
            self._release_applicator.consume(release, terminal_reason)
            self._repository.mark_terminal(coordinator_run_id, terminal_reason, self._now())
            return self._receipt(
                release,
                approval,
                coordinator_run_id,
                release_created,
                work_item_created,
                coordinator_created,
                terminal_reason,
                len(coordinator.artifacts),
                egress_lease_created,
                egress_deactivated,
            )
        except Exception:
            if egress_lease is not None:
                with suppress(Exception):
                    self._controlled_egress.deactivate(egress_lease)
            if release is not None:
                # The store is designed to trip first. Never mask the original failure.
                with suppress(Exception):
                    self._release_applicator.consume(release, terminal_reason)
            raise

    def _require_current_authority(self, release: LiveResearchPermissionRelease) -> None:
        if self._stop.is_active():
            raise ValueError("kill switch blocks the next stage boundary")
        current = self._authority.current_release()
        if current.id != release.id or current.configuration_hash != release.configuration_hash:
            raise ValueError("release expired, revoked, or changed before stage boundary")

    @staticmethod
    def _receipt(
        release: LiveResearchPermissionRelease,
        approval: SampledSlotExecutionApproval,
        coordinator_run_id: UUID,
        release_created: bool,
        work_item_created: bool,
        coordinator_created: bool,
        terminal_reason: str,
        accepted_stage_count: int,
        egress_lease_created: bool,
        egress_deactivated: bool,
    ) -> dict[str, object]:
        return {
            "accepted_stage_count": accepted_stage_count,
            "approval_id": str(approval.approval_id),
            "coordinator_created": coordinator_created,
            "coordinator_run_id": str(coordinator_run_id),
            "controlled_egress_deactivated_after_m1": egress_deactivated,
            "controlled_egress_lease_created": egress_lease_created,
            "release_created": release_created,
            "release_id": str(release.id),
            "terminal_reason": terminal_reason,
            "terminal_state": "NOT_AUTHORIZED",
            "work_item_created": work_item_created,
        }
