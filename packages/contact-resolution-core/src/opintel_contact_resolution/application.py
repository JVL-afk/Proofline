"""M6.10 deterministic pipeline: role ranking, source reconciliation,
verification-threshold gating, legal/source authority gating, privacy
minimization, and endpoint-evidence assembly.

QUALIFIED_COMPANY -> OPPORTUNITY_CONTEXT -> ROLE_REQUIREMENTS ->
PERSON_DISCOVERY -> PERSON_IDENTITY_RECONCILIATION -> ROLE_RANKING ->
CHANNEL_DISCOVERY -> ENDPOINT_CANDIDATES -> SOURCE_RECONCILIATION ->
ENDPOINT_VERIFICATION -> LEGAL_POLICY_GATE -> SUPPRESSION/DNC ->
CHANNEL_RANKING -> RECIPIENT_AND_CHANNEL_PLAN

Every gate here is deterministic and evidence-bound (section 2/20): nothing
in this module calls a provider adapter without first confirming authority,
and nothing here lets a plausible/discovered value become eligible without
passing through the matching verification threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from opintel_contact_resolution.domain import (
    CHANNEL_DELIVERY_MODE,
    FIRST_PARTY_CATEGORIES,
    ROLE_TIER_ORDER,
    AuthorityDomain,
    AuthorityLevel,
    Channel,
    ChannelDeliveryMode,
    ContactEndpointEvidence,
    EligibilityDisposition,
    EmailKind,
    EmailVerificationState,
    IdentityConfidence,
    LinkedInProfileState,
    PersonCandidate,
    PhoneKind,
    PhoneReachability,
    ResolutionAuthorityError,
    RetentionClassification,
    SourceAuthorityMatrix,
    SourceCategory,
    VerificationMethod,
    verification_meets_threshold,
)

# --------------------------------------------------------------------------
# Configuration (sections 22, 25)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ContactSourcePolicySettings:
    """Per-domain policy for one :class:`SourceCategory`. Fail-closed
    defaults: a category with no explicit settings is treated as not
    allowed, no field may be retained, and no corroboration is possible."""

    allowed: bool = False
    retainable_fields: frozenset[str] = frozenset()
    allowed_purpose: str = "professional_business_recipient_identification"
    retention_period_days: int | None = None
    required_verification: EmailVerificationState = EmailVerificationState.MULTI_SOURCE_VERIFIED
    source_alone_sufficient: bool = False
    corroboration_required: bool = True
    pattern_derived_email_permitted: bool = False
    direct_phone_permitted: bool = False
    linkedin_profile_discovery_permitted: bool = False


DEFAULT_SOURCE_POLICY: dict[SourceCategory, ContactSourcePolicySettings] = {
    SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT: ContactSourcePolicySettings(
        allowed=True,
        retainable_fields=frozenset({"name", "role", "endpoint"}),
        required_verification=EmailVerificationState.SOURCE_VERIFIED,
        source_alone_sufficient=True,
        corroboration_required=False,
    ),
    SourceCategory.FIRST_PARTY_PERSON_ROLE: ContactSourcePolicySettings(
        allowed=True,
        retainable_fields=frozenset({"name", "role"}),
        source_alone_sufficient=True,
        corroboration_required=False,
    ),
    SourceCategory.FIRST_PARTY_ROLE_MAILBOX: ContactSourcePolicySettings(
        allowed=True,
        retainable_fields=frozenset({"role", "endpoint"}),
        required_verification=EmailVerificationState.SOURCE_VERIFIED,
        source_alone_sufficient=True,
        corroboration_required=False,
    ),
    # Everything else (directories, enrichment, verification services,
    # pattern-derived, search-discovery-only, unauthorized) is NOT_AUTHORIZED
    # / not allowed until a future ContactSourcePolicySettings entry and a
    # matching AuthorityDomain grant are both explicitly added.
}


@dataclass(frozen=True)
class CostBudget:
    """Section 25. All bounded; a pipeline run that would exceed any of
    these stops early rather than querying "because the adapter exists."""

    max_candidate_people_per_company: int = 5
    max_providers_queried: int = 0
    """0 in this milestone: no live third-party provider is authorized."""
    max_queries_per_person: int = 3
    max_paid_cost_usd: float = 0.0
    stop_once_eligible_recipient_found: bool = True


