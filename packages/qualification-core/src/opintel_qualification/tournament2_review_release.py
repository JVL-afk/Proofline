"""Frozen reviewer assignment and primary package-release contracts for M6.6B-6."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

RECOVERY_COMMIT = "5deb7564c777434144654bc58cf6ccbf9626e3f5"
RECOVERY_RUN_ID = "551c3c0d-d68e-568c-b9b8-14d947eec22e"
RECOVERY_RESULT_SHA256 = "04397a75f504e2574758e23e83462c5cdbfc49827db116f61b6af4f7deaaac00"
RENDERED_OUTPUT_SHA256 = "698a231f57172e362df29261168eda7894573052be54956e1012914eb2fa0726"
ASSIGNMENT_FILE_SHA256 = "c5794d20e00a35a747d30cb7856864ad17ce3ce0a9e94d3431ac3b93985cfbe7"
PACKAGE_SET_SHA256 = "1a1753dfdd409ced403e5864c5e06c49e2f753dde671999a9026d7c09b30bb01"
WORKBOOK_SCHEMA_VERSION = "m6.6b6.primary-review-workbook@1"
IMPORT_SCHEMA_VERSION = "m6.6b6.locked-primary-review@1"
ASSIGNMENTS_FROZEN_AT = "2026-08-20T06:27:24Z"

TASK_REVIEW_CONTEXTS = {
    "evidence_interpretation": (
        "Compare how clearly and faithfully each version communicates the supplied "
        "evidence-bound material while preserving qualifiers and unknowns."
    ),
    "contradiction_analysis": (
        "Compare how clearly and usefully each version presents contradictions without "
        "weakening, hiding, or resolving them."
    ),
    "opportunity_reasoning": (
        "Compare how useful and trustworthy each version is as advisory opportunity reasoning "
        "while preserving evidence limits and uncertainty."
    ),
    "audit_wording": (
        "Compare the versions as evidence-linked audit wording. Prefer clarity and usefulness "
        "without adding facts, certainty, or unsupported precision."
    ),
    "outreach_wording": (
        "Compare the versions as concise permission-seeking outreach wording. Prefer natural, "
        "trustworthy language that preserves scope and does not overclaim."
    ),
}


class ReviewerRole(StrEnum):
    PRIMARY = "primary"
    CONDITIONAL_ADJUDICATOR = "conditional_adjudicator"


class PackageReleaseState(StrEnum):
    RELEASED_TO_PRIMARY = "released_to_primary"
    SEALED_UNRELEASED = "sealed_unreleased"


class ReviewCompletionState(StrEnum):
    IN_PROGRESS = "in_progress"
    LOCKED_PRIMARY_REVIEW = "locked_primary_review"


@dataclass(frozen=True, slots=True)
class FrozenReviewerAssignment:
    reviewer_id: str
    role: ReviewerRole
    sealed_slot: str
    distinct_human_attested: bool
    package_release_state: PackageReleaseState


@dataclass(frozen=True, slots=True)
class ReviewerReleaseManifest:
    version: str
    recovery_commit: str
    recovery_run_id: str
    recovery_result_sha256: str
    rendered_output_sha256: str
    source_assignment_sha256: str
    package_set_sha256: str
    assignments_frozen_at: str
    assignments: tuple[FrozenReviewerAssignment, ...]
    primary_case_count: int
    primary_workbook_count: int
    adjudicator_package_count_released: int
    provider_calls: int
    scoring_performed: bool
    mapping_revealed: bool


FROZEN_REVIEWER_ASSIGNMENTS = (
    FrozenReviewerAssignment(
        "PRIMARY_A",
        ReviewerRole.PRIMARY,
        "PRIMARY_REVIEWER_SLOT_1",
        True,
        PackageReleaseState.RELEASED_TO_PRIMARY,
    ),
    FrozenReviewerAssignment(
        "PRIMARY_B",
        ReviewerRole.PRIMARY,
        "PRIMARY_REVIEWER_SLOT_2",
        True,
        PackageReleaseState.RELEASED_TO_PRIMARY,
    ),
    FrozenReviewerAssignment(
        "PRIMARY_C",
        ReviewerRole.PRIMARY,
        "PRIMARY_REVIEWER_SLOT_3",
        True,
        PackageReleaseState.RELEASED_TO_PRIMARY,
    ),
    FrozenReviewerAssignment(
        "ADJUDICATOR_D",
        ReviewerRole.CONDITIONAL_ADJUDICATOR,
        "CONDITIONAL_ADJUDICATOR_SLOT",
        True,
        PackageReleaseState.SEALED_UNRELEASED,
    ),
)

REVIEWER_RELEASE_MANIFEST = ReviewerReleaseManifest(
    "m6.6b6.reviewer-release@1",
    RECOVERY_COMMIT,
    RECOVERY_RUN_ID,
    RECOVERY_RESULT_SHA256,
    RENDERED_OUTPUT_SHA256,
    ASSIGNMENT_FILE_SHA256,
    PACKAGE_SET_SHA256,
    ASSIGNMENTS_FROZEN_AT,
    FROZEN_REVIEWER_ASSIGNMENTS,
    105,
    3,
    0,
    0,
    False,
    False,
)


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def assignment_manifest_hash() -> str:
    return stable_hash(tuple(asdict(item) for item in FROZEN_REVIEWER_ASSIGNMENTS))


def release_manifest_hash() -> str:
    return stable_hash(asdict(REVIEWER_RELEASE_MANIFEST))


def validate_release_manifest(
    value: ReviewerReleaseManifest = REVIEWER_RELEASE_MANIFEST,
) -> ReviewerReleaseManifest:
    if value.recovery_commit != RECOVERY_COMMIT or value.recovery_run_id != RECOVERY_RUN_ID:
        raise ValueError("review release must bind exact M6.6B-5R lineage")
    if value.assignments_frozen_at != ASSIGNMENTS_FROZEN_AT:
        raise ValueError("reviewer assignment freeze timestamp changed")
    ids = tuple(item.reviewer_id for item in value.assignments)
    slots = tuple(item.sealed_slot for item in value.assignments)
    if ids != ("PRIMARY_A", "PRIMARY_B", "PRIMARY_C", "ADJUDICATOR_D"):
        raise ValueError("reviewer IDs changed")
    if len(set(ids)) != 4 or len(set(slots)) != 4:
        raise ValueError("one human may occupy only one reviewer role")
    if not all(item.distinct_human_attested for item in value.assignments):
        raise ValueError("reviewer distinctness must be owner-attested")
    primaries = tuple(item for item in value.assignments if item.role is ReviewerRole.PRIMARY)
    adjudicators = tuple(
        item for item in value.assignments if item.role is ReviewerRole.CONDITIONAL_ADJUDICATOR
    )
    if len(primaries) != 3 or any(
        item.package_release_state is not PackageReleaseState.RELEASED_TO_PRIMARY
        for item in primaries
    ):
        raise ValueError("exactly three primary packages must be released")
    if len(adjudicators) != 1 or adjudicators[0].package_release_state is not (
        PackageReleaseState.SEALED_UNRELEASED
    ):
        raise ValueError("adjudicator must remain frozen and unreleased")
    if value.primary_case_count != 105 or value.primary_workbook_count != 3:
        raise ValueError("each primary must receive one exact 105-case workbook")
    if (
        value.adjudicator_package_count_released
        or value.provider_calls
        or value.scoring_performed
        or value.mapping_revealed
    ):
        raise ValueError("release cannot call providers, score, reveal, or release adjudication")
    return value


def workbook_filename(reviewer_id: str) -> str:
    if reviewer_id not in {"PRIMARY_A", "PRIMARY_B", "PRIMARY_C"}:
        raise ValueError("only primary reviewer workbooks may be released")
    return f"Tournament-II-Review-{reviewer_id}.xlsx"
