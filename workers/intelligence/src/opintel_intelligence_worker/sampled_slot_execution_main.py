"""Only production-capable M6.7 sampled-slot M1-M5 execution entry point."""

from __future__ import annotations

import json
import os
import re
import sys

from opintel_audit import AuditApplicationService, AuditWorkflowRunner, DeterministicAuditComposer
from opintel_audit_local import CanonicalAuditSourceCatalog, SqlAlchemyAuditRepository
from opintel_demo import DemoApplicationService, DemoWorkflowRunner, DeterministicDemoComposer
from opintel_demo_local import (
    CanonicalDemoSourceCatalog,
    SecureLocalCapabilityFactory,
    SqlAlchemyDemoRepository,
)
from opintel_m0.domain import Principal, Role
from opintel_m0_local import SystemClock, UuidFactory
from opintel_opportunity import OpportunityApplicationService, OpportunityWorkflowRunner
from opintel_opportunity_local import (
    EchoMockReasoner,
    ResearchEvidenceCatalog,
    SqlAlchemyOpportunityRepository,
)
from opintel_outreach import (
    DeterministicOutreachComposer,
    OutreachApplicationService,
    OutreachWorkflowRunner,
)
from opintel_outreach_local import CanonicalOutreachSourceCatalog, SqlAlchemyOutreachRepository
from opintel_research_local import (
    ControlledEgressTransport,
    SqlAlchemyResearchRepository,
    get_research_worker_settings,
)
from opintel_research_worker.activation import FrozenA09DecisionRegistry, SampledSlotActivator
from opintel_research_worker.authorization import AwsSsmResearchAuthorization
from opintel_research_worker.egress_lease import SsmControlledEgressLeaseStore
from opintel_research_worker.kill_switch import AwsSsmStopSignal
from opintel_research_worker.main import build_runner
from opintel_research_worker.release_application import BoundedSampledSlotReleaseApplicator
from opintel_research_worker.release_store import AwsSsmReleaseControlStore
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

from opintel_intelligence_worker.controlled_egress_lifecycle import (
    BoundedControlledEgressLifecycle,
)
from opintel_intelligence_worker.coordinator_persistence import SqlAlchemyCoordinatorRepository
from opintel_intelligence_worker.execution import BoundedSampledSlotExecution
from opintel_intelligence_worker.production_runtime import (
    COORDINATOR_ACTOR,
    CanonicalSampledSlotStageRuntime,
)


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"required bounded execution setting is absent: {name}")
    return value


def _required_sha(name: str) -> str:
    value = _required(name)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError(f"bounded execution setting is not a lowercase SHA-256: {name}")
    return value


