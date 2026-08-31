"""Live-materializer v2 wiring: release fields, _policy_v2, authorization equality.

Covers AUTHORIZE_SLOTS02_06_PHASE1_M1_V2_EXECUTION plumbing. v1 (@3 / homepage)
releases and their hashes must be byte-for-byte unaffected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from opintel_research_worker.activation import (
    SampledSlotActivator,
    release_execution_ceilings_sha256,
)
from opintel_research_worker.release_application import SampledSlotExecutionApproval
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

_NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _v2_release(**changes: object) -> LiveResearchPermissionRelease:
    values: dict[str, object] = {
        "id": UUID("00000000-0000-4000-8000-0000000004a2"),
        "workspace_id": UUID("00000000-0000-4000-8000-000000000301"),
        "version": "1",
        "configuration_hash": "b" * 64,
        "created_at": _NOW,
        "activity": PermissionActivity.REAL_PUBLIC_RESEARCH,
        "state": PermissionState.AUTHORIZED,
        "source_registry_id": UUID("00000000-0000-4000-8000-000000000402"),
        "source_registry_hash": "source-registry",
        "retention_policy_id": UUID("00000000-0000-4000-8000-000000000403"),
        "retention_policy_hash": "retention-policy",
        "environment_id": UUID("00000000-0000-4000-8000-000000000404"),
        "environment_hash": "environment",
        "cohort_policy_id": UUID("00000000-0000-4000-8000-000000000405"),
        "cohort_or_run_restriction": "PHASE1_SLOT_02",
        "starts_at": _NOW - timedelta(minutes=1),
        "expires_at": _NOW + timedelta(minutes=30),
        "approval_ids": ("owner-slot02", "A09_SHA256:" + "c" * 64),
        "kill_switch_id": UUID("00000000-0000-4000-8000-000000000406"),
        "slot_number": 2,
        "business_identity": "Webb Air",
        "exact_hostname": "webbair.com",
        "ordered_package_sha256": (
            "3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b"
        ),
        "research_runtime_revision": "sha256:" + "e" * 64,
        "max_logical_requests": 48,
        "max_attempts": 2,
        "max_response_bytes": 1_000_000,
        "max_total_bytes": 18_000_000,
        "max_duration_seconds": 300,
        "cost_ceiling_usd": Decimal("0"),
        "allowed_source_scope": ("webbair.com",),
        "owner_approval_sha256": "d" * 64,
        "crawl_protocol_version": "phase1-m1@2-bounded-site-crawl",
        "max_useful_page_fetches": 25,
    }
    values.update(changes)
    return LiveResearchPermissionRelease(**values)


def test_v2_release_requires_protocol_and_useful_fetches() -> None:
    with pytest.raises(ValueError, match="v2 authorized research release"):
        _v2_release(crawl_protocol_version="phase1-m1@2-bounded-site-crawl",
                    max_useful_page_fetches=None)
    with pytest.raises(ValueError, match="v2 authorized research release"):
        _v2_release(crawl_protocol_version="phase1-m1@9-something", max_useful_page_fetches=25)


def test_policy_v2_from_release_ceilings() -> None:
    policy = SampledSlotActivator._policy(_v2_release())
    assert policy.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"
    assert policy.max_pages == 25            # useful page fetches
    assert policy.max_total_http_requests == 48
    assert policy.max_total_bytes == 18_000_000
    assert policy.max_duration_seconds == 300
    assert policy.max_depth == 3
    assert policy.max_attempts == 2
    assert policy.max_redirects == 0
    assert policy.max_discovery_fetches == 6
    assert policy.per_domain_delay_seconds == 2.0


def test_policy_v2_respects_batch_clamped_ceilings() -> None:
    # materialiser clamped this slot to the last of the batch headroom
    clamped = _v2_release(
        max_useful_page_fetches=8, max_logical_requests=12,
        max_total_bytes=3_000_000, max_duration_seconds=90,
    )
    policy = SampledSlotActivator._policy(clamped)
    assert policy.max_pages == 8
    assert policy.max_total_http_requests == 12
    assert policy.max_total_bytes == 3_000_000
    assert policy.max_duration_seconds == 90


def test_v2_ceilings_sha256_includes_new_bindings_and_is_stable() -> None:
    a = release_execution_ceilings_sha256(_v2_release())
    b = release_execution_ceilings_sha256(_v2_release())
    assert a == b
    other = release_execution_ceilings_sha256(_v2_release(max_useful_page_fetches=10))
    assert other != a


def test_v1_ceilings_sha256_unchanged_for_non_v2_release() -> None:
    v1 = _v2_release(crawl_protocol_version=None, max_useful_page_fetches=None,
                     slot_number=1, business_identity="903 HVAC", exact_hostname="903hvac.com",
                     allowed_source_scope=("903hvac.com",))
    # The v1 payload must be exactly the legacy 10-key canonical dict (no v2 keys).
    import hashlib
    import json
    expected = hashlib.sha256(
        json.dumps(
            {
                "allowed_source_scope": ["903hvac.com"],
                "cost_ceiling_usd": "0",
                "expires_at": v1.expires_at.isoformat(),
                "max_attempts": 2,
                "max_logical_requests": 48,
                "max_response_bytes": 1_000_000,
                "max_total_bytes": 18_000_000,
                "max_duration_seconds": 300,
                "starts_at": v1.starts_at.isoformat(),
                "terminal_rollback_state": "NOT_AUTHORIZED",
            },
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
        ).encode()
    ).hexdigest()
    assert release_execution_ceilings_sha256(v1) == expected


_APPROVAL_BASE: dict[str, object] = {
    "schema_version": "m67.phase1.sampled-slot-execution-approval@4",
    "state": "OWNER_APPROVED",
    "approval_id": UUID("00000000-0000-4000-8000-000000000701"),
    "owner_statement_sha256": "d28e42594c943debf0144b3f5ecce57589760881e579ebbf52f6984d8150677a",
    "owner_signature_state": "APPROVED_IN_THREAD",
    "current_release_id": UUID("00000000-0000-4000-8000-000000000801"),
    "authorized_release_id": UUID("00000000-0000-4000-8000-000000000802"),
    "workspace_id": UUID("00000000-0000-4000-8000-000000000301"),
    "legacy_lock_sentinel_sha256": __import__("hashlib").sha256(
        b'{"state":"NOT_AUTHORIZED"}'
    ).hexdigest(),
    "permission_type": "REAL_PUBLIC_RESEARCH",
    "source_registry_id": UUID("00000000-0000-4000-8000-000000000402"),
    "source_registry_hash": "a" * 64,
    "retention_policy_id": UUID("00000000-0000-4000-8000-000000000403"),
    "retention_policy_hash": "b" * 64,
    "environment_id": UUID("00000000-0000-4000-8000-000000000404"),
    "environment_hash": "c" * 64,
    "cohort_policy_id": UUID("00000000-0000-4000-8000-000000000405"),
    "kill_switch_id": UUID("00000000-0000-4000-8000-000000000406"),
    "ordered_package_file_sha256": "e" * 64,
    "ordered_package_semantic_sha256": "f" * 64,
    "slot_registry_file_sha256": "1" * 64,
    "slot_registry_semantic_sha256": "2" * 64,
    "slot_number": 2,
    "business_identity": "Webb Air",
    "exact_hostname": "webbair.com",
    "a09_decision_sha256": "3" * 64,
    "research_runtime_revision": "sha256:" + "e" * 64,
    "release_applicator_sha256": "4" * 64,
    "activation_adapter_sha256": "5" * 64,
    "activation_entry_point_sha256": "6" * 64,
    "stage_coordinator_sha256": "7" * 64,
    "m1_runtime_sha256": "8" * 64,
    "m2_m5_runtime_sha256": "9" * 64,
    "starts_at": _NOW - timedelta(minutes=1),
    "expires_at": _NOW + timedelta(minutes=30),
    "max_logical_requests": 48,
    "max_attempts": 2,
    "max_response_bytes": 1_000_000,
    "max_total_bytes": 18_000_000,
    "max_duration_seconds": 300,
    "cost_ceiling_usd": Decimal("0"),
    "allowed_source_scope": ("webbair.com",),
    "terminal_rollback_state": "NOT_AUTHORIZED",
    "crawl_protocol_version": "phase1-m1@2-bounded-site-crawl",
    "max_useful_page_fetches": 25,
}


def test_v4_approval_accepts_slot02_webb_air() -> None:
    approval = SampledSlotExecutionApproval.model_validate(_APPROVAL_BASE)
    assert approval.slot_number == 2
    assert approval.crawl_protocol_version == "phase1-m1@2-bounded-site-crawl"


def test_v4_approval_scope_is_the_frozen_registry_through_slot_24() -> None:
    # Link 9 (AUTHORIZE_SLOTS07_24_...): the frozen scope is registry rows 1..24.
    slot07 = SampledSlotExecutionApproval.model_validate(
        {**_APPROVAL_BASE, "slot_number": 7, "business_identity": "Polar Pros",
         "exact_hostname": "polarprosac.com", "allowed_source_scope": ("polarprosac.com",)}
    )
    assert slot07.slot_number == 7
    slot24 = SampledSlotExecutionApproval.model_validate(
        {**_APPROVAL_BASE, "slot_number": 24,
         "business_identity": "Blue Northern Air Conditioning, Inc.",
         "exact_hostname": "www.bluenorthernac.com",
         "allowed_source_scope": ("www.bluenorthernac.com",)}
    )
    assert slot24.slot_number == 24
    # Slot 25 is outside the frozen registry and fails closed.
    with pytest.raises(ValueError, match="outside the frozen Phase 1 batch scope"):
        SampledSlotExecutionApproval.model_validate(
            {**_APPROVAL_BASE, "slot_number": 25, "business_identity": "Polar Pros",
             "exact_hostname": "polarprosac.com", "allowed_source_scope": ("polarprosac.com",)}
        )
    # Wrong hostname for an in-scope slot is rejected.
    with pytest.raises(ValueError, match="not the frozen slot row"):
        SampledSlotExecutionApproval.model_validate(
            {**_APPROVAL_BASE, "slot_number": 7, "business_identity": "Polar Pros",
             "exact_hostname": "evil.example", "allowed_source_scope": ("evil.example",)}
        )
    with pytest.raises(ValueError, match="not the frozen slot row"):
        SampledSlotExecutionApproval.model_validate(
            {**_APPROVAL_BASE, "exact_hostname": "evil.example",
             "allowed_source_scope": ("evil.example",)}
        )


def test_v4_approval_rejects_slot01_and_v3_rejects_v2_fields() -> None:
    with pytest.raises(ValueError, match="Slot 01 is frozen"):
        SampledSlotExecutionApproval.model_validate(
            {**_APPROVAL_BASE, "slot_number": 1, "business_identity": "903 HVAC",
             "exact_hostname": "903hvac.com", "allowed_source_scope": ("903hvac.com",)}
        )
    with pytest.raises(ValueError, match=r"v1 .@3. approval must not carry v2"):
        SampledSlotExecutionApproval.model_validate(
            {**_APPROVAL_BASE, "schema_version": "m67.phase1.sampled-slot-execution-approval@3",
             "slot_number": 1, "business_identity": "903 HVAC",
             "exact_hostname": "903hvac.com", "allowed_source_scope": ("903hvac.com",)}
        )
