from __future__ import annotations

from dataclasses import replace

import pytest
from opintel_qualification.tournament2_domain import TournamentTask
from opintel_qualification.tournament2_freeze import (
    FROZEN_MANIFEST,
    M66A_COMMIT,
    M66B2_COMMIT,
    M66B3_COMMIT,
    M66B3R_COMMIT,
    TOTAL_HARD_CAP_MICROS,
    ControlState,
    QualificationIdentityClass,
    TournamentManifestState,
    build_frozen_manifest,
    validate_frozen_manifest,
)


def test_manifest_binds_exact_closure_commits_roster_and_twelve_tasks() -> None:
    artifact = FROZEN_MANIFEST
    manifest = artifact.manifest
    assert (
        manifest.m66a_commit,
        manifest.m66b2_commit,
        manifest.m66b3_commit,
        manifest.m66b3r_commit,
    ) == (M66A_COMMIT, M66B2_COMMIT, M66B3_COMMIT, M66B3R_COMMIT)
    assert {item.requested_model for item in manifest.candidates} == {
        "gpt-5.6-sol",
        "claude-sonnet-5",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    }
    assert len(manifest.candidates) == 4
    assert len(manifest.bindings) == 12
    actual = {(item.deployment_key, item.task) for item in manifest.bindings}
    assert actual == {
        ("openai-gpt-5.6-sol", TournamentTask.EVIDENCE_INTERPRETATION),
        ("openai-gpt-5.6-sol", TournamentTask.CONTRADICTION_ANALYSIS),
        ("openai-gpt-5.6-sol", TournamentTask.OPPORTUNITY_REASONING),
        ("anthropic-claude-sonnet-5", TournamentTask.EVIDENCE_INTERPRETATION),
        ("anthropic-claude-sonnet-5", TournamentTask.CONTRADICTION_ANALYSIS),
        ("anthropic-claude-sonnet-5", TournamentTask.OPPORTUNITY_REASONING),
        ("anthropic-claude-sonnet-5", TournamentTask.AUDIT_WORDING),
        ("anthropic-claude-sonnet-5", TournamentTask.OUTREACH_WORDING),
        ("google-gemini-3.6-flash", TournamentTask.AUDIT_WORDING),
        ("google-gemini-3.6-flash", TournamentTask.OUTREACH_WORDING),
        ("google-gemini-3.5-flash-lite", TournamentTask.REPLY_CLASSIFICATION),
        (
            "google-gemini-3.5-flash-lite",
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
        ),
    }
    assert all("subject" not in item.task.value for item in manifest.bindings)
    assert len(artifact.manifest_hash) == 64


def test_identity_policy_is_exact_and_explicitly_non_production() -> None:
    candidates = {item.provider: item for item in FROZEN_MANIFEST.manifest.candidates}
    assert candidates["anthropic"].identity_class is (
        QualificationIdentityClass.PINNED_PROVIDER_IDENTITY
    )
    assert candidates["openai"].identity_class is (
        QualificationIdentityClass.RUN_BOUND_STABLE_IDENTITY
    )
    google = [item for item in FROZEN_MANIFEST.manifest.candidates if item.provider == "google"]
    assert all(
        item.identity_class is QualificationIdentityClass.RUN_BOUND_STABLE_IDENTITY
        for item in google
    )
    for candidate in FROZEN_MANIFEST.manifest.candidates:
        assert candidate.certified_configuration_hashes
        assert candidate.certification_evidence_blobs
        assert candidate.provider_policy_snapshot
        assert candidate.pricing_revision
        assert any("production" in item for item in candidate.identity_limitations)


def test_repaired_google_configuration_hashes_are_frozen() -> None:
    by_deployment = {item.deployment_key: item for item in FROZEN_MANIFEST.manifest.candidates}
    assert by_deployment["google-gemini-3.6-flash"].certified_configuration_hashes == (
        "fd40373329037b3159b0614f90c6c6f6bfb0abd0a1bf18da864325616cef1d56",
    )
    assert by_deployment["google-gemini-3.5-flash-lite"].certified_configuration_hashes == (
        "2dba56adf1ff53caebc27776042275a477917ef12c80e7604aeaf516131800fc",
    )
    assert all(
        item.endpoint.endswith("/v1/interactions")
        for item in by_deployment.values()
        if item.provider == "google"
    )


