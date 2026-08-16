"""Authorized M1 commands and queries."""

from __future__ import annotations

from uuid import UUID

from opintel_m0.domain import AuthorizationError, Principal
from opintel_m0.ports import Clock, IdentifierFactory

from opintel_research.domain import (
    Business,
    CrawlPolicy,
    ExtractedMaterial,
    FetchAttempt,
    PageSnapshot,
    ResearchEvidence,
    ResearchNotFoundError,
    ResearchPage,
    ResearchRun,
    ResearchRunStatus,
)
from opintel_research.ports import ResearchRepository
from opintel_research.url_policy import normalize_public_url


class ResearchApplicationService:
    def __init__(
        self,
        repository: ResearchRepository,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers

    def create_business(self, principal: Principal, name: str, url: str) -> Business:
        self._require_operator(principal)
        normalized = normalize_public_url(url)
        from urllib.parse import urlsplit

        host = urlsplit(normalized).hostname or ""
        business = Business(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            name=name.strip(),
            canonical_url=normalized,
            permitted_host=host,
            created_by=principal.subject,
            created_at=self._clock.now(),
        )
        return self._repository.create_business(business)

    def start_run(
        self,
        principal: Principal,
        business_id: UUID,
        policy: CrawlPolicy,
        idempotency_key: str,
    ) -> tuple[ResearchRun, bool]:
        self._require_operator(principal)
        business = self.get_business(principal, business_id)
        now = self._clock.now()
        run_id = self._identifiers.new()
        run = ResearchRun(
            id=run_id,
            workspace_id=principal.workspace_id,
            business_id=business.id,
            operation_id=self._identifiers.new(),
            trace_id=self._identifiers.new(),
            start_url=business.canonical_url,
            permitted_host=business.permitted_host,
            policy=policy,
            status=ResearchRunStatus.PENDING,
            created_by=principal.subject,
            created_at=now,
            updated_at=now,
        )
        return self._repository.create_or_get_run(run, idempotency_key)

    def get_business(self, principal: Principal, business_id: UUID) -> Business:
        value = self._repository.get_business(principal.workspace_id, business_id)
        if value is None:
            raise ResearchNotFoundError()
        return value

    def get_run(self, principal: Principal, run_id: UUID) -> ResearchRun:
        value = self._repository.get_run(principal.workspace_id, run_id)
        if value is None:
            raise ResearchNotFoundError()
        return value

    def list_pages(self, principal: Principal, run_id: UUID) -> list[ResearchPage]:
        self.get_run(principal, run_id)
        return self._repository.list_pages(principal.workspace_id, run_id)

    def list_attempts(self, principal: Principal, run_id: UUID) -> list[FetchAttempt]:
        self.get_run(principal, run_id)
        return self._repository.list_attempts(principal.workspace_id, run_id)

    def get_snapshot(self, principal: Principal, snapshot_id: UUID) -> PageSnapshot:
        value = self._repository.get_snapshot(principal.workspace_id, snapshot_id)
        if value is None:
            raise ResearchNotFoundError()
        return value

    def get_material(self, principal: Principal, material_id: UUID) -> ExtractedMaterial:
        value = self._repository.get_material(principal.workspace_id, material_id)
        if value is None:
            raise ResearchNotFoundError()
        return value

    def list_evidence(self, principal: Principal, run_id: UUID) -> list[ResearchEvidence]:
        self.get_run(principal, run_id)
        return self._repository.list_evidence(principal.workspace_id, run_id)

    def get_evidence(self, principal: Principal, evidence_id: UUID) -> ResearchEvidence:
        value = self._repository.get_evidence(principal.workspace_id, evidence_id)
        if value is None:
            raise ResearchNotFoundError()
        return value

    @staticmethod
    def _require_operator(principal: Principal) -> None:
        if not principal.can_operate():
            raise AuthorizationError("operator role required")
