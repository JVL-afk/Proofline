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
    channel_suppression_key,
    domain_of,
    normalize_domain,
    normalize_email,
    normalize_opaque_key,
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

    def _suppress_generic(
        self,
        *,
        kind: SuppressionKind,
        workspace_id: UUID,
        normalized_key: str,
        reason: str,
        evidence_ref: str,
        source_mechanism: SuppressionSourceMechanism,
    ) -> SuppressionEntry:
        existing = self._repository.get_active_entry(workspace_id, kind, normalized_key)
        if existing is not None:
            return existing
        now = self._clock.now()
        entry_hash = suppression_event_hash(
            workspace_id=workspace_id,
            kind=kind,
            normalized_value=normalized_key,
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=now,
            suppression_effective_at=now,
            evidence_ref=evidence_ref,
        )
        entry = SuppressionEntry(
            id=self._identifiers.new(),
            workspace_id=workspace_id,
            kind=kind,
            normalized_value=normalized_key,
            normalized_domain="",
            reason=reason,
            source_mechanism=source_mechanism,
            opt_out_received_at=now,
            suppression_effective_at=now,
            evidence_ref=evidence_ref,
            audit_event_hash=entry_hash,
            created_at=now,
        )
        return self._repository.add_entry(entry)

    def suppress_person(
        self,
        *,
        workspace_id: UUID,
        person_key: str,
        reason: str,
        evidence_ref: str,
        source_mechanism: SuppressionSourceMechanism = (
            SuppressionSourceMechanism.MANUAL_OPERATOR_ENTRY
        ),
    ) -> SuppressionEntry:
        """M6.10 PERSON_SUPPRESSED: suppresses one person across every channel."""
        return self._suppress_generic(
            kind=SuppressionKind.PERSON_SUPPRESSED,
            workspace_id=workspace_id,
            normalized_key=normalize_opaque_key(person_key, label="person key"),
            reason=reason,
            evidence_ref=evidence_ref,
            source_mechanism=source_mechanism,
        )

    def suppress_channel(
        self,
        *,
        workspace_id: UUID,
        person_key: str,
        channel: str,
        reason: str,
        evidence_ref: str,
        source_mechanism: SuppressionSourceMechanism = (
            SuppressionSourceMechanism.MANUAL_OPERATOR_ENTRY
        ),
    ) -> SuppressionEntry:
        """M6.10 CHANNEL_SUPPRESSED: suppresses one (person, channel) pair
        only - an email opt-out never silently suppresses phone/LinkedIn too
        unless a separate PERSON_SUPPRESSED/COMPANY_SUPPRESSED entry exists."""
        return self._suppress_generic(
            kind=SuppressionKind.CHANNEL_SUPPRESSED,
            workspace_id=workspace_id,
            normalized_key=channel_suppression_key(person_key, channel),
            reason=reason,
            evidence_ref=evidence_ref,
            source_mechanism=source_mechanism,
        )

    def suppress_company(
        self,
        *,
        workspace_id: UUID,
        company_key: str,
        reason: str,
        evidence_ref: str,
        source_mechanism: SuppressionSourceMechanism = (
            SuppressionSourceMechanism.MANUAL_OPERATOR_ENTRY
        ),
    ) -> SuppressionEntry:
        """M6.10 COMPANY_SUPPRESSED: company-wide do-not-contact."""
        return self._suppress_generic(
            kind=SuppressionKind.COMPANY_SUPPRESSED,
            workspace_id=workspace_id,
            normalized_key=normalize_opaque_key(company_key, label="company key"),
            reason=reason,
            evidence_ref=evidence_ref,
            source_mechanism=source_mechanism,
        )

    def check_channel_blocked(
        self,
        *,
        workspace_id: UUID,
        person_key: str,
        company_key: str,
        channel: str,
    ) -> bool:
        """True if PERSON_SUPPRESSED, CHANNEL_SUPPRESSED (for this exact
        channel), or COMPANY_SUPPRESSED applies. Does not consult
        ADDRESS_SUPPRESSED/DOMAIN_SUPPRESSED - callers already run
        ``check_eligibility`` for the email-specific checks; this method is
        the M6.10-generic layer (section 18)."""
        person_norm = normalize_opaque_key(person_key, label="person key")
        company_norm = normalize_opaque_key(company_key, label="company key")
        if self._repository.get_active_entry(
            workspace_id, SuppressionKind.PERSON_SUPPRESSED, person_norm
        ):
            return True
        if self._repository.get_active_entry(
            workspace_id, SuppressionKind.COMPANY_SUPPRESSED, company_norm
        ):
            return True
        return (
            self._repository.get_active_entry(
                workspace_id,
                SuppressionKind.CHANNEL_SUPPRESSED,
                channel_suppression_key(person_key, channel),
            )
            is not None
        )
