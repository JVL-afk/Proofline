"""M6 domain records. Finding, verifying, eligibility, authorization, and sending stay separate."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Stage(StrEnum):
    PERSON_IDENTIFIED = "person_identified"
    CONTACT_DETAIL_VERIFIED = "contact_detail_verified"
    CONTACT_ELIGIBLE = "contact_eligible"
    SEND_READY = "send_ready"
    SEND_AUTHORIZED = "send_authorized"
    SENT = "sent"


class AcquisitionOrigin(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    FIRST_PARTY_PROVIDED = "first_party_provided"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    STALE = "stale"
    REVOKED = "revoked"


class ProofScope(StrEnum):
    SYNTAX_VALIDITY = "syntax_validity"
    DOMAIN_MAIL_CAPABILITY = "domain_mail_capability"
    MAILBOX_ACCEPTANCE = "mailbox_acceptance"
    DIRECTORY_OBSERVATION = "directory_observation"
    PERSON_CONTACT_ASSOCIATION = "person_contact_association"
    FIRST_PARTY_CONFIRMATION = "first_party_confirmation"


class EligibilityState(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    REQUIRES_REVIEW = "requires_review"
    UNKNOWN = "unknown"


class SenderLifecycle(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AuthorizationState(StrEnum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    CONSUMED = "consumed"


class DeliveryAttemptState(StrEnum):
    PROVIDER_ACCEPTED = "provider_accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    STATUS_UNKNOWN = "status_unknown"


class ReceiptKind(StrEnum):
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    HARD_BOUNCE = "hard_bounce"
    SOFT_BOUNCE = "soft_bounce"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class ReplyKind(StrEnum):
    OPT_OUT = "opt_out"
    WRONG_PERSON = "wrong_person"
    REFERRAL_OFFERED = "referral_offered"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    REQUEST_INFORMATION = "request_information"
    OUT_OF_OFFICE = "out_of_office"
    AUTOMATED_REPLY = "automated_reply"
    AMBIGUOUS = "ambiguous"
    UNCLASSIFIED = "unclassified"


class SuppressionReason(StrEnum):
    OPT_OUT = "opt_out"
    COMPLAINT = "complaint"
    HARD_BOUNCE = "hard_bounce"
    WRONG_PERSON = "wrong_person"
    ADMINISTRATIVE = "administrative"


class QcSeverity(StrEnum):
    HARD_FAILURE = "hard_failure"
    WARNING = "warning"


class StageRecord(FrozenModel):
    record_kind: Literal["stage"] = "stage"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    stage: Stage
    subject_id: UUID
    exact_revisions: dict[str, str]
    provenance_ids: tuple[str, ...]
    policy_versions: dict[str, str]
    actor: str
    operation_id: UUID
    trace_id: UUID
    invalidation_state: Literal["active"] = "active"
    created_at: datetime


class StageInvalidation(FrozenModel):
    record_kind: Literal["stage_invalidation"] = "stage_invalidation"
    id: UUID
    workspace_id: UUID
    stage_record_id: UUID
    reason: str
    actor: str
    created_at: datetime


class PersonIdentity(FrozenModel):
    record_kind: Literal["person"] = "person"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    outreach_revision_id: UUID
    full_name: str
    functional_role: str
    identity_semantics: AcquisitionOrigin
    source_uri: str
    source_locator: str
    source_hash: str
    resolver_version: str
    created_by: str
    created_at: datetime


class ContactPoint(FrozenModel):
    record_kind: Literal["contact"] = "contact"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    person_id: UUID
    channel: Literal["email"]
    value: str
    redacted_value: str
    value_hmac: str
    acquisition_origin: AcquisitionOrigin
    source_uri: str
    source_locator: str
    source_hash: str
    created_by: str
    created_at: datetime


class ContactVerification(FrozenModel):
    record_kind: Literal["verification"] = "verification"
    id: UUID
    workspace_id: UUID
    contact_point_id: UUID
    status: VerificationStatus
    proof_scopes: tuple[ProofScope, ...]
    limitations: tuple[str, ...]
    verifier_version: str
    policy_version: str
    verified_at: datetime
    valid_until: datetime | None

    @property
    def proves_person_association(self) -> bool:
        return self.status == VerificationStatus.VERIFIED and bool(
            {ProofScope.PERSON_CONTACT_ASSOCIATION, ProofScope.FIRST_PARTY_CONFIRMATION}
            & set(self.proof_scopes)
        )


class CommunicationContext(FrozenModel):
    record_kind: Literal["context"] = "context"
    id: UUID
    workspace_id: UUID
    person_id: UUID
    contact_point_id: UUID
    sender_jurisdiction: str
    recipient_jurisdiction: str | None
    recipient_timezone: str | None
    channel: Literal["email"]
    purpose: Literal["b2b_first_contact", "b2b_follow_up"]
    resolver_version: str
    provenance: tuple[str, ...]
    created_at: datetime


class OutreachPolicyRelease(FrozenModel):
    record_kind: Literal["policy"] = "policy"
    id: UUID
    workspace_id: UUID
    version: str
    fixture_only: bool
    live_activation_allowed: bool
    allowed_jurisdictions: tuple[str, ...]
    required_proof_scopes: tuple[ProofScope, ...]
    allowed_local_hour_start: int
    allowed_local_hour_end: int
    cadence_limit: int
    effective_at: datetime
    expires_at: datetime
    approved_by: str
    checksum: str


class EligibilityEvaluation(FrozenModel):
    record_kind: Literal["eligibility"] = "eligibility"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    person_id: UUID
    contact_point_id: UUID
    verification_id: UUID
    context_id: UUID
    policy_release_id: UUID
    state: EligibilityState
    reasons: tuple[str, ...]
    suppression_checked_at: datetime
    actor: str
    operation_id: UUID
    trace_id: UUID
    created_at: datetime


class SuppressionEvent(FrozenModel):
    record_kind: Literal["suppression"] = "suppression"
    id: UUID
    workspace_id: UUID
    contact_point_id: UUID
    person_id: UUID
    reason: SuppressionReason
    source_record_id: UUID | None
    actor: str
    created_at: datetime


class CadenceReservation(FrozenModel):
    record_kind: Literal["cadence"] = "cadence"
    id: UUID
    workspace_id: UUID
    contact_point_id: UUID
    purpose: str
    policy_version: str
    created_at: datetime


class SenderIdentity(FrozenModel):
    record_kind: Literal["sender"] = "sender"
    id: UUID
    workspace_id: UUID
    display_name: str
    mailbox: str
    domain: str
    signature: str
    postal_disclosure: str
    opt_out_instruction: str
    lifecycle: SenderLifecycle
    provenance_uri: str
    verification_version: str
    created_by: str
    created_at: datetime


class SendManifest(FrozenModel):
    record_kind: Literal["manifest"] = "manifest"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    outreach_revision_id: UUID
    outreach_revision_hash: str
    outreach_manifest_hash: str
    outreach_content_hash: str
    artifact_id: UUID
    artifact_kind: str
    artifact_content_hash: str
    person_id: UUID
    contact_point_id: UUID
    verification_id: UUID
    eligibility_evaluation_id: UUID
    communication_context_id: UUID
    sender_identity_id: UUID
    sender_verification_version: str
    policy_release_id: UUID
    policy_checksum: str
    subject: str
    subject_hash: str
    body: str
    body_hash: str
    preview_hash: str
    recipient_count: Literal[1]
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    content_type: Literal["text/plain"] = "text/plain"
    configuration_versions: dict[str, str]
    operation_id: UUID
    trace_id: UUID
    created_by: str
    created_at: datetime


class QcFinding(FrozenModel):
    code: str
    severity: QcSeverity
    message: str


class SendReadiness(FrozenModel):
    record_kind: Literal["readiness"] = "readiness"
    id: UUID
    workspace_id: UUID
    manifest_id: UUID
    passed: bool
    findings: tuple[QcFinding, ...]
    suppression_checked_at: datetime
    policy_version: str
    actor: str
    operation_id: UUID
    trace_id: UUID
    created_at: datetime


class HumanSendAuthorization(FrozenModel):
    record_kind: Literal["authorization"] = "authorization"
    id: UUID
    workspace_id: UUID
    manifest_id: UUID
    readiness_id: UUID
    manifest_hash: str
    preview_hash: str
    action: Literal["AUTHORIZE_ONE_SEND"] = "AUTHORIZE_ONE_SEND"
    actor: str
    actor_roles: tuple[str, ...]
    reason: str
    created_at: datetime
    expires_at: datetime


class DeliveryAttempt(FrozenModel):
    record_kind: Literal["attempt"] = "attempt"
    id: UUID
    workspace_id: UUID
    authorization_id: UUID
    manifest_id: UUID
    state: DeliveryAttemptState
    provider: Literal["deterministic_mock"] = "deterministic_mock"
    provider_message_id: str | None
    idempotency_key: str
    retry_count: Literal[0] = 0
    safe_detail: str
    operation_id: UUID
    trace_id: UUID
    created_at: datetime


class DeliveryReceipt(FrozenModel):
    record_kind: Literal["receipt"] = "receipt"
    id: UUID
    workspace_id: UUID
    attempt_id: UUID
    provider_event_id: str
    kind: ReceiptKind
    authenticated: bool
    received_at: datetime


class InboundReply(FrozenModel):
    record_kind: Literal["reply"] = "reply"
    id: UUID
    workspace_id: UUID
    attempt_id: UUID
    provider_event_id: str
    body: str
    body_hash: str
    authenticated: bool
    received_at: datetime


class ReplyClassification(FrozenModel):
    record_kind: Literal["classification"] = "classification"
    id: UUID
    workspace_id: UUID
    reply_id: UUID
    kind: ReplyKind
    classifier_version: str
    human_corrected: bool
    actor: str
    created_at: datetime


class FirstPartyStatement(FrozenModel):
    record_kind: Literal["statement"] = "statement"
    id: UUID
    workspace_id: UUID
    reply_id: UUID
    person_id: UUID
    semantics: Literal["FIRST_PARTY_ASSERTED"] = "FIRST_PARTY_ASSERTED"
    statement_type: str
    exact_fragment: str
    locator: str
    extractor_version: str
    created_at: datetime


class ReanalysisRequested(FrozenModel):
    record_kind: Literal["reanalysis"] = "reanalysis"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    statement_ids: tuple[UUID, ...]
    affected_contexts: tuple[Literal["M2", "M3"], ...]
    reason: str
    requested_by: str
    created_at: datetime


class InteractionEvent(FrozenModel):
    record_kind: Literal["interaction"] = "interaction"
    id: UUID
    workspace_id: UUID
    business_id: UUID
    event_type: str
    subject_id: UUID
    safe_metadata: dict[str, str]
    actor: str
    created_at: datetime


M6Record = Annotated[
    StageRecord
    | StageInvalidation
    | PersonIdentity
    | ContactPoint
    | ContactVerification
    | CommunicationContext
    | OutreachPolicyRelease
    | EligibilityEvaluation
    | SuppressionEvent
    | CadenceReservation
    | SenderIdentity
    | SendManifest
    | SendReadiness
    | HumanSendAuthorization
    | DeliveryAttempt
    | DeliveryReceipt
    | InboundReply
    | ReplyClassification
    | FirstPartyStatement
    | ReanalysisRequested
    | InteractionEvent,
    Field(discriminator="record_kind"),
]
M6_RECORD_ADAPTER: TypeAdapter[M6Record] = TypeAdapter(M6Record)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ContactError(Exception):
    code = "contact_error"
    safe_message = "contact operation failed"


class ContactNotFoundError(ContactError):
    code = "not_found"
    safe_message = "contact resource not found"


class ContactAuthorizationError(ContactError):
    code = "forbidden"
    safe_message = "contact action is not permitted"


class ContactValidationError(ContactError):
    code = "invalid_input"
    safe_message = "contact input is invalid"


class ContactConflictError(ContactError):
    code = "conflict"
    safe_message = "contact state conflicts with the requested action"