DEFAULT_COST_BUDGET = CostBudget()


# --------------------------------------------------------------------------
# Role ranking (section 4)
# --------------------------------------------------------------------------


def rank_person_candidates(
    candidates: tuple[PersonCandidate, ...],
) -> tuple[PersonCandidate, ...]:
    """Deterministic: role tier first (owner/president highest), then
    first-party status, then identity confidence. Never delegates the
    ordering decision to an LLM (section 4/20)."""

    def _key(c: PersonCandidate) -> tuple[int, int, int]:
        tier_rank = ROLE_TIER_ORDER.index(c.role_tier)
        first_party_rank = 0 if c.first_party else 1
        confidence_rank = {
            IdentityConfidence.HIGH: 0,
            IdentityConfidence.MEDIUM: 1,
            IdentityConfidence.LOW: 2,
            IdentityConfidence.CONFLICTED: 3,
        }[c.identity_confidence]
        return (tier_rank, first_party_rank, confidence_rank)

    return tuple(sorted(candidates, key=_key))


# --------------------------------------------------------------------------
# Legal / source authority gate (sections 6, 21)
# --------------------------------------------------------------------------


def require_authority(matrix: SourceAuthorityMatrix, domain: AuthorityDomain) -> AuthorityLevel:
    """Raises if the domain is NOT_AUTHORIZED. Callers use this before any
    provider query and before treating a source category's output as usable
    beyond CONTACT_SOURCE_NOT_AUTHORIZED discovery-only status."""
    level = matrix.level(domain)
    if level is AuthorityLevel.NOT_AUTHORIZED:
        raise ResolutionAuthorityError(f"{domain} is NOT_AUTHORIZED")
    return level


_AUTHORITY_FOR_SOURCE: dict[SourceCategory, AuthorityDomain] = {
    SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY: (
        AuthorityDomain.PROFESSIONAL_DIRECTORY_AUTHORITY
    ),
    SourceCategory.APPROVED_CONTACT_ENRICHMENT: AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY,
    SourceCategory.APPROVED_CONTACT_VERIFICATION: AuthorityDomain.EMAIL_VERIFICATION_AUTHORITY,
    SourceCategory.APPROVED_PROFESSIONAL_PROFILE: (
        AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY
    ),
}


def source_category_authority_level(
    matrix: SourceAuthorityMatrix, category: SourceCategory
) -> AuthorityLevel:
    if category in FIRST_PARTY_CATEGORIES:
        return AuthorityLevel.AUTHORIZED
    domain = _AUTHORITY_FOR_SOURCE.get(category)
    if domain is None:
        # PATTERN_DERIVED / SEARCH_DISCOVERY_ONLY / MULTI_SOURCE_CORROBORATED /
        # UNAUTHORIZED_SOURCE never carry independent query authority; they
        # are discovery-shaped labels, not a queryable third-party channel.
        return AuthorityLevel.NOT_AUTHORIZED
    return matrix.level(domain)


# --------------------------------------------------------------------------
# Privacy minimization (section 14)
# --------------------------------------------------------------------------


_DURABLE_FIELD_ALLOWLIST = frozenset(
    {"name", "role", "endpoint", "channel", "source", "verification_result", "eligibility"}
)


def minimize_raw_result(raw_fields: dict[str, str]) -> dict[str, str]:
    """EPHEMERAL_RAW_RESULT -> DETERMINISTIC_CONTACT_MINIMIZATION ->
    DURABLE_MINIMIZED_CONTACT_EVIDENCE. Strips anything not in the durable
    allowlist (personal email/phone/home-address/birthdate/family/social
    content/consumer data/unrelated attributes never pass through)."""
    return {k: v for k, v in raw_fields.items() if k in _DURABLE_FIELD_ALLOWLIST}


