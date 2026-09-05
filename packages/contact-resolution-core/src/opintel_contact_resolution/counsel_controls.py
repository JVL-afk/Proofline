"""M6.10 counsel-directed operational controls.

Owner authorization "M6.10 LEGAL SOURCE ACTIVATION + LIVE A-PLUS RECIPIENT
RESOLUTION" (2026-09-06). Texas counsel returned all eight decision fields
as ``APPROVED_WITH_CONTROLS`` - never collapsed to a bare ``AUTHORIZED``
here; every control below is recorded as the exact counsel-directed
restriction, not an internally derived legal conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from opintel_contact_resolution.domain import (
    AuthorityDomain,
    AuthorityLevel,
    EligibilityDisposition,
    PhoneKind,
    SourceAuthorityMatrix,
    SourceCategory,
)

# --------------------------------------------------------------------------
# 1. Counsel authority matrix (section 1)
# --------------------------------------------------------------------------

COUNSEL_APPROVED_DOMAINS: frozenset[AuthorityDomain] = frozenset(
    {
        AuthorityDomain.PROFESSIONAL_DIRECTORY_AUTHORITY,
        AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY,
        AuthorityDomain.EMAIL_VERIFICATION_AUTHORITY,
        AuthorityDomain.LINKEDIN_PROFILE_DISCOVERY_AUTHORITY,
        AuthorityDomain.PHONE_CONTACT_DATA_AUTHORITY,
    }
)
"""The five AuthorityDomain values counsel's eight decision fields map onto
(PATTERN_DERIVED_BUT_INDEPENDENTLY_VERIFIED_EMAIL_USE and RETENTION_CONTROLS
are policy, not a query-gate domain; DIRECT_BUSINESS_PHONE_RESOLUTION shares
PHONE_CONTACT_DATA_AUTHORITY with BUSINESS_PHONE_RESOLUTION, both counsel
fields answered identically)."""


def counsel_controlled_authority_matrix() -> SourceAuthorityMatrix:
    """Every counsel-approved domain -> AUTHORIZED_WITH_CONTROLS, explicitly
    - never the bare AUTHORIZED. ``THIRD_PARTY_CONTACT_SOURCE_AUTHORITY``
    (the umbrella gate) is raised too, since every category it gates now has
    its own specific control; ``PHONE_OUTBOUND_EXECUTION_AUTHORITY`` is
    deliberately left NOT_AUTHORIZED - counsel authorized phone *resolution*
    only, pending a separate Texas telemarketing review (section 11)."""
    levels = dict.fromkeys(AuthorityDomain, AuthorityLevel.NOT_AUTHORIZED)
    levels[AuthorityDomain.THIRD_PARTY_CONTACT_SOURCE_AUTHORITY] = (
        AuthorityLevel.AUTHORIZED_WITH_CONTROLS
    )
    for domain in COUNSEL_APPROVED_DOMAINS:
        levels[domain] = AuthorityLevel.AUTHORIZED_WITH_CONTROLS
    # Explicit, not merely absent: execution stays blocked.
    levels[AuthorityDomain.PHONE_OUTBOUND_EXECUTION_AUTHORITY] = AuthorityLevel.NOT_AUTHORIZED
    return SourceAuthorityMatrix(levels=levels)


@dataclass(frozen=True)
class CounselDecisionRecord:
    """One of the eight fields counsel returned, recorded exactly."""

    decision_field: str
    counsel_answer: str  # "APPROVED_WITH_CONTROLS" for all eight, verbatim
    classification: str = "COUNSEL_DIRECTED_OPERATIONAL_CONTROL"


COUNSEL_DECISIONS: tuple[CounselDecisionRecord, ...] = tuple(
    CounselDecisionRecord(decision_field=f, counsel_answer="APPROVED_WITH_CONTROLS")
    for f in (
        "PROFESSIONAL_DIRECTORY_USE",
        "CONTACT_ENRICHMENT_USE",
        "EMAIL_VERIFICATION_USE",
        "PATTERN_DERIVED_BUT_INDEPENDENTLY_VERIFIED_EMAIL_USE",
        "PROFESSIONAL_PROFILE_USE",
        "BUSINESS_PHONE_RESOLUTION",
        "DIRECT_BUSINESS_PHONE_RESOLUTION",
        "RETENTION_CONTROLS",
    )
)


# --------------------------------------------------------------------------
# 2/3. Professional directories / contact enrichment (sections 2, 3)
# --------------------------------------------------------------------------

DIRECTORY_DURABLE_FIELDS: frozenset[str] = frozenset(
    {"name", "title", "employer", "work_email", "business_phone", "source", "retrieval_date"}
)
"""Section 2's exact allowlist - narrower than the general
``application._DURABLE_FIELD_ALLOWLIST``; directory-sourced fields must
satisfy both."""

PROHIBITED_DIRECTORY_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "consumer_people_search",
        "consumer_profile_database",
        "ad_tech",
        "location_tracking",
    }
)


class DirectorySourceKind(StrEnum):
    BUSINESS_PROFESSIONAL_DIRECTORY = "business_professional_directory"
    CONSUMER_PEOPLE_SEARCH = "consumer_people_search"
    CONSUMER_PROFILE_DATABASE = "consumer_profile_database"
    AD_TECH = "ad_tech"
    LOCATION_TRACKING = "location_tracking"


def directory_source_permitted(kind: DirectorySourceKind) -> bool:
    return kind is DirectorySourceKind.BUSINESS_PROFESSIONAL_DIRECTORY


@dataclass(frozen=True)
class RolePreVerification:
    """Section 3: enrichment may execute only after the target's role is
    already verified from the company's own site or an equally
    authoritative published source - enrichment must never originate the
    targeting decision."""

    role_confirmed: bool
    role_source_category: SourceCategory


def enrichment_permitted_for_person(pre: RolePreVerification) -> bool:
    if not pre.role_confirmed:
        return False
    return pre.role_source_category in (
        SourceCategory.FIRST_PARTY_PERSON_ROLE,
        SourceCategory.FIRST_PARTY_EXPLICIT_CONTACT,
        SourceCategory.APPROVED_PROFESSIONAL_DIRECTORY,
    )


@dataclass(frozen=True)
class VendorComplianceChecklist:
    """Section 3's required evidence fields before any specific vendor may
    be activated. All must be True/provided - missing any one means the
    vendor stays not activated (section 3: "do not activate that vendor")."""

    lawful_sourcing_warranty: bool = False
    per_record_provenance: bool = False
    no_sensitive_categories: bool = False
    no_minors: bool = False
    no_scraped_credentials: bool = False
    deletion_on_request: bool = False
    vendor_contractual_controls_or_indemnity: bool = False
    texas_data_broker_registry_screened: bool = False

    @property
    def satisfied(self) -> bool:
        return all(
            (
                self.lawful_sourcing_warranty,
                self.per_record_provenance,
                self.no_sensitive_categories,
                self.no_minors,
                self.no_scraped_credentials,
                self.deletion_on_request,
                self.vendor_contractual_controls_or_indemnity,
                self.texas_data_broker_registry_screened,
            )
        )

    @property
    def missing(self) -> tuple[str, ...]:
        fields = (
            "lawful_sourcing_warranty",
            "per_record_provenance",
            "no_sensitive_categories",
            "no_minors",
            "no_scraped_credentials",
            "deletion_on_request",
            "vendor_contractual_controls_or_indemnity",
            "texas_data_broker_registry_screened",
        )
        return tuple(f for f in fields if not getattr(self, f))


# --------------------------------------------------------------------------
# 4. Texas Data Broker Registry screening (section 4)
# --------------------------------------------------------------------------


class DataBrokerRegistryResult(StrEnum):
    REGISTERED = "registered"
    NOT_REGISTERED = "not_registered"
    UNKNOWN = "unknown"
    NOT_APPLICABLE_FIRST_PARTY = "not_applicable_first_party"


@dataclass(frozen=True)
class TexasDataBrokerRegistryCheck:
    provider: str
    registry_result: DataBrokerRegistryResult
    check_date: datetime
    source: str
    disposition: str
    """Registration is NEVER treated as proof of lawful sourcing by itself
    (section 4) - ``disposition`` must independently justify activation."""


# --------------------------------------------------------------------------
# 5. Ingest minimization (section 5) - directory/enrichment specific
# --------------------------------------------------------------------------


def minimize_directory_result(raw_fields: dict[str, str]) -> dict[str, str]:
    """Section 2's narrower allowlist for directory/enrichment ingest -
    stricter than the general ``application.minimize_raw_result``. Personal
    email, home address, an unconfirmed personal/mobile number, family/
    personal info, consumer-profile attributes, and sensitive attributes are
    all outside this allowlist and therefore always dropped."""
    return {k: v for k, v in raw_fields.items() if k in DIRECTORY_DURABLE_FIELDS}


# --------------------------------------------------------------------------
# 6. Email verification: method classification + 90-day expiry (section 6)
# --------------------------------------------------------------------------


class VerificationMethodClass(StrEnum):
    PASSIVE_ALLOWED = "passive_allowed"
    """syntax validation; corporate-domain validation; DNS/MX; approved
    verification-provider confidence; catch-all detection."""
    DECEPTIVE_PROHIBITED = "deceptive_prohibited"
    """pretexting; impersonation; deceptive calls/emails; unauthorized
    system access."""


_PASSIVE_METHODS: frozenset[str] = frozenset(
    {
        "syntax_validation",
        "corporate_domain_validation",
        "dns_mx",
        "approved_verification_provider_confidence",
        "catch_all_detection",
    }
)
_DECEPTIVE_METHODS: frozenset[str] = frozenset(
    {"pretexting", "impersonation", "deceptive_contact", "unauthorized_system_access"}
)


def classify_verification_method(method: str) -> VerificationMethodClass:
    if method in _PASSIVE_METHODS:
        return VerificationMethodClass.PASSIVE_ALLOWED
    if method in _DECEPTIVE_METHODS:
        return VerificationMethodClass.DECEPTIVE_PROHIBITED
    # Fail closed: an unrecognized method is never assumed passive.
    return VerificationMethodClass.DECEPTIVE_PROHIBITED


EMAIL_VERIFICATION_MAX_AGE = timedelta(days=90)


def verification_is_expired(verified_at: datetime, now: datetime) -> bool:
    return (now - verified_at) > EMAIL_VERIFICATION_MAX_AGE


# --------------------------------------------------------------------------
# 7. Pattern-derived email rules (section 7)
# --------------------------------------------------------------------------

_GENERIC_ROLE_MAILBOX_LOCALPARTS: frozenset[str] = frozenset(
    {"info", "sales", "support", "contact", "office", "admin", "hello", "help", "service"}
)


def is_corporate_domain(email_domain: str, company_domain: str) -> bool:
    """section 7: corporate domain only, never a personal-provider domain."""
    personal_providers = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
    }
    domain = email_domain.strip().lower()
    if domain in personal_providers:
        return False
    return domain == company_domain.strip().lower()


def is_generic_role_mailbox(candidate_local_part: str) -> bool:
    """section 7: never substitute info@/sales@/etc. as if it were a
    specific person's own work address."""
    return candidate_local_part.strip().lower() in _GENERIC_ROLE_MAILBOX_LOCALPARTS


