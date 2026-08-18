"""M6 synthetic contact eligibility and one-message controlled delivery."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Literal, TypeVar, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory
from opintel_outreach.domain import ArtifactKind, OutreachRevisionState, OutreachValidity

from opintel_contact.domain import (
    AcquisitionOrigin,
    CadenceReservation,
    CommunicationContext,
    ContactAuthorizationError,
    ContactConflictError,
    ContactNotFoundError,
    ContactPoint,
    ContactValidationError,
    ContactVerification,
    DeliveryAttempt,
    DeliveryAttemptState,
    DeliveryReceipt,
    EligibilityEvaluation,
    EligibilityState,
    FirstPartyStatement,
    HumanSendAuthorization,
    InboundReply,
    InteractionEvent,
    M6Record,
    OutreachPolicyRelease,
    PersonIdentity,
    ProofScope,
    QcFinding,
    QcSeverity,
    ReanalysisRequested,
    ReceiptKind,
    ReplyClassification,
    ReplyKind,
    SenderIdentity,
    SenderLifecycle,
    SendManifest,
    SendReadiness,
    Stage,
    StageInvalidation,
    StageRecord,
    SuppressionEvent,
    SuppressionReason,
    stable_hash,
)
from opintel_contact.ports import (
    ApprovedOutreachCatalog,
    ContactRepository,
    ContactVerifierPort,
    ContextResolverPort,
    DeliveryProviderPort,
    FirstPartyStatementExtractorPort,
    PersonResolverPort,
    ReplyClassifierPort,
    SenderVerifierPort,
)

T = TypeVar("T")
EMAIL = re.compile(r"^[^\s@\r\n]+@fixture\.invalid$")
FORBIDDEN_BODY = re.compile(
    r"(?:https?://|<\s*/?\s*(?:html|script|img|iframe|object|form)|javascript:|"
    r"tracking\s*pixel|\bon(?:load|error|click)\s*=)",
    re.I,
)
FAKE_THREAD = re.compile(r"^(?:re|fwd):", re.I)


class ContactApplicationService:
    def __init__(
        self,
        repository: ContactRepository,
        outreach: ApprovedOutreachCatalog,
        clock: Clock,
        identifiers: IdentifierFactory,
        person_resolver: PersonResolverPort,
        contact_verifier: ContactVerifierPort,
        context_resolver: ContextResolverPort,
        sender_verifier: SenderVerifierPort,
        delivery_provider: DeliveryProviderPort,
        reply_classifier: ReplyClassifierPort,
        statement_extractor: FirstPartyStatementExtractorPort,
    ) -> None:
        self._repository = repository
        self._outreach = outreach
        self._clock = clock
        self._ids = identifiers
        self._person_resolver = person_resolver
        self._contact_verifier = contact_verifier
        self._context_resolver = context_resolver
        self._sender_verifier = sender_verifier
        self._provider = delivery_provider
        self._reply_classifier = reply_classifier
        self._statement_extractor = statement_extractor
        self._global_kill_switch = False

    def activate_global_kill_switch(self) -> None:
        self._global_kill_switch = True

    def clear_global_kill_switch_for_test(self) -> None:
        self._global_kill_switch = False

    def ensure_fixture_policy(self, workspace_id: UUID) -> OutreachPolicyRelease:
        existing = self._latest(workspace_id, "policy", OutreachPolicyRelease)
        if existing is not None:
            return existing
        now = self._clock.now()
        body = {
            "version": "m6.fixture-policy@1",
            "fixture_only": True,
            "live_activation_allowed": False,
            "jurisdictions": ["TEST_ONLY"],
            "proof": [str(ProofScope.PERSON_CONTACT_ASSOCIATION)],
        }
        policy = OutreachPolicyRelease(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="m6.fixture-policy@1",
            fixture_only=True,
            live_activation_allowed=False,
            allowed_jurisdictions=("TEST_ONLY",),
            required_proof_scopes=(ProofScope.PERSON_CONTACT_ASSOCIATION,),
            allowed_local_hour_start=0,
            allowed_local_hour_end=24,
            cadence_limit=2,
            effective_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=365),
            approved_by="fixture-policy-owner",
            checksum=stable_hash(body),
        )
        self._repository.save(policy)
        return policy

    def identify_person(
        self,
        principal: Principal,
        outreach_revision_id: UUID,
        full_name: str,
        functional_role: str,
        source_uri: str,
        source_locator: str,
    ) -> PersonIdentity:
        self._require_operator(principal)
        bundle = self._approved_outreach(principal.workspace_id, outreach_revision_id)
        normalized, resolver_version = self._person_resolver.validate_fixture_identity(
            full_name, source_uri
        )
        now = self._clock.now()
        person = PersonIdentity(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=bundle.revision.business_id,
            outreach_revision_id=outreach_revision_id,
            full_name=normalized,
            functional_role=functional_role,
            identity_semantics=AcquisitionOrigin.OBSERVED,
            source_uri=source_uri,
            source_locator=source_locator,
            source_hash=stable_hash((source_uri, source_locator, normalized)),
            resolver_version=resolver_version,
            created_by=principal.subject,
            created_at=now,
        )
        self._repository.save(person)
        self._save_stage(
            principal,
            bundle.revision.business_id,
            Stage.PERSON_IDENTIFIED,
            person.id,
            {"outreach_revision": str(outreach_revision_id)},
            (person.source_hash,),
            {"resolver": resolver_version},
        )
        self._event(
            person.workspace_id,
            person.business_id,
            "person_identified",
            person.id,
            principal.subject,
        )
        return person

    def create_contact_point(
        self,
        principal: Principal,
        person_id: UUID,
        value: str,
        origin: AcquisitionOrigin,
        source_uri: str,
        source_locator: str,
    ) -> ContactPoint:
        self._require_operator(principal)
        person = self._get(principal.workspace_id, "person", person_id, PersonIdentity)
        normalized = value.strip().lower()
        if not EMAIL.fullmatch(normalized):
            raise ContactValidationError("only reserved fixture.invalid email values are allowed")
        local = normalized.split("@", 1)[0]
        contact = ContactPoint(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=person.business_id,
            person_id=person.id,
            channel="email",
            value=normalized,
            redacted_value=f"{local[:1]}***@fixture.invalid",
            value_hmac=stable_hash(("fixture-hmac-key-id", normalized)),
            acquisition_origin=origin,
            source_uri=source_uri,
            source_locator=source_locator,
            source_hash=stable_hash((source_uri, source_locator, normalized)),
            created_by=principal.subject,
            created_at=self._clock.now(),
        )
        self._repository.save(contact)
        self._event(
            contact.workspace_id,
            contact.business_id,
            "contact_point_recorded",
            contact.id,
            principal.subject,
        )
        return contact

    def verify_contact(self, principal: Principal, contact_point_id: UUID) -> ContactVerification:
        self._require_operator(principal)
        contact = self._get(principal.workspace_id, "contact", contact_point_id, ContactPoint)
        status, scopes, limitations, valid_seconds = self._contact_verifier.verify(contact)
        now = self._clock.now()
        verification = ContactVerification(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            contact_point_id=contact.id,
            status=status,
            proof_scopes=scopes,
            limitations=limitations,
            verifier_version="m6.fixture-contact-verifier@1",
            policy_version="m6.fixture-verification-policy@1",
            verified_at=now,
            valid_until=now + timedelta(seconds=valid_seconds) if valid_seconds else now,
        )
        self._repository.save(verification)
        if verification.proves_person_association and self._verification_current(verification):
            self._save_stage(
                principal,
                contact.business_id,
                Stage.CONTACT_DETAIL_VERIFIED,
                contact.id,
                {
                    "person": str(contact.person_id),
                    "contact_point": str(contact.id),
                    "verification": str(verification.id),
                },
                (contact.source_hash,),
                {
                    "verifier": verification.verifier_version,
                    "verification_policy": verification.policy_version,
                },
            )
        self._event(
            contact.workspace_id,
            contact.business_id,
            f"contact_verification_{verification.status}",
            verification.id,
            principal.subject,
        )
        return verification

    def evaluate_eligibility(
        self, principal: Principal, contact_point_id: UUID, purpose: str
    ) -> EligibilityEvaluation:
        self._require_operator(principal)
        if purpose not in {"b2b_first_contact", "b2b_follow_up"}:
            raise ContactValidationError("unsupported fixture purpose")
        contact = self._get(principal.workspace_id, "contact", contact_point_id, ContactPoint)
        verification = self._latest_for(
            principal.workspace_id,
            "verification",
            ContactVerification,
            "contact_point_id",
            contact.id,
        )
        if verification is None:
            raise ContactValidationError("contact has no verification result")
        jurisdiction, timezone, provenance = self._context_resolver.resolve(contact, purpose)
        context = CommunicationContext(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            person_id=contact.person_id,
            contact_point_id=contact.id,
            sender_jurisdiction="TEST_ONLY",
            recipient_jurisdiction=jurisdiction,
            recipient_timezone=timezone,
            channel="email",
            purpose=cast(Literal["b2b_first_contact", "b2b_follow_up"], purpose),
            resolver_version="m6.fixture-context-resolver@1",
            provenance=provenance,
            created_at=self._clock.now(),
        )
        self._repository.save(context)
        policy = self.ensure_fixture_policy(principal.workspace_id)
        state, reasons = self._eligibility_state(contact, verification, context, policy)
        operation_id, trace_id = self._ids.new(), self._ids.new()
        evaluation = EligibilityEvaluation(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=contact.business_id,
            person_id=contact.person_id,
            contact_point_id=contact.id,
            verification_id=verification.id,
            context_id=context.id,
            policy_release_id=policy.id,
            state=state,
            reasons=reasons,
            suppression_checked_at=self._clock.now(),
            actor=principal.subject,
            operation_id=operation_id,
            trace_id=trace_id,
            created_at=self._clock.now(),
        )
        self._repository.save(evaluation)
        if state == EligibilityState.ELIGIBLE:
            self._save_stage(
                principal,
                contact.business_id,
                Stage.CONTACT_ELIGIBLE,
                contact.id,
                {
                    "person": str(contact.person_id),
                    "contact_point": str(contact.id),
                    "verification": str(verification.id),
                    "context": str(context.id),
                    "eligibility": str(evaluation.id),
                },
                context.provenance,
                {"policy": policy.version, "context_resolver": context.resolver_version},
                operation_id,
                trace_id,
            )
        self._event(
            contact.workspace_id,
            contact.business_id,
            f"eligibility_{state}",
            evaluation.id,
            principal.subject,
        )
        return evaluation

    def suppress(
        self,
        principal: Principal,
        contact_point_id: UUID,
        reason: SuppressionReason,
        source_record_id: UUID | None = None,
    ) -> SuppressionEvent:
        if not (principal.can_operate() or principal.can_review()):
            raise ContactAuthorizationError()
        contact = self._get(principal.workspace_id, "contact", contact_point_id, ContactPoint)
        return self._suppress(
            contact,
            reason,
            source_record_id,
            principal.subject,
        )

    def create_sender(
        self,
        principal: Principal,
        display_name: str,
        mailbox: str,
        signature: str,
        postal_disclosure: str,
        opt_out_instruction: str,
    ) -> SenderIdentity:
        self._require_operator(principal)
        if not EMAIL.fullmatch(mailbox.lower()) or any(
            "\r" in value or "\n" in value
            for value in (display_name, mailbox, signature, postal_disclosure, opt_out_instruction)
        ):
            raise ContactValidationError("sender must be a safe reserved fixture identity")
        sender = SenderIdentity(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            display_name=display_name,
            mailbox=mailbox.lower(),
            domain="fixture.invalid",
            signature=signature,
            postal_disclosure=postal_disclosure,
            opt_out_instruction=opt_out_instruction,
            lifecycle=SenderLifecycle.VERIFIED,
            provenance_uri="fixture://m6/senders/verified",
            verification_version="m6.fixture-sender-verifier@1",
            created_by=principal.subject,
            created_at=self._clock.now(),
        )
        if not self._sender_verifier.verify(sender):
            sender = sender.model_copy(update={"lifecycle": SenderLifecycle.UNVERIFIED})
        self._repository.save(sender)
        return sender

    def prepare_send(
        self,
        principal: Principal,
        outreach_revision_id: UUID,
        contact_point_id: UUID,
        sender_identity_id: UUID,
        artifact_kind: str,
    ) -> tuple[SendManifest, SendReadiness]:
        self._require_operator(principal)
        bundle = self._approved_outreach(principal.workspace_id, outreach_revision_id)
        contact = self._get(principal.workspace_id, "contact", contact_point_id, ContactPoint)
        person = self._get(principal.workspace_id, "person", contact.person_id, PersonIdentity)
        if contact.business_id != bundle.revision.business_id:
            raise ContactValidationError("recipient and M5 package business mismatch")
        sender = self._get(principal.workspace_id, "sender", sender_identity_id, SenderIdentity)
        verification = self._latest_for(
            principal.workspace_id,
            "verification",
            ContactVerification,
            "contact_point_id",
            contact.id,
        )
        evaluation = self._latest_for(
            principal.workspace_id,
            "eligibility",
            EligibilityEvaluation,
            "contact_point_id",
            contact.id,
        )
        if verification is None or evaluation is None:
            raise ContactValidationError("verification and eligibility are required")
        context = self._get(
            principal.workspace_id, "context", evaluation.context_id, CommunicationContext
        )
        policy = self._get(
            principal.workspace_id, "policy", evaluation.policy_release_id, OutreachPolicyRelease
        )
        kind = ArtifactKind(artifact_kind)
        if kind not in {ArtifactKind.FIRST_CONTACT_EMAIL, ArtifactKind.FOLLOW_UP_DRAFT}:
            raise ContactValidationError("only registered email artifacts are sendable")
        artifact = next((item for item in bundle.revision.artifacts if item.kind == kind), None)
        subject_artifact = next(
            (item for item in bundle.revision.artifacts if item.kind == ArtifactKind.SUBJECT), None
        )
        if artifact is None or subject_artifact is None:
            raise ContactValidationError("required exact M5 artifacts are absent")
        body = artifact.rendered_text
        body = body.replace("{{functional_role_or_team}}", person.functional_role.replace("_", " "))
        slot_values = {
            "{{verified_sender_signature}}": sender.signature,
            "{{required_postal_disclosure}}": sender.postal_disclosure,
            "{{approved_opt_out_instruction}}": sender.opt_out_instruction,
        }
        for placeholder, value in slot_values.items():
            if placeholder not in body:
                raise ContactValidationError("required typed M5 delivery slot is absent")
            body = body.replace(placeholder, value)
        operation_id, trace_id = self._ids.new(), self._ids.new()
        now = self._clock.now()
        preview_hash = stable_hash(
            {
                "recipient": contact.value_hmac,
                "sender": sender.id,
                "subject": subject_artifact.rendered_text,
                "body": body,
            }
        )
        manifest = SendManifest(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=contact.business_id,
            outreach_revision_id=bundle.revision.id,
            outreach_revision_hash=bundle.revision.revision_hash,
            outreach_manifest_hash=bundle.revision.manifest.checksum,
            outreach_content_hash=bundle.revision.content_hash,
            artifact_id=artifact.id,
            artifact_kind=str(kind),
            artifact_content_hash=artifact.content_hash,
            person_id=contact.person_id,
            contact_point_id=contact.id,
            verification_id=verification.id,
            eligibility_evaluation_id=evaluation.id,
            communication_context_id=context.id,
            sender_identity_id=sender.id,
            sender_verification_version=sender.verification_version,
            policy_release_id=policy.id,
            policy_checksum=policy.checksum,
            subject=subject_artifact.rendered_text,
            subject_hash=stable_hash(subject_artifact.rendered_text),
            body=body,
            body_hash=stable_hash(body),
            preview_hash=preview_hash,
            recipient_count=1,
            configuration_versions={
                "m5_template": bundle.revision.manifest.template_version,
                "m6_manifest": "m6.send-manifest@1",
                "m6_qc": "m6.send-readiness-qc@1",
                "fixture_policy": policy.version,
            },
            operation_id=operation_id,
            trace_id=trace_id,
            created_by=principal.subject,
            created_at=now,
        )
        findings = self._readiness_findings(
            contact, verification, evaluation, context, policy, sender, manifest
        )
        readiness = SendReadiness(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            manifest_id=manifest.id,
            passed=not any(item.severity == QcSeverity.HARD_FAILURE for item in findings),
            findings=findings,
            suppression_checked_at=now,
            policy_version=policy.version,
            actor=principal.subject,
            operation_id=operation_id,
            trace_id=trace_id,
            created_at=now,
        )
        self._repository.save(manifest)
        self._repository.save(readiness)
        if readiness.passed:
            self._repository.save(
                CadenceReservation(
                    id=self._ids.new(),
                    workspace_id=principal.workspace_id,
                    contact_point_id=contact.id,
                    purpose=context.purpose,
                    policy_version=policy.version,
                    created_at=now,
                )
            )
            self._save_stage(
                principal,
                contact.business_id,
                Stage.SEND_READY,
                manifest.id,
                {
                    "outreach_revision": str(bundle.revision.id),
                    "person": str(contact.person_id),
                    "contact": str(contact.id),
                    "verification": str(verification.id),
                    "eligibility": str(evaluation.id),
                    "sender": str(sender.id),
                    "manifest": str(manifest.id),
                    "readiness": str(readiness.id),
                },
                (bundle.revision.content_hash, contact.source_hash, sender.provenance_uri),
                manifest.configuration_versions,
                operation_id,
                trace_id,
            )
        return manifest, readiness

    def authorize_send(
        self,
        principal: Principal,
        manifest_id: UUID,
        expected_manifest_hash: str,
        expected_preview_hash: str,
        reason: str,
    ) -> HumanSendAuthorization:
        if not principal.can_review():
            raise ContactAuthorizationError()
        manifest = self._get(principal.workspace_id, "manifest", manifest_id, SendManifest)
        readiness = self._latest_for(
            principal.workspace_id, "readiness", SendReadiness, "manifest_id", manifest.id
        )
        actual_manifest_hash = stable_hash(manifest.model_dump(mode="json"))
        if (
            readiness is None
            or not readiness.passed
            or expected_manifest_hash != actual_manifest_hash
            or expected_preview_hash != manifest.preview_hash
        ):
            raise ContactValidationError("exact ready manifest precondition failed")
        self._require_manifest_current(manifest)
        if self._is_suppressed(principal.workspace_id, manifest.contact_point_id):
            raise ContactValidationError("suppression overrides authorization")
        now = self._clock.now()
        authorization = HumanSendAuthorization(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            manifest_id=manifest.id,
            readiness_id=readiness.id,
            manifest_hash=actual_manifest_hash,
            preview_hash=manifest.preview_hash,
            actor=principal.subject,
            actor_roles=tuple(str(role) for role in principal.roles),
            reason=reason,
            created_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self._repository.save(authorization)
        self._save_stage(
            principal,
            manifest.business_id,
            Stage.SEND_AUTHORIZED,
            authorization.id,
            {"manifest": str(manifest.id), "readiness": str(readiness.id)},
            (manifest.preview_hash,),
            manifest.configuration_versions,
            manifest.operation_id,
            manifest.trace_id,
        )
        return authorization

    def submit_authorized(
        self, principal: Principal, authorization_id: UUID, idempotency_key: str
    ) -> DeliveryAttempt:
        self._require_operator(principal)
        authorization = self._get(
            principal.workspace_id, "authorization", authorization_id, HumanSendAuthorization
        )
        existing = next(
            (
                item
                for item in self._typed_list(principal.workspace_id, "attempt", DeliveryAttempt)
                if item.authorization_id == authorization.id
            ),
            None,
        )
        if existing is not None:
            return existing
        manifest = self._get(
            principal.workspace_id, "manifest", authorization.manifest_id, SendManifest
        )
        if self._global_kill_switch:
            raise ContactValidationError("global delivery kill switch is active")
        if self._clock.now() >= authorization.expires_at:
            raise ContactValidationError("send authorization expired")
        self._require_manifest_current(manifest)
        if self._is_suppressed(principal.workspace_id, manifest.contact_point_id):
            raise ContactValidationError("suppression overrides provider submission")
        contact = self._get(
            principal.workspace_id, "contact", manifest.contact_point_id, ContactPoint
        )
        result = self._provider.submit_one(
            recipient=contact.value,
            subject=manifest.subject,
            body=manifest.body,
            idempotency_key=idempotency_key,
        )
        if result.status_unknown:
            state = DeliveryAttemptState.STATUS_UNKNOWN
        elif result.accepted:
            state = DeliveryAttemptState.PROVIDER_ACCEPTED
        else:
            state = DeliveryAttemptState.REJECTED
        attempt = DeliveryAttempt(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            authorization_id=authorization.id,
            manifest_id=manifest.id,
            state=state,
            provider_message_id=result.provider_message_id,
            idempotency_key=idempotency_key,
            safe_detail=result.safe_detail,
            operation_id=self._ids.new(),
            trace_id=manifest.trace_id,
            created_at=self._clock.now(),
        )
        self._repository.save(attempt)
        if state == DeliveryAttemptState.PROVIDER_ACCEPTED:
            self._save_stage(
                principal,
                manifest.business_id,
                Stage.SENT,
                attempt.id,
                {"manifest": str(manifest.id), "authorization": str(authorization.id)},
                (manifest.preview_hash,),
                manifest.configuration_versions,
                attempt.operation_id,
                attempt.trace_id,
            )
        self._event(
            manifest.workspace_id,
            manifest.business_id,
            f"delivery_{state}",
            attempt.id,
            principal.subject,
        )
        return attempt

    def ingest_fixture_event(
        self,
        principal: Principal,
        attempt_id: UUID,
        event_id: str,
        event_type: str,
        body: str,
        signature: str,
    ) -> tuple[M6Record, ...]:
        self._require_operator(principal)
        attempt = self._get(principal.workspace_id, "attempt", attempt_id, DeliveryAttempt)
        if any(
            getattr(item, "provider_event_id", None) == event_id
            for kind in ("receipt", "reply")
            for item in self._repository.list(principal.workspace_id, kind)
        ):
            raise ContactConflictError("provider event replay rejected")
        normalized_type, normalized_body = self._provider.parse_signed_fixture_event(
            event_id=event_id,
            event_type=event_type,
            body=body,
            signature=signature,
        )
        manifest = self._get(principal.workspace_id, "manifest", attempt.manifest_id, SendManifest)
        if normalized_type != "reply":
            try:
                receipt_kind = ReceiptKind(normalized_type)
            except ValueError as error:
                raise ContactValidationError("unsupported fixture receipt") from error
            receipt = DeliveryReceipt(
                id=self._ids.new(),
                workspace_id=principal.workspace_id,
                attempt_id=attempt.id,
                provider_event_id=event_id,
                kind=receipt_kind,
                authenticated=True,
                received_at=self._clock.now(),
            )
            self._repository.save(receipt)
            if receipt_kind in {ReceiptKind.HARD_BOUNCE, ReceiptKind.COMPLAINT}:
                reason = (
                    SuppressionReason.HARD_BOUNCE
                    if receipt_kind == ReceiptKind.HARD_BOUNCE
                    else SuppressionReason.COMPLAINT
                )
                contact = self._get(
                    principal.workspace_id, "contact", manifest.contact_point_id, ContactPoint
                )
                self._suppress(contact, reason, receipt.id, "m6-safety-policy")
            self._event(
                manifest.workspace_id,
                manifest.business_id,
                f"receipt_{receipt_kind}",
                receipt.id,
                "fixture-provider",
            )
            return (receipt,)
        if len(normalized_body) > 5000:
            raise ContactValidationError("reply exceeds fixture size limit")
        reply = InboundReply(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            attempt_id=attempt.id,
            provider_event_id=event_id,
            body=normalized_body,
            body_hash=stable_hash(normalized_body),
            authenticated=True,
            received_at=self._clock.now(),
        )
        self._repository.save(reply)
        reply_kind = self._reply_classifier.classify(normalized_body)
        classification = ReplyClassification(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            reply_id=reply.id,
            kind=reply_kind,
            classifier_version="m6.rule-reply-classifier@1",
            human_corrected=False,
            actor="fixture-classifier",
            created_at=self._clock.now(),
        )
        self._repository.save(classification)
        contact = self._get(
            principal.workspace_id, "contact", manifest.contact_point_id, ContactPoint
        )
        if reply_kind == ReplyKind.OPT_OUT:
            self._suppress(contact, SuppressionReason.OPT_OUT, reply.id, "m6-safety-policy")
        elif reply_kind == ReplyKind.WRONG_PERSON:
            self._suppress(contact, SuppressionReason.WRONG_PERSON, reply.id, "m6-safety-policy")
        statements: list[FirstPartyStatement] = []
        for statement_type, fragment, locator in self._statement_extractor.extract(normalized_body):
            statement = FirstPartyStatement(
                id=self._ids.new(),
                workspace_id=principal.workspace_id,
                reply_id=reply.id,
                person_id=manifest.person_id,
                statement_type=statement_type,
                exact_fragment=fragment,
                locator=locator,
                extractor_version="m6.fixture-statement-extractor@1",
                created_at=self._clock.now(),
            )
            self._repository.save(statement)
            statements.append(statement)
        if reply_kind == ReplyKind.REFERRAL_OFFERED:
            self._create_referral_candidate(principal, manifest, reply)
        self._event(
            manifest.workspace_id,
            manifest.business_id,
            f"reply_{reply_kind}",
            reply.id,
            "fixture-provider",
        )
        return (reply, classification, *statements)

    def correct_reply_classification(
        self, principal: Principal, reply_id: UUID, kind: ReplyKind
    ) -> ReplyClassification:
        if not principal.can_review():
            raise ContactAuthorizationError()
        self._get(principal.workspace_id, "reply", reply_id, InboundReply)
        value = ReplyClassification(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            reply_id=reply_id,
            kind=kind,
            classifier_version="human-correction@1",
            human_corrected=True,
            actor=principal.subject,
            created_at=self._clock.now(),
        )
        self._repository.save(value)
        return value

    def request_reanalysis(
        self,
        principal: Principal,
        business_id: UUID,
        statement_ids: tuple[UUID, ...],
        reason: str,
    ) -> ReanalysisRequested:
        if not principal.can_review() or not statement_ids:
            raise ContactAuthorizationError()
        for statement_id in statement_ids:
            self._get(principal.workspace_id, "statement", statement_id, FirstPartyStatement)
        value = ReanalysisRequested(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=business_id,
            statement_ids=statement_ids,
            affected_contexts=("M2", "M3"),
            reason=reason,
            requested_by=principal.subject,
            created_at=self._clock.now(),
        )
        self._repository.save(value)
        return value

    def verify_first_contact(self, principal: Principal, attempt_id: UUID) -> InteractionEvent:
        if not principal.can_review():
            raise ContactAuthorizationError()
        attempt = self._get(principal.workspace_id, "attempt", attempt_id, DeliveryAttempt)
        if attempt.state != DeliveryAttemptState.PROVIDER_ACCEPTED:
            raise ContactValidationError("first contact was not provider-accepted")
        manifest = self._get(principal.workspace_id, "manifest", attempt.manifest_id, SendManifest)
        return self._event(
            manifest.workspace_id,
            manifest.business_id,
            "first_contact_verified",
            attempt.id,
            principal.subject,
        )

    def get_record(self, principal: Principal, record_kind: str, record_id: UUID) -> M6Record:
        value = self._repository.get(principal.workspace_id, record_kind, record_id)
        if value is None:
            raise ContactNotFoundError()
        return value

    def timeline(self, principal: Principal, business_id: UUID) -> tuple[InteractionEvent, ...]:
        return tuple(
            item
            for item in self._typed_list(principal.workspace_id, "interaction", InteractionEvent)
            if item.business_id == business_id
        )

    def _approved_outreach(self, workspace_id: UUID, revision_id: UUID):  # type: ignore[no-untyped-def]
        bundle = self._outreach.get_approved(workspace_id, revision_id)
        if (
            bundle is None
            or bundle.revision.state != OutreachRevisionState.CONTENT_APPROVED
            or bundle.revision.validity != OutreachValidity.CURRENT
            or not bundle.review_valid
        ):
            raise ContactValidationError("exact current CONTENT_APPROVED M5 revision is required")
        return bundle

    def _eligibility_state(
        self,
        contact: ContactPoint,
        verification: ContactVerification,
        context: CommunicationContext,
        policy: OutreachPolicyRelease,
    ) -> tuple[EligibilityState, tuple[str, ...]]:
        if self._is_suppressed(contact.workspace_id, contact.id):
            return EligibilityState.INELIGIBLE, ("active_suppression",)
        if contact.value.startswith("ineligible"):
            return EligibilityState.INELIGIBLE, ("fixture_hard_prohibition",)
        if contact.value.startswith("review"):
            return EligibilityState.REQUIRES_REVIEW, ("fixture_policy_requires_human_review",)
        if (
            context.recipient_jurisdiction is None
            or context.recipient_timezone is None
            or context.recipient_jurisdiction not in policy.allowed_jurisdictions
        ):
            return EligibilityState.UNKNOWN, ("jurisdiction_or_timezone_unknown",)
        if (
            not verification.proves_person_association
            or not self._verification_current(verification)
            or not set(policy.required_proof_scopes).issubset(verification.proof_scopes)
        ):
            return EligibilityState.UNKNOWN, ("sufficient_person_contact_proof_missing",)
        return EligibilityState.ELIGIBLE, ("fixture_policy_passed",)

    def _readiness_findings(
        self,
        contact: ContactPoint,
        verification: ContactVerification,
        evaluation: EligibilityEvaluation,
        context: CommunicationContext,
        policy: OutreachPolicyRelease,
        sender: SenderIdentity,
        manifest: SendManifest,
    ) -> tuple[QcFinding, ...]:
        findings: list[QcFinding] = []

        def fail(code: str, message: str) -> None:
            findings.append(QcFinding(code=code, severity=QcSeverity.HARD_FAILURE, message=message))

        if not verification.proves_person_association or not self._verification_current(
            verification
        ):
            fail("contact_verification", "Current person/contact association proof is required.")
        if evaluation.state != EligibilityState.ELIGIBLE:
            fail("contact_eligibility", "Only an ELIGIBLE evaluation is sendable.")
        if self._is_suppressed(contact.workspace_id, contact.id):
            fail("suppression", "Suppression overrides readiness.")
        if sender.lifecycle != SenderLifecycle.VERIFIED or not self._sender_verifier.verify(sender):
            fail("sender", "Synthetic sender identity is not currently verified.")
        if not policy.fixture_only or policy.live_activation_allowed:
            fail("policy_scope", "M6 accepts only the non-live fixture policy release.")
        if not (policy.effective_at <= self._clock.now() < policy.expires_at):
            fail("policy_expired", "Fixture policy is not active.")
        if context.recipient_timezone is None or not self.contact_time_allowed(
            self._clock.now(),
            context.recipient_timezone,
            policy.allowed_local_hour_start,
            policy.allowed_local_hour_end,
        ):
            fail("contact_time", "Recipient timezone is unknown or contact time is not allowed.")
        reservations = [
            item
            for item in self._typed_list(contact.workspace_id, "cadence", CadenceReservation)
            if item.contact_point_id == contact.id and item.purpose == context.purpose
        ]
        if len(reservations) >= policy.cadence_limit:
            fail("cadence", "Fixture cadence limit is exhausted.")
        findings.extend(
            self.message_shape_findings(
                subject=manifest.subject,
                body=manifest.body,
                content_type=manifest.content_type,
                recipient_count=manifest.recipient_count,
                cc=manifest.cc,
                bcc=manifest.bcc,
            )
        )
        if "{{" in manifest.body or "}}" in manifest.body:
            fail("unresolved_slot", "All registered M5 delivery slots must resolve exactly.")
        if context.purpose == "b2b_follow_up" and not self._first_contact_verified(
            contact.workspace_id, contact.id
        ):
            fail("follow_up_precondition", "A human-verified first contact is required.")
        return tuple(findings)

    @staticmethod
    def message_shape_findings(
        *,
        subject: str,
        body: str,
        content_type: str,
        recipient_count: int,
        cc: tuple[str, ...],
        bcc: tuple[str, ...],
    ) -> tuple[QcFinding, ...]:
        findings: list[QcFinding] = []
        if recipient_count != 1 or cc or bcc:
            findings.append(
                QcFinding(
                    code="recipient_count",
                    severity=QcSeverity.HARD_FAILURE,
                    message="Exactly one recipient and no CC/BCC are required.",
                )
            )
        if FAKE_THREAD.match(subject) or "\r" in subject or "\n" in subject:
            findings.append(
                QcFinding(
                    code="subject",
                    severity=QcSeverity.HARD_FAILURE,
                    message="Fake thread prefixes and header injection are prohibited.",
                )
            )
        if FORBIDDEN_BODY.search(body) or "\r" in body or content_type != "text/plain":
            findings.append(
                QcFinding(
                    code="active_content",
                    severity=QcSeverity.HARD_FAILURE,
                    message="Only safe plain text without URLs or active content is allowed.",
                )
            )
        return tuple(findings)

    @staticmethod
    def contact_time_allowed(
        now: datetime, timezone_name: str, start_hour: int, end_hour: int
    ) -> bool:
        try:
            local = now.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            if timezone_name != "America/Chicago":
                return False
            local = now.astimezone(timezone(_chicago_offset(now)))
        return start_hour <= local.hour < end_hour

    def _require_manifest_current(self, manifest: SendManifest) -> None:
        bundle = self._approved_outreach(manifest.workspace_id, manifest.outreach_revision_id)
        if (
            bundle.revision.revision_hash != manifest.outreach_revision_hash
            or bundle.revision.manifest.checksum != manifest.outreach_manifest_hash
            or bundle.revision.content_hash != manifest.outreach_content_hash
        ):
            raise ContactValidationError("upstream M5 manifest drifted")

    def _verification_current(self, value: ContactVerification) -> bool:
        return value.valid_until is not None and self._clock.now() < value.valid_until

    def _is_suppressed(self, workspace_id: UUID, contact_id: UUID) -> bool:
        return any(
            item.contact_point_id == contact_id
            for item in self._typed_list(workspace_id, "suppression", SuppressionEvent)
        )

    def _suppress(
        self,
        contact: ContactPoint,
        reason: SuppressionReason,
        source_record_id: UUID | None,
        actor: str,
    ) -> SuppressionEvent:
        event = SuppressionEvent(
            id=self._ids.new(),
            workspace_id=contact.workspace_id,
            contact_point_id=contact.id,
            person_id=contact.person_id,
            reason=reason,
            source_record_id=source_record_id,
            actor=actor,
            created_at=self._clock.now(),
        )
        self._repository.save(event)
        self._invalidate_pending_authorizations(contact, event)
        self._event(
            contact.workspace_id,
            contact.business_id,
            f"suppressed_{reason}",
            event.id,
            actor,
        )
        return event

    def _invalidate_pending_authorizations(
        self, contact: ContactPoint, suppression: SuppressionEvent
    ) -> None:
        manifests = {
            item.id
            for item in self._typed_list(contact.workspace_id, "manifest", SendManifest)
            if item.contact_point_id == contact.id
        }
        authorizations = {
            item.id
            for item in self._typed_list(
                contact.workspace_id, "authorization", HumanSendAuthorization
            )
            if item.manifest_id in manifests
        }
        for stage in self._typed_list(contact.workspace_id, "stage", StageRecord):
            if stage.stage == Stage.SEND_AUTHORIZED and stage.subject_id in authorizations:
                self._repository.save(
                    StageInvalidation(
                        id=self._ids.new(),
                        workspace_id=contact.workspace_id,
                        stage_record_id=stage.id,
                        reason=f"suppression:{suppression.reason}",
                        actor=suppression.actor,
                        created_at=suppression.created_at,
                    )
                )

    def _first_contact_verified(self, workspace_id: UUID, contact_id: UUID) -> bool:
        manifests = {
            item.id
            for item in self._typed_list(workspace_id, "manifest", SendManifest)
            if item.contact_point_id == contact_id
            and item.artifact_kind == str(ArtifactKind.FIRST_CONTACT_EMAIL)
        }
        attempts = {
            item.id
            for item in self._typed_list(workspace_id, "attempt", DeliveryAttempt)
            if item.manifest_id in manifests
            and item.state == DeliveryAttemptState.PROVIDER_ACCEPTED
        }
        return any(
            item.event_type == "first_contact_verified" and item.subject_id in attempts
            for item in self._typed_list(workspace_id, "interaction", InteractionEvent)
        )

    def _create_referral_candidate(
        self, principal: Principal, manifest: SendManifest, reply: InboundReply
    ) -> None:
        match = re.search(
            r"referr(?:al|ed).*?([A-Za-z][A-Za-z .'-]{1,60}).*?"
            r"([\w.+-]+@fixture\.invalid)",
            reply.body,
            re.I,
        )
        if not match:
            return
        person = PersonIdentity(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=manifest.business_id,
            outreach_revision_id=manifest.outreach_revision_id,
            full_name=match.group(1).strip(),
            functional_role="unverified_referral",
            identity_semantics=AcquisitionOrigin.FIRST_PARTY_PROVIDED,
            source_uri=f"reply://{reply.id}",
            source_locator="referral",
            source_hash=reply.body_hash,
            resolver_version="m6.referral-candidate@1",
            created_by="fixture-reply-ingestion",
            created_at=self._clock.now(),
        )
        self._repository.save(person)
        email = match.group(2).lower()
        self._repository.save(
            ContactPoint(
                id=self._ids.new(),
                workspace_id=principal.workspace_id,
                business_id=manifest.business_id,
                person_id=person.id,
                channel="email",
                value=email,
                redacted_value=f"{email[0]}***@fixture.invalid",
                value_hmac=stable_hash(("fixture-hmac-key-id", email)),
                acquisition_origin=AcquisitionOrigin.FIRST_PARTY_PROVIDED,
                source_uri=f"reply://{reply.id}",
                source_locator="referral",
                source_hash=reply.body_hash,
                created_by="fixture-reply-ingestion",
                created_at=self._clock.now(),
            )
        )

    def _save_stage(
        self,
        principal: Principal,
        business_id: UUID,
        stage: Stage,
        subject_id: UUID,
        revisions: dict[str, str],
        provenance: tuple[str, ...],
        policies: dict[str, str],
        operation_id: UUID | None = None,
        trace_id: UUID | None = None,
    ) -> StageRecord:
        value = StageRecord(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            business_id=business_id,
            stage=stage,
            subject_id=subject_id,
            exact_revisions=revisions,
            provenance_ids=provenance,
            policy_versions=policies,
            actor=principal.subject,
            operation_id=operation_id or self._ids.new(),
            trace_id=trace_id or self._ids.new(),
            created_at=self._clock.now(),
        )
        self._repository.save(value)
        return value

    def _event(
        self,
        workspace_id: UUID,
        business_id: UUID,
        event_type: str,
        subject_id: UUID,
        actor: str,
    ) -> InteractionEvent:
        value = InteractionEvent(
            id=self._ids.new(),
            workspace_id=workspace_id,
            business_id=business_id,
            event_type=event_type,
            subject_id=subject_id,
            safe_metadata={},
            actor=actor,
            created_at=self._clock.now(),
        )
        self._repository.save(value)
        return value

    def _latest(self, workspace_id: UUID, kind: str, expected: type[T]) -> T | None:
        values = self._typed_list(workspace_id, kind, expected)
        return max(values, key=_record_time) if values else None

    def _latest_for(
        self,
        workspace_id: UUID,
        kind: str,
        expected: type[T],
        attribute: str,
        identifier: UUID,
    ) -> T | None:
        values = [
            item
            for item in self._typed_list(workspace_id, kind, expected)
            if getattr(item, attribute) == identifier
        ]
        return max(values, key=_record_time) if values else None

    def _typed_list(self, workspace_id: UUID, kind: str, expected: type[T]) -> tuple[T, ...]:
        return tuple(
            cast(T, item)
            for item in self._repository.list(workspace_id, kind)
            if isinstance(item, expected)
        )

    def _get(
        self,
        workspace_id: UUID,
        kind: str,
        identifier: UUID,
        expected: type[T],
    ) -> T:
        value = self._repository.get(workspace_id, kind, identifier)
        if value is None or not isinstance(value, expected):
            raise ContactNotFoundError()
        return value

    @staticmethod
    def _require_operator(principal: Principal) -> None:
        if not principal.can_operate():
            raise ContactAuthorizationError()


def _record_time(value: object) -> datetime:
    for attribute in ("created_at", "verified_at", "effective_at", "received_at"):
        candidate = getattr(value, attribute, None)
        if isinstance(candidate, datetime):
            return candidate
    raise TypeError("M6 record has no timestamp")


def _chicago_offset(now: datetime) -> timedelta:
    """US Central fixture fallback for Windows environments without IANA tzdata."""
    utc_now = now.astimezone(UTC)
    year = utc_now.year
    march_anchor = date(year, 3, 8)
    march_day = 8 + (6 - march_anchor.weekday()) % 7
    november_anchor = date(year, 11, 1)
    november_day = 1 + (6 - november_anchor.weekday()) % 7
    dst_start = datetime(year, 3, march_day, 8, tzinfo=UTC)
    dst_end = datetime(year, 11, november_day, 7, tzinfo=UTC)
    return timedelta(hours=-5 if dst_start <= utc_now < dst_end else -6)