# --------------------------------------------------------------------------
# Email eligibility (sections 7, 8)
# --------------------------------------------------------------------------


def email_kind_for_source(category: SourceCategory) -> EmailKind | None:
    if category is SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT:
        return EmailKind.FIRST_PARTY_PUBLISHED_EMAIL
    if category is SourceCategory.FIRST_PARTY_ROLE_MAILBOX:
        return EmailKind.ROLE_MAILBOX
    if category is SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY:
        return EmailKind.THIRD_PARTY_PROFESSIONAL_EMAIL
    if category is SourceCategory.MULTI_SOURCE_CORROBORATED:
        return EmailKind.MULTI_SOURCE_EMAIL
    if category is SourceCategory.PATTERN_DERIVED:
        return EmailKind.PATTERN_DERIVED_EMAIL
    return None


def evaluate_email_eligibility(
    *,
    email_kind: EmailKind,
    source_category: SourceCategory,
    verification_state: EmailVerificationState,
    identity_match: bool,
    company_domain_match: bool,
    role_eligible: bool,
    matrix: SourceAuthorityMatrix,
    policy: dict[SourceCategory, ContactSourcePolicySettings],
    suppressed: bool,
) -> EligibilityDisposition:
    """Section 8's exact requirement list, applied in order. A
    PATTERN_DERIVED_EMAIL is rejected before any other check runs -
    section 7's "never eligible by itself" is absolute, not merely
    lowest-priority."""
    if email_kind is EmailKind.PATTERN_DERIVED_EMAIL:
        settings = policy.get(source_category)
        if settings is None or not settings.pattern_derived_email_permitted:
            return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
        # Even when policy permits pattern-derived candidates, they still
        # need independent verification through an authorized method - a
        # bare pattern match is never itself sufficient (section 7).
        if verification_state not in (
            EmailVerificationState.MULTI_SOURCE_VERIFIED,
            EmailVerificationState.SOURCE_VERIFIED,
        ):
            return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE

    if suppressed:
        return EligibilityDisposition.SUPPRESSED

    authority = source_category_authority_level(matrix, source_category)
    if authority is AuthorityLevel.NOT_AUTHORIZED:
        return EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED

    if not company_domain_match:
        return EligibilityDisposition.DOMAIN_MISMATCH
    if not identity_match:
        return EligibilityDisposition.IDENTITY_CONFLICT
    if not role_eligible:
        return EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED

    settings = policy.get(source_category, ContactSourcePolicySettings())
    if not verification_meets_threshold(verification_state, settings.required_verification):
        return EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED

    return EligibilityDisposition.ELIGIBLE_VERIFIED_RECIPIENT


# --------------------------------------------------------------------------
# LinkedIn eligibility (section 9)
# --------------------------------------------------------------------------


def evaluate_linkedin_eligibility(
    *,
    profile_state: LinkedInProfileState,
    matrix: SourceAuthorityMatrix,
    suppressed: bool,
) -> tuple[EligibilityDisposition, ChannelDeliveryMode]:
    if suppressed:
        return EligibilityDisposition.SUPPRESSED, ChannelDeliveryMode.NOT_AUTHORIZED
    authority = matrix.level(AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY)
    if authority is AuthorityLevel.NOT_AUTHORIZED:
        return (
            EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED,
            ChannelDeliveryMode.NOT_AUTHORIZED,
        )
    if profile_state is LinkedInProfileState.LINKEDIN_PROFILE_UNVERIFIED:
        return (
            EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED,
            ChannelDeliveryMode.MANUAL_HUMAN_ONLY,
        )
    # VERIFIED and PROBABLE both recommend the channel for a later,
    # separately-reviewed manual message; PROBABLE is disclosed, not upgraded.
    return (
        EligibilityDisposition.ELIGIBLE_MANUAL_CHANNEL,
        ChannelDeliveryMode.MANUAL_HUMAN_ONLY,
    )


