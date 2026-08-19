"""Successor Tournament II manifest for machine-stage readiness only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

from opintel_qualification.tournament2_freeze import FROZEN_MANIFEST, BudgetHierarchy


class AutomatedTournamentReadiness(StrEnum):
    READY_FOR_AUTOMATED_TOURNAMENT = "ready_for_automated_tournament"
    NOT_APPROVED = "not_approved"


class FindingState(StrEnum):
    VERIFIED = "verified"
    UNKNOWN_NONBLOCKING = "unknown_nonblocking"
    UNKNOWN_BLOCKING = "unknown_blocking"


@dataclass(frozen=True, slots=True)
class AccountControlFinding:
    provider: str
    deployment_and_endpoint: FindingState
    account_tier: FindingState
    request_token_capacity: FindingState
    billing_spend_capacity: FindingState
    credential_scope_isolation: FindingState
    standard_retention_accepted: FindingState
    opt_in_training_sharing_disabled: FindingState
    rationale: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderPacing:
    provider: str
    maximum_concurrency: int
    minimum_seconds_between_requests: int
    maximum_outstanding_requests: int
    maximum_estimated_input_tokens_per_minute: int
    maximum_estimated_output_tokens_per_minute: int
    rate_limit_response: str
    retry_policy: str


@dataclass(frozen=True, slots=True)
class ReviewerSlotPolicy:
    reserved_slots: tuple[str, ...]
    assigned_reviewer_ids: tuple[str, ...]
    packages_sealed: bool
    package_release_allowed: bool
    identities_required_before_release: bool
    distinct_primary_reviewers_required: bool
    project_owner_may_fill_one_primary: bool
    project_owner_may_be_sole_adjudicator: bool


@dataclass(frozen=True, slots=True)
class AutomatedStagePolicy:
    stages: tuple[str, ...]
    stage_5b_action: str
    stage_5b_release_gate: str
    stage_6_gate: str
    successful_certification_repeated: bool


@dataclass(frozen=True, slots=True)
class TournamentExecutionSuccessorManifest:
    version: str
    predecessor_manifest_hash: str
    readiness: AutomatedTournamentReadiness
    frozen_at: datetime
    candidates_hash: str
    bindings_hash: str
    candidate_count: int
    binding_count: int
    provider_policy_snapshot: str
    pricing_snapshot: str
    accepted_synthetic_retention_decision: str
    account_control_evidence: str
    account_findings: tuple[AccountControlFinding, ...]
    pacing: tuple[ProviderPacing, ...]
    budget_hash: str
    budget_hierarchy: BudgetHierarchy
    reviewer_policy: ReviewerSlotPolicy
    stage_policy: AutomatedStagePolicy
    identity_policy: str
    corpus_metadata_hash: str
    evaluator_hash: str
    safety_policy_hash: str
    repetition_policy_hash: str
    credential_policy: str
    security_policy: tuple[str, ...]
    hidden_corpus_policy: str
    global_kill_switch_armed: bool
    budget_kill_switch_armed: bool
    execution_owner: str
    stop_operator: str
    execution_window_start: datetime
    execution_window_end: datetime
    hidden_fixture_access_during_freeze: bool
    inference_calls_during_gate_resolution: int
    route_activation_allowed: bool
    human_review_package_release_allowed: bool
    exact_remaining_blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SuccessorManifestArtifact:
    manifest: TournamentExecutionSuccessorManifest
    manifest_hash: str


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _account_findings() -> tuple[AccountControlFinding, ...]:
    common = (
        "exact model metadata access returned HTTP 200 on 2026-08-19",
        "exact account tier and quotas are not exposed to the ordinary project credential",
        "global concurrency one and provider pacing keep volume below public entry-tier limits",
        "429 pauses the provider and permits at most one unambiguous transient retry",
    )
    return (
        AccountControlFinding(
            "openai",
            FindingState.VERIFIED,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.VERIFIED,
            FindingState.VERIFIED,
            FindingState.UNKNOWN_BLOCKING,
            (
                *common,
                "Responses requests must set store=false and background=false",
                "effective project data-sharing opt-in state was not observable",
            ),
            (
                "m6.6b4a.control-plane-probe@1",
                "m6.6b4a.provider-policy-pricing@2026-08-19",
            ),
        ),
        AccountControlFinding(
            "anthropic",
            FindingState.VERIFIED,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.VERIFIED,
            FindingState.VERIFIED,
            FindingState.VERIFIED,
            (
                *common,
                "commercial API data is not used for training without explicit permission",
                "no files batches cache or persisted conversation is permitted",
            ),
            (
                "m6.6b4a.control-plane-probe@1",
                "m6.6b4a.provider-policy-pricing@2026-08-19",
            ),
        ),
        AccountControlFinding(
            "google",
            FindingState.VERIFIED,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.UNKNOWN_NONBLOCKING,
            FindingState.VERIFIED,
            FindingState.VERIFIED,
            FindingState.UNKNOWN_BLOCKING,
            (
                *common,
                "Interactions requests must set store=false with no previous interaction",
                "effective project logging or dataset-sharing opt-in state was not observable",
            ),
            (
                "m6.6b4a.control-plane-probe@1",
                "m6.6b4a.provider-policy-pricing@2026-08-19",
            ),
        ),
    )


def _pacing() -> tuple[ProviderPacing, ...]:
    retry = (
        "one retry only after unambiguous transient failure and no accepted result; "
        "semantic or hard-gate failures never retry"
    )
    return (
        ProviderPacing(
            "openai",
            1,
            15,
            1,
            9_616,
            8_800,
            "honor retry-after; otherwise pause 60 seconds; second 429 stops provider",
            retry,
        ),
        ProviderPacing(
            "anthropic",
            1,
            15,
            1,
            9_616,
            9_600,
            "honor retry-after; otherwise pause 60 seconds; second 429 stops provider",
            retry,
        ),
        ProviderPacing(
            "google",
            1,
            30,
            1,
            3_474,
            4_800,
            "honor retry-after; otherwise pause 120 seconds; second 429 stops provider",
            retry,
        ),
    )


def _reviewer_policy() -> ReviewerSlotPolicy:
    return ReviewerSlotPolicy(
        (
            "PRIMARY_REVIEWER_SLOT_1",
            "PRIMARY_REVIEWER_SLOT_2",
            "PRIMARY_REVIEWER_SLOT_3",
            "CONDITIONAL_ADJUDICATOR_SLOT",
        ),
        (),
        True,
        False,
        True,
        True,
        True,
        False,
    )


def _blockers(findings: tuple[AccountControlFinding, ...]) -> tuple[str, ...]:
    return tuple(
        f"{item.provider}:verify_account_opt_in_training_or_data_sharing_is_disabled"
        for item in findings
        if item.opt_in_training_sharing_disabled is FindingState.UNKNOWN_BLOCKING
    )


def build_successor_manifest() -> SuccessorManifestArtifact:
    predecessor = FROZEN_MANIFEST.manifest
    findings = _account_findings()
    blockers = _blockers(findings)
    readiness = (
        AutomatedTournamentReadiness.NOT_APPROVED
        if blockers
        else AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT
    )
    manifest = TournamentExecutionSuccessorManifest(
        "m6.6b4a.tournament-execution-manifest@2",
        FROZEN_MANIFEST.manifest_hash,
        readiness,
        datetime(2026, 8, 19, 11, 50, tzinfo=UTC),
        _hash([asdict(item) for item in predecessor.candidates]),
        _hash([asdict(item) for item in predecessor.bindings]),
        len(predecessor.candidates),
        len(predecessor.bindings),
        "m6.6b4a.provider-policy-pricing@2026-08-19",
        "m6.6b4a.provider-policy-pricing@2026-08-19",
        "M6.6 synthetic-only standard provider retention accepted by project owner",
        "m6.6b4a.control-plane-probe@1",
        findings,
        _pacing(),
        _hash(asdict(predecessor.budget)),
        predecessor.budget,
        _reviewer_policy(),
        AutomatedStagePolicy(
            (
                "stage_1_certification_confirmation",
                "stage_2_safety_gauntlet",
                "stage_3_hidden_qualification",
                "stage_4_required_repetitions",
                "stage_5a_objective_dominance",
                "stage_5b_generate_and_seal_blinded_packages",
                "stage_6_final_reporting_after_human_review",
            ),
            "generate and seal only",
            "three named distinct primaries and one named conditional adjudicator",
            "completed locked human review",
            False,
        ),
        "ADR-0063 pinned and run-bound synthetic identity",
        predecessor.corpus_metadata_hash,
        predecessor.evaluator_hash,
        predecessor.safety_policy_hash,
        predecessor.repetition_policy_hash,
        "provider-specific ignored local credentials; exact-host egress; no value retention",
        (
            "provider-specific isolated runner",
            "allowlisted HTTPS egress only",
            "no application database or M6 M6.5 M6.7 credential access",
            "no tools search browsing files functions code or computer",
            "task-minimized synthetic fixtures only",
            "raw bodies in memory only and safe metadata persistence",
            "reserve budget before every call",
        ),
        "sealed; runner receives task-minimized projections only after live authorization",
        True,
        True,
        "project-owner",
        "codex-local-tournament-runner-under-project-owner-control",
        datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
        datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
        False,
        0,
        False,
        False,
        blockers,
    )
    validate_successor_manifest(manifest)
    return SuccessorManifestArtifact(manifest, _hash(asdict(manifest)))


def validate_successor_manifest(
    manifest: TournamentExecutionSuccessorManifest,
) -> TournamentExecutionSuccessorManifest:
    if manifest.predecessor_manifest_hash != FROZEN_MANIFEST.manifest_hash:
        raise ValueError("successor must bind the exact M6.6B-4 predecessor")
    if manifest.candidate_count != 4 or manifest.binding_count != 12:
        raise ValueError("successor roster or binding count changed")
    if (
        manifest.hidden_fixture_access_during_freeze
        or manifest.inference_calls_during_gate_resolution
    ):
        raise ValueError("gate resolution cannot access hidden fixtures or run inference")
    if manifest.route_activation_allowed or manifest.human_review_package_release_allowed:
        raise ValueError("successor cannot activate routes or release review packages")
    if not manifest.global_kill_switch_armed or not manifest.budget_kill_switch_armed:
        raise ValueError("both tournament kill switches must be armed")
    if manifest.budget_hierarchy.total_hard_cap_micros != 25_000_000:
        raise ValueError("hard budget must remain exactly USD 25")
    if manifest.reviewer_policy.package_release_allowed:
        raise ValueError("unnamed reviewer slots cannot release packages")
    if manifest.readiness is AutomatedTournamentReadiness.READY_FOR_AUTOMATED_TOURNAMENT:
        if manifest.exact_remaining_blockers:
            raise ValueError("ready manifest cannot retain blockers")
    elif not manifest.exact_remaining_blockers:
        raise ValueError("not-approved manifest must state exact blockers")
    return manifest


SUCCESSOR_MANIFEST = build_successor_manifest()
