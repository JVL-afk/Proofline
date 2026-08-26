from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from opintel_research.domain import Business, ResearchRun
from opintel_research_worker.activation import (
    A09_MARKER_PREFIX,
    FrozenA09DecisionRegistry,
    SampledSlotActivator,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json"
A09 = ROOT / "infra/container/phase1-worker/phase1-a09-decision-registry.json"
RUNTIME = "sha256:" + "9" * 64
A09_SHA256 = "1d938be8cf8946bd2b3d0d652500590652e031e056c69ddb0f9449b348261182"
WORKSPACE = UUID("10000000-0000-4000-8000-000000000001")


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch: pytest.MonkeyPatch):
    calls: list[object] = []

    def deny(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("activation denial must precede DNS")

    monkeypatch.setattr(socket, "getaddrinfo", deny)
    yield
    assert calls == []


def _release(**changes: object) -> LiveResearchPermissionRelease:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": UUID("10000000-0000-4000-8000-000000000010"),
        "workspace_id": WORKSPACE,
        "version": "m67.slot01.release@1",
        "configuration_hash": "a" * 64,
        "created_at": now - timedelta(minutes=1),
        "activity": PermissionActivity.REAL_PUBLIC_RESEARCH,
        "state": PermissionState.AUTHORIZED,
        "source_registry_id": uuid4(),
        "source_registry_hash": "source",
        "retention_policy_id": uuid4(),
        "retention_policy_hash": "retention",
        "environment_id": uuid4(),
        "environment_hash": "environment",
        "cohort_policy_id": uuid4(),
        "cohort_or_run_restriction": "PHASE1_SLOT_01",
        "starts_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(minutes=14),
        "approval_ids": ("owner", f"{A09_MARKER_PREFIX}{A09_SHA256}"),
        "kill_switch_id": uuid4(),
        "slot_number": 1,
        "business_identity": "903 HVAC",
        "exact_hostname": "903hvac.com",
        "ordered_package_sha256": (
            "3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b"
        ),
        "research_runtime_revision": RUNTIME,
        "max_logical_requests": 5,
        "max_attempts": 5,
        "max_response_bytes": 250_000,
        "max_total_bytes": 1_250_000,
        "max_duration_seconds": 120,
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": ("903hvac.com",),
        "owner_approval_sha256": "b" * 64,
    }
    values.update(changes)
    return LiveResearchPermissionRelease(**values)


class _Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class _Stop:
    def __init__(self, active: bool = False) -> None:
        self.active = active

    def is_active(self) -> bool:
        return self.active


class _Authority:
    def __init__(self, release: LiveResearchPermissionRelease | Exception) -> None:
        self.release = release
        self.authorized: list[UUID] = []

    def current_release(self) -> LiveResearchPermissionRelease:
        if isinstance(self.release, Exception):
            raise self.release
        return self.release

    def authorize(self, run: ResearchRun, business: Business) -> None:
        release = self.current_release()
        activation = run.sampled_slot_activation
        identity = run.sampled_slot_identity
        if (
            activation is None
            or identity is None
            or activation.authorization_release_id != release.id
            or identity.slot_number != release.slot_number
            or identity.business_identity != business.name
            or identity.exact_hostname != business.permitted_host
        ):
            raise ValueError("work item authority mismatch")
        self.authorized.append(run.id)


class _Repository:
    def __init__(self) -> None:
        self.businesses: dict[UUID, Business] = {}
        self.runs: dict[UUID, ResearchRun] = {}
        self.activation_calls = 0

    def get_business(self, workspace_id: UUID, business_id: UUID) -> Business | None:
        value = self.businesses.get(business_id)
        return value if value and value.workspace_id == workspace_id else None

    def get_run(self, workspace_id: UUID, run_id: UUID) -> ResearchRun | None:
        value = self.runs.get(run_id)
        return value if value and value.workspace_id == workspace_id else None

    def activate_sampled_run(
        self, business: Business, run: ResearchRun, idempotency_key: str
    ) -> tuple[ResearchRun, bool]:
        assert idempotency_key.endswith(":1")
        self.activation_calls += 1
        existing = self.runs.get(run.id)
        if existing:
            return existing, False
        self.businesses[business.id] = business
        self.runs[run.id] = run
        return run, True