# --------------------------------------------------------------------------
# Phone eligibility (sections 10, 11)
# --------------------------------------------------------------------------


def evaluate_phone_eligibility(
    *,
    phone_kind: PhoneKind,
    reachability: PhoneReachability,
    verified: bool,
    matrix: SourceAuthorityMatrix,
    suppressed: bool,
) -> EligibilityDisposition:
    if suppressed:
        return EligibilityDisposition.SUPPRESSED
    if phone_kind is PhoneKind.MAIN_BUSINESS_PHONE:
        # First-party main lines need no third-party authority.
        if not verified:
            return EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED
        return EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT
    authority = matrix.level(AuthorityDomain.PHONE_CONTACT_DATA_AUTHORITY)
    if authority is AuthorityLevel.NOT_AUTHORIZED:
        return EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED
    if not verified:
        return EligibilityDisposition.CONTACT_CANDIDATE_UNVERIFIED
    if reachability is PhoneReachability.DIRECT:
        return EligibilityDisposition.ELIGIBLE_HUMAN_CALL_DIRECT
    return EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT


# --------------------------------------------------------------------------
# Suppression bridge (section 18) - kept as a thin adapter so this package
# has no hard dependency on any one suppression backend; the M6.9 pilot
# wires this to opintel_suppression.SuppressionRegistryService.
# --------------------------------------------------------------------------


class SuppressionCheck(Protocol):
    """Given a candidate endpoint, returns whether ANY applicable
    suppression (address/domain/person/channel/company DNC) blocks it."""

    def __call__(self, *, channel: Channel, endpoint: str) -> bool: ...


def no_suppression(*, channel: Channel, endpoint: str) -> bool:
    del channel, endpoint
    return False


# --------------------------------------------------------------------------
# Endpoint evidence assembly
# --------------------------------------------------------------------------


def build_endpoint_evidence(
    *,
    id_: UUID,
    person: PersonCandidate,
    channel: Channel,
    endpoint: str,
    endpoint_kind: str,
    source_category: SourceCategory,
    provider: str,
    source_url: str | None,
    observed_at: datetime,
    source_evidence_sha256: str | None,
    identity_match: bool,
    company_domain_match: bool,
    verification_method: VerificationMethod,
    verification_result: EmailVerificationState | LinkedInProfileState | None,
    matrix: SourceAuthorityMatrix,
    eligibility_disposition: EligibilityDisposition,
    suppressed: bool,
    source_agreement_conflicts: tuple[str, ...] = (),
) -> ContactEndpointEvidence:
    retention = (
        RetentionClassification.EPHEMERAL_ONLY_NOT_RETAINED
        if eligibility_disposition is EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED
        else RetentionClassification.DURABLE_MINIMIZED_CONTACT_EVIDENCE
    )
    authority_for_category = source_category_authority_level(matrix, source_category)
    return ContactEndpointEvidence(
        id=id_,
        company_id=person.company_id,
        person_id=person.id,
        person_name=person.full_name,
        role_title=person.role_title_as_stated,
        role_evidence=person.role_evidence,
        channel=channel,
        endpoint=endpoint,
        endpoint_kind=endpoint_kind,
        source_category=source_category,
        provider=provider,
        source_url=source_url,
        observed_at=observed_at,
        source_evidence_sha256=source_evidence_sha256,
        identity_match=identity_match,
        company_domain_match=company_domain_match,
        verification_method=verification_method,
        verification_result=verification_result,
        source_agreement_conflicts=source_agreement_conflicts,
        confidence=person.identity_confidence,
        legal_source_authority=authority_for_category,
        channel_authority=CHANNEL_DELIVERY_MODE[channel],
        suppression_status="suppressed" if suppressed else "clear",
        retention_classification=retention,
        eligibility_disposition=eligibility_disposition,
    )
