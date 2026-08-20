from __future__ import annotations

from dataclasses import replace

import pytest
from opintel_qualification.tournament2_review_release import (
    FROZEN_REVIEWER_ASSIGNMENTS,
    REVIEWER_RELEASE_MANIFEST,
    PackageReleaseState,
    ReviewerRole,
    assignment_manifest_hash,
    release_manifest_hash,
    validate_release_manifest,
    workbook_filename,
)


def test_exact_distinct_reviewer_assignments_freeze_only_primary_release() -> None:
    value = validate_release_manifest()
    assert tuple(item.reviewer_id for item in value.assignments) == (
        "PRIMARY_A",
        "PRIMARY_B",
        "PRIMARY_C",
        "ADJUDICATOR_D",
    )
    assert len({item.sealed_slot for item in value.assignments}) == 4
    assert len(assignment_manifest_hash()) == len(release_manifest_hash()) == 64
    assert all(
        item.package_release_state is PackageReleaseState.RELEASED_TO_PRIMARY
        for item in FROZEN_REVIEWER_ASSIGNMENTS
        if item.role is ReviewerRole.PRIMARY
    )
    assert FROZEN_REVIEWER_ASSIGNMENTS[-1].package_release_state is (
        PackageReleaseState.SEALED_UNRELEASED
    )


def test_release_has_zero_provider_scoring_mapping_or_adjudicator_authority() -> None:
    value = validate_release_manifest()
    assert value.provider_calls == 0
    assert not value.scoring_performed
    assert not value.mapping_revealed
    assert value.adjudicator_package_count_released == 0
    assert value.primary_case_count == 105
    assert value.primary_workbook_count == 3


def test_duplicate_assignment_or_adjudicator_release_fails_closed() -> None:
    duplicate = replace(
        REVIEWER_RELEASE_MANIFEST.assignments[-1],
        reviewer_id="PRIMARY_A",
        package_release_state=PackageReleaseState.RELEASED_TO_PRIMARY,
    )
    with pytest.raises(ValueError):
        validate_release_manifest(
            replace(
                REVIEWER_RELEASE_MANIFEST,
                assignments=(*FROZEN_REVIEWER_ASSIGNMENTS[:3], duplicate),
            )
        )


def test_only_primary_workbook_names_are_available() -> None:
    assert workbook_filename("PRIMARY_A") == "Tournament-II-Review-PRIMARY_A.xlsx"
    with pytest.raises(ValueError, match="primary"):
        workbook_filename("ADJUDICATOR_D")
