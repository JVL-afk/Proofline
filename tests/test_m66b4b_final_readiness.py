from __future__ import annotations

from dataclasses import replace

import pytest
from opintel_qualification.tournament2_final_readiness import (
    FINAL_READINESS_MANIFEST,
    AttestationProvenance,
    ReviewReleaseState,
    VerifiedControlState,
    validate_final_readiness_manifest,
)
from opintel_qualification.tournament2_readiness import (
    SUCCESSOR_MANIFEST,
    AutomatedTournamentReadiness,
)


def test_final_successor_binds_exact_m66b4a_manifest() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    assert manifest.predecessor_manifest_hash == SUCCESSOR_MANIFEST.manifest_hash
    assert manifest.preserved_predecessor == SUCCESSOR_MANIFEST.manifest
    assert manifest.preserved_predecessor.candidate_count == 4
    assert manifest.preserved_predecessor.binding_count == 12
    assert manifest.preserved_predecessor.budget_hierarchy.total_hard_cap_micros == 25_000_000
    assert len(FINAL_READINESS_MANIFEST.manifest_hash) == 64


def test_openai_human_attestation_records_all_three_disabled_controls() -> None:
    openai = FINAL_READINESS_MANIFEST.manifest.human_attestations[0]
    assert openai.control == "OPENAI_DATA_SHARING"
    assert openai.state is VerifiedControlState.DATA_SHARING_DISABLED_VERIFIED
    assert openai.provenance is AttestationProvenance.HUMAN_CONTROL_PLANE_ATTESTATION
    assert dict(openai.settings) == {
        "platform_model_feedback_sharing": "disabled",
        "evaluation_and_fine_tuning_data_sharing": "disabled",
        "inputs_and_outputs_sharing": "disabled",
    }
    assert not openai.zero_data_retention_claimed


def test_google_human_attestation_and_paid_data_conclusion_are_exact() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    google = manifest.human_attestations[1]
    assert google.control == "GOOGLE_INTERACTIONS_REQUEST_STORAGE"
    assert google.state is VerifiedControlState.DISABLED_VERIFIED
    assert google.provenance is AttestationProvenance.HUMAN_CONTROL_PLANE_ATTESTATION
    assert dict(google.settings)["interactions_api_request_storage"] == "disabled"
    conclusion = manifest.google_data_use_conclusion
    assert conclusion.paid_project_verified_by_prior_certification
    assert not conclusion.paid_service_prompts_used_for_product_improvement_by_default
    assert conclusion.normal_abuse_security_retention_may_apply
    assert conclusion.request_storage_disabled
    assert not conclusion.separate_contribution_control_relevant_to_ordinary_paid_calls


def test_readiness_resolves_only_machine_stage_blockers() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    assert manifest.readiness is AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT
    assert manifest.exact_remaining_blockers == ()
    assert manifest.stage_5_review_release_state is (
        ReviewReleaseState.STAGE_5_REVIEW_RELEASE_BLOCKED_PENDING_NAMED_REVIEWERS
    )
    assert not manifest.human_review_package_release_allowed
    assert not manifest.automated_tournament_execution_authorized_by_manifest
    assert not manifest.application_route_activation_allowed


def test_no_inference_hidden_access_or_zdr_claim_is_introduced() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    assert manifest.provider_inference_calls_during_gate_resolution == 0
    assert not manifest.hidden_fixture_access_during_gate_resolution
    assert not manifest.zero_data_retention_claimed
    assert manifest.openai_standard_abuse_logging_may_apply
    assert manifest.google_standard_abuse_logging_may_apply


def test_final_validator_rejects_authority_or_retention_escalation() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    for field in (
        "human_review_package_release_allowed",
        "automated_tournament_execution_authorized_by_manifest",
        "application_route_activation_allowed",
        "zero_data_retention_claimed",
    ):
        with pytest.raises(ValueError):
            validate_final_readiness_manifest(replace(manifest, **{field: True}))


def test_final_validator_rejects_predecessor_or_attestation_drift() -> None:
    manifest = FINAL_READINESS_MANIFEST.manifest
    with pytest.raises(ValueError, match=r"exact M6\.6B-4A"):
        validate_final_readiness_manifest(replace(manifest, predecessor_manifest_hash="0" * 64))
    openai = manifest.human_attestations[0]
    changed = replace(openai, state=VerifiedControlState.DISABLED_VERIFIED)
    with pytest.raises(ValueError, match="OpenAI data sharing"):
        validate_final_readiness_manifest(
            replace(manifest, human_attestations=(changed, manifest.human_attestations[1]))
        )
