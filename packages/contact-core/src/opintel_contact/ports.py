"""Provider-neutral M6 ports. No port exposes bulk delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from opintel_outreach.domain import OutreachBundle

from opintel_contact.domain import (
    ContactPoint,
    M6Record,
    ProofScope,
    ReplyKind,
    SenderIdentity,
    VerificationStatus,
)


class ContactRepository(Protocol):
    def initialize(self) -> None: ...
    def save(self, record: M6Record) -> None: ...
    def get(self, workspace_id: UUID, record_kind: str, record_id: UUID) -> M6Record | None: ...
    def list(self, workspace_id: UUID, record_kind: str) -> tuple[M6Record, ...]: ...


class ApprovedOutreachCatalog(Protocol):
    def get_approved(self, workspace_id: UUID, revision_id: UUID) -> OutreachBundle | None: ...


class PersonResolverPort(Protocol):
    def validate_fixture_identity(self, full_name: str, source_uri: str) -> tuple[str, str]: ...


class ContactVerifierPort(Protocol):
    def verify(
        self, contact: ContactPoint
    ) -> tuple[VerificationStatus, tuple[ProofScope, ...], tuple[str, ...], int]: ...


class ContextResolverPort(Protocol):
    def resolve(
        self, contact: ContactPoint, purpose: str
    ) -> tuple[str | None, str | None, tuple[str, ...]]: ...


class SenderVerifierPort(Protocol):
    def verify(self, sender: SenderIdentity) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeliverySubmitResult:
    accepted: bool
    status_unknown: bool
    provider_message_id: str | None
    safe_detail: str


class DeliveryProviderPort(Protocol):
    provider_name: str

    def submit_one(
        self, *, recipient: str, subject: str, body: str, idempotency_key: str
    ) -> DeliverySubmitResult: ...

    def query_status(self, provider_message_id: str) -> str: ...
    def parse_signed_fixture_event(
        self, *, event_id: str, event_type: str, body: str, signature: str
    ) -> tuple[str, str]: ...


class ReplyClassifierPort(Protocol):
    def classify(self, body: str) -> ReplyKind: ...


class FirstPartyStatementExtractorPort(Protocol):
    def extract(self, body: str) -> tuple[tuple[str, str, str], ...]: ...


class ConfidentialValueProtectorPort(Protocol):
    """Production boundary for field protection; local use is synthetic-only."""

    def protect(self, value: str) -> str: ...
    def reveal(self, protected_value: str) -> str: ...