@dataclass(frozen=True)
class PatternCandidateSet:
    """Section 7: exactly one final candidate may ever advance toward
    eligibility for a person - no permutation spraying. This type makes that
    structurally explicit: it holds candidates for audit, but only
    ``chosen`` may ever be passed to eligibility evaluation."""

    person_key: str
    all_generated: tuple[str, ...]
    chosen: str | None

    def __post_init__(self) -> None:
        if self.chosen is not None and self.chosen not in self.all_generated:
            raise ValueError("chosen candidate must be one of all_generated")

    @property
    def is_single_candidate_selection(self) -> bool:
        return self.chosen is not None


@dataclass(frozen=True)
class CatchAllDetectionResult:
    is_catch_all_domain: bool
    inconclusive: bool

    @property
    def blocks_candidate(self) -> bool:
        """section 7: catch-all domain or inconclusive verification = DROP."""
        return self.is_catch_all_domain or self.inconclusive


@dataclass(frozen=True)
class DomainBounceMonitor:
    """Section 7: support bounce-rate monitoring by domain for future real
    sends; domain-pattern use must be suspended when its configured
    threshold is exceeded."""

    domain: str
    bounce_count: int
    send_count: int
    suspend_threshold: float = 0.05
    """5% default; a project-specific override may be supplied."""

    @property
    def bounce_rate(self) -> float:
        if self.send_count == 0:
            return 0.0
        return self.bounce_count / self.send_count

    @property
    def suspended(self) -> bool:
        return self.send_count > 0 and self.bounce_rate > self.suspend_threshold


