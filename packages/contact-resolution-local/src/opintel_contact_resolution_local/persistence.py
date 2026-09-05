"""SQLAlchemy persistence for M6.10 contact-endpoint evidence records.

Append-only, mirroring the Stage A suppression-registry pattern
(``opintel_suppression_local.persistence``): a corrected record is a new
row, never an edit of an existing one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from opintel_contact_resolution.domain import (
    AuthorityLevel,
    Channel,
    ChannelDeliveryMode,
    ContactEndpointEvidence,
    EligibilityDisposition,
    EmailVerificationState,
    IdentityConfidence,
    LinkedInProfileState,
    RetentionClassification,
    SourceCategory,
    VerificationMethod,
)
from sqlalchemy import DateTime, String, Text, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ContactEndpointEvidenceRow(Base):
    __tablename__ = "contact_endpoint_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    person_name: Mapped[str] = mapped_column(Text)
    role_title: Mapped[str] = mapped_column(Text)
    role_evidence: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(40))
    endpoint: Mapped[str] = mapped_column(Text)
    endpoint_kind: Mapped[str] = mapped_column(String(60))
    source_category: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_match: Mapped[bool]
    company_domain_match: Mapped[bool]
    verification_method: Mapped[str] = mapped_column(String(60))
    verification_result: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_agreement_conflicts_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(20))
    legal_source_authority: Mapped[str] = mapped_column(String(40))
    channel_authority: Mapped[str] = mapped_column(String(40))
    suppression_status: Mapped[str] = mapped_column(String(20))
    retention_classification: Mapped[str] = mapped_column(String(60))
    eligibility_disposition: Mapped[str] = mapped_column(String(60))
    evidence_record_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyContactEndpointEvidenceRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("contact-resolution repository requires sqlite or postgresql+psycopg")
        self.engine = create_engine(database_url, future=True)
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(connection: object, record: object) -> None:
        del record
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def add(self, evidence: ContactEndpointEvidence) -> ContactEndpointEvidence:
        row = ContactEndpointEvidenceRow(
            id=str(evidence.id),
            company_id=str(evidence.company_id),
            person_id=str(evidence.person_id),
            person_name=evidence.person_name,
            role_title=evidence.role_title,
            role_evidence=evidence.role_evidence,
            channel=str(evidence.channel),
            endpoint=evidence.endpoint,
            endpoint_kind=evidence.endpoint_kind,
            source_category=str(evidence.source_category),
            provider=evidence.provider,
            source_url=evidence.source_url,
            observed_at=_aware(evidence.observed_at),
            source_evidence_sha256=evidence.source_evidence_sha256,
            identity_match=evidence.identity_match,
            company_domain_match=evidence.company_domain_match,
            verification_method=str(evidence.verification_method),
            verification_result=str(evidence.verification_result)
            if evidence.verification_result
            else None,
            source_agreement_conflicts_json=json.dumps(list(evidence.source_agreement_conflicts)),
            confidence=str(evidence.confidence),
            legal_source_authority=str(evidence.legal_source_authority),
            channel_authority=str(evidence.channel_authority),
            suppression_status=evidence.suppression_status,
            retention_classification=str(evidence.retention_classification),
            eligibility_disposition=str(evidence.eligibility_disposition),
            evidence_record_hash=evidence.evidence_record_hash,
            created_at=_aware(evidence.observed_at),
        )
        with self._sessions.begin() as session:
            session.add(row)
        return evidence

    def list_for_person(self, person_id: UUID) -> tuple[ContactEndpointEvidence, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ContactEndpointEvidenceRow)
                .where(ContactEndpointEvidenceRow.person_id == str(person_id))
                .order_by(ContactEndpointEvidenceRow.created_at)
            ).all()
            return tuple(_evidence(row) for row in rows)

    def purge_expired(self, *, retention_days: int, now: datetime) -> int:
        """Section 13: deletes ContactEndpointEvidence rows older than
        ``retention_days``, unconditionally - including rows for a
        suppressed person. This is safe because suppression enforcement
        lives entirely in the separate, permanent ``opintel_suppression``
        registry (an irreversible, hash-keyed, never-purged store) - purging
        this evidence table never lifts a suppression. Returns the number of
        rows deleted."""
        cutoff = _aware(now) - timedelta(days=retention_days)
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ContactEndpointEvidenceRow).where(
                    ContactEndpointEvidenceRow.observed_at < cutoff
                )
            ).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            return count

    def delete_for_person(self, person_id: UUID) -> int:
        """Immediate deletion (section 14: DELETE_MY_INFORMATION requests),
        independent of retention age. Returns the number of rows deleted."""
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ContactEndpointEvidenceRow).where(
                    ContactEndpointEvidenceRow.person_id == str(person_id)
                )
            ).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            return count


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _parse_verification_result(
    value: str | None,
) -> EmailVerificationState | LinkedInProfileState | None:
    if value is None:
        return None
    try:
        return EmailVerificationState(value)
    except ValueError:
        return LinkedInProfileState(value)


def _evidence(row: ContactEndpointEvidenceRow) -> ContactEndpointEvidence:
    return ContactEndpointEvidence(
        id=UUID(row.id),
        company_id=UUID(row.company_id),
        person_id=UUID(row.person_id),
        person_name=row.person_name,
        role_title=row.role_title,
        role_evidence=row.role_evidence,
        channel=Channel(row.channel),
        endpoint=row.endpoint,
        endpoint_kind=row.endpoint_kind,
        source_category=SourceCategory(row.source_category),
        provider=row.provider,
        source_url=row.source_url,
        observed_at=_aware(row.observed_at),
        source_evidence_sha256=row.source_evidence_sha256,
        identity_match=row.identity_match,
        company_domain_match=row.company_domain_match,
        verification_method=VerificationMethod(row.verification_method),
        verification_result=_parse_verification_result(row.verification_result),
        source_agreement_conflicts=tuple(json.loads(row.source_agreement_conflicts_json)),
        confidence=IdentityConfidence(row.confidence),
        legal_source_authority=AuthorityLevel(row.legal_source_authority),
        channel_authority=ChannelDeliveryMode(row.channel_authority),
        suppression_status=row.suppression_status,
        retention_classification=RetentionClassification(row.retention_classification),
        eligibility_disposition=EligibilityDisposition(row.eligibility_disposition),
    )
