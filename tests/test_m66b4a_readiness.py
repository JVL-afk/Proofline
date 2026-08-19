from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from opintel_qualification.tournament2_freeze import FROZEN_MANIFEST
from opintel_qualification.tournament2_readiness import (
    SUCCESSOR_MANIFEST,
    AutomatedTournamentReadiness,
    FindingState,
    validate_successor_manifest,
)
from opintel_qualification_live.contracts import HttpResponse
from opintel_qualification_live.tournament2_control_plane import (
    PROBES,
    ProbeOutcome,
    run_control_plane_probe,
    safe_result_dict,
)
from opintel_qualification_live.transport import UrllibJsonTransport

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class FakeReadOnlyTransport:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.calls: list[tuple[str, Mapping[str, str], float]] = []

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((url, headers, timeout_seconds))
        model = url.rsplit("/", 1)[-1]
        body = {"name": f"models/{model}"} if self.provider == "google" else {"id": model}
        return HttpResponse(200, {}, json.dumps(body).encode(), 4)


def test_read_only_probe_uses_exact_models_and_no_inference() -> None:
    transports = {
        provider: FakeReadOnlyTransport(provider) for provider in ("openai", "anthropic", "google")
    }
    result = run_control_plane_probe(
        now=lambda: NOW,
        secret_for_provider=lambda _provider: "test-secret",
        transport_for_provider=lambda provider: transports[provider],
    )
    assert len(PROBES) == 4
    assert result.calls_attempted == result.calls_completed == 4
    assert result.inference_calls == 0
    assert not result.hidden_fixture_access
    assert not result.raw_bodies_retained
    assert not result.credentials_retained
    assert all(item.outcome is ProbeOutcome.VERIFIED for item in result.receipts)
    assert all(item.inference_requested is False for item in result.receipts)
    rendered = json.dumps(safe_result_dict(result), default=str)
    assert "test-secret" not in rendered


def test_metadata_transport_rejects_non_allowlisted_host_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail(f"network attempted: {args} {kwargs}"),
    )
    transport = UrllibJsonTransport(allowed_hosts=frozenset({"api.openai.com"}))
    with pytest.raises(RuntimeError, match="outside_egress_allowlist"):
        transport.get(
            "https://example.invalid/v1/models/test",
            {"Authorization": "Bearer test-secret"},
            1,
        )


def test_successor_binds_exact_predecessor_roster_and_budget() -> None:
    manifest = SUCCESSOR_MANIFEST.manifest
    predecessor = FROZEN_MANIFEST.manifest
    assert manifest.predecessor_manifest_hash == FROZEN_MANIFEST.manifest_hash
    assert manifest.candidate_count == len(predecessor.candidates) == 4
    assert manifest.binding_count == len(predecessor.bindings) == 12
    assert manifest.budget_hierarchy == predecessor.budget
    assert manifest.budget_hierarchy.total_hard_cap_micros == 25_000_000
    assert manifest.budget_hierarchy.conservative_preflight_micros == 21_970_114
    assert manifest.budget_hierarchy.emergency_reserve_micros == 3_029_886
    assert len(SUCCESSOR_MANIFEST.manifest_hash) == 64


def test_synthetic_retention_is_accepted_but_opt_in_unknowns_block_exactly() -> None:
    manifest = SUCCESSOR_MANIFEST.manifest
    assert "synthetic-only" in manifest.accepted_synthetic_retention_decision
    findings = {item.provider: item for item in manifest.account_findings}
    assert findings["anthropic"].opt_in_training_sharing_disabled is FindingState.VERIFIED
    assert findings["openai"].opt_in_training_sharing_disabled is FindingState.UNKNOWN_BLOCKING
    assert findings["google"].opt_in_training_sharing_disabled is FindingState.UNKNOWN_BLOCKING
    assert manifest.exact_remaining_blockers == (
        "openai:verify_account_opt_in_training_or_data_sharing_is_disabled",
        "google:verify_account_opt_in_training_or_data_sharing_is_disabled",
    )
    assert manifest.readiness is AutomatedTournamentReadiness.NOT_APPROVED


def test_tier_and_rate_unknowns_are_nonblocking_under_conservative_pacing() -> None:
    manifest = SUCCESSOR_MANIFEST.manifest
    assert all(
        item.account_tier is FindingState.UNKNOWN_NONBLOCKING for item in manifest.account_findings
    )
    assert all(
        item.request_token_capacity is FindingState.UNKNOWN_NONBLOCKING
        for item in manifest.account_findings
    )
    assert {item.provider: item.minimum_seconds_between_requests for item in manifest.pacing} == {
        "openai": 15,
        "anthropic": 15,
        "google": 30,
    }
    assert all(item.maximum_concurrency == 1 for item in manifest.pacing)
    assert all(item.maximum_outstanding_requests == 1 for item in manifest.pacing)
    assert all("second 429 stops provider" in item.rate_limit_response for item in manifest.pacing)


def test_reviewer_slots_allow_sealed_generation_but_never_release() -> None:
    policy = SUCCESSOR_MANIFEST.manifest.reviewer_policy
    assert policy.reserved_slots == (
        "PRIMARY_REVIEWER_SLOT_1",
        "PRIMARY_REVIEWER_SLOT_2",
        "PRIMARY_REVIEWER_SLOT_3",
        "CONDITIONAL_ADJUDICATOR_SLOT",
    )
    assert not policy.assigned_reviewer_ids
    assert policy.packages_sealed
    assert not policy.package_release_allowed
    assert policy.identities_required_before_release
    assert policy.distinct_primary_reviewers_required
    assert not policy.project_owner_may_be_sole_adjudicator
    stage = SUCCESSOR_MANIFEST.manifest.stage_policy
    assert "stage_5b_generate_and_seal_blinded_packages" in stage.stages
    assert stage.stage_5b_action == "generate and seal only"
    assert not SUCCESSOR_MANIFEST.manifest.human_review_package_release_allowed


def test_security_hidden_corpus_and_routes_remain_closed() -> None:
    manifest = SUCCESSOR_MANIFEST.manifest
    assert manifest.global_kill_switch_armed
    assert manifest.budget_kill_switch_armed
    assert not manifest.hidden_fixture_access_during_freeze
    assert manifest.inference_calls_during_gate_resolution == 0
    assert not manifest.route_activation_allowed
    assert "sealed" in manifest.hidden_corpus_policy
    assert any("no tools" in item for item in manifest.security_policy)
    for field in ("route_activation_allowed", "human_review_package_release_allowed"):
        with pytest.raises(ValueError, match="cannot activate routes or release"):
            validate_successor_manifest(replace(manifest, **{field: True}))


def test_readiness_cannot_ignore_or_hide_blockers() -> None:
    manifest = SUCCESSOR_MANIFEST.manifest
    with pytest.raises(ValueError, match="ready manifest cannot retain blockers"):
        validate_successor_manifest(
            replace(
                manifest,
                readiness=AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT,
            )
        )
    with pytest.raises(ValueError, match="must state exact blockers"):
        validate_successor_manifest(replace(manifest, exact_remaining_blockers=()))


def test_successor_manifest_build_is_deterministic_and_non_executable() -> None:
    assert SUCCESSOR_MANIFEST == SUCCESSOR_MANIFEST
    assert SUCCESSOR_MANIFEST.manifest.readiness is AutomatedTournamentReadiness.NOT_APPROVED
    assert not SUCCESSOR_MANIFEST.manifest.route_activation_allowed