def pattern_email_eligibility_disposition(
    *,
    candidate_set: PatternCandidateSet,
    company_domain: str,
    catch_all: CatchAllDetectionResult,
    bounce_monitor: DomainBounceMonitor | None,
    verification_method: str,
) -> EligibilityDisposition | None:
    """Returns a blocking disposition if any section-7 rule fails, else
    None (caller proceeds to the normal ``application.evaluate_email_eligibility``
    gate, which still separately requires independent verification)."""
    if candidate_set.chosen is None:
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    if "@" not in candidate_set.chosen:
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    local_part, _, domain = candidate_set.chosen.partition("@")
    if not is_corporate_domain(domain, company_domain):
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    if is_generic_role_mailbox(local_part):
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    if catch_all.blocks_candidate:
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    if bounce_monitor is not None and bounce_monitor.suspended:
        return EligibilityDisposition.CONTACT_SOURCE_NOT_AUTHORIZED
    if classify_verification_method(verification_method) is (
        VerificationMethodClass.DECEPTIVE_PROHIBITED
    ):
        return EligibilityDisposition.PATTERN_ONLY_NOT_ELIGIBLE
    return None


# --------------------------------------------------------------------------
# 8. Professional profiles / LinkedIn conflict resolution (section 8)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceConflict:
    field_name: str
    first_party_value: str
    linkedin_value: str