def _activator(
    release: LiveResearchPermissionRelease | Exception,
    *,
    stop: _Stop | None = None,
    repository: _Repository | None = None,
) -> tuple[SampledSlotActivator, _Repository]:
    repository = repository or _Repository()
    return (
        SampledSlotActivator(
            sample_registry=FrozenPhaseOneSampleRegistry(SAMPLES),
            a09_registry=FrozenA09DecisionRegistry(A09),
            repository=repository,
            authority=_Authority(release),
            stop_signal=stop or _Stop(),
            clock=_Clock(),
            runtime_revision=RUNTIME,
        ),
        repository,
    )


def test_exact_release_derives_only_frozen_slot01_and_is_idempotent() -> None:
    release = _release()
    activator, repository = _activator(release)
    first, created = activator.activate(1, release.id)
    second, duplicate_created = activator.activate(1, release.id)
    assert created is True
    assert duplicate_created is False
    assert first == second
    assert repository.activation_calls == 1
    assert len(repository.runs) == 1
    assert first.sampled_slot_identity is not None
    assert first.sampled_slot_identity.business_identity == "903 HVAC"
    assert first.sampled_slot_identity.exact_hostname == "903hvac.com"
    assert first.sampled_slot_activation is not None
    assert first.sampled_slot_activation.a09_decision_sha256 == A09_SHA256


@pytest.mark.parametrize(
    ("release", "slot", "release_id"),
    [
        (_release(), 99, _release().id),
        (_release(), 1, UUID("10000000-0000-4000-8000-000000000099")),
        (_release(activity=PermissionActivity.REAL_BUSINESS_DISCOVERY), 1, _release().id),
        (_release(slot_number=2), 1, _release().id),
        (_release(ordered_package_sha256="f" * 64), 1, _release().id),
        (_release(business_identity="Forged"), 1, _release().id),
        (
            _release(
                exact_hostname="forged.example",
                allowed_source_scope=("forged.example",),
            ),
            1,
            _release().id,
        ),
        (_release(state=PermissionState.NOT_AUTHORIZED), 1, _release().id),
        (_release(approval_ids=("owner",)), 1, _release().id),
        (_release(research_runtime_revision="sha256:" + "8" * 64), 1, _release().id),
    ],
    ids=(
        "nonexistent-slot",
        "wrong-release",
        "wrong-permission",
        "wrong-slot",
        "wrong-package",
        "wrong-business",
        "wrong-host",
        "revoked-or-not-authorized",
        "missing-a09",
        "wrong-runtime",
    ),
)
def test_invalid_activation_creates_no_work(
    release: LiveResearchPermissionRelease, slot: int, release_id: UUID
) -> None:
    activator, repository = _activator(release)
    with pytest.raises((ValueError, IndexError)):
        activator.activate(slot, release_id)
    assert repository.runs == {}
    assert repository.businesses == {}


def test_expired_malformed_and_kill_switch_create_no_work() -> None:
    past = datetime.now(UTC) - timedelta(minutes=2)
    expired = _release(starts_at=past - timedelta(minutes=15), expires_at=past)
    activator, repository = _activator(expired)
    with pytest.raises(ValueError):
        activator.activate(1, expired.id)
    malformed, malformed_repository = _activator(ValueError("malformed release"))
    with pytest.raises(ValueError):
        malformed.activate(1, uuid4())
    stopped, stopped_repository = _activator(_release(), stop=_Stop(True))
    with pytest.raises(ValueError):
        stopped.activate(1, _release().id)
    assert repository.runs == malformed_repository.runs == stopped_repository.runs == {}


def test_activation_record_hash_and_registry_are_content_addressed() -> None:
    release = _release()
    run, _ = _activator(release)[0].activate(1, release.id)
    activation = run.sampled_slot_activation
    assert activation is not None
    assert activation.activation_sha256 == activation.computed_sha256()
    assert len(FrozenA09DecisionRegistry(A09).file_sha256) == 64
