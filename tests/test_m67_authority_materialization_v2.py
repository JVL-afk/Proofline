"""materialize_v2: sealed-artifact-bound v2 approval for Slots 02-06."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.authority_materialization import AuthorityMaterializationError
from opintel_research_worker.authority_materialization_v2 import (
    BatchConsumed,
    BatchHeadroomExhausted,
    MaterializationInputsV2,
    materialize_v2,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/readiness/m6.7-deployment"
REGISTRY = str(ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json")
_NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
_ENV_KEYS = {
    "OPINTEL_RELEASE_APPLICATOR_SHA256": "a" * 64,
    "OPINTEL_ACTIVATION_ADAPTER_SHA256": "b" * 64,
    "OPINTEL_ACTIVATION_ENTRY_POINT_SHA256": "c" * 64,
    "OPINTEL_STAGE_COORDINATOR_SHA256": "d" * 64,
    "OPINTEL_M1_RUNTIME_SHA256": "e" * 64,
    "OPINTEL_M2_M5_RUNTIME_SHA256": "f" * 64,
}


def _deployed_digest() -> str:
    dep = json.loads((DOCS / "phase1-m1-v2-deployment-2026-08-30.json").read_text(encoding="utf-8"))
    return str(dep["image"]["successor_registry_digest"])


def _a09_registry(tmp_path: Path, slot: int, business: str, host: str) -> FrozenA09DecisionRegistry:
    payload = {
        "schema_version": "m67-phase1-a09-decision-registry-v1",
        "decisions": [
            {
                "slot_number": 1, "business_identity": "903 HVAC", "exact_hostname": "903hvac.com",
                "decision_sha256": (
                    "1d938be8cf8946bd2b3d0d652500590652e031e056c69ddb0f9449b348261182"
                ),
                "state": "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH",
            },
            {
                "slot_number": slot, "business_identity": business, "exact_hostname": host,
                "decision_sha256": hashlib.sha256(f"{slot}:{host}".encode()).hexdigest(),
                "state": "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH",
            },
        ],
    }
    p = tmp_path / "a09.json"
    p.write_text(json.dumps(payload))
    return FrozenA09DecisionRegistry(p)


def _consumed_predecessor() -> str:
    now = _NOW
    rel = LiveResearchPermissionRelease(
        id=UUID("375a88da-da88-5ebf-9daf-cb09934e02b9"),
        workspace_id=UUID("00000000-0000-4000-8000-000000000301"),
        version="prev", configuration_hash="9" * 64, created_at=now - timedelta(days=1),
        activity=PermissionActivity.REAL_PUBLIC_RESEARCH, state=PermissionState.NOT_AUTHORIZED,
        source_registry_id=UUID("00000000-0000-4000-8000-000000000402"),
        source_registry_hash="a1" * 32,
        retention_policy_id=UUID("00000000-0000-4000-8000-000000000403"),
        retention_policy_hash="b2" * 32,
        environment_id=UUID("00000000-0000-4000-8000-000000000404"),
        environment_hash="c3" * 32,
        cohort_policy_id=UUID("00000000-0000-4000-8000-000000000405"),
        cohort_or_run_restriction="PHASE1_SLOT_01",
        starts_at=now - timedelta(days=1), expires_at=now - timedelta(hours=1),
        approval_ids=("owner-slot01",), kill_switch_id=UUID("00000000-0000-4000-8000-000000000406"),
        slot_number=1, business_identity="903 HVAC", exact_hostname="903hvac.com",
        ordered_package_sha256="3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b",
        research_runtime_revision="sha256:" + "7" * 64,
        max_logical_requests=5, max_attempts=5, max_response_bytes=250_000,
        max_total_bytes=1_250_000, max_duration_seconds=120,
        cost_ceiling_usd=0, allowed_source_scope=("903hvac.com",),
        owner_approval_sha256="72401dda" + "0" * 56,
        suspended_reason="CONSUMED:M2_INSUFFICIENT_EVIDENCE", revoked_at=now - timedelta(hours=1),
    )
    return rel.model_dump_json()


def _doc(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _inputs(tmp_path: Path, *, slot=2, business="Webb Air", host="webbair.com",
           consumed: BatchConsumed | None = None, now=_NOW) -> MaterializationInputsV2:
    consumed = consumed or BatchConsumed()
    digest = _deployed_digest()
    return MaterializationInputsV2(
        slot_number=slot,
        authorization_package_raw=_doc(
            "ready-for-slots02-06-phase1-m1-v2-execution-authorization-2026-08-30.json"
        ),
        owner_decision_raw=_doc(
            "authorize-slots02-06-phase1-m1-v2-execution-owner-decision-2026-08-30.json"
        ),
        execution_ceiling_envelope_raw=_doc(
            "phase1-m1-v2-execution-ceiling-envelope-2026-08-30.json"
        ),
        deployment_evidence_raw=_doc("phase1-m1-v2-deployment-2026-08-30.json"),
        sample_registry=FrozenPhaseOneSampleRegistry(REGISTRY),
        a09_registry=_a09_registry(tmp_path, slot, business, host),
        current_research_release_raw=_consumed_predecessor(),
        kill_switch_state="TRIPPED",
        stored_sampled_slot_approval_raw='{"state":"NOT_AUTHORIZED"}',
        deployed_activator_environment={**_ENV_KEYS, "OPINTEL_RESEARCH_RUNTIME_REVISION": digest},
        batch_consumed=consumed,
        now=now,
    )


def test_materialize_v2_slot02_from_sealed_artifacts(tmp_path: Path) -> None:
    result = materialize_v2(_inputs(tmp_path))
    approval = result.envelope.approval
    assert approval.schema_version == "m67.phase1.sampled-slot-execution-approval@4"
    assert approval.slot_number == 2
    assert approval.business_identity == "Webb Air"
    assert approval.exact_hostname == "webbair.com"
    assert approval.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"
    assert approval.max_useful_page_fetches == 25
    assert approval.max_logical_requests == 48          # v2 total-HTTP ceiling
    assert approval.max_total_bytes == 18_000_000
    assert approval.max_duration_seconds == 300
    assert approval.cost_ceiling_usd == 0
    assert approval.owner_statement_sha256 == (
        "d28e42594c943debf0144b3f5ecce57589760881e579ebbf52f6984d8150677a"
    )
    assert result.diagnostics["deployed_digest"] == _deployed_digest()


def test_materialize_v2_clamps_to_remaining_batch_headroom(tmp_path: Path) -> None:
    # four slots already spent most of the batch: 118 fetches / 232 HTTP / 86 MB / 1440 s
    consumed = BatchConsumed(
        useful_page_fetches=118, total_http_requests=232,
        total_bytes=86_000_000, m1_duration_seconds=1_440,
    )
    result = materialize_v2(_inputs(tmp_path, slot=6, business="Calvin's Climate",
                                    host="www.calvinsclimate.com", consumed=consumed))
    approval = result.envelope.approval
    assert approval.max_useful_page_fetches == 7        # 125 - 118
    assert approval.max_logical_requests == 8           # 240 - 232
    assert approval.max_total_bytes == 4_000_000        # 90M - 86M
    assert approval.max_duration_seconds == 60          # 1500 - 1440


def test_materialize_v2_batch_exhausted_is_not_a_defect(tmp_path: Path) -> None:
    consumed = BatchConsumed(useful_page_fetches=125, total_http_requests=200,
                             total_bytes=1, m1_duration_seconds=1)
    with pytest.raises(BatchHeadroomExhausted):
        materialize_v2(_inputs(tmp_path, slot=6, business="Calvin's Climate",
                               host="www.calvinsclimate.com", consumed=consumed))


def test_materialize_v2_rejects_wrong_slot_and_wrong_digest(tmp_path: Path) -> None:
    from dataclasses import replace

    with pytest.raises(AuthorityMaterializationError, match="not in the authorised 02-06 batch"):
        materialize_v2(_inputs(tmp_path, slot=7, business="Polar Pros", host="polarprosac.com"))
    bad = replace(
        _inputs(tmp_path),
        deployed_activator_environment={
            **_ENV_KEYS, "OPINTEL_RESEARCH_RUNTIME_REVISION": "sha256:" + "0" * 64
        },
    )
    with pytest.raises(
        AuthorityMaterializationError, match="not the package-bound v2 image digest"
    ):
        materialize_v2(bad)


def test_materialize_v2_requires_tripped_kill_switch(tmp_path: Path) -> None:
    from dataclasses import replace

    with pytest.raises(AuthorityMaterializationError, match="kill switch is not TRIPPED"):
        materialize_v2(replace(_inputs(tmp_path), kill_switch_state="RUN"))
