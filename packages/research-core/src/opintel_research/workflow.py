"""Bounded durable M1 crawl orchestration."""

from __future__ import annotations

import hashlib
from collections import deque
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID

from opintel_m0.ports import Clock, IdentifierFactory

from opintel_research.domain import (
    BrowserFallbackUnavailable,
    CaptureQuarantine,
    DurableMinimizedCapture,
    DurablePageBundle,
    ExtractedMaterial,
    FetchAttempt,
    FetchError,
    MinimizedPageSnapshot,
    PageSnapshot,
    PageStatus,
    ResearchEvidence,
    ResearchPage,
    ResearchRun,
    ResearchRunStatus,
    UrlPolicyError,
    contains_prohibited_contact_value,
)
from opintel_research.ports import (
    BrowserFallback,
    CaptureMinimizer,
    HtmlExtractor,
    PublicFetcher,
    ResearchRepository,
    Sleeper,
    StopSignal,
)
from opintel_research.url_policy import normalize_public_url


class ResearchWorkflowRunner:
    def __init__(
        self,
        repository: ResearchRepository,
        fetcher: PublicFetcher,
        browser: BrowserFallback,
        extractor: HtmlExtractor,
        clock: Clock,
        identifiers: IdentifierFactory,
        sleeper: Sleeper,
        capture_minimizer: CaptureMinimizer,
        lease_duration: timedelta = timedelta(seconds=60),
        stop_signal: StopSignal | None = None,
    ) -> None:
        self._repository = repository
        self._fetcher = fetcher
        self._browser = browser
        self._extractor = extractor
        self._clock = clock
        self._identifiers = identifiers
        self._sleeper = sleeper
        self._capture_minimizer = capture_minimizer
        self._lease = lease_duration
        self._stop_signal = stop_signal

    def recover_stale(self) -> int:
        return self._repository.recover_stale_runs(self._clock.now())

    def run_once(self) -> bool:
        run = self._repository.claim_run(self._clock.now(), self._lease)
        if run is None:
            return False
        self._execute(run)
        return True

    def _execute(self, run: ResearchRun) -> None:
        business = self._repository.get_business(run.workspace_id, run.business_id)
        if business is None:
            raise RuntimeError("research business is missing")
        queue: deque[tuple[str, int]] = deque([(run.start_url, 0)])
        visited: set[str] = set()
        pages_attempted = 0
        pages_succeeded = 0
        total_bytes = 0
        first_error: str | None = None
        started = self._clock.now()
        policy = run.policy

        while queue and pages_attempted < policy.max_pages:
            if self._stop_signal is not None and self._stop_signal.is_active():
                first_error = first_error or "kill_switch_active"
                break
            if (self._clock.now() - started).total_seconds() >= policy.max_duration_seconds:
                first_error = first_error or "crawl_duration_exceeded"
                break
            requested_url, depth = queue.popleft()
            try:
                normalized = normalize_public_url(requested_url)
                if (urlsplit(normalized).hostname or "") != run.permitted_host:
                    raise UrlPolicyError("link host is outside permit")
            except UrlPolicyError:
                continue
            if normalized in visited:
                continue
            visited.add(normalized)
            pages_attempted += 1

            cached = self._repository.find_cached_snapshot(
                run.workspace_id,
                run.business_id,
                normalized,
                self._clock.now() - timedelta(seconds=policy.cache_ttl_seconds),
            )
            if cached is not None:
                snapshot, material = cached
                if total_bytes + snapshot.content_length > policy.max_total_bytes:
                    first_error = first_error or "crawl_byte_budget_exceeded"
                    break
                page = ResearchPage(
                    id=self._identifiers.new(),
                    workspace_id=run.workspace_id,
                    business_id=run.business_id,
                    research_run_id=run.id,
                    requested_url=requested_url,
                    normalized_url=normalized,
                    depth=depth,
                    status=PageStatus.CACHED,
                    snapshot_id=snapshot.id,
                    material_id=material.id,
                    fetched_at=self._clock.now(),
                )
                evidence = self._evidence(run, page, snapshot, material)
                self._repository.save_page_bundle(
                    page, DurablePageBundle(snapshot, material, tuple(evidence))
                )
                pages_succeeded += 1
                total_bytes += snapshot.content_length
                self._enqueue_links(queue, material.links, depth, run)
                continue

            document = None
            final_error: FetchError | UrlPolicyError | None = None
            for attempt_number in range(1, policy.max_attempts + 1):
                if self._stop_signal is not None and self._stop_signal.is_active():
                    final_error = FetchError("kill_switch_active", "research is suspended")
                    break
                attempt_started = self._clock.now()
                if policy.per_domain_delay_seconds and (pages_attempted > 1 or attempt_number > 1):
                    self._sleeper.sleep(policy.per_domain_delay_seconds)
                try:
                    document = self._fetcher.fetch(
                        normalized, run.permitted_host, policy, attempt_number
                    )
                    self._repository.record_attempt(
                        FetchAttempt(
                            id=self._identifiers.new(),
                            research_run_id=run.id,
                            normalized_url=normalized,
                            attempt_number=attempt_number,
                            started_at=attempt_started,
                            completed_at=self._clock.now(),
                            outcome="succeeded",
                        )
                    )
                    break
                except (FetchError, UrlPolicyError) as error:
                    final_error = error
                    self._repository.record_attempt(
                        FetchAttempt(
                            id=self._identifiers.new(),
                            research_run_id=run.id,
                            normalized_url=normalized,
                            attempt_number=attempt_number,
                            started_at=attempt_started,
                            completed_at=self._clock.now(),
                            outcome="retryable_failure" if error.retryable else "permanent_failure",
                            error_code=error.code,
                        )
                    )
                    if not error.retryable or attempt_number >= policy.max_attempts:
                        break
                    self._sleeper.sleep(min(2 ** (attempt_number - 1), 4))

            if document is None:
                error_code = final_error.code if final_error else "fetch_failed"
                first_error = first_error or error_code
                now = self._clock.now()
                page = ResearchPage(
                    id=self._identifiers.new(),
                    workspace_id=run.workspace_id,
                    business_id=run.business_id,
                    research_run_id=run.id,
                    requested_url=requested_url,
                    normalized_url=normalized,
                    depth=depth,
                    status=PageStatus.FAILED,
                    snapshot_id=None,
                    material_id=None,
                    fetched_at=now,
                    error_code=error_code,
                )
                self._repository.save_failed_page(
                    page,
                    FetchAttempt(
                        id=self._identifiers.new(),
                        research_run_id=run.id,
                        normalized_url=normalized,
                        attempt_number=0,
                        started_at=now,
                        completed_at=now,
                        outcome="page_failed",
                        error_code=error_code,
                    ),
                )
                continue

            if total_bytes + len(document.content) > policy.max_total_bytes:
                first_error = first_error or "crawl_byte_budget_exceeded"
                break
            raw_snapshot = self._snapshot(run, document)
            raw_material = self._extractor.extract(
                raw_snapshot, self._identifiers.new(), self._clock.now()
            )
            if (
                policy.browser_fallback_enabled
                and len(raw_material.visible_text) < 40
                and "html" in raw_snapshot.content_type
            ):
                try:
                    rendered = self._browser.render(normalized, run.permitted_host)
                    raw_snapshot = self._snapshot(run, rendered)
                    raw_material = self._extractor.extract(
                        raw_snapshot, self._identifiers.new(), self._clock.now()
                    )
                except BrowserFallbackUnavailable:
                    pass

            minimized = self._minimize(raw_snapshot, business.name, raw_material.visible_text)
            if isinstance(minimized, CaptureQuarantine):
                now = self._clock.now()
                first_error = first_error or "minimization_quarantine"
                self._repository.save_quarantined_page(
                    ResearchPage(
                        id=self._identifiers.new(),
                        workspace_id=run.workspace_id,
                        business_id=run.business_id,
                        research_run_id=run.id,
                        requested_url=requested_url,
                        normalized_url=normalized,
                        depth=depth,
                        status=PageStatus.FAILED,
                        snapshot_id=None,
                        material_id=None,
                        fetched_at=now,
                        error_code="minimization_quarantine",
                    ),
                    minimized,
                    FetchAttempt(
                        id=self._identifiers.new(),
                        research_run_id=run.id,
                        normalized_url=normalized,
                        attempt_number=0,
                        started_at=now,
                        completed_at=now,
                        outcome="quarantined",
                        error_code="minimization_quarantine",
                    ),
                )
                continue

            snapshot = self._durable_snapshot(raw_snapshot, minimized)
            material = self._durable_material(raw_material, snapshot)
            evidence = self._evidence(run, page_id := self._identifiers.new(), snapshot, material)
            page = ResearchPage(
                id=page_id,
                workspace_id=run.workspace_id,
                business_id=run.business_id,
                research_run_id=run.id,
                requested_url=requested_url,
                normalized_url=normalized,
                depth=depth,
                status=PageStatus.FETCHED,
                snapshot_id=snapshot.id,
                material_id=material.id,
                fetched_at=snapshot.captured_at,
            )
            self._repository.save_page_bundle(
                page, DurablePageBundle(snapshot, material, tuple(evidence))
            )
            pages_succeeded += 1
            total_bytes += snapshot.content_length
            self._enqueue_links(queue, raw_material.links, depth, run)

        if pages_succeeded == 0:
            status = ResearchRunStatus.FAILED
        elif first_error:
            status = ResearchRunStatus.PARTIAL
        else:
            status = ResearchRunStatus.SUCCEEDED
        self._repository.complete_run(
            run.id,
            status,
            pages_attempted,
            pages_succeeded,
            total_bytes,
            self._clock.now(),
            first_error,
            "bounded research completed with failures" if first_error else None,
        )

    def _snapshot(self, run: ResearchRun, document: object) -> PageSnapshot:
        from opintel_research.domain import FetchedDocument

        assert isinstance(document, FetchedDocument)
        digest = hashlib.sha256(document.content).hexdigest()
        return PageSnapshot(
            id=self._identifiers.new(),
            workspace_id=run.workspace_id,
            business_id=run.business_id,
            research_run_id=run.id,
            operation_id=run.operation_id,
            trace_id=run.trace_id,
            source_url=document.source_url,
            canonical_url=document.canonical_url,
            final_url=document.final_url,
            snapshot_version=f"sha256:{digest}",
            captured_at=document.captured_at,
            content_sha256=digest,
            content_type=document.content_type,
            charset=document.charset,
            status_code=document.status_code,
            content_length=len(document.content),
            response_headers=document.headers,
            content=document.content,
        )

    def _minimize(
        self, snapshot: PageSnapshot, business_name: str, observed_visible_text: str
    ) -> DurableMinimizedCapture | CaptureQuarantine:
        try:
            return self._capture_minimizer.minimize(snapshot, business_name, observed_visible_text)
        except Exception:
            raw_hash = hashlib.sha256(snapshot.content).hexdigest()
            event = hashlib.sha256(
                f"{raw_hash}|MINIMIZATION_FAILED|phase1-minimizer@1".encode()
            ).hexdigest()
            return CaptureQuarantine(
                source_uri=snapshot.final_url,
                captured_at=snapshot.captured_at,
                raw_content_sha256=raw_hash,
                required_evidence_markers=(),
                quarantine_reasons=("MINIMIZATION_FAILED",),
                minimizer_version="phase1-minimizer@1",
                minimization_event_sha256=event,
            )

    @staticmethod
    def _durable_snapshot(
        raw: PageSnapshot, capture: DurableMinimizedCapture
    ) -> MinimizedPageSnapshot:
        minimized = capture.minimized_text
        return MinimizedPageSnapshot(
            id=raw.id,
            workspace_id=raw.workspace_id,
            business_id=raw.business_id,
            research_run_id=raw.research_run_id,
            operation_id=raw.operation_id,
            trace_id=raw.trace_id,
            source_url=raw.source_url,
            canonical_url=raw.canonical_url,
            final_url=raw.final_url,
            snapshot_version=f"minimized-sha256:{capture.minimized_content_sha256}",
            captured_at=raw.captured_at,
            source_content_sha256=capture.raw_content_sha256,
            content_sha256=capture.minimized_content_sha256,
            content_type="text/plain",
            charset="utf-8",
            status_code=raw.status_code,
            content_length=len(minimized.encode("utf-8")),
            minimized_text=minimized,
            minimizer_version=capture.minimizer_version,
            minimization_event_sha256=capture.minimization_event_sha256,
            removed_email_count=capture.removed_email_count,
            removed_phone_count=capture.removed_phone_count,
            removed_structured_contact_blocks=capture.removed_structured_contact_blocks,
            required_evidence_markers=capture.required_evidence_markers,
        )

    @staticmethod
    def _durable_material(
        raw: ExtractedMaterial, snapshot: MinimizedPageSnapshot
    ) -> ExtractedMaterial:
        minimized = snapshot.minimized_text

        def safe(value: str | None) -> bool:
            return bool(
                value and value in minimized and not contains_prohibited_contact_value(value)
            )

        title = raw.title if safe(raw.title) else None
        headings = tuple(item for item in raw.headings if safe(item[1]))
        buttons = tuple(item for item in raw.buttons if safe(item[1]))
        return ExtractedMaterial(
            id=raw.id,
            snapshot_id=snapshot.id,
            extractor_name="phase1_minimized_projection",
            extractor_version="1",
            title=title,
            metadata=(),
            headings=headings,
            visible_text=minimized,
            links=(),
            forms=(),
            buttons=buttons,
            contacts=(),
            structured_data=(),
            technology_signals=(),
            prompt_injection_suspected=raw.prompt_injection_suspected,
            created_at=raw.created_at,
        )

    def _evidence(
        self,
        run: ResearchRun,
        page: ResearchPage | UUID,
        snapshot: MinimizedPageSnapshot,
        material: object,
    ) -> list[ResearchEvidence]:
        from opintel_research.domain import ExtractedMaterial

        assert isinstance(material, ExtractedMaterial)
        fragments: list[tuple[str, str]] = []
        if material.title:
            fragments.append(("html:title", material.title))
        fragments.extend((locator, text) for _, text, locator in material.headings[:20])
        if material.visible_text:
            fragments.append(("visible-text:0-2000", material.visible_text[:2000]))
        return [
            ResearchEvidence(
                id=self._identifiers.new(),
                workspace_id=run.workspace_id,
                business_id=run.business_id,
                research_run_id=run.id,
                operation_id=run.operation_id,
                trace_id=run.trace_id,
                page_id=page if isinstance(page, UUID) else page.id,
                snapshot_id=snapshot.id,
                snapshot_version=snapshot.snapshot_version,
                source_uri=snapshot.final_url,
                captured_at=snapshot.captured_at,
                content_sha256=snapshot.content_sha256,
                locator=locator,
                extracted_fragment=fragment,
                extractor_name=material.extractor_name,
                extractor_version=material.extractor_version,
                created_at=self._clock.now(),
            )
            for locator, fragment in fragments
        ]

    @staticmethod
    def _enqueue_links(
        queue: deque[tuple[str, int]],
        links: tuple[tuple[str, str, str], ...],
        depth: int,
        run: ResearchRun,
    ) -> None:
        if depth >= run.policy.max_depth:
            return
        for href, _, _ in links:
            try:
                normalized = normalize_public_url(href)
            except UrlPolicyError:
                continue
            if (urlsplit(normalized).hostname or "") == run.permitted_host:
                queue.append((normalized, depth + 1))
