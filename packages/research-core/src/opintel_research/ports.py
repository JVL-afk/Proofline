"""Ports for M1 research adapters."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from opintel_research.domain import (
    Business,
    CaptureQuarantine,
    CrawlPolicy,
    DurableMinimizedCapture,
    DurablePageBundle,
    ExtractedMaterial,
    FetchAttempt,
    FetchedDocument,
    MinimizedPageSnapshot,
    PageSnapshot,
    RawHttpResponse,
    ResearchEvidence,
    ResearchPage,
    ResearchRun,
    RobotsPolicyEvidence,
    ValidatedUrl,
)


class Resolver(Protocol):
    def resolve(self, host: str, port: int) -> tuple[str, ...]: ...


class HttpTransport(Protocol):
    def request(
        self, target: ValidatedUrl, timeout_seconds: float, max_bytes: int
    ) -> RawHttpResponse: ...


class PublicFetcher(Protocol):
    def fetch(
        self, url: str, permitted_host: str, policy: CrawlPolicy, attempt_number: int
    ) -> FetchedDocument: ...


class BrowserFallback(Protocol):
    def render(self, url: str, permitted_host: str) -> FetchedDocument: ...


class HtmlExtractor(Protocol):
    name: str
    version: str

    def extract(
        self, snapshot: PageSnapshot, material_id: UUID, now: datetime
    ) -> ExtractedMaterial: ...


class Sleeper(Protocol):
    def sleep(self, seconds: float) -> None: ...


class StopSignal(Protocol):
    def is_active(self) -> bool: ...


class ResearchAuthorization(Protocol):
    def authorize(self, run: ResearchRun, business: Business) -> None: ...


class CaptureMinimizer(Protocol):
    def minimize(
        self, snapshot: PageSnapshot, business_name: str, observed_visible_text: str
    ) -> DurableMinimizedCapture | CaptureQuarantine: ...


class RobotsPolicy(Protocol):
    def evaluate(
        self, research_run_id: UUID, url: str, permitted_host: str, policy: CrawlPolicy
    ) -> RobotsPolicyEvidence: ...


class ResearchRepository(Protocol):
    def initialize(self) -> None: ...
    def create_business(self, business: Business) -> Business: ...
    def get_business(self, workspace_id: UUID, business_id: UUID) -> Business | None: ...
    def create_or_get_run(
        self, run: ResearchRun, idempotency_key: str
    ) -> tuple[ResearchRun, bool]: ...
    def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None: ...
    def claim_run(self, now: datetime, lease: timedelta) -> ResearchRun | None: ...
    def recover_stale_runs(self, now: datetime) -> int: ...
    def record_attempt(self, attempt: FetchAttempt) -> None: ...
    def record_robots_evidence(self, evidence: RobotsPolicyEvidence) -> None: ...
    def list_attempts(self, workspace_id: UUID, run_id: UUID) -> list[FetchAttempt]: ...
    def save_page_bundle(
        self,
        page: ResearchPage,
        bundle: DurablePageBundle,
    ) -> None: ...
    def save_quarantined_page(
        self, page: ResearchPage, quarantine: CaptureQuarantine, attempt: FetchAttempt
    ) -> None: ...
    def save_failed_page(self, page: ResearchPage, attempt: FetchAttempt) -> None: ...
    def find_cached_snapshot(
        self, workspace_id: UUID, business_id: UUID, normalized_url: str, not_before: datetime
    ) -> tuple[MinimizedPageSnapshot, ExtractedMaterial] | None: ...
    def complete_run(
        self,
        run_id: UUID,
        status: str,
        pages_attempted: int,
        pages_succeeded: int,
        bytes_stored: int,
        now: datetime,
        error_code: str | None = None,
        safe_message: str | None = None,
    ) -> None: ...
    def list_pages(self, workspace_id: UUID, run_id: UUID) -> list[ResearchPage]: ...
    def get_page(self, workspace_id: UUID, page_id: UUID) -> ResearchPage | None: ...
    def get_snapshot(
        self, workspace_id: UUID, snapshot_id: UUID
    ) -> MinimizedPageSnapshot | None: ...
    def get_material(self, workspace_id: UUID, material_id: UUID) -> ExtractedMaterial | None: ...
    def list_evidence(self, workspace_id: UUID, run_id: UUID) -> list[ResearchEvidence]: ...
    def get_evidence(self, workspace_id: UUID, evidence_id: UUID) -> ResearchEvidence | None: ...
