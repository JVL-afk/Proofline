"""Bounded production activation for one immutable sampled Phase 1 slot."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_research.domain import (
    Business,
    CrawlPolicy,
    ResearchRun,
    ResearchRunStatus,
    SampledSlotActivation,
)
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

A09_MARKER_PREFIX = "A09_SHA256:"
ACTIVATION_IDEMPOTENCY_REVISION = "m67.phase1.sampled-slot-activation@1"
REPAIR_ATTEMPT_LINEAGE_REVISION = "m67.phase1.repair-attempt@1"
# Deterministic execution-attempt identity for the original (non-repaired) run.
ORIGINAL_ATTEMPT_LINEAGE_SHA256 = hashlib.sha256(
    f"{REPAIR_ATTEMPT_LINEAGE_REVISION}:original".encode()
).hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


V2_CRAWL_PROTOCOL = "phase1-m1@2-bounded-site-crawl"

# PHASE1_M1_V2_BOUNDED_SITE_CRAWL fixed crawl knobs from the sealed execution-
# ceiling envelope (execution_ceilings_sha256
# 083b70520f161d4c21aa72cc221cb063dc2b99cf19ab15caa9c0cd7011b0506b). Only the
# batch-relevant ceilings (useful fetches, total HTTP requests, total bytes,
# duration) are carried per-release and clamped by the materialiser; these knobs
# never vary.
_V2_MAX_DEPTH = 3
_V2_MAX_RESPONSE_BYTES = 1_000_000
_V2_MAX_ATTEMPTS = 2
_V2_MAX_DISCOVERY_FETCHES = 6
_V2_MAX_SITEMAP_ENTRIES = 2_000
_V2_MAX_QUERY_VARIANTS = 3
_V2_MAX_PATH_SEGMENTS = 6
_V2_MAX_PAGES_PER_CATEGORY = 4
_V2_NO_PROGRESS_WINDOW = 3
_V2_LOW_RELEVANCE_FLOOR = 20
_V2_PER_DOMAIN_DELAY_SECONDS = 2.0
_V2_REQUEST_TIMEOUT_SECONDS = 8.0
_V2_MAX_REDIRECTS = 0


def release_execution_ceilings_sha256(release: LiveResearchPermissionRelease) -> str:
    payload: dict[str, object] = {
        "allowed_source_scope": list(release.allowed_source_scope),
        "cost_ceiling_usd": str(release.cost_ceiling_usd),
        "expires_at": release.expires_at.isoformat(),
        "max_attempts": release.max_attempts,
        "max_logical_requests": release.max_logical_requests,
        "max_response_bytes": release.max_response_bytes,
        "max_total_bytes": release.max_total_bytes,
        "max_duration_seconds": release.max_duration_seconds,
        "starts_at": release.starts_at.isoformat(),
        "terminal_rollback_state": release.terminal_rollback_state,
    }
    if release.crawl_protocol_version is not None:
        payload["crawl_protocol_version"] = release.crawl_protocol_version
        payload["max_useful_page_fetches"] = release.max_useful_page_fetches
    return _canonical_sha256(payload)


@dataclass(frozen=True, slots=True)
class A09Decision:
    slot_number: int
    business_identity: str
    exact_hostname: str
    decision_sha256: str
    state: str


class FrozenA09DecisionRegistry:
    """Image-bound accepted exact-host decisions; absence always fails closed."""

    def __init__(self, path: str | Path) -> None:
        raw = Path(path).read_bytes()
        self.file_sha256 = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        if payload.get("schema_version") != "m67-phase1-a09-decision-registry-v1":
            raise ValueError("unsupported A-09 decision registry")
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            raise ValueError("A-09 decision registry is malformed")
        self._decisions = {
            int(item["slot_number"]): A09Decision(
                slot_number=int(item["slot_number"]),
                business_identity=str(item["business_identity"]),
                exact_hostname=str(item["exact_hostname"]),
                decision_sha256=str(item["decision_sha256"]),
                state=str(item["state"]),
            )
            for item in decisions
        }

    def require_approved(self, slot_number: int, business: str, hostname: str) -> A09Decision:
        decision = self._decisions.get(slot_number)
        if (
            decision is None
            or decision.state != "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH"
            or decision.business_identity != business
            or decision.exact_hostname != hostname
            or not re.fullmatch(r"[0-9a-f]{64}", decision.decision_sha256)
        ):
            raise ValueError("exact accepted A-09 decision is absent or mismatched")
        return decision


class ActivationRepository(Protocol):
    def get_business(self, workspace_id: UUID, business_id: UUID) -> Business | None: ...

    def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None: ...

    def activate_sampled_run(
        self, business: Business, run: ResearchRun, idempotency_key: str
    ) -> tuple[ResearchRun, bool]: ...


class ReleaseAuthority(Protocol):
    def current_release(self) -> LiveResearchPermissionRelease: ...

    def authorize(self, run: ResearchRun, business: Business) -> None: ...


class StopSignal(Protocol):
    def is_active(self) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SampledSlotActivator:
    """Resolve caller slot+release into exactly one registry-derived immutable run."""

    def __init__(
        self,
        *,
        sample_registry: FrozenPhaseOneSampleRegistry,
        a09_registry: FrozenA09DecisionRegistry,
        repository: ActivationRepository,
        authority: ReleaseAuthority,
        stop_signal: StopSignal,
        clock: Clock,
        runtime_revision: str,
    ) -> None:
        self._samples = sample_registry
        self._a09 = a09_registry
        self._repository = repository
        self._authority = authority
        self._stop = stop_signal
        self._clock = clock
        self._runtime = runtime_revision

    def activate(self, slot_number: int, release_id: UUID) -> tuple[ResearchRun, bool]:
        if self._stop.is_active():
            raise ValueError("kill switch blocks sampled-slot activation")
        release = self._authority.current_release()
        if release.id != release_id:
            raise ValueError("requested release is not the current exact release")
        self._validate_release(release, slot_number)

        # Execution-attempt identity: stable for an identical sealed authority,
        # distinct for each eligible bounded repair successor within the same
        # frozen experiment. A prior terminal attempt keeps its own identity and
        # is never re-driven or overwritten.
        attempt_lineage = release.repair_attempt_lineage_sha256 or ORIGINAL_ATTEMPT_LINEAGE_SHA256
        attempt_token = (
            f"{ACTIVATION_IDEMPOTENCY_REVISION}:{release.id}:{slot_number}:{attempt_lineage}"
        )
        run_id = uuid5(NAMESPACE_URL, attempt_token)
        # Bounded storage key (<=128) that still uniquely and deterministically
        # identifies the attempt via the lineage-derived run id.
        idempotency_key = f"{ACTIVATION_IDEMPOTENCY_REVISION}:{run_id}"
        identity = self._samples.issue(run_id, slot_number)
        decision = self._a09.require_approved(
            slot_number, identity.business_identity, identity.exact_hostname
        )
        if f"{A09_MARKER_PREFIX}{decision.decision_sha256}" not in release.approval_ids:
            raise ValueError("release does not bind the accepted A-09 decision")

        business_id = uuid5(NAMESPACE_URL, f"m67.phase1.business:{identity.source_row_sha256}")
        now = self._clock.now()
        business = Business(
            id=business_id,
            workspace_id=release.workspace_id,
            name=identity.business_identity,
            canonical_url=f"https://{identity.exact_hostname}/",
            permitted_host=identity.exact_hostname,
            created_by="m67-sampled-slot-activator",
            created_at=release.created_at,
        )
        policy = self._policy(release)
        ceilings_sha256 = release_execution_ceilings_sha256(release)
        activation = SampledSlotActivation.create(
            activation_id=uuid5(
                NAMESPACE_URL,
                f"m67.phase1.activation:{release.id}:{slot_number}:{attempt_lineage}",
            ),
            authorization_release_id=release.id,
            authorization_configuration_hash=release.configuration_hash,
            a09_decision_sha256=decision.decision_sha256,
            research_runtime_revision=self._runtime,
            execution_ceilings_sha256=ceilings_sha256,
            activated_at=now,
            sampled_slot_identity=identity,
        )
        run = ResearchRun(
            id=run_id,
            workspace_id=release.workspace_id,
            business_id=business_id,
            operation_id=uuid5(NAMESPACE_URL, f"m67.phase1.operation:{run_id}"),
            trace_id=uuid5(NAMESPACE_URL, f"m67.phase1.trace:{run_id}"),
            start_url=business.canonical_url,
            permitted_host=business.permitted_host,
            policy=policy,
            status=ResearchRunStatus.PENDING,
            created_by="m67-sampled-slot-activator",
            created_at=now,
            updated_at=now,
            sampled_slot_identity=identity,
            sampled_slot_activation=activation,
            crawl_protocol_version=release.crawl_protocol_version or "phase1-m1@1-homepage",
        )
        self._authority.authorize(run, business)
        if self._stop.is_active():
            raise ValueError("kill switch changed before sampled-slot commit")

        existing = self._repository.get_run(release.workspace_id, run_id)
        if existing is not None:
            existing_business = self._repository.get_business(release.workspace_id, business_id)
            if existing_business is None:
                raise ValueError("duplicate activation has no immutable business")
            self._authority.authorize(existing, existing_business)
            return existing, False

        result, created = self._repository.activate_sampled_run(
            business,
            run,
            idempotency_key,
        )
        # A revocation after commit cannot make the item executable: every worker revalidates the
        # current release before DNS. Revalidate here so the activation caller also fails closed.
        self._authority.authorize(result, business)
        if self._stop.is_active():
            raise ValueError("kill switch changed after sampled-slot commit")
        return result, created

    def _validate_release(self, release: LiveResearchPermissionRelease, slot_number: int) -> None:
        now = self._clock.now()
        if (
            release.activity is not PermissionActivity.REAL_PUBLIC_RESEARCH
            or release.state is not PermissionState.AUTHORIZED
            or release.slot_number != slot_number
            or not release.starts_at <= now < release.expires_at
            or release.research_runtime_revision != self._runtime
            or release.terminal_rollback_state != "NOT_AUTHORIZED"
            or not re.fullmatch(r"[0-9a-f]{64}", release.configuration_hash)
            or release.max_logical_requests is None
            or release.max_attempts is None
            or release.max_response_bytes is None
            or release.max_total_bytes is None
            or release.max_duration_seconds is None
            or release.cost_ceiling_usd != Decimal("0")
        ):
            raise ValueError("release is not an exact bounded sampled-slot authority")
        if release.crawl_protocol_version is not None and (
            release.crawl_protocol_version != V2_CRAWL_PROTOCOL
            or release.max_useful_page_fetches is None
            or release.max_useful_page_fetches < 1
        ):
            raise ValueError("release carries an unrecognised bounded-crawl protocol")
        self._samples.verify_release(release)

    @staticmethod
    def _policy(release: LiveResearchPermissionRelease) -> CrawlPolicy:
        assert release.max_logical_requests is not None
        assert release.max_attempts is not None
        assert release.max_response_bytes is not None
        assert release.max_total_bytes is not None
        assert release.max_duration_seconds is not None
        if release.crawl_protocol_version == V2_CRAWL_PROTOCOL:
            return SampledSlotActivator._policy_v2(release)
        duration = max(
            1,
            min(
                120,
                release.max_duration_seconds,
                int((release.expires_at - release.starts_at).total_seconds()),
            ),
        )
        return CrawlPolicy(
            max_pages=min(10, release.max_logical_requests),
            max_depth=1,
            max_total_bytes=min(5_000_000, release.max_total_bytes),
            max_response_bytes=min(1_000_000, release.max_response_bytes),
            max_compressed_bytes=min(1_000_000, release.max_response_bytes),
            max_duration_seconds=duration,
            request_timeout_seconds=8.0,
            max_redirects=0,
            max_attempts=min(3, release.max_attempts),
            per_domain_delay_seconds=2.0,
            cache_ttl_seconds=0,
            browser_fallback_enabled=False,
        )

    @staticmethod
    def _policy_v2(release: LiveResearchPermissionRelease) -> CrawlPolicy:
        """Bounded-site-crawl policy. The materialiser has already clamped the
        batch-relevant ceilings on the release (useful fetches, total HTTP
        requests via max_logical_requests, total bytes, duration); every other
        knob is fixed by the sealed envelope. No v1 min() re-clamping: the
        release ceilings ARE the authority."""
        useful = release.max_useful_page_fetches
        total_http = release.max_logical_requests
        total_bytes = release.max_total_bytes
        duration = release.max_duration_seconds
        attempts = release.max_attempts
        response_bytes = release.max_response_bytes
        assert useful is not None and total_http is not None and total_bytes is not None
        assert duration is not None and attempts is not None and response_bytes is not None
        return CrawlPolicy(
            max_pages=useful,
            max_depth=_V2_MAX_DEPTH,
            max_total_bytes=total_bytes,
            max_response_bytes=min(_V2_MAX_RESPONSE_BYTES, response_bytes),
            max_compressed_bytes=min(_V2_MAX_RESPONSE_BYTES, response_bytes),
            max_duration_seconds=duration,
            request_timeout_seconds=_V2_REQUEST_TIMEOUT_SECONDS,
            max_redirects=_V2_MAX_REDIRECTS,
            max_attempts=min(_V2_MAX_ATTEMPTS, attempts),
            per_domain_delay_seconds=_V2_PER_DOMAIN_DELAY_SECONDS,
            cache_ttl_seconds=0,
            browser_fallback_enabled=False,
            max_total_http_requests=total_http,
            max_discovery_fetches=_V2_MAX_DISCOVERY_FETCHES,
            max_sitemap_entries_parsed=_V2_MAX_SITEMAP_ENTRIES,
            max_query_variants_per_path=_V2_MAX_QUERY_VARIANTS,
            max_path_segments=_V2_MAX_PATH_SEGMENTS,
            max_pages_per_category=_V2_MAX_PAGES_PER_CATEGORY,
            no_progress_window=_V2_NO_PROGRESS_WINDOW,
            low_relevance_floor=_V2_LOW_RELEVANCE_FLOOR,
            crawl_protocol_version=V2_CRAWL_PROTOCOL,
        )