def test_exact_task_prompt_schema_and_configuration_lineage_is_bound() -> None:
    for binding in FROZEN_MANIFEST.manifest.bindings:
        assert binding.task_contract_version
        assert binding.input_schema_version
        assert binding.output_schema_version
        assert binding.prompt_policy_version == "m6.6a.prompt@1"
        assert len(binding.prompt_hash) == 64
        assert len(binding.provider_schema_hash) == 64
        assert len(binding.candidate_configuration_hash) == 64


def test_hidden_partition_stays_sealed_and_cannot_be_authorized() -> None:
    manifest = FROZEN_MANIFEST.manifest
    assert not manifest.hidden_partition_contents_exposed
    assert "sealed" in manifest.hidden_partition_custody_policy
    assert not manifest.hidden_fixture_access_authorized
    assert manifest.corpus_metadata_hash
    with pytest.raises(ValueError, match="cannot grant execution"):
        validate_frozen_manifest(replace(manifest, hidden_fixture_access_authorized=True))


def test_account_controls_fail_closed_on_unverified_account_state() -> None:
    controls = FROZEN_MANIFEST.manifest.account_controls
    assert {item.provider for item in controls} == {"openai", "anthropic", "google"}
    assert all(item.deployment_access is ControlState.VERIFIED for item in controls)
    assert all(item.endpoint_entitlement is ControlState.VERIFIED for item in controls)
    assert all(item.synthetic_evaluation_permitted is ControlState.VERIFIED for item in controls)
    assert all(item.credential_isolation is ControlState.VERIFIED for item in controls)
    assert all(item.bounded_rate_tier_adequacy is ControlState.UNKNOWN for item in controls)
    assert all(
        item.retention_data_control_understood is ControlState.REQUIRES_REVIEW for item in controls
    )
    assert all(item.account_logging_conflict_absent is ControlState.UNKNOWN for item in controls)


def test_reviewer_and_execution_governance_are_deliberately_unresolved() -> None:
    manifest = FROZEN_MANIFEST.manifest
    assert not manifest.reviewer_freeze.complete
    assert manifest.reviewer_freeze.primary_reviewer_ids == ()
    assert manifest.reviewer_freeze.conditional_adjudicator_id is None
    assert manifest.reviewer_freeze.provider_identity_hidden
    assert manifest.reviewer_freeze.randomized_left_right
    assert manifest.reviewer_freeze.independent_before_score_visibility
    assert manifest.execution_owner is None
    assert manifest.stop_operator is None
    assert manifest.execution_window_start is None
    assert manifest.execution_window_end is None
    assert manifest.explicit_manifest_approval_ref is None


def test_refreshed_hierarchical_budget_fits_exact_twenty_five_dollar_cap() -> None:
    budget = FROZEN_MANIFEST.manifest.budget
    assert budget.total_hard_cap_micros == TOTAL_HARD_CAP_MICROS == 25_000_000
    assert budget.primary_call_cap_micros == 10_985_057
    assert budget.retry_cap_micros == 10_985_057
    assert budget.conservative_preflight_micros == 21_970_114
    assert budget.emergency_reserve_micros == 3_029_886
    assert sum(dict(budget.provider_caps).values()) == 21_970_113
    assert sum(dict(budget.deployment_caps).values()) == 21_970_113
    assert sum(dict(budget.task_caps).values()) == 21_970_113
    assert budget.unknown_pricing_fails_closed
    assert budget.task_local_hard_failure_releases_future_reservations


def test_non_approved_manifest_cannot_gain_live_or_route_authority() -> None:
    manifest = FROZEN_MANIFEST.manifest
    assert manifest.state is TournamentManifestState.NOT_APPROVED
    assert manifest.unresolved_requirements
    assert not manifest.live_authorization_active
    assert not manifest.route_activation_allowed
    for field in (
        "hidden_fixture_access_authorized",
        "live_authorization_active",
        "route_activation_allowed",
    ):
        with pytest.raises(ValueError, match="cannot grant execution"):
            validate_frozen_manifest(replace(manifest, **{field: True}))
    with pytest.raises(ValueError, match="unresolved requirements"):
        validate_frozen_manifest(
            replace(manifest, state=TournamentManifestState.READY_FOR_EXECUTION)
        )


def test_manifest_build_is_deterministic_and_has_no_execution_side_effect() -> None:
    rebuilt = build_frozen_manifest()
    assert rebuilt == FROZEN_MANIFEST
    assert rebuilt.manifest.synthetic_only
    assert rebuilt.manifest.global_kill_switch_armed
    assert rebuilt.manifest.budget_kill_switch_armed
    assert not rebuilt.manifest.live_authorization_active
