"""Deterministic suppression-registry application service.

Suppression is checked before every send-eligibility decision and applies
immediately once recorded (``record_opt_out``/``suppress_domain`` persist
through the repository synchronously, before returning). There is no code
path that unsuppresses automatically; ``owner_authorized_unsuppress`` is the
only way to lift a suppression and it requires a non-empty ``authorized_by``
attribution plus a reason.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from opintel_m0.ports import Clock, IdentifierFactory

from opintel_suppression.domain import (
    OwnerUnsuppressionRecord,
    SuppressionAuthorizationError,
    SuppressionCheckOutcome,
    SuppressionCheckResult,
    SuppressionEntry,
    SuppressionKind,
    SuppressionSourceMechanism,
    domain_of,
    normalize_domain,
    normalize_email,
    suppression_event_hash,
)
from opintel_suppression.ports import SuppressionRepository


class SuppressionRegistryService:
    def __init__(
        self, repository: SuppressionRepository, clock: Clock, identifiers: IdentifierFactory
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers

    def record_address_opt_out(
        self,
        *,
        workspace_id: UUID,
        raw_email: str,
        reason: str,
        evidence_ref: str,
        opt_out_received_at: datetime | None = None,
        source_mechanism: SuppressionSourceMechanism = (
            SuppressionSourceMechanism.REPLY_BASED_OPT_OUT
        ),
    ) -> SuppressionEntry:
        """Idempotent: a duplicate opt-out for an already-active address returns
        the existing entry unchanged rather than creating a second one."""
        normalized_email = normalize_email(raw_email)
        existing = self._repository.get_active_entry(
            workspace_id, SuppressionKind.ADDRESS_SUPPRESSED, normalized_email
        )
        if existing is not None:
            return existing
        received_at = opt_out_received_at or self._clock.now()
        effective_at = received_at
        entry_hash = suppression_event_hash(
            workspace_id=workspace_id,
            kind=SuppressionKind.ADDRESS_SUPPRESSED,
            normalized_value=normalized_email,
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=received_at,
            suppression_effective_at=effective_at,
            evidence_ref=evidence_ref,
        )
        entry = SuppressionEntry(
            id=self._identifiers.new(),
            workspace_id=workspace_id,
            kind=SuppressionKind.ADDRESS_SUPPRESSED,
            normalized_value=normalized_email,
            normalized_domain=domain_of(normalized_email),
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=received_at,
            suppression_effective_at=effective_at,
            evidence_ref=evidence_ref,
            audit_event_hash=entry_hash,
            created_at=self._clock.now(),
        )
        return self._repository.add_entry(entry)

    def suppress_domain(
        self,
        *,
        workspace_id: UUID,
        raw_domain: str,
        reason: str,
        evidence_ref: str,
        source_mechanism: SuppressionSourceMechanism = (
            SuppressionSourceMechanism.MANUAL_OPERATOR_ENTRY
        ),
    ) -> SuppressionEntry:
        normalized_domain = normalize_domain(raw_domain)
        existing = self._repository.get_active_entry(
            workspace_id, SuppressionKind.DOMAIN_SUPPRESSED, normalized_domain
        )
        if existing is not None:
            return existing
        now = self._clock.now()
        entry_hash = suppression_event_hash(
            workspace_id=workspace_id,
            kind=SuppressionKind.DOMAIN_SUPPRESSED,
            normalized_value=normalized_domain,
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=now,
            suppression_effective_at=now,
            evidence_ref=evidence_ref,
        )
        entry = SuppressionEntry(
            id=self._identifiers.new(),
            workspace_id=workspace_id,
            kind=SuppressionKind.DOMAIN_SUPPRESSED,
            normalized_value=normalized_domain,
            normalized_domain=normalized_domain,
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=now,
            suppression_effective_at=now,
            evidence_ref=evidence_ref,
            audit_event_hash=entry_hash,
            created_at=now,
        )
        return self._repository.add_entry(entry)

    def check_eligibility(
        self, *, workspace_id: UUID, candidate_email: str
    ) -> SuppressionCheckResult:
        """Deterministic. Must be called immediately before any real send; no
        parameter exists to bypass or override the result."""
        normalized_email = normalize_email(candidate_email)
        normalized_domain = domain_of(normalized_email)
        checked_at = self._clock.now()

        address_hit = self._repository.get_active_entry(
            workspace_id, SuppressionKind.ADDRESS_SUPPRESSED, normalized_email
        )
        if address_hit is not None:
            return SuppressionCheckResult(
                outcome=SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED,
                candidate_email=candidate_email,
                normalized_email=normalized_email,
                normalized_domain=normalized_domain,
                matched_entry_id=address_hit.id,
                matched_kind=SuppressionKind.ADDRESS_SUPPRESSED,
                checked_at=checked_at,
            )

        domain_hit = self._repository.get_active_entry(
            workspace_id, SuppressionKind.DOMAIN_SUPPRESSED, normalized_domain
        )
        if domain_hit is not None:
            return SuppressionCheckResult(
                outcome=SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED,
                candidate_email=candidate_email,
                normalized_email=normalized_email,
                normalized_domain=normalized_domain,
                matched_entry_id=domain_hit.id,
                matched_kind=SuppressionKind.DOMAIN_SUPPRESSED,
                checked_at=checked_at,
            )

        return SuppressionCheckResult(
            outcome=SuppressionCheckOutcome.ELIGIBLE,
            candidate_email=candidate_email,
            normalized_email=normalized_email,
            normalized_domain=normalized_domain,
            matched_entry_id=None,
            matched_kind=None,
            checked_at=checked_at,
        )

    def owner_authorized_unsuppress(
        self,
        *,
        workspace_id: UUID,
        suppressed_entry_id: UUID,
        authorized_by: str,
        reason: str,
    ) -> OwnerUnsuppressionRecord:
        if not authorized_by.strip() or not reason.strip():
            raise SuppressionAuthorizationError(
                "unsuppression requires a named PROJECT_OWNER authority and a reason"
            )
        record = OwnerUnsuppressionRecord(
            id=self._identifiers.new(),
            workspace_id=workspace_id,
            suppressed_entry_id=suppressed_entry_id,
            authorized_by=authorized_by,
            reason=reason,
            created_at=self._clock.now(),
        )
        return self._repository.add_owner_unsuppression(record)
