"""One-shot, network-free validation of the deployed Phase 1 persistence boundary."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID, uuid5

from opintel_research import ObservationalHtmlExtractor, ResearchWorkflowRunner
from opintel_research.domain import (
    Business,
    CrawlPolicy,
    FetchedDocument,
    MinimizedPageSnapshot,
    ResearchRun,
    ResearchRunStatus,
    contains_prohibited_contact_value,
)
from opintel_research.ports import StopSignal
from opintel_research_local import (
    DisabledBrowserFallback,
    ResearchWorkerSettings,
    SqlAlchemyResearchRepository,
    SystemClock,
)

from opintel_research_worker.kill_switch import AwsSsmStopSignal
from opintel_research_worker.minimization import ProductionPhaseOneCaptureMinimizer

_NAMESPACE: Final = UUID("4c0ab969-cc2b-4a7e-9edf-4efb5567a4d7")
_MODES: Final = frozenset(
    {"KILL_SWITCH_BLOCK_V1", "MINIMIZATION_PERSISTENCE_V1", "RESTORE_INSPECTION_V1"}
)
_FIXTURE: Final = b"""<html><head><title>Synthetic Commercial HVAC</title></head><body>
<h1>Texas commercial HVAC service for business facilities</h1>
<p>Businesses may request a service estimate online.</p>
<p>Email validation@example.invalid or call +1 (512) 555-0199.</p>
<section class="staff contact-card"><h2>Synthetic Technician</h2>
<p>technician@example.invalid</p><p>512-555-0101</p></section>
<script type="application/ld+json">{"@type":"ContactPoint","telephone":"5125550102"}</script>
</body></html>"""
_PROHIBITED: Final = (
    "validation@example.invalid",
    "technician@example.invalid",
    "512-555-0199",
    "512-555-0101",
    "5125550102",
    "Synthetic Technician",
)


class _NoSleep:
    def sleep(self, seconds: float) -> None:
        del seconds


class _DeterministicIdentifiers:
    def __init__(self, validation_id: str) -> None:
        self._validation_id = validation_id
        self._counter = 0

    def new(self) -> UUID:
        self._counter += 1
        return uuid5(_NAMESPACE, f"{self._validation_id}:generated:{self._counter}")


class _SyntheticFetcher:
    """Returns the image-contained fixture and cannot perform network I/O."""

    def __init__(self) -> None:
        self.called = False

    def fetch(
        self, url: str, permitted_host: str, policy: CrawlPolicy, attempt_number: int
    ) -> FetchedDocument:
        del policy, attempt_number
        if url != "https://synthetic.invalid/" or permitted_host != "synthetic.invalid":
            raise RuntimeError("synthetic validation attempted an unauthorized source")
        self.called = True
        return FetchedDocument(
            source_url=url,
            canonical_url=url,
            final_url=url,
            status_code=200,
            headers=(("content-type", "text/html; charset=utf-8"),),
            content=_FIXTURE,
            content_type="text/html",
            charset="utf-8",
            captured_at=SystemClock().now(),
        )


@dataclass(frozen=True, slots=True)
class SyntheticValidationResult:
    mode: str
    validation_ref_sha256: str
    run_status: str
    fetch_called: bool
    snapshot_count: int
    evidence_count: int
    removed_email_count: int
    removed_phone_count: int
    removed_structured_contact_blocks: int
    source_content_sha256: str | None
    minimized_content_sha256: str | None
    minimization_event_sha256: str | None

    def safe_log_record(self) -> str:
        return json.dumps(
            {"event": "phase1.synthetic_validation.completed", **asdict(self)},
            sort_keys=True,
            separators=(",", ":"),
        )


def _ids(validation_id: str) -> dict[str, UUID]:
    return {
        name: uuid5(_NAMESPACE, f"{validation_id}:{name}")
        for name in ("workspace", "business", "run", "operation", "trace")
    }


def _inspect(
    repository: SqlAlchemyResearchRepository,
    validation_id: str,
    mode: str,
    *,
    fetch_called: bool,
) -> SyntheticValidationResult:
    ids = _ids(validation_id)
    run = repository.get_run(ids["workspace"], ids["run"])
    if run is None:
        raise RuntimeError("synthetic validation run is missing")
    pages = repository.list_pages(ids["workspace"], ids["run"])
    snapshots: list[MinimizedPageSnapshot] = []
    for page in pages:
        if page.snapshot_id is not None:
            snapshot = repository.get_snapshot(ids["workspace"], page.snapshot_id)
            if snapshot is not None:
                snapshots.append(snapshot)
    evidence = repository.list_evidence(ids["workspace"], ids["run"])

    if mode == "KILL_SWITCH_BLOCK_V1":
        if fetch_called or snapshots or run.status is not ResearchRunStatus.FAILED:
            raise RuntimeError("kill-switch synthetic validation failed closed-state checks")
        if run.last_error_code != "kill_switch_active":
            raise RuntimeError("kill-switch synthetic validation lacks the expected reason")
        return SyntheticValidationResult(
            mode=mode,
            validation_ref_sha256=hashlib.sha256(validation_id.encode()).hexdigest(),
            run_status=run.status.value,
            fetch_called=False,
            snapshot_count=0,
            evidence_count=0,
            removed_email_count=0,
            removed_phone_count=0,
            removed_structured_contact_blocks=0,
            source_content_sha256=None,
            minimized_content_sha256=None,
            minimization_event_sha256=None,
        )

    if run.status is not ResearchRunStatus.SUCCEEDED or len(snapshots) != 1:
        raise RuntimeError("minimized synthetic validation did not produce one successful snapshot")
    snapshot = snapshots[0]
    durable_values = [snapshot.minimized_text]
    for page in pages:
        if page.material_id is not None:
            material = repository.get_material(ids["workspace"], page.material_id)
            if material is None or material.contacts:
                raise RuntimeError("durable synthetic material retained contact data")
            durable_values.extend((material.visible_text, repr(material.metadata)))
    durable_values.extend(item.extracted_fragment for item in evidence)
    durable_text = "\n".join(durable_values)
    if any(value in durable_text for value in _PROHIBITED):
        raise RuntimeError("durable synthetic validation retained a prohibited value")
    if contains_prohibited_contact_value(durable_text):
        raise RuntimeError("durable synthetic validation retained contact-shaped data")
    if not evidence or "Texas commercial HVAC service" not in snapshot.minimized_text:
        raise RuntimeError("required synthetic business evidence was not preserved")
    return SyntheticValidationResult(
        mode=mode,
        validation_ref_sha256=hashlib.sha256(validation_id.encode()).hexdigest(),
        run_status=run.status.value,
        fetch_called=fetch_called,
        snapshot_count=1,
        evidence_count=len(evidence),
        removed_email_count=snapshot.removed_email_count,
        removed_phone_count=snapshot.removed_phone_count,
        removed_structured_contact_blocks=snapshot.removed_structured_contact_blocks,
        source_content_sha256=snapshot.source_content_sha256,
        minimized_content_sha256=snapshot.content_sha256,
        minimization_event_sha256=snapshot.minimization_event_sha256,
    )


def execute_synthetic_validation(
    repository: SqlAlchemyResearchRepository,
    mode: str,
    validation_id: str,
    stop_signal: StopSignal,
) -> SyntheticValidationResult:
    if mode not in _MODES:
        raise ValueError("unsupported synthetic validation mode")
    if not validation_id or len(validation_id) > 96:
        raise ValueError("synthetic validation id is required and bounded")
    repository.initialize()
    if mode == "RESTORE_INSPECTION_V1":
        if not stop_signal.is_active():
            raise RuntimeError("restore inspection requires the kill switch to be tripped")
        return _inspect(repository, validation_id, mode, fetch_called=False)

    ids = _ids(validation_id)
    now = SystemClock().now()
    if repository.get_business(ids["workspace"], ids["business"]) is None:
        repository.create_business(
            Business(
                id=ids["business"],
                workspace_id=ids["workspace"],
                name="Synthetic Phase 1 Commercial HVAC Validation",
                canonical_url="https://synthetic.invalid/",
                permitted_host="synthetic.invalid",
                created_by="m67-synthetic-validation",
                created_at=now,
            )
        )
    run = ResearchRun(
        id=ids["run"],
        workspace_id=ids["workspace"],
        business_id=ids["business"],
        operation_id=ids["operation"],
        trace_id=ids["trace"],
        start_url="https://synthetic.invalid/",
        permitted_host="synthetic.invalid",
        policy=CrawlPolicy(max_pages=1, max_attempts=1, per_domain_delay_seconds=0),
        status=ResearchRunStatus.PENDING,
        created_by="m67-synthetic-validation",
        created_at=now,
        updated_at=now,
    )
    _, created = repository.create_or_get_run(run, f"synthetic:{validation_id}")
    if not created:
        raise RuntimeError("synthetic validation id has already been consumed")
    fetcher = _SyntheticFetcher()
    runner = ResearchWorkflowRunner(
        repository=repository,
        fetcher=fetcher,
        browser=DisabledBrowserFallback(),
        extractor=ObservationalHtmlExtractor(),
        clock=SystemClock(),
        identifiers=_DeterministicIdentifiers(validation_id),
        sleeper=_NoSleep(),
        capture_minimizer=ProductionPhaseOneCaptureMinimizer(),
        lease_duration=timedelta(seconds=30),
        stop_signal=stop_signal,
    )
    if not runner.run_once():
        raise RuntimeError("synthetic validation run was not claimed")
    return _inspect(repository, validation_id, mode, fetch_called=fetcher.called)


def run_deployed_synthetic_validation(
    settings: ResearchWorkerSettings, mode: str, validation_id: str
) -> None:
    if settings.app_env != "phase1":
        raise RuntimeError("deployed synthetic validation requires Phase 1 configuration")
    if settings.research_live_enabled or settings.research_browser_enabled:
        raise RuntimeError(
            "deployed synthetic validation requires live and browser access disabled"
        )
    if settings.egress_policy_revision != "NOT_AUTHORIZED":
        raise RuntimeError("deployed synthetic validation requires egress policy NOT_AUTHORIZED")
    repository = SqlAlchemyResearchRepository(settings.resolved_database_url())
    try:
        result = execute_synthetic_validation(
            repository,
            mode,
            validation_id,
            AwsSsmStopSignal(settings.kill_switch_parameter or "", settings.aws_region),
        )
        logging.info(result.safe_log_record())
    finally:
        repository.engine.dispose()


__all__ = [
    "SyntheticValidationResult",
    "execute_synthetic_validation",
    "run_deployed_synthetic_validation",
]