def resolve_first_party_vs_linkedin_conflict(
    conflicts: tuple[SourceConflict, ...],
) -> dict[str, str]:
    """FIRST_PARTY_COMPANY_SOURCE_WINS (section 8): the company's own site
    always wins a conflict with LinkedIn/profile evidence."""
    return {c.field_name: c.first_party_value for c in conflicts}


# --------------------------------------------------------------------------
# 9/10/11. Phone (sections 9, 10, 11)
# --------------------------------------------------------------------------


def phone_kind_from_provenance(
    *, company_assigned_proven: bool, ambiguous: bool
) -> PhoneKind | None:
    """section 10: if a source cannot distinguish a direct business line
    from a personal mobile, exclude it - return None rather than guess."""
    if ambiguous:
        return None
    if company_assigned_proven:
        return PhoneKind.DIRECT_BUSINESS_PHONE
    return PhoneKind.MAIN_BUSINESS_PHONE


def phone_execution_disposition(
    resolution_disposition: EligibilityDisposition, matrix: SourceAuthorityMatrix
) -> EligibilityDisposition:
    """section 11: resolving a route is never execution permission. A
    resolved-eligible phone disposition is downgraded to
    RESOLVED_BUT_EXECUTION_NOT_AUTHORIZED unless
    PHONE_OUTBOUND_EXECUTION_AUTHORITY is itself granted (it structurally
    never is in this milestone - section 11's telemarketing-review gate)."""
    resolved_kinds = frozenset(
        {
            EligibilityDisposition.ELIGIBLE_HUMAN_CALL_INDIRECT,
            EligibilityDisposition.ELIGIBLE_HUMAN_CALL_DIRECT,
        }
    )
    if resolution_disposition not in resolved_kinds:
        return resolution_disposition
    if matrix.level(AuthorityDomain.PHONE_OUTBOUND_EXECUTION_AUTHORITY) is (
        AuthorityLevel.NOT_AUTHORIZED
    ):
        return EligibilityDisposition.RESOLVED_BUT_EXECUTION_NOT_AUTHORIZED
    return resolution_disposition


# --------------------------------------------------------------------------
# 13/14. Retention, purge, deletion/provenance requests (sections 13, 14)
# --------------------------------------------------------------------------

RETENTION_DAYS_MIN = 30
RETENTION_DAYS_MAX = 90
RETENTION_DAYS_DEFAULT = 60


@dataclass(frozen=True)
class RetentionPolicy:
    purge_after_days: int = RETENTION_DAYS_DEFAULT

    def __post_init__(self) -> None:
        if not (RETENTION_DAYS_MIN <= self.purge_after_days <= RETENTION_DAYS_MAX):
            raise ValueError(
                f"purge_after_days must be within counsel's permitted "
                f"{RETENTION_DAYS_MIN}-{RETENTION_DAYS_MAX} day range"
            )

    def is_expired(self, observed_at: datetime, now: datetime) -> bool:
        return (now - observed_at) > timedelta(days=self.purge_after_days)


DEFAULT_RETENTION_POLICY = RetentionPolicy()


@dataclass(frozen=True)
class DeletionProvenanceReport:
    """Section 14: the system's answer to a HOW_DID_YOU_GET_MY_INFORMATION
    or DELETE_MY_INFORMATION request, regardless of whether TDPSA legally
    applies to this individual."""

    person_name: str
    source: str
    retrieval_date: datetime
    purpose: str
    retained_fields: tuple[str, ...]
    action_taken: str


def build_deletion_provenance_report(
    *,
    person_name: str,
    source: str,
    retrieval_date: datetime,
    retained_fields: tuple[str, ...],
    deletion_requested: bool,
) -> DeletionProvenanceReport:
    action = "DELETED_AND_SUPPRESSED" if deletion_requested else "PROVENANCE_DISCLOSED_NO_DELETION"
    return DeletionProvenanceReport(
        person_name=person_name,
        source=source,
        retrieval_date=retrieval_date,
        purpose="professional_business_recipient_identification",
        retained_fields=retained_fields,
        action_taken=action,
    )
