"""Blinded review artifacts; final reviewer count and gain threshold are intentionally absent."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from uuid import UUID

from opintel_qualification.tournament2_domain import (
    BlindedReviewArtifact,
    ReviewerScores,
    TournamentTask,
)


def create_blinded_review(
    artifact_id: UUID,
    case_id: UUID,
    task: TournamentTask,
    deterministic_hash: str,
    candidate_hash: str,
    randomization_nonce: str,
    *,
    automated_safety_passed: bool,
) -> BlindedReviewArtifact:
    if not automated_safety_passed:
        raise ValueError("human review cannot begin before automated safety passes")
    order_hash = hashlib.sha256(
        f"{case_id}:{task.value}:{randomization_nonce}".encode()
    ).hexdigest()
    left, right = (
        (candidate_hash, deterministic_hash)
        if int(order_hash[-1], 16) % 2
        else (deterministic_hash, candidate_hash)
    )
    return BlindedReviewArtifact(
        id=artifact_id,
        case_id=case_id,
        task=task,
        left_artifact_hash=left,
        right_artifact_hash=right,
        presentation_order_hash=order_hash,
        provider_identity_hidden=True,
    )


def validate_scores(scores: ReviewerScores) -> ReviewerScores:
    values = (
        scores.clarity,
        scores.naturalness,
        scores.concision,
        scores.usefulness,
        scores.relevance,
        scores.trustworthiness,
    )
    if any(value < 1 or value > 5 for value in values):
        raise ValueError("review scores must use the 1-5 rubric")
    if scores.preferred_side not in {"left", "right", "tie"}:
        raise ValueError("paired preference must be left, right, or tie")
    return scores


def raw_review_distribution(scores: tuple[ReviewerScores, ...]) -> tuple[dict[str, object], ...]:
    """Preserve raw observations without producing a universal quality score."""
    return tuple(asdict(validate_scores(item)) for item in scores)