def run() -> None:
    if len(sys.argv) != 1:
        raise RuntimeError("sampled-slot production execution accepts no caller identity fields")
    settings = get_research_worker_settings()
    if settings.app_env != "phase1":
        raise RuntimeError("sampled-slot production execution requires Phase 1")
    database_url = settings.resolved_database_url()
    clock = SystemClock()
    sample_registry = FrozenPhaseOneSampleRegistry(settings.phase1_slot_registry_path or "")
    a09_registry = FrozenA09DecisionRegistry(_required("OPINTEL_PHASE1_A09_DECISION_REGISTRY_PATH"))
    store = AwsSsmReleaseControlStore(
        approval_parameter=_required("OPINTEL_SLOT_EXECUTION_APPROVAL_PARAMETER"),
        release_parameter=settings.research_release_parameter or "",
        kill_switch_parameter=settings.kill_switch_parameter or "",
        region=settings.aws_region,
    )
    applicator = BoundedSampledSlotReleaseApplicator(
        store=store,
        sample_registry=sample_registry,
        a09_registry=a09_registry,
        runtime_revision=settings.research_runtime_revision or "",
        expected_release_applicator_sha256=_required_sha("OPINTEL_RELEASE_APPLICATOR_SHA256"),
        expected_activation_adapter_sha256=_required_sha("OPINTEL_ACTIVATION_ADAPTER_SHA256"),
        expected_activation_entry_point_sha256=_required_sha(
            "OPINTEL_ACTIVATION_ENTRY_POINT_SHA256"
        ),
        expected_stage_coordinator_sha256=_required_sha("OPINTEL_STAGE_COORDINATOR_SHA256"),
        expected_m1_runtime_sha256=_required_sha("OPINTEL_M1_RUNTIME_SHA256"),
        expected_m2_m5_runtime_sha256=_required_sha("OPINTEL_M2_M5_RUNTIME_SHA256"),
        now=clock.now,
    )
    authority = AwsSsmResearchAuthorization(
        settings.research_release_parameter or "",
        settings.aws_region,
        settings.research_runtime_revision or "",
        settings.phase1_slot_registry_path or "",
        settings.controlled_egress_lease_parameter,
    )
    stop_signal = AwsSsmStopSignal(settings.kill_switch_parameter or "", settings.aws_region)
    research_repository = SqlAlchemyResearchRepository(database_url)
    research_repository.initialize()
    activator = SampledSlotActivator(
        sample_registry=sample_registry,
        a09_registry=a09_registry,
        repository=research_repository,
        authority=authority,
        stop_signal=stop_signal,
        clock=clock,
        runtime_revision=settings.research_runtime_revision or "",
    )
    coordinator_repository = SqlAlchemyCoordinatorRepository(database_url)
    coordinator_repository.initialize()
    research_runner = build_runner()
    egress_transport = ControlledEgressTransport(
        settings.controlled_egress_url or "",
        authority.current_revision,
        authority.current_gateway_capability,
    )
    controlled_egress = BoundedControlledEgressLifecycle(
        store=SsmControlledEgressLeaseStore(
            settings.controlled_egress_lease_parameter or "", settings.aws_region
        ),
        authority=authority,
        stop_signal=stop_signal,
        transport=egress_transport,
    )

    opportunity_repository = SqlAlchemyOpportunityRepository(database_url)
    opportunity_repository.initialize()
    opportunity_service = OpportunityApplicationService(
        opportunity_repository, clock, UuidFactory()
    )
    opportunity_runner = OpportunityWorkflowRunner(
        opportunity_repository,
        ResearchEvidenceCatalog(research_repository),
        EchoMockReasoner(),
        clock,
        UuidFactory(),
    )
    audit_repository = SqlAlchemyAuditRepository(database_url)
    audit_repository.initialize()
    audit_source = CanonicalAuditSourceCatalog(opportunity_repository, research_repository)
    audit_service = AuditApplicationService(audit_repository, audit_source, clock, UuidFactory())
    audit_runner = AuditWorkflowRunner(
        audit_repository, audit_source, DeterministicAuditComposer(UuidFactory()), clock
    )
    demo_repository = SqlAlchemyDemoRepository(database_url)
    demo_repository.initialize()
    demo_source = CanonicalDemoSourceCatalog(
        audit_repository, opportunity_repository, research_repository
    )
    demo_service = DemoApplicationService(
        demo_repository,
        demo_source,
        clock,
        UuidFactory(),
        SecureLocalCapabilityFactory(),
        issuance_enabled=False,
    )
    demo_runner = DemoWorkflowRunner(
        demo_repository, demo_source, DeterministicDemoComposer(UuidFactory()), clock
    )
    outreach_repository = SqlAlchemyOutreachRepository(database_url)
    outreach_repository.initialize()
    outreach_source = CanonicalOutreachSourceCatalog(
        demo_repository, audit_repository, opportunity_repository, research_repository
    )
    outreach_service = OutreachApplicationService(
        outreach_repository, outreach_source, clock, UuidFactory(), generation_enabled=True
    )
    outreach_runner = OutreachWorkflowRunner(
        outreach_repository,
        outreach_source,
        DeterministicOutreachComposer(UuidFactory()),
        clock,
    )

    def stage_runtime(run: object) -> CanonicalSampledSlotStageRuntime:
        workspace_id = run.workspace_id  # type: ignore[attr-defined]
        principal = Principal(
            COORDINATOR_ACTOR,
            workspace_id,
            frozenset({Role.OPERATOR, Role.REVIEWER}),
        )
        return CanonicalSampledSlotStageRuntime(
            workspace_id=workspace_id,
            work_item_id=run.id,  # type: ignore[attr-defined]
            business_id=run.business_id,  # type: ignore[attr-defined]
            principal=principal,
            research_repository=research_repository,
            research_runner=research_runner,
            opportunity_service=opportunity_service,
            opportunity_runner=opportunity_runner,
            audit_service=audit_service,
            audit_runner=audit_runner,
            demo_service=demo_service,
            demo_runner=demo_runner,
            outreach_service=outreach_service,
            outreach_runner=outreach_runner,
        )

    execution = BoundedSampledSlotExecution(
        release_applicator=applicator,
        activator=activator,
        authority=authority,
        stop_signal=stop_signal,
        repository=coordinator_repository,
        stage_runtime_factory=stage_runtime,
        controlled_egress=controlled_egress,
        now=clock.now,
    )
    print(json.dumps(execution.run(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    run()
