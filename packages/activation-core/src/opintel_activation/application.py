"""Deterministic M6.5 readiness and mandatory zero-send shadow evaluation."""

from __future__ import annotations

from datetime import timedelta
from typing import TypeVar
from uuid import UUID

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory

from opintel_activation.domain import (
    ActivationAuthorizationError,
    ActivationDecisionSnapshot,
    ActivationNotFoundError,
    ActivationRecord,
    ActivationRecordBase,
    ActivationValidationError,
    ArtifactReference,
    AttestationState,
    AuthorizationPolicyRelease,
    CertificationState,
    ContactSourcePolicyRelease,
    DecisionEntry,
    DecisionStatus,
    ExternalPresenceAttestation,
    ExternalPresenceKind,
    GatePhase,
    GateResult,
    GateState,
    GovernanceReviewRecord,
    InfrastructureControlAttestation,
    InfrastructureControlRequirementSet,
    LaunchEnvelopeRelease,
    LiveActivationReadiness,
    M66GateRelease,
    OperationalReadinessRecord,
    PermissionState,
    ProductionOutreachPolicyRelease,
    ProductionProofScope,
    ProviderCertificationRecord,
    ReadinessState,
    ReadinessTestReport,
    RealDataActivity,
    RealDataPermission,
    RealDataPermissionRelease,
    ReleaseState,
    RetentionPolicyRelease,
    ShadowCandidateManifest,
    ShadowReadinessAssessment,
    ShadowState,
    SourceRule,
    SourceStatus,
    VerificationProfileRelease,
    stable_hash,
)
from opintel_activation.ports import ActivationRepository

TRecord = TypeVar("TRecord", bound=ActivationRecordBase)

REQUIRED_DECISIONS = (
    "A-03",
    "A-04",
    "A-05",
    "A-06",
    "A-07",
    "A-08",
    "A-09",
    "A-15",
    "A-16",
    "A-17",
    "A-18",
    "A-20",
)
REQUIRED_CONTROLS = (
    "oidc_configured",
    "step_up_authentication_evidenced",
    "field_encryption_evidenced",
    "secret_isolation_evidenced",
    "provider_only_egress_evidenced",
    "webhook_authenticity_evidenced",
    "backups_evidenced",
    "reply_monitoring_evidenced",
    "global_kill_switch_evidenced",
)
REQUIRED_TEST_CASES = (
    "missing_or_expired_policy",
    "unapproved_source",
    "insufficient_proof_scope",
    "unknown_jurisdiction_timezone",
    "missing_m5_compliance_slot",
    "retention_gap",
    "missing_step_up",
    "sender_attestation_failure",
    "provider_certification_drift",
    "infrastructure_control_gap",
    "complaint_threshold_suspension",
    "reply_monitoring_failure",
    "kill_switch",
    "cross_workspace_access",
    "tombstone_non_recontact",
    "changed_policy_or_m5_hash",
    "shadow_cannot_send",
    "texas_exact_scope",
)
REQUIRED_COMPLIANCE_SLOTS = (
    "sender_signature",
    "postal_disclosure",
    "opt_out_instruction",
)


