from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from opintel_research.domain import (
    Business,
    CrawlPolicy,
    FetchError,
    ResearchRun,
    ResearchRunStatus,
    SampledSlotIdentity,
)
from opintel_research_worker.authorization import AwsSsmResearchAuthorization
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_research_local import SqlAlchemyResearchRepository
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json"
RUNTIME = "m67-slot01-runtime-successor-v3"
RUN_ID = UUID("00000000-0000-4000-8000-000000000101")
BUSINESS_ID = UUID("00000000-0000-4000-8000-000000000201")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000301")


def _release(**changes: object) -> LiveResearchPermissionRelease:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": UUID("00000000-0000-4000-8000-000000000401"),
        "workspace_id": WORKSPACE_ID,
        "version": "1",
        "configuration_hash": "release-config-v3",
        "created_at": now,
        "activity": PermissionActivity.REAL_PUBLIC_RESEARCH,
        "state": PermissionState.AUTHORIZED,
        "source_registry_id": UUID("00000000-0000-4000-8000-000000000402"),
        "source_registry_hash": "source-registry",
        "retention_policy_id": UUID("00000000-0000-4000-8000-000000000403"),
        "retention_policy_hash": "retention-policy",
        "environment_id": UUID("00000000-0000-4000-8000-000000000404"),
        "environment_hash": "environment",
        "cohort_policy_id": UUID("00000000-0000-4000-8000-000000000405"),
        "cohort_or_run_restriction": "phase1-slot01",
        "starts_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(minutes=14),
        "approval_ids": ("owner-slot01",),
        "kill_switch_id": UUID("00000000-0000-4000-8000-000000000406"),
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
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": ("903hvac.com",),
        "owner_approval_sha256": "a" * 64,
    }
    values.update(changes)
    return LiveResearchPermissionRelease(**values)


class _Ssm:
    def __init__(self, release: LiveResearchPermissionRelease | None) -> None:
        self.release = release

    def get_parameter(self, **_: object) -> dict[str, object]:
        if self.release is None:
            raise RuntimeError("absent")
        return {"Parameter": {"Value": self.release.model_dump_json()}}


def _business(name: str = "903 HVAC", host: str = "903hvac.com") -> Business:
    return Business(
        id=BUSINESS_ID,
        workspace_id=WORKSPACE_ID,
        name=name,
        canonical_url=f"https://{host}/",
        permitted_host=host,
        created_by="synthetic-test",
        created_at=datetime.now(UTC),
    )


def _run(identity: SampledSlotIdentity | None) -> ResearchRun:
    now = datetime.now(UTC)
    return ResearchRun(
        id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        business_id=BUSINESS_ID,
        operation_id=UUID("00000000-0000-4000-8000-000000000501"),
        trace_id=UUID("00000000-0000-4000-8000-000000000502"),
        start_url="https://903hvac.com/",
        permitted_host="903hvac.com",
        policy=CrawlPolicy(),
        status=ResearchRunStatus.PENDING,
        created_by="synthetic-test",
        created_at=now,
        updated_at=now,
        sampled_slot_identity=identity,
    )


def _adapter(monkeypatch: pytest.MonkeyPatch, release: LiveResearchPermissionRelease | None):
    monkeypatch.setattr(
        "opintel_research_worker.authorization.boto3.client", lambda *args, **kwargs: _Ssm(release)
    )
    return AwsSsmResearchAuthorization("/synthetic/release", "us-east-2", RUNTIME, str(REGISTRY))


def test_correct_slot_release_and_work_item_are_permitted(monkeypatch: pytest.MonkeyPatch) -> None:
    identity = FrozenPhaseOneSampleRegistry(REGISTRY).issue(RUN_ID, 1)
    _adapter(monkeypatch, _release()).authorize(_run(identity), _business())


@pytest.mark.parametrize(
    "release_changes",
    [
        {
            "slot_number": 2,
            "business_identity": "Webb Air",
            "exact_hostname": "webbair.com",
            "allowed_source_scope": ("webbair.com",),
        },
        {"ordered_package_sha256": "f" * 64},
        {"business_identity": "Wrong Business"},
        {"exact_hostname": "wrong.example", "allowed_source_scope": ("wrong.example",)},
    ],
    ids=("wrong-slot", "wrong-package", "wrong-business", "wrong-host"),
)
def test_release_mismatches_are_blocked_before_transport(
    monkeypatch: pytest.MonkeyPatch, release_changes: dict[str, object]
) -> None:
    identity = FrozenPhaseOneSampleRegistry(REGISTRY).issue(RUN_ID, 1)
    with pytest.raises(FetchError):
        _adapter(monkeypatch, _release(**release_changes)).authorize(_run(identity), _business())


def test_missing_malformed_and_forged_work_item_identity_are_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(monkeypatch, _release())
    with pytest.raises(FetchError):
        adapter.authorize(_run(None), _business())
    valid = FrozenPhaseOneSampleRegistry(REGISTRY).issue(RUN_ID, 1)
    with pytest.raises(ValueError):
        replace(valid, work_item_id=UUID("00000000-0000-4000-8000-000000000999"))
    forged = SampledSlotIdentity.create(
        ordered_package_file_sha256=valid.ordered_package_file_sha256,
        ordered_package_semantic_sha256=valid.ordered_package_semantic_sha256,
        slot_registry_sha256=valid.slot_registry_sha256,
        slot_number=1,
        business_identity="Forged Business",
        exact_hostname="903hvac.com",
        source_row_sha256=valid.source_row_sha256,
        work_item_id=RUN_ID,
    )
    with pytest.raises(FetchError):
        adapter.authorize(_run(forged), _business())


def test_absent_and_expired_release_are_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    identity = FrozenPhaseOneSampleRegistry(REGISTRY).issue(RUN_ID, 1)
    with pytest.raises(FetchError):
        _adapter(monkeypatch, None).authorize(_run(identity), _business())
    past = datetime.now(UTC) - timedelta(minutes=2)
    with pytest.raises(FetchError):
        _adapter(
            monkeypatch,
            _release(starts_at=past - timedelta(minutes=15), expires_at=past),
        ).authorize(_run(identity), _business())


def test_sampled_identity_round_trips_without_a_schema_migration(tmp_path: Path) -> None:
    repository = SqlAlchemyResearchRepository(f"sqlite:///{tmp_path / 'sampled.db'}")
    repository.initialize()
    business = repository.create_business(_business())
    identity = FrozenPhaseOneSampleRegistry(REGISTRY).issue(RUN_ID, 1)
    expected = _run(identity)
    actual, created = repository.create_or_get_run(expected, "sampled-slot01-v3")
    assert created is True
    assert actual.sampled_slot_identity == identity
    assert repository.get_run(WORKSPACE_ID, RUN_ID) == expected
    assert business.name == identity.business_identity
