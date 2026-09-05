"""Minimum safe operator workflow for an unsubscribe reply.

recipient sends opt-out reply -> human/operator observes reply -> operator
records opt-out -> suppression registry updates -> future contact eligibility
fails. Manual ingestion (an operator reading the monitored mailbox and calling
``ingest_operator_observed_opt_out``) is acceptable for the first pilot; no
mailbox automation is implemented because none is required for one recipient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from opintel_suppression.application import SuppressionRegistryService
from opintel_suppression.copy import OPT_OUT_SUPPRESSION_MAX_SLA
from opintel_suppression.domain import SuppressionEntry, SuppressionSourceMechanism


@dataclass(frozen=True)
class OperatorOptOutIngestionResult:
    entry: SuppressionEntry
    received_at: datetime
    suppressed_at: datetime
    elapsed: timedelta
    within_sla: bool


def ingest_operator_observed_opt_out(
    service: SuppressionRegistryService,
    *,
    workspace_id: UUID,
    raw_email: str,
    reply_evidence_ref: str,
    received_at: datetime,
    recorded_at: datetime,
) -> OperatorOptOutIngestionResult:
    """``received_at``: when the recipient's UNSUBSCRIBE reply arrived in the
    monitored mailbox. ``recorded_at``: when the operator recorded it (the
    suppression's effective timestamp is the earlier of the two, since
    suppression is meant to apply as of the request, not the paperwork)."""
    effective_at = min(received_at, recorded_at)
    entry = service.record_address_opt_out(
        workspace_id=workspace_id,
        raw_email=raw_email,
        reason="recipient replied UNSUBSCRIBE to the monitored reply-to mailbox",
        evidence_ref=reply_evidence_ref,
        opt_out_received_at=effective_at,
        source_mechanism=SuppressionSourceMechanism.REPLY_BASED_OPT_OUT,
    )
    elapsed = recorded_at - received_at
    return OperatorOptOutIngestionResult(
        entry=entry,
        received_at=received_at,
        suppressed_at=entry.suppression_effective_at,
        elapsed=elapsed,
        within_sla=elapsed <= OPT_OUT_SUPPRESSION_MAX_SLA,
    )