class ActivationReadinessService:
    def __init__(
        self,
        repository: ActivationRepository,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._ids = identifiers

    def ensure_baseline(self, workspace_id: UUID) -> None:
        if self._repository.list(workspace_id, "launch_envelope"):
            return
        now = self._clock.now()
        expires = now + timedelta(days=3650)
        envelope_config = {
            "country": "US",
            "recipient_jurisdictions": ["US-TX"],
            "industry": "commercial_hvac",
            "opportunity": "inbound_lead_response_qualification",
            "channel": "b2b_email",
            "recipient_count": 1,
            "messages_per_authorization": 1,
            "links_allowed": False,
            "attachments_allowed": False,
            "tracking_allowed": False,
            "sequences_allowed": False,
            "nationwide_authorization": False,
            "delivery_enabled_by_default": False,
        }
        envelope = LaunchEnvelopeRelease(
            id=self._ids.new(),
            workspace_id=workspace_id,
            version="texas-commercial-hvac-v1",
            configuration_hash=stable_hash(envelope_config),
            created_at=now,
            state=ReleaseState.ACTIVE,
            country="US",
            recipient_jurisdictions=("US-TX",),
            industry="commercial_hvac",
            opportunity="inbound_lead_response_qualification",
            channel="b2b_email",
            integrations_allowed=(),
            effective_at=now,
            expires_at=expires,
        )
        self._repository.save(envelope)
        accepted_decisions = {
            "A-15": "ADR-0049",
            "A-16": "ADR-0043",
        }
        decisions = tuple(
            DecisionEntry(
                decision_id=item,
                status=(
                    DecisionStatus.ACCEPTED if item in accepted_decisions else DecisionStatus.OPEN
                ),
                accountable_role=self._decision_owner(item),
                evidence_refs=(accepted_decisions[item],) if item in accepted_decisions else (),
                approval_classes=self._decision_approvals(item),
            )
            for item in REQUIRED_DECISIONS
        )
        self._repository.save(
            ActivationDecisionSnapshot(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="activation-decisions-v1",
                configuration_hash=stable_hash(
                    [item.model_dump(mode="json") for item in decisions]
                ),
                created_at=now,
                decisions=decisions,
            )
        )
        source_rules = (
            SourceRule(
                category="business_controlled_professional_contact",
                status=SourceStatus.CONDITIONAL_CONTACT_USE,
                permitted_acquisition="business-controlled publication",
                permitted_use="pending A-09/A-17 approval",
                provenance_required=True,
                proof_scopes=(
                    ProductionProofScope.SOURCE_OBSERVED,
                    ProductionProofScope.PERSON_CONTACT_ASSOCIATION,
                ),
                freshness_policy_ref=None,
                restrictions=("proposal_only", "texas_only"),
                real_outreach_allowed=False,
            ),
            SourceRule(
                category="first_party_confirmation_or_referral",
                status=SourceStatus.CONDITIONAL_CONTACT_USE,
                permitted_acquisition="explicit first-party statement",
                permitted_use="pending A-09/A-17 approval",
                provenance_required=True,
                proof_scopes=(ProductionProofScope.FIRST_PARTY_CONFIRMED,),
                freshness_policy_ref=None,
                restrictions=("candidate_must_be_reverified",),
                real_outreach_allowed=False,
            ),
            SourceRule(
                category="third_party_enrichment",
                status=SourceStatus.PROHIBITED,
                permitted_acquisition="none",
                permitted_use="none",
                provenance_required=True,
                proof_scopes=(),
                freshness_policy_ref=None,
                restrictions=("outside_initial_envelope",),
                real_outreach_allowed=False,
            ),
            SourceRule(
                category="inferred_pattern_address",
                status=SourceStatus.IDENTITY_ONLY,
                permitted_acquisition="candidate only",
                permitted_use="never sufficient proof",
                provenance_required=True,
                proof_scopes=(),
                freshness_policy_ref=None,
                restrictions=("not_contact_verified",),
                real_outreach_allowed=False,
            ),
        )
        self._repository.save(
            ContactSourcePolicyRelease(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="initial-source-envelope-proposal-v1",
                configuration_hash=stable_hash(
                    [item.model_dump(mode="json") for item in source_rules]
                ),
                created_at=now,
                state=ReleaseState.DRAFT,
                proposal_only=True,
                live_authorization_allowed=False,
                shadow_authorization_allowed=False,
                rules=source_rules,
                approvals=(),
                effective_at=now,
                expires_at=expires,
            )
        )
        required_scopes = (
            ProductionProofScope.SYNTAX_VALID,
            ProductionProofScope.DOMAIN_MAIL_CAPABLE,
            ProductionProofScope.MAILBOX_ACCEPTANCE_CURRENT,
            ProductionProofScope.PROFESSIONAL_CONTEXT_CURRENT,
            ProductionProofScope.SOURCE_USE_APPROVED,
        )
        self._repository.save(
            VerificationProfileRelease(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="initial-verification-proposal-v1",
                configuration_hash=stable_hash([item.value for item in required_scopes]),
                created_at=now,
                state=ReleaseState.DRAFT,
                proposal_only=True,
                live_authorization_allowed=False,
                shadow_authorization_allowed=False,
                required_scopes=required_scopes,
                association_alternatives=(
                    (ProductionProofScope.PERSON_CONTACT_ASSOCIATION,),
                    (ProductionProofScope.FIRST_PARTY_CONFIRMED,),
                ),
                approvals=(),
                effective_at=now,
                expires_at=expires,
            )
        )
        self._repository.save(
            InfrastructureControlRequirementSet(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="m6.5-production-controls-v1",
                configuration_hash=stable_hash(REQUIRED_CONTROLS),
                created_at=now,
                required_controls=REQUIRED_CONTROLS,
            )
        )
        permissions = tuple(
            RealDataPermission(
                activity=activity,
                state=PermissionState.NOT_AUTHORIZED,
                approval_refs=(),
                policy_versions={},
            )
            for activity in RealDataActivity
        )
        self._repository.save(
            RealDataPermissionRelease(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="m6.7-all-real-data-disabled-v1",
                configuration_hash=stable_hash(
                    [item.model_dump(mode="json") for item in permissions]
                ),
                created_at=now,
                state=ReleaseState.ACTIVE,
                permissions=permissions,
                effective_at=now,
                expires_at=expires,
            )
        )
        m66_conditions = (
            "task_evaluation_scope_approved",
            "synthetic_corpus_policy_approved",
            "a10_evaluation_terms_approved",
            "provider_credentials_isolated",
            "cost_budget_reserved",
            "deterministic_m1_m6_authority_confirmed",
            "ai_cannot_affect_send_authorization_or_delivery",
        )
        self._repository.save(
            M66GateRelease(
                id=self._ids.new(),
                workspace_id=workspace_id,
                version="m6.6-gate-v1",
                configuration_hash=stable_hash(m66_conditions),
                created_at=now,
                state=ReleaseState.ACTIVE,
                required_conditions=m66_conditions,
            )
        )

    def save_record(self, principal: Principal, record: ActivationRecord) -> None:
        if not principal.can_review():
            raise ActivationAuthorizationError()
        if record.workspace_id != principal.workspace_id:
            raise ActivationAuthorizationError()
        if isinstance(record, LiveActivationReadiness):
            raise ActivationValidationError("readiness is a deterministic projection")
        if isinstance(record, ShadowReadinessAssessment):
            raise ActivationValidationError("shadow readiness is a deterministic projection")
        self._repository.save(record)

    def evaluate(self, principal: Principal) -> LiveActivationReadiness:
        envelope = self._latest(principal.workspace_id, "launch_envelope", LaunchEnvelopeRelease)
        decisions = self._latest(
            principal.workspace_id, "decision_snapshot", ActivationDecisionSnapshot
        )
        policy = self._latest(
            principal.workspace_id, "outreach_policy", ProductionOutreachPolicyRelease
        )
        sources = self._latest(principal.workspace_id, "source_policy", ContactSourcePolicyRelease)
        verification = self._latest(
            principal.workspace_id, "verification_profile", VerificationProfileRelease
        )
        authorization = self._latest(
            principal.workspace_id, "authorization_policy", AuthorizationPolicyRelease
        )
        retention = self._latest(principal.workspace_id, "retention_policy", RetentionPolicyRelease)
        requirements = self._latest(
            principal.workspace_id,
            "infrastructure_requirements",
            InfrastructureControlRequirementSet,
        )
        test_report = self._latest(
            principal.workspace_id, "readiness_test_report", ReadinessTestReport
        )
        gates: list[GateResult] = []
        gates.append(
            self._gate(
                "LAUNCH_ENVELOPE",
                "Exact accepted US/Texas Commercial HVAC one-message envelope is active",
                GatePhase.PROVIDER_CERTIFICATION,
                envelope,
                self._valid_envelope(envelope),
                ("active ADR-0043 Texas-only launch-envelope release",),
                "product_owner",
                ("product", "security", "privacy"),
                "launch_envelope",
            )
        )
        decision_missing = self._missing_decisions(decisions)
        gates.append(
            self._gate(
                "ACTIVATION_DECISIONS",
                "All blocking production decisions have owners and accepted evidence",
                GatePhase.PROVIDER_CERTIFICATION,
                decisions,
                not decision_missing,
                decision_missing,
                "architecture_owner",
                ("product", "security", "privacy", "operations"),
                "decision_register",
            )
        )
        gates.append(
            self._gate(
                "A17_POLICY_RELEASE",
                "An active signed production legal/privacy outreach policy exactly matches Texas",
                GatePhase.PROVIDER_CERTIFICATION,
                policy,
                self._valid_policy(policy, envelope),
                ("active signed non-fixture A-17 production policy release",),
                "legal_privacy_owner",
                ("legal", "privacy", "security", "product"),
                "policy_release",
            )
        )
        gates.append(
            self._gate(
                "A09_CONTACT_SOURCES",
                "An active source release authorizes the exact initial contact sources",
                GatePhase.PROVIDER_CERTIFICATION,
                sources,
                self._valid_sources(sources),
                ("approved A-09 source policy with live-contact use",),
                "data_governance_owner",
                ("legal", "privacy", "product"),
                "source_policy",
            )
        )
        gates.append(
            self._gate(
                "PRODUCTION_PROOF_PROFILE",
                (
                    "An active proof profile requires technical, professional, source-use and "
                    "association proof"
                ),
                GatePhase.PROVIDER_CERTIFICATION,
                verification,
                self._valid_verification(verification),
                ("approved active production verification profile",),
                "data_governance_owner",
                ("privacy", "security", "product"),
                "verification_policy",
            )
        )
        gates.append(
            self._gate(
                "PRODUCTION_AUTHORIZATION_POLICY",
                (
                    "Separation of duties, step-up, expiry and exact one-message acknowledgment "
                    "are active"
                ),
                GatePhase.PROVIDER_CERTIFICATION,
                authorization,
                self._valid_authorization(authorization),
                ("accepted A-07/A-15 authorization policy",),
                "security_owner",
                ("security", "product"),
                "authorization_policy",
            )
        )
        gates.append(
            self._gate(
                "A08_RETENTION_POLICY",
                (
                    "Every M6 production record has encryption, retention, deletion, hold and "
                    "tombstone handling"
                ),
                GatePhase.PROVIDER_CERTIFICATION,
                retention,
                self._valid_retention(retention),
                ("complete approved A-08 retention/deletion release",),
                "privacy_data_governance_owner",
                ("privacy", "legal", "security"),
                "retention_policy",
            )
        )
        for review_class in ("legal", "privacy", "security", "product"):
            review = self._latest_review(principal.workspace_id, review_class)
            gates.append(
                self._gate(
                    f"{review_class.upper()}_REVIEW",
                    f"Current {review_class} review approves the exact launch-envelope scope",
                    GatePhase.PROVIDER_CERTIFICATION,
                    review,
                    self._valid_review(review, envelope),
                    (f"current {review_class} review record",),
                    f"{review_class}_owner",
                    (review_class,),
                    "governance_review",
                )
            )
        required_controls = requirements.required_controls if requirements else REQUIRED_CONTROLS
        for control_id in required_controls:
            attestation = self._latest_control(principal.workspace_id, control_id)
            gates.append(
                self._gate(
                    f"CONTROL_{control_id.upper()}",
                    f"Production control '{control_id}' has current evidence",
                    GatePhase.PROVIDER_CERTIFICATION,
                    attestation,
                    self._valid_attestation(attestation),
                    (f"evidence for {control_id}",),
                    "security_operations_owner",
                    ("security", "operations"),
                    "infrastructure_attestation",
                )
            )
        gates.append(
            self._gate(
                "READINESS_TEST_REPORT",
                "The deterministic safety suite passes with zero credentials and network calls",
                GatePhase.PROVIDER_CERTIFICATION,
                test_report,
                self._valid_test_report(test_report),
                ("passing M6.5 deterministic test report",),
                "quality_owner",
                ("security", "product"),
                "test_evidence",
            )
        )
        for presence_kind in ExternalPresenceKind:
            presence = self._latest_presence(principal.workspace_id, presence_kind)
            gates.append(
                self._gate(
                    f"PRESENCE_{presence_kind.value.upper()}",
                    f"Independent external-presence state {presence_kind.value} is evidenced",
                    GatePhase.FIRST_REAL_CONTACT,
                    presence,
                    self._valid_presence(presence),
                    (f"current {presence_kind.value} attestation",),
                    "sender_domain_owner",
                    ("security", "product", "privacy"),
                    "external_presence",
                )
            )
        provider = self._latest(
            principal.workspace_id, "provider_certification", ProviderCertificationRecord
        )
        gates.append(
            self._gate(
                "PROVIDER_CERTIFICATION",
                (
                    "A current version-specific one-message provider certification matches exact "
                    "policies"
                ),
                GatePhase.FIRST_REAL_CONTACT,
                provider,
                self._valid_provider(provider, envelope, policy, sources),
                ("certified provider/configuration with exact policy hashes",),
                "provider_owner",
                ("security", "privacy", "legal", "operations"),
                "provider_certification",
            )
        )
        operations = self._latest(
            principal.workspace_id, "operational_readiness", OperationalReadinessRecord
        )
        gates.append(
            self._gate(
                "OPERATIONAL_READINESS",
                (
                    "Owners, runbook, reply monitoring, kill switches and incident procedures are "
                    "current"
                ),
                GatePhase.FIRST_REAL_CONTACT,
                operations,
                self._valid_operations(operations),
                ("complete A-18 operational readiness attestation",),
                "operations_owner",
                ("operations", "security", "product"),
                "operational_readiness",
            )
        )
        provider_blocked = any(
            item.blocking
            and item.state == GateState.BLOCKED
            and item.phase == GatePhase.PROVIDER_CERTIFICATION
            for item in gates
        )
        first_contact_blocked = any(
            item.blocking
            and item.state == GateState.BLOCKED
            and item.phase == GatePhase.FIRST_REAL_CONTACT
            for item in gates
        )
        if provider_blocked:
            state = ReadinessState.NOT_READY
        elif first_contact_blocked:
            state = ReadinessState.READY_FOR_PROVIDER_CERTIFICATION
        else:
            state = ReadinessState.READY_FOR_FIRST_REAL_CONTACT_REVIEW
        inputs = tuple(
            self._ref(item)
            for item in (
                envelope,
                decisions,
                policy,
                sources,
                verification,
                authorization,
                retention,
                requirements,
                test_report,
                provider,
                operations,
            )
            if item is not None
        )
        blockers = tuple(item.gate_id for item in gates if item.state == GateState.BLOCKED)
        result_config = stable_hash(
            {
                "state": state,
                "inputs": [item.model_dump(mode="json") for item in inputs],
                "gates": [item.model_dump(mode="json") for item in gates],
            }
        )
        result = LiveActivationReadiness(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.5-readiness-evaluator-v1",
            configuration_hash=result_config,
            created_at=self._clock.now(),
            state=state,
            launch_envelope_id=envelope.id if envelope else None,
            input_manifest=inputs,
            gates=tuple(gates),
            blocking_gate_ids=blockers,
        )
        self._repository.save(result)
        return result

    def evaluate_shadow(
        self, principal: Principal, manifest: ShadowCandidateManifest
    ) -> ShadowReadinessAssessment:
        envelope = self._get_typed(
            principal.workspace_id,
            "launch_envelope",
            manifest.launch_envelope_id,
            LaunchEnvelopeRelease,
        )
        sources = self._get_typed(
            principal.workspace_id,
            "source_policy",
            manifest.source_policy_id,
            ContactSourcePolicyRelease,
        )
        verification = self._get_typed(
            principal.workspace_id,
            "verification_profile",
            manifest.verification_profile_id,
            VerificationProfileRelease,
        )
        policy = self._get_typed(
            principal.workspace_id,
            "outreach_policy",
            manifest.policy_release_id,
            ProductionOutreachPolicyRelease,
        )
        permissions = self._get_typed(
            principal.workspace_id,
            "real_data_permissions",
            manifest.permission_release_id,
            RealDataPermissionRelease,
        )
        blockers: list[str] = []
        if not self._valid_envelope(envelope):
            blockers.append("launch_envelope_not_active")
        if manifest.country != "US" or manifest.recipient_jurisdiction != "US-TX":
            blockers.append("recipient_jurisdiction_not_exact_texas_scope")
        if manifest.recipient_timezone is None:
            blockers.append("recipient_timezone_unknown")
        if not self._valid_policy(policy, envelope):
            blockers.append("production_policy_not_active_or_scope_mismatch")
        if not self._active(sources) or not sources.shadow_authorization_allowed:
            blockers.append("source_policy_not_approved_for_shadow")
        else:
            source_rule = next(
                (item for item in sources.rules if item.category == manifest.source_category), None
            )
            if source_rule is None or source_rule.status not in {
                SourceStatus.CONDITIONAL_CONTACT_USE,
                SourceStatus.APPROVED_CONTACT_USE,
            }:
                blockers.append("source_category_not_approved")
        if not self._active(verification) or not verification.shadow_authorization_allowed:
            blockers.append("verification_profile_not_approved_for_shadow")
        else:
            actual_scopes = set(manifest.proof_scopes)
            if not set(verification.required_scopes).issubset(actual_scopes):
                blockers.append("required_proof_scopes_missing")
            if not any(
                set(option).issubset(actual_scopes)
                for option in verification.association_alternatives
            ):
                blockers.append("person_contact_association_missing")
        permission_map = {item.activity: item.state for item in permissions.permissions}
        for activity in RealDataActivity:
            if permission_map.get(activity) != PermissionState.AUTHORIZED:
                blockers.append(f"permission_{activity.value}_not_authorized")
        if not set(REQUIRED_COMPLIANCE_SLOTS).issubset(manifest.compliance_slots):
            blockers.append("m5_compliance_slot_missing")
        if manifest.m5_revision_hash != manifest.expected_m5_revision_hash:
            blockers.append("m5_revision_hash_changed")
        if manifest.policy_hash != manifest.expected_policy_hash:
            blockers.append("policy_hash_changed")
        if manifest.policy_hash != policy.configuration_hash:
            blockers.append("policy_manifest_binding_mismatch")
        if manifest.suppression_tombstone_active:
            blockers.append("suppression_tombstone_active")
        lineage = (
            self._ref(envelope),
            self._ref(sources),
            self._ref(verification),
            self._ref(policy),
            self._ref(permissions),
        )
        result = ShadowReadinessAssessment(
            id=self._ids.new(),
            workspace_id=principal.workspace_id,
            version="m6.7-shadow-evaluator-v1",
            configuration_hash=stable_hash(
                {
                    "manifest": manifest.model_dump(mode="json"),
                    "blockers": blockers,
                }
            ),
            created_at=self._clock.now(),
            state=ShadowState.BLOCKED if blockers else ShadowState.SHADOW_READY,
            candidate_ref=manifest.candidate_ref,
            exact_lineage=lineage,
            policy_versions={
                "launch_envelope": envelope.version,
                "source_policy": sources.version,
                "verification_profile": verification.version,
                "outreach_policy": policy.version,
                "real_data_permissions": permissions.version,
            },
            blockers=tuple(blockers),
        )
        self._repository.save(result)
        return result

    def authorize_shadow(self, principal: Principal, assessment_id: UUID) -> None:
        self.get_record(principal, "shadow_readiness", assessment_id)
        raise ActivationValidationError("SHADOW_READY cannot be authorized or delivered")

    def get_record(
        self, principal: Principal, record_kind: str, record_id: UUID
    ) -> ActivationRecord:
        record = self._repository.get(principal.workspace_id, record_kind, record_id)
        if record is None:
            raise ActivationNotFoundError()
        return record

    def launch_envelope(self, principal: Principal) -> LaunchEnvelopeRelease:
        result = self._latest(principal.workspace_id, "launch_envelope", LaunchEnvelopeRelease)
        if result is None:
            raise ActivationNotFoundError()
        return result

    def m66_gate(self, principal: Principal) -> M66GateRelease:
        result = self._latest(principal.workspace_id, "m66_gate", M66GateRelease)
        if result is None:
            raise ActivationNotFoundError()
        return result

    def real_data_permissions(self, principal: Principal) -> RealDataPermissionRelease:
        result = self._latest(
            principal.workspace_id, "real_data_permissions", RealDataPermissionRelease
        )
        if result is None:
            raise ActivationNotFoundError()
        return result

    def _gate(
        self,
        gate_id: str,
        requirement: str,
        phase: GatePhase,
        artifact: ActivationRecordBase | None,
        satisfied: bool,
        missing_evidence: tuple[str, ...],
        accountable_role: str,
        approval_classes: tuple[str, ...],
        remediation_category: str,
    ) -> GateResult:
        return GateResult(
            gate_id=gate_id,
            requirement=requirement,
            state=GateState.SATISFIED if satisfied else GateState.BLOCKED,
            blocking=True,
            phase=phase,
            artifact=self._ref(artifact) if artifact else None,
            missing_evidence=() if satisfied else missing_evidence,
            accountable_role=accountable_role,
            required_approval_class=approval_classes,
            remediation_category=remediation_category,
            policy_config_version=artifact.version if artifact else "missing",
        )

    def _active(self, record: ActivationRecordBase | None) -> bool:
        if record is None:
            return False
        state = getattr(record, "state", None)
        effective = getattr(record, "effective_at", None)
        expires = getattr(record, "expires_at", None)
        return bool(
            state == ReleaseState.ACTIVE
            and effective is not None
            and expires is not None
            and effective <= self._clock.now() < expires
        )

    def _valid_envelope(self, record: LaunchEnvelopeRelease | None) -> bool:
        return bool(
            record
            and self._active(record)
            and record.country == "US"
            and record.recipient_jurisdictions == ("US-TX",)
            and not record.nationwide_authorization
            and record.recipient_count == 1
            and record.messages_per_authorization == 1
            and not any(
                (
                    record.links_allowed,
                    record.attachments_allowed,
                    record.tracking_allowed,
                    record.sequences_allowed,
                    record.delivery_enabled_by_default,
                )
            )
        )

    def _valid_policy(
        self,
        policy: ProductionOutreachPolicyRelease | None,
        envelope: LaunchEnvelopeRelease | None,
    ) -> bool:
        approvals = {item.approval_class for item in policy.approvals} if policy else set()
        return bool(
            policy
            and envelope
            and self._active(policy)
            and not policy.fixture_only
            and policy.legal_rules_populated
            and policy.allowed_recipient_jurisdictions == envelope.recipient_jurisdictions
            and policy.channel == envelope.channel
            and {"legal", "privacy", "security", "product"}.issubset(approvals)
            and all(
                (
                    policy.sender_legal_entity,
                    policy.suppression_scope,
                    policy.cadence_policy_ref,
                    policy.contact_time_policy_ref,
                    policy.behavior_policy_ref,
                    policy.privacy_rights_policy_ref,
                    policy.retention_policy_version,
                    policy.provider_constraints_ref,
                    policy.security_requirements_ref,
                    policy.sender_domain_requirements_ref,
                    policy.rollout_limits_ref,
                    policy.monitoring_ref,
                    policy.emergency_suspension_ref,
                )
            )
        )

    def _valid_sources(self, record: ContactSourcePolicyRelease | None) -> bool:
        if not (
            record
            and self._active(record)
            and not record.proposal_only
            and record.live_authorization_allowed
        ):
            return False
        categories = {item.category: item for item in record.rules}
        business = categories.get("business_controlled_professional_contact")
        referral = categories.get("first_party_confirmation_or_referral")
        enrichment = categories.get("third_party_enrichment")
        inferred = categories.get("inferred_pattern_address")
        return bool(
            business
            and business.real_outreach_allowed
            and referral
            and referral.real_outreach_allowed
            and enrichment
            and enrichment.status == SourceStatus.PROHIBITED
            and inferred
            and not inferred.real_outreach_allowed
        )

    def _valid_verification(self, record: VerificationProfileRelease | None) -> bool:
        required = {
            ProductionProofScope.SYNTAX_VALID,
            ProductionProofScope.DOMAIN_MAIL_CAPABLE,
            ProductionProofScope.MAILBOX_ACCEPTANCE_CURRENT,
            ProductionProofScope.PROFESSIONAL_CONTEXT_CURRENT,
            ProductionProofScope.SOURCE_USE_APPROVED,
        }
        alternatives = [set(item) for item in record.association_alternatives] if record else []
        return bool(
            record
            and self._active(record)
            and not record.proposal_only
            and record.live_authorization_allowed
            and required.issubset(record.required_scopes)
            and {ProductionProofScope.PERSON_CONTACT_ASSOCIATION} in alternatives
            and {ProductionProofScope.FIRST_PARTY_CONFIRMED} in alternatives
            and not record.inferred_pattern_sufficient
            and not record.third_party_enrichment_allowed
        )

    def _valid_authorization(self, record: AuthorizationPolicyRelease | None) -> bool:
        return bool(
            record
            and self._active(record)
            and record.content_reviewer_separate
            and record.contact_steward_separate
            and not record.self_authorization_allowed
            and record.step_up_required
            and record.authorization_expiry_policy_ref
            and record.reason_required
            and record.exact_one_message_acknowledgement
            and not record.hard_gate_override_allowed
        )

    def _valid_retention(self, record: RetentionPolicyRelease | None) -> bool:
        expected = {
            "person_identity_evidence",
            "contact_values",
            "verification_history",
            "communication_contexts",
            "eligibility_decisions",
            "suppression_records",
            "send_manifests",
            "human_authorizations",
            "delivery_attempts_receipts",
            "reply_bodies",
            "first_party_statements",
            "operational_audit_events",
        }
        present = {item.record_category for item in record.rules} if record else set()
        return bool(
            record
            and self._active(record)
            and record.complete
            and expected.issubset(present)
            and record.suppression_tombstone_policy_ref
            and all(
                item.retention_period_ref
                and item.deletion_process_ref
                and item.legal_hold_process_ref
                for item in record.rules
            )
        )

    def _valid_review(
        self,
        record: GovernanceReviewRecord | None,
        envelope: LaunchEnvelopeRelease | None,
    ) -> bool:
        return bool(
            record
            and envelope
            and record.state == AttestationState.EVIDENCED
            and record.scope_hash == envelope.configuration_hash
            and record.evidence_refs
            and record.effective_at <= self._clock.now() < record.expires_at
        )

    def _valid_attestation(self, record: InfrastructureControlAttestation | None) -> bool:
        return bool(
            record
            and record.state == AttestationState.EVIDENCED
            and record.evidence_refs
            and record.effective_at <= self._clock.now() < record.expires_at
        )

    def _valid_presence(self, record: ExternalPresenceAttestation | None) -> bool:
        return bool(
            record
            and record.state == AttestationState.EVIDENCED
            and record.evidence_refs
            and record.effective_at <= self._clock.now() < record.expires_at
        )

    def _valid_provider(
        self,
        record: ProviderCertificationRecord | None,
        envelope: LaunchEnvelopeRelease | None,
        policy: ProductionOutreachPolicyRelease | None,
        sources: ContactSourcePolicyRelease | None,
    ) -> bool:
        return bool(
            record
            and envelope
            and policy
            and sources
            and record.state == CertificationState.CERTIFIED
            and record.effective_at <= self._clock.now() < record.expires_at
            and record.launch_envelope_hash == envelope.configuration_hash
            and record.policy_hash == policy.configuration_hash
            and record.source_policy_hash == sources.configuration_hash
            and record.tracking_disabled
            and record.one_message_only
            and record.ambiguous_submit_reconciliation
            and record.signed_webhooks
            and record.replay_protection
            and record.provider_only_egress
            and record.secret_isolation
        )

    def _valid_operations(self, record: OperationalReadinessRecord | None) -> bool:
        required_roles = {
            "send_operator",
            "legal_privacy_owner",
            "security_owner",
            "sender_mailbox_owner",
            "incident_owner",
            "suppression_owner",
            "kill_switch_owner",
            "provider_owner",
            "monitoring_owner",
            "reply_monitoring_owner",
        }
        return bool(
            record
            and record.state == AttestationState.EVIDENCED
            and required_roles.issubset(record.accountable_roles)
            and record.runbook_ref
            and record.reply_monitoring_evidenced
            and record.kill_switch_evidenced
            and not record.complaint_threshold_suspended
            and record.provider_outage_procedure_ref
            and record.ambiguous_status_procedure_ref
            and record.effective_at <= self._clock.now() < record.expires_at
        )

    def _valid_test_report(self, record: ReadinessTestReport | None) -> bool:
        return bool(
            record
            and record.state == AttestationState.EVIDENCED
            and not record.failed_case_ids
            and set(REQUIRED_TEST_CASES).issubset(record.passed_case_ids)
            and record.network_call_count == 0
            and record.credential_count == 0
        )

    def _missing_decisions(self, snapshot: ActivationDecisionSnapshot | None) -> tuple[str, ...]:
        decisions = {item.decision_id: item for item in snapshot.decisions} if snapshot else {}
        return tuple(
            f"{decision_id} accepted decision with owner and evidence"
            for decision_id in REQUIRED_DECISIONS
            if decision_id not in decisions
            or decisions[decision_id].status != DecisionStatus.ACCEPTED
            or not decisions[decision_id].accountable_role
            or not decisions[decision_id].evidence_refs
        )

    def _latest(
        self, workspace_id: UUID, record_kind: str, record_type: type[TRecord]
    ) -> TRecord | None:
        records = [
            item
            for item in self._repository.list(workspace_id, record_kind)
            if isinstance(item, record_type)
        ]
        return max(records, key=lambda item: item.created_at) if records else None

    def _get_typed(
        self,
        workspace_id: UUID,
        record_kind: str,
        record_id: UUID,
        record_type: type[TRecord],
    ) -> TRecord:
        record = self._repository.get(workspace_id, record_kind, record_id)
        if not isinstance(record, record_type):
            raise ActivationNotFoundError()
        return record

    def _latest_control(
        self, workspace_id: UUID, control_id: str
    ) -> InfrastructureControlAttestation | None:
        records = [
            item
            for item in self._repository.list(workspace_id, "infrastructure_attestation")
            if isinstance(item, InfrastructureControlAttestation) and item.control_id == control_id
        ]
        return max(records, key=lambda item: item.created_at) if records else None

    def _latest_presence(
        self, workspace_id: UUID, kind: ExternalPresenceKind
    ) -> ExternalPresenceAttestation | None:
        records = [
            item
            for item in self._repository.list(workspace_id, "external_presence")
            if isinstance(item, ExternalPresenceAttestation) and item.kind == kind
        ]
        return max(records, key=lambda item: item.created_at) if records else None

    def _latest_review(
        self, workspace_id: UUID, review_class: str
    ) -> GovernanceReviewRecord | None:
        records = [
            item
            for item in self._repository.list(workspace_id, "governance_review")
            if isinstance(item, GovernanceReviewRecord) and item.review_class == review_class
        ]
        return max(records, key=lambda item: item.created_at) if records else None

    @staticmethod
    def _ref(record: ActivationRecordBase) -> ArtifactReference:
        return ArtifactReference(
            record_kind=record.record_kind,
            artifact_id=record.id,
            version=record.version,
            configuration_hash=record.configuration_hash,
        )

    @staticmethod
    def _decision_owner(decision_id: str) -> str:
        return {
            "A-07": "security_owner",
            "A-08": "privacy_data_governance_owner",
            "A-09": "data_governance_owner",
            "A-15": "product_owner",
            "A-16": "product_owner",
            "A-17": "legal_privacy_owner",
            "A-18": "operations_owner",
            "A-20": "product_owner",
        }.get(decision_id, "architecture_owner")

    @staticmethod
    def _decision_approvals(decision_id: str) -> tuple[str, ...]:
        return {
            "A-08": ("privacy", "legal", "security"),
            "A-09": ("legal", "privacy", "product"),
            "A-17": ("legal", "privacy", "security", "product"),
            "A-18": ("operations", "security", "product"),
        }.get(decision_id, ("product", "security"))
