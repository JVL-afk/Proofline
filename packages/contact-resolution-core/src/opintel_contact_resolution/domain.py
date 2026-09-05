"""M6.10 recipient & channel resolution: domain model.

Core truth invariant, enforced structurally throughout this module and its
application layer, never by an LLM:

    DISCOVERED != VERIFIED
    PLAUSIBLE != TRUE
    VERIFIED != LEGALLY_AUTHORIZED
    AUTHORIZED_CHANNEL != AUTHORIZED_SEND
    UNKNOWN stays UNKNOWN.

No field in this module lets an "AI recommendation" or "confidence score"
promote a discovered/plausible/pattern-derived value directly to eligible.
Every eligibility disposition in :class:`EligibilityState` is reached only
through the deterministic gates in ``application.py`` and ``ranking.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

# --------------------------------------------------------------------------
# Channels (section 15)
# --------------------------------------------------------------------------


class Channel(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    SMS = "sms"
    AUTONOMOUS_VOICE = "autonomous_voice"


class ChannelDeliveryMode(StrEnum):
    """What executing this channel is allowed to look like, independent of
    whether an eligible endpoint has been resolved for it."""

    EXISTING_M6_M69_CONTROLS = "existing_m6_m69_controls"
    """Delivery remains gated by the existing M6/M6.9 approval path (email)."""
    MANUAL_HUMAN_ONLY = "manual_human_only"
    HUMAN_CALL_ONLY = "human_call_only"
    NOT_AUTHORIZED = "not_authorized"


CHANNEL_DELIVERY_MODE: dict[Channel, ChannelDeliveryMode] = {
    Channel.EMAIL: ChannelDeliveryMode.EXISTING_M6_M69_CONTROLS,
    Channel.LINKEDIN: ChannelDeliveryMode.MANUAL_HUMAN_ONLY,
    Channel.PHONE: ChannelDeliveryMode.HUMAN_CALL_ONLY,
    Channel.SMS: ChannelDeliveryMode.NOT_AUTHORIZED,
    Channel.AUTONOMOUS_VOICE: ChannelDeliveryMode.NOT_AUTHORIZED,
}
"""M6.10 never overrides this table. Resolving an endpoint for SMS or
AUTONOMOUS_VOICE is meaningless here - those channels are not implemented at
all (section 10/15), not merely gated."""


# --------------------------------------------------------------------------
# Source taxonomy (section 5)
# --------------------------------------------------------------------------


class SourceCategory(StrEnum):
    """A policy class - what KIND of source this is, never which specific
    provider. A category is a precondition for querying; a provider is an
    implementation detail behind a :class:`ports.SourceProviderPort`."""

    FIRST_PARTY_EXPLICIT_CONTACT = "first_party_explicit_contact"
    FIRST_PARTY_PERSON_ROLE = "first_party_person_role"
    FIRST_PARTY_ROLE_MAILBOX = "first_party_role_mailbox"
    APPROVED_PROFESSIONAL_DIRECTORY = "approved_professional_directory"
    APPROVED_PROFESSIONAL_PROFILE = "approved_professional_profile"
    APPROVED_CONTACT_ENRICHMENT = "approved_contact_enrichment"
    APPROVED_CONTACT_VERIFICATION = "approved_contact_verification"
    MULTI_SOURCE_CORROBORATED = "multi_source_corroborated"
    PATTERN_DERIVED = "pattern_derived"
    SEARCH_DISCOVERY_ONLY = "search_discovery_only"
    UNAUTHORIZED_SOURCE = "unauthorized_source"


FIRST_PARTY_CATEGORIES: frozenset[SourceCategory] = frozenset(
    {
        SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        SourceCategory.FIRST_PARTY_PERSON_ROLE,
        SourceCategory.FIRST_PARTY_ROLE_MAILBOX,
    }
)


# --------------------------------------------------------------------------
# Legal / source authority (section 6, 22)
# --------------------------------------------------------------------------


class AuthorityLevel(StrEnum):
    NOT_AUTHORIZED = "not_authorized"
    AUTHORIZED_WITH_CONTROLS = "authorized_with_controls"
    AUTHORIZED = "authorized"


class AuthorityDomain(StrEnum):
    THIRD_PARTY_CONTACT_SOURCE_AUTHORITY = "third_party_contact_source_authority"
    PROFESSIONAL_DIRECTORY_AUTHORITY = "professional_directory_authority"
    CONTACT_ENRICHMENT_AUTHORITY = "contact_enrichment_authority"
    EMAIL_VERIFICATION_AUTHORITY = "email_verification_authority"
    LINKEDIN_PROFILE_DISCOVERY_AUTHORITY = "linkedin_profile_discovery_authority"
    PHONE_CONTACT_DATA_AUTHORITY = "phone_contact_data_authority"


@dataclass(frozen=True)
class SourceAuthorityMatrix:
    """Fail-closed: every domain defaults to NOT_AUTHORIZED. Constructing an
    instance with anything else requires an explicit, named override -
    nothing here defaults open."""

    levels: dict[AuthorityDomain, AuthorityLevel] = field(
        default_factory=lambda: dict.fromkeys(AuthorityDomain, AuthorityLevel.NOT_AUTHORIZED)
    )

    def level(self, domain: AuthorityDomain) -> AuthorityLevel:
        return self.levels.get(domain, AuthorityLevel.NOT_AUTHORIZED)

    def permits_query(self, domain: AuthorityDomain) -> bool:
        return self.level(domain) is not AuthorityLevel.NOT_AUTHORIZED


DEFAULT_AUTHORITY_MATRIX = SourceAuthorityMatrix()
"""Every M6.10 pipeline run must pass an explicit matrix or use this one -
never an implicit "authorized" default anywhere in this codebase."""


# --------------------------------------------------------------------------
# Person / role resolution (section 4)
# --------------------------------------------------------------------------


class RoleTier(StrEnum):
    """The opportunity-sensitive hierarchy, reused from the M6.9 pilot
    (commercial HVAC inbound intake), ordered highest-preference first."""

    OWNER_PRESIDENT = "owner_president"
    GENERAL_MANAGER = "general_manager"
    OPERATIONS_LEADERSHIP = "operations_leadership"
    SERVICE_LEADERSHIP = "service_leadership"
    COMMERCIAL_SERVICE_LEADERSHIP = "commercial_service_leadership"
    DISPATCH_CUSTOMER_SERVICE_LEADERSHIP = "dispatch_customer_service_leadership"
    SALES_LEADERSHIP = "sales_leadership"
    UNRANKED = "unranked"


ROLE_TIER_ORDER: tuple[RoleTier, ...] = (
    RoleTier.OWNER_PRESIDENT,
    RoleTier.GENERAL_MANAGER,
    RoleTier.OPERATIONS_LEADERSHIP,
    RoleTier.SERVICE_LEADERSHIP,
    RoleTier.COMMERCIAL_SERVICE_LEADERSHIP,
    RoleTier.DISPATCH_CUSTOMER_SERVICE_LEADERSHIP,
    RoleTier.SALES_LEADERSHIP,
    RoleTier.UNRANKED,
)


class IdentityConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class PersonCandidate:
    """One candidate decision-maker. Never mutated - a corrected or
    re-evaluated candidate is a new record referencing the old one."""

    id: UUID
    company_id: UUID
    full_name: str
    role_title_as_stated: str
    role_tier: RoleTier
    role_evidence: str
    """The exact quoted/observed text this role classification rests on."""
    source_category: SourceCategory
    source_url: str | None
    source_content_sha256: str | None
    observed_at: datetime
    first_party: bool
    identity_confidence: IdentityConfidence
    conflicting_evidence: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Endpoint candidates and verification (sections 7, 8, 12)
# --------------------------------------------------------------------------


class EmailKind(StrEnum):
    FIRST_PARTY_PUBLISHED_EMAIL = "first_party_published_email"
    ROLE_MAILBOX = "role_mailbox"
    THIRD_PARTY_PROFESSIONAL_EMAIL = "third_party_professional_email"
    MULTI_SOURCE_EMAIL = "multi_source_email"
    PATTERN_DERIVED_EMAIL = "pattern_derived_email"


class EmailVerificationState(StrEnum):
    SOURCE_VERIFIED = "source_verified"
    MULTI_SOURCE_VERIFIED = "multi_source_verified"
    MAILBOX_VERIFIED = "mailbox_verified"
    DOMAIN_ONLY_VERIFIED = "domain_only_verified"
    SYNTAX_ONLY = "syntax_only"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"


_VERIFICATION_RANK: dict[EmailVerificationState, int] = {
    EmailVerificationState.CONFLICTED: -1,
    EmailVerificationState.UNVERIFIED: 0,
    EmailVerificationState.SYNTAX_ONLY: 1,
    EmailVerificationState.DOMAIN_ONLY_VERIFIED: 2,
    EmailVerificationState.MAILBOX_VERIFIED: 3,
    EmailVerificationState.SOURCE_VERIFIED: 4,
    EmailVerificationState.MULTI_SOURCE_VERIFIED: 5,
}


def verification_meets_threshold(
    actual: EmailVerificationState, required: EmailVerificationState
) -> bool:
    return _VERIFICATION_RANK[actual] >= _VERIFICATION_RANK[required]


class LinkedInProfileState(StrEnum):
    LINKEDIN_PROFILE_VERIFIED = "linkedin_profile_verified"
    LINKEDIN_PROFILE_PROBABLE = "linkedin_profile_probable"
    LINKEDIN_PROFILE_UNVERIFIED = "linkedin_profile_unverified"


class LinkedInChannelState(StrEnum):
    LINKEDIN_CHANNEL_ELIGIBLE_MANUAL = "linkedin_channel_eligible_manual"
    LINKEDIN_CHANNEL_NOT_AUTHORIZED = "linkedin_channel_not_authorized"


class PhoneKind(StrEnum):
    MAIN_BUSINESS_PHONE = "main_business_phone"
    DEPARTMENT_PHONE = "department_phone"
    DIRECT_BUSINESS_PHONE = "direct_business_phone"


class PhoneReachability(StrEnum):
    DIRECT = "direct"
    """Rings the specific person."""
    INDIRECT = "indirect"
    """Rings the company/department; reaching the person needs a human step."""


class PhoneChannelState(StrEnum):
    PHONE_HUMAN_CALL_ELIGIBLE = "phone_human_call_eligible"
    PHONE_NOT_AUTHORIZED = "phone_not_authorized"


class VerificationMethod(StrEnum):
    FIRST_PARTY_PAGE_OBSERVATION = "first_party_page_observation"
    MULTI_SOURCE_CORROBORATION = "multi_source_corroboration"
    APPROVED_THIRD_PARTY_VERIFICATION_SERVICE = "approved_third_party_verification_service"
    NONE = "none"


class RetentionClassification(StrEnum):
    DURABLE_MINIMIZED_CONTACT_EVIDENCE = "durable_minimized_contact_evidence"
    EPHEMERAL_ONLY_NOT_RETAINED = "ephemeral_only_not_retained"


# --------------------------------------------------------------------------
# Eligibility (section 13)
# --------------------------------------------------------------------------


class EligibilityDisposition(StrEnum):
    ELIGIBLE_VERIFIED_RECIPIENT = "eligible_verified_recipient"
    IDENTITY_VERIFIED_CONTACT_UNRESOLVED = "identity_verified_contact_unresolved"
    CONTACT_CANDIDATE_UNVERIFIED = "contact_candidate_unverified"
    PATTERN_ONLY_NOT_ELIGIBLE = "pattern_only_not_eligible"
    CONTACT_SOURCE_NOT_AUTHORIZED = "contact_source_not_authorized"
    CHANNEL_NOT_AUTHORIZED = "channel_not_authorized"
    IDENTITY_CONFLICT = "identity_conflict"
    CONTACT_SOURCE_CONFLICT = "contact_source_conflict"
    DOMAIN_MISMATCH = "domain_mismatch"
    SUPPRESSED = "suppressed"
    DO_NOT_CONTACT = "do_not_contact"
    NO_ELIGIBLE_VERIFIED_RECIPIENT = "no_eligible_verified_recipient"
    ELIGIBLE_MANUAL_CHANNEL = "eligible_manual_channel"
    """LinkedIn: identity/profile confidence is sufficient to recommend the
    channel for a later, separately-reviewed human message - not itself an
    authorization to send anything."""
    ELIGIBLE_HUMAN_CALL_INDIRECT = "eligible_human_call_indirect"
    ELIGIBLE_HUMAN_CALL_DIRECT = "eligible_human_call_direct"


BLOCKING_DISPOSITIONS: frozenset[EligibilityDisposition] = frozenset(
    {
        EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED,
        EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE,
        EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED,
        EligibilityDisposition.CHANNEL_NOT_AUTHORIZED,
        EligibilityDisposition.IDENTITY_CONFLICT,
        EligibilityDisposition.CONTACT_SOURCE_CONFLICT,
        EligibilityDisposition.DOMAIN_MISMATCH,
        EligibilityDisposition.SUPPRESSED,
        EligibilityDisposition.DO_NOT_CONTACT,
        EligibilityDisposition.NO_ELIGIBLE_VERIFIED_RECIPIENT,
        EligibilityDisposition.IDENTITY_VERIFIED_CONTACT_UNRESOLVED,
    }
)
"""Dispositions that mean 'do not use this endpoint for the delivery channel
this record's channel authorization would otherwise apply to.' Hard
blockers (section 16): always override a ranking score, unconditionally."""


@dataclass(frozen=True)
class ContactEndpointEvidence:
    """The authoritative machine-readable record for one candidate endpoint
    (section 12). Immutable: a corrected record is a new one, never an edit."""

    id: UUID
    company_id: UUID
    person_id: UUID
    person_name: str
    role_title: str
    role_evidence: str
    channel: Channel
    endpoint: str
    """The redacted/normalized form for anything durably retained (section 14) -
    callers must not put a full personal email/phone here if
    ``retention_classification`` is EPHEMERAL_ONLY_NOT_RETAINED."""
    endpoint_kind: str
    """EmailKind / PhoneKind / 'linkedin_profile_url' value, as a string so
    this one record type serves every channel."""
    source_category: SourceCategory
    provider: str
    """Free-text adapter/provider name - e.g. 'aplusac.com (first party)'.
    Never a business-logic branch target; see ports.py."""
    source_url: str | None
    observed_at: datetime
    source_evidence_sha256: str | None
    identity_match: bool
    company_domain_match: bool
    verification_method: VerificationMethod
    verification_result: EmailVerificationState | LinkedInProfileState | None
    source_agreement_conflicts: tuple[str, ...]
    confidence: IdentityConfidence
    legal_source_authority: AuthorityLevel
    channel_authority: ChannelDeliveryMode
    suppression_status: str
    retention_classification: RetentionClassification
    eligibility_disposition: EligibilityDisposition

    @property
    def evidence_record_hash(self) -> str:
        payload = {
            "company_id": str(self.company_id),
            "person_id": str(self.person_id),
            "person_name": self.person_name,
            "role_title": self.role_title,
            "channel": str(self.channel),
            "endpoint": self.endpoint,
            "endpoint_kind": self.endpoint_kind,
            "source_category": str(self.source_category),
            "provider": self.provider,
            "source_url": self.source_url,
            "observed_at": self.observed_at.isoformat(),
            "source_evidence_sha256": self.source_evidence_sha256,
            "identity_match": self.identity_match,
            "company_domain_match": self.company_domain_match,
            "verification_method": str(self.verification_method),
            "verification_result": str(self.verification_result)
            if self.verification_result
            else None,
            "eligibility_disposition": str(self.eligibility_disposition),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class ResolutionError(Exception):
    code = "resolution_error"
    safe_message = "recipient/channel resolution operation failed"


class ResolutionValidationError(ResolutionError):
    code = "invalid_input"


class ResolutionAuthorityError(ResolutionError):
    code = "forbidden"
    safe_message = "source or channel authority does not permit this operation"
