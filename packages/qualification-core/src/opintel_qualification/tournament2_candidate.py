"""Immutable fake-only candidate intake for M6.6A."""

from __future__ import annotations

from dataclasses import replace

from opintel_qualification.tournament2_domain import CandidateIntake, CandidateKind, IntakeState


def approve_candidate(
    candidate: CandidateIntake, approval_refs: tuple[str, ...]
) -> CandidateIntake:
    if candidate.state is not IntakeState.DRAFT:
        raise ValueError("only a draft candidate can be approved")
    if candidate.kind is not CandidateKind.DETERMINISTIC_FAKE:
        raise ValueError("M6.6A accepts deterministic fake candidates only")
    if not candidate.provider_key.startswith("fixture-"):
        raise ValueError("M6.6A candidate must use a fixture provider")
    if not approval_refs:
        raise ValueError("candidate approval references are required")
    if not candidate.structured_output_supported:
        raise ValueError("structured output support is required")
    return replace(candidate, state=IntakeState.APPROVED, approval_refs=approval_refs)


def freeze_candidate(candidate: CandidateIntake) -> CandidateIntake:
    if candidate.state is not IntakeState.APPROVED:
        raise ValueError("only an approved candidate can be frozen")
    if candidate.pricing_version is None:
        raise ValueError("unknown fixture pricing fails closed")
    return replace(candidate, state=IntakeState.FROZEN)
