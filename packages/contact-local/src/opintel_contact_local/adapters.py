"""Credential-free, zero-network M6 fixture adapters."""

from __future__ import annotations

import re
from uuid import UUID

from opintel_contact.domain import (
    AcquisitionOrigin,
    ContactPoint,
    ContactValidationError,
    ProofScope,
    ReplyKind,
    SenderIdentity,
    SenderLifecycle,
    VerificationStatus,
)
from opintel_contact.ports import DeliverySubmitResult
from opintel_outreach.domain import OutreachBundle
from opintel_outreach.ports import OutreachRepository


class ApprovedOutreachSource:
    def __init__(self, outreach: OutreachRepository) -> None:
        self._outreach = outreach

    def get_approved(self, workspace_id: UUID, revision_id: UUID) -> OutreachBundle | None:
        return self._outreach.get_revision(workspace_id, revision_id)


class SyntheticPersonResolver:
    def validate_fixture_identity(self, full_name: str, source_uri: str) -> tuple[str, str]:
        normalized = " ".join(full_name.split())
        if (
            not source_uri.startswith("fixture://")
            or len(normalized) < 2
            or any(char in normalized for char in "\r\n<>")
        ):
            raise ContactValidationError("invalid synthetic identity fixture")
        return normalized, "m6.synthetic-person-resolver@1"


class DeterministicContactVerifier:
    def verify(
        self, contact: ContactPoint
    ) -> tuple[VerificationStatus, tuple[ProofScope, ...], tuple[str, ...], int]:
        local = contact.value.split("@", 1)[0]
        baseline = (ProofScope.SYNTAX_VALIDITY, ProofScope.DOMAIN_MAIL_CAPABILITY)
        if local.startswith(("observed-only", "syntax-only")):
            return (
                VerificationStatus.INCONCLUSIVE,
                (*baseline, ProofScope.DIRECTORY_OBSERVATION),
                (
                    "Directory observation and domain capability do not establish mailbox control "
                    "or person/contact association.",
                ),
                3600,
            )
        scopes = (
            *baseline,
            ProofScope.MAILBOX_ACCEPTANCE,
            ProofScope.PERSON_CONTACT_ASSOCIATION,
        )
        if local.startswith("stale"):
            return (
                VerificationStatus.VERIFIED,
                scopes,
                ("Fixture result is already stale.",),
                0,
            )
        limitations: tuple[str, ...] = (
            "Fixture proof establishes only person/contact association for deterministic M6 tests.",
            "It does not establish legal eligibility, consent, delivery, or engagement.",
        )
        if contact.acquisition_origin == AcquisitionOrigin.INFERRED:
            limitations = (
                *limitations,
                "The acquisition origin remains inferred after verification.",
            )
        return VerificationStatus.VERIFIED, scopes, limitations, 3600


class FixtureContextResolver:
    def resolve(
        self, contact: ContactPoint, purpose: str
    ) -> tuple[str | None, str | None, tuple[str, ...]]:
        del purpose
        if contact.value.startswith(("unknown", "unknown-timezone")):
            return None, None, ("fixture://m6/context/unknown",)
        return "TEST_ONLY", "America/Chicago", ("fixture://m6/context/test-only",)


class DeterministicSenderVerifier:
    def verify(self, sender: SenderIdentity) -> bool:
        return (
            sender.mailbox.endswith("@fixture.invalid")
            and sender.domain == "fixture.invalid"
            and sender.lifecycle == SenderLifecycle.VERIFIED
            and sender.provenance_uri.startswith("fixture://")
        )


class DeterministicMockDeliveryProvider:
    provider_name = "deterministic_mock"

    def __init__(self) -> None:
        self.submission_count = 0
        self.network_call_count = 0

    def submit_one(
        self, *, recipient: str, subject: str, body: str, idempotency_key: str
    ) -> DeliverySubmitResult:
        del subject, body
        self.submission_count += 1
        safe_id = f"mock-{idempotency_key}"
        if recipient.startswith("timeout-after-acceptance"):
            return DeliverySubmitResult(
                accepted=False,
                status_unknown=True,
                provider_message_id=safe_id,
                safe_detail="mock provider outcome is ambiguous; retry prohibited",
            )
        if recipient.startswith("reject"):
            return DeliverySubmitResult(
                accepted=False,
                status_unknown=False,
                provider_message_id=None,
                safe_detail="mock provider rejected the fixture message",
            )
        return DeliverySubmitResult(
            accepted=True,
            status_unknown=False,
            provider_message_id=safe_id,
            safe_detail="mock provider accepted one synthetic message",
        )

    def query_status(self, provider_message_id: str) -> str:
        return "unknown" if provider_message_id.startswith("mock-timeout") else "accepted"

    def parse_signed_fixture_event(
        self, *, event_id: str, event_type: str, body: str, signature: str
    ) -> tuple[str, str]:
        del event_id
        if signature != "fixture-signature-v1":
            raise ContactValidationError("fixture event signature is invalid")
        allowed = {
            "delivered",
            "deferred",
            "hard_bounce",
            "soft_bounce",
            "complaint",
            "unknown",
            "reply",
        }
        if event_type not in allowed:
            raise ContactValidationError("unsupported fixture event type")
        return event_type, body


class RuleBasedReplyClassifier:
    def classify(self, body: str) -> ReplyKind:
        text = " ".join(body.lower().split())
        if re.search(r"\b(?:unsubscribe|opt[ -]?out|do not (?:email|contact))\b", text):
            return ReplyKind.OPT_OUT
        if "wrong person" in text or "no longer works here" in text:
            return ReplyKind.WRONG_PERSON
        if "referral" in text or "speak with" in text:
            return ReplyKind.REFERRAL_OFFERED
        if "out of office" in text or "away from the office" in text:
            return ReplyKind.OUT_OF_OFFICE
        if "automatic reply" in text or "automated response" in text:
            return ReplyKind.AUTOMATED_REPLY
        if "not interested" in text:
            return ReplyKind.NOT_INTERESTED
        if "send more information" in text or "what does" in text:
            return ReplyKind.REQUEST_INFORMATION
        if "interested" in text or "let's talk" in text:
            return ReplyKind.INTERESTED
        if not text:
            return ReplyKind.UNCLASSIFIED
        return ReplyKind.AMBIGUOUS


class BoundedFirstPartyStatementExtractor:
    def extract(self, body: str) -> tuple[tuple[str, str, str], ...]:
        normalized = " ".join(body.split())[:1000]
        if not normalized:
            return ()
        return (("reply_statement", normalized, "reply.body[0]"),)


class SyntheticConfidentialValueProtector:
    """Interface-preserving local protector; accepts reserved synthetic data only."""

    def protect(self, value: str) -> str:
        if "fixture.invalid" not in value:
            raise ContactValidationError("only synthetic fixture values may use local protection")
        return value

    def reveal(self, protected_value: str) -> str:
        return protected_value
