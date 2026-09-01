"""Human-review domain for M6.8-2.

A review is immutable and exact-version-bound: it names one envelope SHA-256 and
one generation record hash, and every transition re-checks them. The reviewer
can only:

* select a candidate that is in the record's ``selectable_candidate_ids``
  (populated by the store from PASS-validation ranked candidates only) - a
  FAILED candidate is structurally unselectable;
* reject a candidate;
* reject all candidates;
* accept a ``COMMUNICATION_NOT_DISTINCTIVE_ENOUGH`` terminal.

The reviewer never creates a fact, never edits rendered content, and never
clears a validator finding. This module has no link to contact eligibility or
delivery.
"""

from __future__ import annotations

from dataclasses import replace

from opintel_communication.domain import (
    TERMINAL_REVIEW_STATES,
    CommunicationOutcome,
    GenerationRecord,
    HumanReview,
    HumanReviewAction,
    HumanReviewEvent,
    HumanReviewState,
)


class ReviewTransitionError(Exception):
    """A review transition that the invariants forbid."""


def open_review(record: GenerationRecord, review_id: str) -> HumanReview:
    return HumanReview(
        review_id=review_id,
        envelope_sha256=record.envelope_sha256,
        generation_record_hash=record.record_hash,
        selectable_candidate_ids=record.selectable_candidate_ids(),
        terminal_outcome=record.terminal_outcome,
        state=HumanReviewState.PENDING,
    )


def _guard_binding(review: HumanReview, record: GenerationRecord) -> None:
    if review.generation_record_hash != record.record_hash:
        raise ReviewTransitionError("review is bound to a different generation record hash")
    if review.envelope_sha256 != record.envelope_sha256:
        raise ReviewTransitionError("review is bound to a different envelope sha256")


def _guard_open(review: HumanReview) -> None:
    if review.state in TERMINAL_REVIEW_STATES:
        raise ReviewTransitionError(f"review already terminal in state {review.state}")


def _append(
    review: HumanReview,
    action: HumanReviewAction,
    candidate_id: str | None,
    at_epoch_seconds: int,
    reviewer_ref: str,
    note: str,
    new_state: HumanReviewState,
    selected_candidate_id: str | None,
) -> HumanReview:
    event = HumanReviewEvent(
        action=action,
        candidate_id=candidate_id,
        at_epoch_seconds=at_epoch_seconds,
        reviewer_ref=reviewer_ref,
        note=note,
    )
    return replace(
        review,
        state=new_state,
        history=(*review.history, event),
        selected_candidate_id=selected_candidate_id,
    )


def select_candidate(
    review: HumanReview,
    record: GenerationRecord,
    candidate_id: str,
    *,
    at_epoch_seconds: int,
    reviewer_ref: str,
    note: str = "",
) -> HumanReview:
    _guard_binding(review, record)
    _guard_open(review)
    if candidate_id not in review.selectable_candidate_ids:
        # Either it does not exist, or its validation FAILED (so it never entered
        # the ranked/selectable set). Both are structurally unselectable.
        raise ReviewTransitionError(
            f"candidate {candidate_id} is not selectable (not a PASS-validation ranked candidate)"
        )
    return _append(
        review,
        HumanReviewAction.SELECT_CANDIDATE,
        candidate_id,
        at_epoch_seconds,
        reviewer_ref,
        note,
        HumanReviewState.CANDIDATE_SELECTED,
        candidate_id,
    )


def reject_candidate(
    review: HumanReview,
    record: GenerationRecord,
    candidate_id: str,
    *,
    at_epoch_seconds: int,
    reviewer_ref: str,
    note: str = "",
) -> HumanReview:
    _guard_binding(review, record)
    _guard_open(review)
    known = {c.candidate_id for c in record.candidates}
    if candidate_id not in known:
        raise ReviewTransitionError(f"candidate {candidate_id} is not in this record")
    return _append(
        review,
        HumanReviewAction.REJECT_CANDIDATE,
        candidate_id,
        at_epoch_seconds,
        reviewer_ref,
        note,
        HumanReviewState.CANDIDATE_REJECTED,
        None,
    )


def reject_all(
    review: HumanReview,
    record: GenerationRecord,
    *,
    at_epoch_seconds: int,
    reviewer_ref: str,
    note: str = "",
) -> HumanReview:
    _guard_binding(review, record)
    _guard_open(review)
    return _append(
        review,
        HumanReviewAction.REJECT_ALL,
        None,
        at_epoch_seconds,
        reviewer_ref,
        note,
        HumanReviewState.ALL_REJECTED,
        None,
    )


def accept_not_distinctive(
    review: HumanReview,
    record: GenerationRecord,
    *,
    at_epoch_seconds: int,
    reviewer_ref: str,
    note: str = "",
) -> HumanReview:
    _guard_binding(review, record)
    _guard_open(review)
    if record.terminal_outcome != CommunicationOutcome.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH:
        raise ReviewTransitionError(
            "accept_not_distinctive is only valid when the record terminal is "
            "COMMUNICATION_NOT_DISTINCTIVE_ENOUGH"
        )
    return _append(
        review,
        HumanReviewAction.ACCEPT_NOT_DISTINCTIVE,
        None,
        at_epoch_seconds,
        reviewer_ref,
        note,
        HumanReviewState.ACCEPTED_NOT_DISTINCTIVE,
        None,
    )
