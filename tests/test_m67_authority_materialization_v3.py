"""materialize_v3: sealed-artifact-bound @4 approval for the owner-named Slots 07-24 batch.

Same machine as materialize_v2, repointed to the 07-24 EXECUTION_READY artefacts and
the Link 9 image. Operator-local; never baked into any image.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.authority_materialization import AuthorityMaterializationError
from opintel_research_worker.authority_materialization_v3 import (
    BatchConsumed,
    BatchHeadroomExhausted,
    MaterializationInputsV3,
    materialize_v3,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "docs/readiness/m6.7-authorization"
DEP = ROOT / "docs/readiness/m6.7-deployment"
REGISTRY = str(ROOT / "infra/container/phase1-worker/phase1-frozen-slot-registry.json")
_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)

_ENV_KEYS = {
    "OPINTEL_RELEASE_APPLICATOR_SHA256": "a" * 64,
    "OPINTEL_ACTIVATION_ADAPTER_SHA256": "b" * 64,
    "OPINTEL_ACTIVATION_ENTRY_POINT_SHA256": "c" * 64,
    "OPINTEL_STAGE_COORDINATOR_SHA256": "d" * 64,
    "OPINTEL_M1_RUNTIME_SHA256": "e" * 64,
    "OPINTEL_M2_M5_RUNTIME_SHA256": "f" * 64,
}

_PKG = AUTH / "slots07-24-phase1-personalization-v2-EXECUTION-READY-2026-08-31.json"
_OWNER = AUTH / "slots07-24-owner-decision-machine-values-2026-08-31.json"
_ENVELOPE = DEP / "phase1-m1-v2-execution-ceiling-envelope-2026-08-30.json"
_DEPLOY = DEP / "slots07-24-link9-deployment-evidence-2026-08-31.json"


def _deployed_digest() -> str:
    doc = json.loads(_DEPLOY.read_text(encoding="utf-8"))
    return str(doc["image"]["successor_registry_digest"])


def _a09_registry(tmp_path: Path, slot: int, business: str, host: str,
                  decision_sha: str | None = None) -> FrozenA09DecisionRegistry:
    payload = {
        "schema_version": "m67-phase1-a09-decision-registry-v1",
        "decisions": [
            {
                "slot_number": 1, "business_identity": "903 HVAC", "exact_hostname": "903hvac.com",
                "decision_sha256":
                    "1d938be8cf8946bd2b3d0d652500590652e031e056c69ddb0f9449b348261182",
                "state": "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH",
            },
            {
                "slot_number": slot, "business_identity": business, "exact_hostname": host,
                "decision_sha256": decision_sha
                or hashlib.sha256(f"{slot}:{host}".encode()).hexdigest(),
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
        id=UUID("f22c6eba-b0af-57fc-be9d-47e6fa007df5"),
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
        cohort_or_run_restriction="PHASE1_SLOT_05",
        starts_at=now - timedelta(days=1), expires_at=now - timedelta(hours=1),
        approval_ids=("owner-slot05",), kill_switch_id=UUID("00000000-0000-4000-8000-000000000406"),
        slot_number=5, business_identity="Fintastic Cooling & Heating",
        exact_hostname="www.callfintastic.com",
        ordered_package_sha256="3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b",
        research_runtime_revision="sha256:" + "7" * 64,
        max_logical_requests=48, max_attempts=2, max_response_bytes=1_000_000,
        max_total_bytes=18_000_000, max_duration_seconds=300,
        cost_ceiling_usd=0, allowed_source_scope=("www.callfintastic.com",),
        owner_approval_sha256="72401dda" + "0" * 56,
        suspended_reason="CONSUMED:M2_INSUFFICIENT_EVIDENCE", revoked_at=now - timedelta(hours=1),
    )
    return rel.model_dump_json()


def _inputs(tmp_path: Path, *, slot=7, business="Polar Pros", host="polarprosac.com",
            decision_sha: str | None = None,
            consumed: BatchConsumed | None = None, now=_NOW) -> MaterializationInputsV3:
    return MaterializationInputsV3(
        slot_number=slot,
        authorization_package_raw=_PKG.read_text(encoding="utf-8"),
        owner_decision_raw=_OWNER.read_text(encoding="utf-8"),
        execution_ceiling_envelope_raw=_ENVELOPE.read_text(encoding="utf-8"),
        deployment_evidence_raw=_DEPLOY.read_text(encoding="utf-8"),
        sample_registry=FrozenPhaseOneSampleRegistry(REGISTRY),
        a09_registry=_a09_registry(tmp_path, slot, business, host, decision_sha),
        current_research_release_raw=_consumed_predecessor(),
        kill_switch_state="TRIPPED",
        stored_sampled_slot_approval_raw='{"state":"NOT_AUTHORIZED"}',
        deployed_activator_environment={
            **_ENV_KEYS, "OPINTEL_RESEARCH_RUNTIME_REVISION": _deployed_digest(),
        },
        batch_consumed=consumed or BatchConsumed(),
        now=now,
    )


def test_materialize_v3_slot07_from_sealed_artifacts(tmp_path: Path) -> None:
    result = materialize_v3(_inputs(
        tmp_path, decision_sha="cb5d7b06eca3b99f1fa796bb78b227a0f1d71cd6bfba49c6a11a572319a6bd96"))
    assert result.envelope.approval.slot_number == 7
    assert result.envelope.approval.business_identity == "Polar Pros"
    assert result.envelope.approval.exact_hostname == "polarprosac.com"
    assert result.envelope.approval.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"
    d = result.diagnostics
    # per-slot ceilings from the sealed envelope, unclamped when batch is fresh
    assert d["clamped_ceilings"]["max_useful_page_fetches"] == 25
    assert d["clamped_ceilings"]["max_logical_requests"] == 48
    assert d["clamped_ceilings"]["max_total_bytes"] == 18_000_000
    assert d["clamped_ceilings"]["max_duration_seconds"] == 300


def test_materialize_v3_rejects_slot_outside_07_24(tmp_path: Path) -> None:
    with pytest.raises(AuthorityMaterializationError, match="not in the authorised 07-24 batch"):
        materialize_v3(_inputs(tmp_path, slot=25))
    with pytest.raises(AuthorityMaterializationError, match="not in the authorised 07-24 batch"):
        materialize_v3(_inputs(tmp_path, slot=6, business="Calvin's Climate",
                               host="www.calvinsclimate.com"))


def test_materialize_v3_rejects_absent_a09(tmp_path: Path) -> None:
    # slot 9 (C&R Services) returned a truthful NOT_APPROVED and is absent from the registry
    payload = {
        "schema_version": "m67-phase1-a09-decision-registry-v1",
        "decisions": [{
            "slot_number": 1, "business_identity": "903 HVAC", "exact_hostname": "903hvac.com",
            "decision_sha256": "1d938be8cf8946bd2b3d0d652500590652e031e056c69ddb0f9449b348261182",
            "state": "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH",
        }],
    }
    p = tmp_path / "a09_absent.json"
    p.write_text(json.dumps(payload))
    inp = _inputs(tmp_path, slot=9, business="C&R Services", host="crhvacpro.com")
    inp = dataclasses.replace(inp, a09_registry=FrozenA09DecisionRegistry(p))
    # slot 9 is not in the baked registry -> FrozenA09DecisionRegistry.require_approved
    # fails closed (raw ValueError), the materialiser never emits an approval.
    with pytest.raises(ValueError, match="absent or mismatched"):
        materialize_v3(inp)


def test_materialize_v3_clamps_to_remaining_batch_headroom(tmp_path: Path) -> None:
    # 449 of 450 useful-page-fetch batch allowance already consumed -> next slot clamped to 1
    consumed = BatchConsumed(useful_page_fetches=449, total_http_requests=100,
                             total_bytes=1_000_000, m1_duration_seconds=100)
    result = materialize_v3(_inputs(tmp_path, consumed=consumed))
    c = result.diagnostics["clamped_ceilings"]
    assert c["max_useful_page_fetches"] == 1          # min(25, 450-449)
    assert c["max_logical_requests"] == 48            # min(48, 864-100)
    assert c["max_total_bytes"] == 18_000_000         # min(18e6, 324e6-1e6)


def test_materialize_v3_per_slot_headroom_is_independent(tmp_path: Path) -> None:
    # modest batch_consumed well below every batch ceiling -> per-slot ceilings unchanged
    consumed = BatchConsumed(useful_page_fetches=57, total_http_requests=64,
                             total_bytes=15_697_997, m1_duration_seconds=196)
    result = materialize_v3(_inputs(tmp_path, consumed=consumed))
    c = result.diagnostics["clamped_ceilings"]
    assert c["max_useful_page_fetches"] == 25
    assert c["max_logical_requests"] == 48
    assert c["max_total_bytes"] == 18_000_000
    assert c["max_duration_seconds"] == 300


def test_materialize_v3_batch_exhausted_is_not_a_defect(tmp_path: Path) -> None:
    consumed = BatchConsumed(useful_page_fetches=450, total_http_requests=200,
                             total_bytes=2_000_000, m1_duration_seconds=200)
    with pytest.raises(BatchHeadroomExhausted):
        materialize_v3(_inputs(tmp_path, consumed=consumed))


def test_materialize_v3_requires_tripped_kill_switch(tmp_path: Path) -> None:
    inp = _inputs(tmp_path)
    inp = dataclasses.replace(inp, kill_switch_state="RUN")
    with pytest.raises(AuthorityMaterializationError, match="kill switch is not TRIPPED"):
        materialize_v3(inp)
