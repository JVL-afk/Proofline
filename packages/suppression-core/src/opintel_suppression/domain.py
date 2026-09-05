"""M6.9 deterministic suppression / opt-out registry.

Authoritative for contact eligibility. No provider/LLM output and no prior
package approval may override a suppression match (see ``gate.py``). Entries
are append-only: there is no automatic unsuppression; a later record can only
be added by explicit PROJECT_OWNER authority (``record_owner_unsuppression``),
never inferred or scheduled.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SuppressionKind(StrEnum):
    ADDRESS_SUPPRESSED = "address_suppressed"
    DOMAIN_SUPPRESSED = "domain_suppressed"


class SuppressionSourceMechanism(StrEnum):
    REPLY_BASED_OPT_OUT = "reply_based_opt_out"
    MANUAL_OPERATOR_ENTRY = "manual_operator_entry"
    OWNER_DIRECTIVE = "owner_directive"


class SuppressionCheckOutcome(StrEnum):
    ELIGIBLE = "eligible"
    DELIVERY_BLOCKED_SUPPRESSED = "delivery_blocked_suppressed"


class SuppressionError(Exception):
    code = "suppression_error"
    safe_message = "suppression-registry operation failed"


class SuppressionValidationError(SuppressionError):
    code = "invalid_input"
    safe_message = "suppression-registry input is invalid"


class SuppressionAuthorizationError(SuppressionError):
    code = "forbidden"
    safe_message = "unsuppression requires explicit PROJECT_OWNER authority"


def normalize_email(raw: str) -> str:
    value = raw.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise SuppressionValidationError(f"not a valid email address: {raw!r}")
    return value


def normalize_domain(raw: str) -> str:
    value = raw.strip().lower()
    if value.startswith("@"):
        value = value[1:]
    if not value or " " in value or "@" in value:
        raise SuppressionValidationError(f"not a valid domain: {raw!r}")
    return value


def domain_of(normalized_email: str) -> str:
    return normalized_email.rsplit("@", 1)[1]


def suppression_event_hash(
    *,
    workspace_id: UUID,
    kind: SuppressionKind,
    normalized_value: str,
    reason: str,
    source_mechanism: SuppressionSourceMechanism,
    opt_out_received_at: datetime,
    suppression_effective_at: datetime,
    evidence_ref: str,
) -> str:
    """Immutable audit hash binding every fact needed to prove the suppression."""
    payload = {
        "workspace_id": str(workspace_id),
        "kind": str(kind),
        "normalized_value": normalized_value,
        "reason": reason,
        "source_mechanism": str(source_mechanism),
        "opt_out_received_at": opt_out_received_at.isoformat(),
        "suppression_effective_at": suppression_effective_at.isoformat(),
        "evidence_ref": evidence_ref,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class SuppressionEntry:
    """One immutable suppression record. Never mutated after creation."""

    id: UUID
    workspace_id: UUID
    kind: SuppressionKind
    normalized_value: str
    """The normalized email (ADDRESS_SUPPRESSED) or domain (DOMAIN_SUPPRESSED)."""
    normalized_domain: str
    """Always populated: the domain implicated by this entry, for domain-scope
    reporting even when ``kind`` is ADDRESS_SUPPRESSED."""
    reason: str
    source_mechanism: SuppressionSourceMechanism
    opt_out_received_at: datetime
    suppression_effective_at: datetime
    evidence_ref: str
    audit_event_hash: str
    created_at: datetime


@dataclass(frozen=True)
class OwnerUnsuppressionRecord:
    """The only permitted way to lift a suppression: an explicit, attributed,
    PROJECT_OWNER-authorized event referencing the entry it lifts. Never
    created automatically, on a timer, or by inference."""

    id: UUID
    workspace_id: UUID
    suppressed_entry_id: UUID
    authorized_by: str
    reason: str
    created_at: datetime


@dataclass(frozen=True)
class SuppressionCheckResult:
    outcome: SuppressionCheckOutcome
    candidate_email: str
    normalized_email: str
    normalized_domain: str
    matched_entry_id: UUID | None
    matched_kind: SuppressionKind | None
    checked_at: datetime

    @property
    def blocked(self) -> bool:
        return self.outcome is SuppressionCheckOutcome.DELIVERY_BLOCKED_SUPPRESSED
