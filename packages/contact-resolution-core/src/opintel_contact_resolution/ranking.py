"""M6.10 deterministic channel ranking (section 16).

Hard blockers always override score - a channel with a blocking
eligibility disposition can never outrank an eligible one no matter how it
scores on the soft factors below. No LLM chooses the channel; this module
is the only place a "recommended channel" is computed.
"""

from __future__ import annotations

from dataclasses import dataclass

from opintel_contact_resolution.domain import (
    BLOCKING_DISPOSITIONS,
    Channel,
    ContactEndpointEvidence,
    EligibilityDisposition,
    IdentityConfidence,
)

_ELIGIBLE_DISPOSITIONS: frozenset[EligibilityDisposition] = frozenset(
    {
        EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT,
        EligibilityDisposition.ELIGIBLE_MANUAL_CHANNEL,
        EligibilityDisposition.ELIGIBLE_HUMAN_CALL_DIRECT,
        EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT,
    }
)

_CHANNEL_CAN_PRESENT_DEMO: dict[Channel, bool] = {
    Channel.EMAIL: True,
    Channel.LINKEDIN: True,
    Channel.PHONE: False,
    Channel.SMS: False,
    Channel.AUTONOMOUS_VOICE: False,
}

_DIRECTNESS_SCORE: dict[EligibilityDisposition, int] = {
    EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT: 100,
    EligibilityDisposition.ELIGIBLE_HUMAN_CALL_DIRECT: 80,
    EligibilityDisposition.ELIGIBLE_MANUAL_CHANNEL: 60,
    EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT: 40,
}

_CONFIDENCE_PENALTY: dict[IdentityConfidence, int] = {
    IdentityConfidence.HIGH: 0,
    IdentityConfidence.MEDIUM: -10,
    IdentityConfidence.LOW: -25,
    IdentityConfidence.CONFLICTED: -1000,
}


@dataclass(frozen=True)
class ChannelRankingEntry:
    channel: Channel
    disposition: EligibilityDisposition
    eligible: bool
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ChannelRankingResult:
    entries: tuple[ChannelRankingEntry, ...]
    recommended_channel: Channel | None
    recommendation_reason: str


def _score_one(evidence: ContactEndpointEvidence) -> ChannelRankingEntry:
    disposition = evidence.eligibility_disposition
    reasons: list[str] = []

    if disposition in BLOCKING_DISPOSITIONS:
        reasons.append(f"blocked: {disposition.value}")
        return ChannelRankingEntry(
            channel=evidence.channel,
            disposition=disposition,
            eligible=False,
            score=-1_000_000,
            reasons=tuple(reasons),
        )

    if disposition not in _ELIGIBLE_DISPOSITIONS:
        reasons.append(f"not eligible: {disposition.value}")
        return ChannelRankingEntry(
            channel=evidence.channel,
            disposition=disposition,
            eligible=False,
            score=-1_000_000,
            reasons=tuple(reasons),
        )

    score = _DIRECTNESS_SCORE.get(disposition, 0)
    reasons.append(f"base directness score {score} for {disposition.value}")

    score += _CONFIDENCE_PENALTY[evidence.confidence]
    reasons.append(f"identity confidence {evidence.confidence.value}")

    if _CHANNEL_CAN_PRESENT_DEMO.get(evidence.channel, False):
        score += 15
        reasons.append("can present the approved demo (+15)")

    if evidence.company_domain_match:
        score += 5
    if evidence.identity_match:
        score += 5

    if evidence.confidence is IdentityConfidence.CONFLICTED:
        return ChannelRankingEntry(
            channel=evidence.channel,
            disposition=disposition,
            eligible=False,
            score=-1_000_000,
            reasons=(*reasons, "conflicted identity - hard blocker"),
        )

    return ChannelRankingEntry(
        channel=evidence.channel,
        disposition=disposition,
        eligible=True,
        score=score,
        reasons=tuple(reasons),
    )


def rank_channels(
    endpoint_evidence: tuple[ContactEndpointEvidence, ...],
) -> ChannelRankingResult:
    """One entry per (channel, best-endpoint) pair - callers should pass the
    single best endpoint per channel already selected by
    ``application.rank_person_candidates`` + source reconciliation upstream."""
    entries = tuple(_score_one(e) for e in endpoint_evidence)
    eligible = [e for e in entries if e.eligible]
    if not eligible:
        return ChannelRankingResult(
            entries=entries,
            recommended_channel=None,
            recommendation_reason="no channel is eligible - every candidate endpoint is blocked",
        )
    best = max(eligible, key=lambda e: e.score)
    reason = (
        f"{best.channel.value} scored highest ({best.score}) among eligible channels: "
        + "; ".join(best.reasons)
    )
    return ChannelRankingResult(
        entries=entries, recommended_channel=best.channel, recommendation_reason=reason
    )
