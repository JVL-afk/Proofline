"""Human-attested final machine-stage readiness successor for Tournament II."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

from opintel_qualification.tournament2_readiness import (
    SUCCESSOR_MANIFEST,
    AutomatedTournamentReadiness,
    TournamentExecutionSuccessorManifest,
)


class AttestationProvenance(StrEnum):
    HUMAN_CONTROL_PLANE_ATTESTATION = "human_control_plane_attestation"


class VerifiedControlState(StrEnum):
    DATA_SHARING_DISABLED_VERIFIED = "data_sharing_disabled_verified"
    DISABLED_VERIFIED = "disabled_verified"


class ReviewReleaseState(StrEnum):
    STAGE_5_REVIEW_RELEASE_BLOCKED_PENDING_NAMED_REVIEWERS = (
        "stage_5_review_release_blocked_pending_named_reviewers"
    )


@dataclass(frozen=True, slots=True)
class HumanControlPlaneAttestation:
    provider: str
    control: str
    state: VerifiedControlState
    provenance: AttestationProvenance
    attested_at: datetime
    evidence_form: str
    settings: tuple[tuple[str, str], ...]
    zero_data_retention_claimed: bool


@dataclass(frozen=True, slots=True)
class GoogleDataUseConclusion:
    paid_project_verified_by_prior_certification: bool
    paid_service_prompts_used_for_product_improvement_by_default: bool
    normal_abuse_security_retention_may_apply: bool
    request_storage_disabled: bool
    separate_contribution_control_relevant_to_ordinary_paid_calls: bool
    rationale: tuple[str, ...]
    official_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinalAutomatedReadinessManifest:
    version: str
    predecessor_manifest_hash: str
    readiness: AutomatedTournamentReadiness
    created_at: datetime
    preserved_predecessor: TournamentExecutionSuccessorManifest
    human_attestations: tuple[HumanControlPlaneAttestation, ...]
    google_data_use_conclusion: GoogleDataUseConclusion
    openai_standard_abuse_logging_may_apply: bool
    google_standard_abuse_logging_may_apply: bool
    zero_data_retention_claimed: bool
    provider_inference_calls_during_gate_resolution: int
    hidden_fixture_access_during_gate_resolution: bool
    exact_remaining_blockers: tuple[str, ...]
    stage_5_review_release_state: ReviewReleaseState
    human_review_package_release_allowed: bool
    automated_tournament_execution_authorized_by_manifest: bool
    application_route_activation_allowed: bool


@dataclass(frozen=True, slots=True)
class FinalReadinessArtifact:
    manifest: FinalAutomatedReadinessManifest
    manifest_hash: str


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def build_final_readiness_manifest() -> FinalReadinessArtifact:
    attested_at = datetime(2026, 8, 19, 12, 19, 37, tzinfo=UTC)
    attestations = (
        HumanControlPlaneAttestation(
            "openai",
            "OPENAI_DATA_SHARING",
            VerifiedControlState.DATA_SHARING_DISABLED_VERIFIED,
            AttestationProvenance.HUMAN_CONTROL_PLANE_ATTESTATION,
            attested_at,
            "account-owner supplied screenshot attestation; screenshot binary not stored",
            (
                ("platform_model_feedback_sharing", "disabled"),
                ("evaluation_and_fine_tuning_data_sharing", "disabled"),
                ("inputs_and_outputs_sharing", "disabled"),
            ),
            False,
        ),
        HumanControlPlaneAttestation(
            "google",
            "GOOGLE_INTERACTIONS_REQUEST_STORAGE",
            VerifiedControlState.DISABLED_VERIFIED,
            AttestationProvenance.HUMAN_CONTROL_PLANE_ATTESTATION,
            attested_at,
            "account-owner supplied screenshot attestation; screenshot binary not stored",
            (
                ("generate_content_api_request_storage", "disabled"),
                ("interactions_api_request_storage", "disabled"),
            ),
            False,
        ),
    )
    manifest = FinalAutomatedReadinessManifest(
        "m6.6b4b.tournament-execution-readiness@3",
        SUCCESSOR_MANIFEST.manifest_hash,
        AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT,
        attested_at,
        SUCCESSOR_MANIFEST.manifest,
        attestations,
        GoogleDataUseConclusion(
            True,
            False,
            True,
            True,
            False,
            (
                "paid Gemini API prompts and responses are not used to improve products by default",
                "developer-owned API logging is separate from abuse-monitoring retention",
                "dataset contribution or feedback is an explicit manual opt-in using selected logs",
                "Interactions request storage is disabled, so ordinary paid calls create no logs "
                "available for later dataset contribution",
                "no additional global contribution toggle applies to ordinary paid API calls",
            ),
            (
                "https://ai.google.dev/gemini-api/terms",
                "https://ai.google.dev/gemini-api/docs/logs-policy",
            ),
        ),
        True,
        True,
        False,
        0,
        False,
        (),
        ReviewReleaseState.STAGE_5_REVIEW_RELEASE_BLOCKED_PENDING_NAMED_REVIEWERS,
        False,
        False,
        False,
    )
    validate_final_readiness_manifest(manifest)
    return FinalReadinessArtifact(manifest, _hash(asdict(manifest)))


def validate_final_readiness_manifest(
    manifest: FinalAutomatedReadinessManifest,
) -> FinalAutomatedReadinessManifest:
    if manifest.predecessor_manifest_hash != SUCCESSOR_MANIFEST.manifest_hash:
        raise ValueError("final readiness must bind the exact M6.6B-4A manifest")
    if manifest.preserved_predecessor != SUCCESSOR_MANIFEST.manifest:
        raise ValueError("M6.6B-4A controls must remain byte-semantically unchanged")
    if manifest.readiness is not AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT:
        raise ValueError("resolved machine-stage gates must produce automated readiness")
    if manifest.exact_remaining_blockers:
        raise ValueError("ready manifest cannot retain execution-material blockers")
    controls = {item.control: item for item in manifest.human_attestations}
    if controls["OPENAI_DATA_SHARING"].state is not (
        VerifiedControlState.DATA_SHARING_DISABLED_VERIFIED
    ):
        raise ValueError("OpenAI data sharing must be human-verified disabled")
    if controls["GOOGLE_INTERACTIONS_REQUEST_STORAGE"].state is not (
        VerifiedControlState.DISABLED_VERIFIED
    ):
        raise ValueError("Google Interactions storage must be human-verified disabled")
    if any(
        item.provenance is not AttestationProvenance.HUMAN_CONTROL_PLANE_ATTESTATION
        for item in manifest.human_attestations
    ):
        raise ValueError("provider setting evidence must remain human-attested")
    if manifest.zero_data_retention_claimed or any(
        item.zero_data_retention_claimed for item in manifest.human_attestations
    ):
        raise ValueError("M6.6B-4B cannot claim zero data retention")
    google_data = manifest.google_data_use_conclusion
    if google_data.separate_contribution_control_relevant_to_ordinary_paid_calls:
        raise ValueError("ordinary paid calls do not require a separate contribution toggle")
    if manifest.provider_inference_calls_during_gate_resolution:
        raise ValueError("M6.6B-4B authorizes zero provider inference calls")
    if manifest.hidden_fixture_access_during_gate_resolution:
        raise ValueError("M6.6B-4B cannot access hidden fixtures")
    if manifest.human_review_package_release_allowed:
        raise ValueError("unnamed reviewers keep Stage 5 package release blocked")
    if manifest.automated_tournament_execution_authorized_by_manifest:
        raise ValueError("readiness is not a one-shot execution authorization")
    if manifest.application_route_activation_allowed:
        raise ValueError("final readiness cannot activate an application route")
    return manifest


FINAL_READINESS_MANIFEST = build_final_readiness_manifest()
