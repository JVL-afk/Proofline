from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from conftest import TOKEN, WORKSPACE_ID, FakeClock
from fastapi.testclient import TestClient
from opintel_activation.application import (
    REQUIRED_COMPLIANCE_SLOTS,
    REQUIRED_CONTROLS,
    REQUIRED_DECISIONS,
    REQUIRED_TEST_CASES,
    ActivationReadinessService,
)
from opintel_activation.domain import (
    ActivationDecisionSnapshot,
    ActivationNotFoundError,
    ActivationValidationError,
    AttestationState,
    AuthorizationPolicyRelease,
    CertificationState,
    ContactSourcePolicyRelease,
    DecisionEntry,
    DecisionStatus,
    ExternalPresenceAttestation,
    ExternalPresenceKind,
    GateState,
    GovernanceReviewRecord,
    InfrastructureControlAttestation,
    OperationalReadinessRecord,
    PermissionState,
    PolicyApproval,
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
    RetentionRule,
    ShadowCandidateManifest,
    ShadowState,
    SourceRule,
    SourceStatus,
    VerificationProfileRelease,
    stable_hash,
)
from opintel_contact.domain import Stage
from opintel_contact_local import SqlAlchemyContactRepository
from opintel_m0.domain import Principal, Role

RETENTION_CATEGORIES = (
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
)


def principal_for(client: TestClient) -> Principal:
    principal = client.app.state.authenticator.authenticate(TOKEN)
    assert principal is not None
    return principal


def approvals(clock: FakeClock) -> tuple[PolicyApproval, ...]:
    return tuple(
        PolicyApproval(
            approval_class=approval_class,
            accountable_role=f"{approval_class}_owner",
            evidence_ref=f"fixture://m6.5/approval/{approval_class}",
            approved_at=clock.now(),
        )
        for approval_class in ("legal", "privacy", "security", "product")
    )


def satisfy_provider_phase(
    service: ActivationReadinessService,
    principal: Principal,
    clock: FakeClock,
) -> dict[str, object]:
    clock.advance(timedelta(seconds=1))
    now = clock.now()
    expires = now + timedelta(days=30)
    envelope = service.launch_envelope(principal)
    decision_entries = tuple(
        DecisionEntry(
            decision_id=item,
            status=DecisionStatus.ACCEPTED,
            accountable_role=f"owner_{item.lower()}",
            evidence_refs=(f"fixture://m6.5/decision/{item}",),
            approval_classes=("product", "security"),
        )
        for item in REQUIRED_DECISIONS
    )
    decisions = ActivationDecisionSnapshot(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="accepted-decisions-test-v1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in decision_entries]),
        created_at=now,
        decisions=decision_entries,
    )
    service.save_record(principal, decisions)
    policy = ProductionOutreachPolicyRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="production-policy-test-v1",
        configuration_hash=stable_hash("production-policy-test-v1"),
        created_at=now,
        state=ReleaseState.ACTIVE,
        fixture_only=False,
        legal_rules_populated=True,
        sender_legal_entity="Fixture Legal Entity",
        allowed_sender_jurisdictions=("US-TX",),
        allowed_recipient_jurisdictions=("US-TX",),
        channel="b2b_email",
        message_purpose="inbound_lead_response_qualification",
        permitted_source_categories=(
            "business_controlled_professional_contact",
            "first_party_confirmation_or_referral",
        ),
        required_proof_scopes=tuple(ProductionProofScope),
        required_disclosure_slots=REQUIRED_COMPLIANCE_SLOTS,
        suppression_scope="workspace_entity_channel",
        cadence_policy_ref="fixture://m6.5/policy/cadence",
        contact_time_policy_ref="fixture://m6.5/policy/contact-time",
        behavior_policy_ref="fixture://m6.5/policy/behavior",
        privacy_rights_policy_ref="fixture://m6.5/policy/rights",
        retention_policy_version="retention-test-v1",
        provider_constraints_ref="fixture://m6.5/policy/provider",
        security_requirements_ref="fixture://m6.5/policy/security",
        sender_domain_requirements_ref="fixture://m6.5/policy/sender",
        rollout_limits_ref="fixture://m6.5/policy/rollout",
        monitoring_ref="fixture://m6.5/policy/monitoring",
        emergency_suspension_ref="fixture://m6.5/policy/suspension",
        approvals=approvals(clock),
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, policy)
    source_rules = (
        SourceRule(
            category="business_controlled_professional_contact",
            status=SourceStatus.APPROVED_CONTACT_USE,
            permitted_acquisition="fixture approved",
            permitted_use="fixture shadow and live policy test",
            provenance_required=True,
            proof_scopes=(
                ProductionProofScope.SOURCE_OBSERVED,
                ProductionProofScope.PERSON_CONTACT_ASSOCIATION,
            ),
            freshness_policy_ref="fixture://m6.5/source/freshness",
            restrictions=("US-TX",),
            real_outreach_allowed=True,
        ),
        SourceRule(
            category="first_party_confirmation_or_referral",
            status=SourceStatus.APPROVED_CONTACT_USE,
            permitted_acquisition="fixture approved",
            permitted_use="fixture shadow and live policy test",
            provenance_required=True,
            proof_scopes=(ProductionProofScope.FIRST_PARTY_CONFIRMED,),
            freshness_policy_ref="fixture://m6.5/source/freshness",
            restrictions=("reverify",),
            real_outreach_allowed=True,
        ),
        SourceRule(
            category="third_party_enrichment",
            status=SourceStatus.PROHIBITED,
            permitted_acquisition="none",
            permitted_use="none",
            provenance_required=True,
            proof_scopes=(),
            freshness_policy_ref=None,
            restrictions=("prohibited",),
            real_outreach_allowed=False,
        ),
        SourceRule(
            category="inferred_pattern_address",
            status=SourceStatus.IDENTITY_ONLY,
            permitted_acquisition="candidate only",
            permitted_use="not sufficient proof",
            provenance_required=True,
            proof_scopes=(),
            freshness_policy_ref=None,
            restrictions=("not sendable",),
            real_outreach_allowed=False,
        ),
    )
    sources = ContactSourcePolicyRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="source-policy-test-v1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in source_rules]),
        created_at=now,
        state=ReleaseState.ACTIVE,
        proposal_only=False,
        live_authorization_allowed=True,
        shadow_authorization_allowed=True,
        rules=source_rules,
        approvals=approvals(clock),
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, sources)
    required_scopes = (
        ProductionProofScope.SYNTAX_VALID,
        ProductionProofScope.DOMAIN_MAIL_CAPABLE,
        ProductionProofScope.MAILBOX_ACCEPTANCE_CURRENT,
        ProductionProofScope.PROFESSIONAL_CONTEXT_CURRENT,
        ProductionProofScope.SOURCE_USE_APPROVED,
    )
    verification = VerificationProfileRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="verification-test-v1",
        configuration_hash=stable_hash([item.value for item in required_scopes]),
        created_at=now,
        state=ReleaseState.ACTIVE,
        proposal_only=False,
        live_authorization_allowed=True,
        shadow_authorization_allowed=True,
        required_scopes=required_scopes,
        association_alternatives=(
            (ProductionProofScope.PERSON_CONTACT_ASSOCIATION,),
            (ProductionProofScope.FIRST_PARTY_CONFIRMED,),
        ),
        approvals=approvals(clock),
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, verification)
    authorization = AuthorizationPolicyRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="authorization-test-v1",
        configuration_hash=stable_hash("authorization-test-v1"),
        created_at=now,
        state=ReleaseState.ACTIVE,
        content_reviewer_separate=True,
        contact_steward_separate=True,
        self_authorization_allowed=False,
        step_up_required=True,
        authorization_expiry_policy_ref="fixture://m6.5/auth/expiry",
        reason_required=True,
        exact_one_message_acknowledgement=True,
        hard_gate_override_allowed=False,
        approvals=approvals(clock),
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, authorization)
    rules = tuple(
        RetentionRule(
            record_category=item,
            classification="confidential",
            encrypted=True,
            redacted_display=True,
            routine_logging_allowed=False,
            retention_period_ref=f"fixture://m6.5/retention/{item}",
            deletion_process_ref="fixture://m6.5/retention/deletion",
            tombstone_behavior_ref=(
                "fixture://m6.5/retention/tombstone"
                if item in {"contact_values", "suppression_records"}
                else None
            ),
            legal_hold_process_ref="fixture://m6.5/retention/legal-hold",
        )
        for item in RETENTION_CATEGORIES
    )
    retention = RetentionPolicyRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="retention-test-v1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in rules]),
        created_at=now,
        state=ReleaseState.ACTIVE,
        complete=True,
        rules=rules,
        suppression_tombstone_policy_ref="fixture://m6.5/retention/tombstone",
        approvals=approvals(clock),
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, retention)
    for review_class in ("legal", "privacy", "security", "product"):
        service.save_record(
            principal,
            GovernanceReviewRecord(
                id=uuid4(),
                workspace_id=principal.workspace_id,
                version=f"{review_class}-review-test-v1",
                configuration_hash=stable_hash(review_class),
                created_at=now,
                review_class=review_class,
                state=AttestationState.EVIDENCED,
                scope_hash=envelope.configuration_hash,
                evidence_refs=(f"fixture://m6.5/review/{review_class}",),
                accountable_role=f"{review_class}_owner",
                effective_at=now,
                expires_at=expires,
            ),
        )
    for control_id in REQUIRED_CONTROLS:
        service.save_record(
            principal,
            InfrastructureControlAttestation(
                id=uuid4(),
                workspace_id=principal.workspace_id,
                version=f"{control_id}-test-v1",
                configuration_hash=stable_hash(control_id),
                created_at=now,
                control_id=control_id,
                state=AttestationState.EVIDENCED,
                evidence_refs=(f"fixture://m6.5/control/{control_id}",),
                attested_by="security_operations_owner",
                effective_at=now,
                expires_at=expires,
            ),
        )
    test_report = ReadinessTestReport(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="readiness-tests-v1",
        configuration_hash=stable_hash(REQUIRED_TEST_CASES),
        created_at=now,
        state=AttestationState.EVIDENCED,
        suite_version="m6.5-deterministic-v1",
        passed_case_ids=REQUIRED_TEST_CASES,
        failed_case_ids=(),
        network_call_count=0,
        credential_count=0,
    )
    service.save_record(principal, test_report)
    return {
        "envelope": envelope,
        "policy": policy,
        "sources": sources,
        "verification": verification,
        "authorization": authorization,
        "retention": retention,
    }


def satisfy_first_contact_phase(
    service: ActivationReadinessService,
    principal: Principal,
    clock: FakeClock,
    records: dict[str, object],
) -> dict[str, object]:
    clock.advance(timedelta(seconds=1))
    now = clock.now()
    expires = now + timedelta(days=30)
    envelope = records["envelope"]
    policy = records["policy"]
    sources = records["sources"]
    assert hasattr(envelope, "configuration_hash")
    assert hasattr(policy, "configuration_hash")
    assert hasattr(sources, "configuration_hash")
    for kind in ExternalPresenceKind:
        service.save_record(
            principal,
            ExternalPresenceAttestation(
                id=uuid4(),
                workspace_id=principal.workspace_id,
                version=f"{kind.value}-test-v1",
                configuration_hash=stable_hash(kind),
                created_at=now,
                kind=kind,
                state=AttestationState.EVIDENCED,
                subject_ref=f"fixture://m6.5/presence/{kind.value}",
                evidence_refs=(f"fixture://m6.5/presence/{kind.value}/evidence",),
                attested_by="sender_domain_owner",
                effective_at=now,
                expires_at=expires,
            ),
        )
    provider = ProviderCertificationRecord(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="provider-cert-test-v1",
        configuration_hash=stable_hash("provider-cert-test-v1"),
        created_at=now,
        provider_ref="fixture-provider",
        deployment_ref="fixture-deployment",
        state=CertificationState.CERTIFIED,
        launch_envelope_hash=envelope.configuration_hash,
        policy_hash=policy.configuration_hash,
        source_policy_hash=sources.configuration_hash,
        tracking_disabled=True,
        one_message_only=True,
        ambiguous_submit_reconciliation=True,
        signed_webhooks=True,
        replay_protection=True,
        provider_only_egress=True,
        secret_isolation=True,
        test_report_ref="fixture://m6.5/provider/test-report",
        contractual_review_ref="fixture://m6.5/provider/contract",
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, provider)
    roles = {
        item: f"fixture_{item}"
        for item in (
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
        )
    }
    operations = OperationalReadinessRecord(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="operations-test-v1",
        configuration_hash=stable_hash(roles),
        created_at=now,
        state=AttestationState.EVIDENCED,
        accountable_roles=roles,
        runbook_ref="fixture://m6.5/operations/runbook",
        reply_monitoring_evidenced=True,
        kill_switch_evidenced=True,
        complaint_threshold_suspended=False,
        provider_outage_procedure_ref="fixture://m6.5/operations/provider-outage",
        ambiguous_status_procedure_ref="fixture://m6.5/operations/ambiguous",
        effective_at=now,
        expires_at=expires,
    )
    service.save_record(principal, operations)
    records.update({"provider": provider, "operations": operations})
    return records


def shadow_permissions(
    service: ActivationReadinessService, principal: Principal, clock: FakeClock
) -> RealDataPermissionRelease:
    clock.advance(timedelta(seconds=1))
    now = clock.now()
    permissions = tuple(
        RealDataPermission(
            activity=activity,
            state=PermissionState.AUTHORIZED,
            approval_refs=(f"fixture://m6.5/permission/{activity.value}",),
            policy_versions={"shadow": "v1"},
        )
        for activity in RealDataActivity
    )
    result = RealDataPermissionRelease(
        id=uuid4(),
        workspace_id=principal.workspace_id,
        version="shadow-permissions-test-v1",
        configuration_hash=stable_hash([item.model_dump(mode="json") for item in permissions]),
        created_at=now,
        state=ReleaseState.ACTIVE,
        permissions=permissions,
        effective_at=now,
        expires_at=now + timedelta(days=30),
    )
    service.save_record(principal, result)
    return result


def valid_shadow_manifest(
    records: dict[str, object], permissions: RealDataPermissionRelease
) -> ShadowCandidateManifest:
    envelope = records["envelope"]
    sources = records["sources"]
    verification = records["verification"]
    policy = records["policy"]
    assert hasattr(envelope, "id")
    assert hasattr(sources, "id")
    assert hasattr(verification, "id")
    assert hasattr(policy, "id") and hasattr(policy, "configuration_hash")
    m5_hash = stable_hash("approved-m5-fixture")
    return ShadowCandidateManifest(
        candidate_ref="fixture://m6.7/candidate/one",
        launch_envelope_id=envelope.id,
        country="US",
        recipient_jurisdiction="US-TX",
        recipient_timezone="America/Chicago",
        source_category="business_controlled_professional_contact",
        source_policy_id=sources.id,
        verification_profile_id=verification.id,
        policy_release_id=policy.id,
        permission_release_id=permissions.id,
        proof_scopes=(
            ProductionProofScope.SYNTAX_VALID,
            ProductionProofScope.DOMAIN_MAIL_CAPABLE,
            ProductionProofScope.MAILBOX_ACCEPTANCE_CURRENT,
            ProductionProofScope.PROFESSIONAL_CONTEXT_CURRENT,
            ProductionProofScope.SOURCE_USE_APPROVED,
            ProductionProofScope.PERSON_CONTACT_ASSOCIATION,
        ),
        m5_revision_id=uuid4(),
        m5_revision_hash=m5_hash,
        expected_m5_revision_hash=m5_hash,
        policy_hash=policy.configuration_hash,
        expected_policy_hash=policy.configuration_hash,
        compliance_slots=REQUIRED_COMPLIANCE_SLOTS,
        suppression_tombstone_active=False,
    )


@pytest.mark.integration
def test_default_readiness_is_explicit_not_ready_and_creates_no_m6_send_state(
    client: TestClient,
    auth_headers: dict[str, str],
    contact_repository: SqlAlchemyContactRepository,
) -> None:
    before = {
        kind: len(contact_repository.list(WORKSPACE_ID, kind))
        for kind in ("stage", "manifest", "readiness", "authorization", "attempt")
    }
    response = client.get("/api/v1/live-activation/readiness", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness"]["state"] == ReadinessState.NOT_READY
    assert payload["readiness"]["aggregate_score"] is None
    assert payload["live_delivery_enabled"] is False
    gates = {item["gate_id"]: item for item in payload["readiness"]["gates"]}
    assert gates["A17_POLICY_RELEASE"]["state"] == GateState.BLOCKED
    assert gates["A17_POLICY_RELEASE"]["artifact"] is None
    assert gates["A17_POLICY_RELEASE"]["missing_evidence"] == [
        "active signed non-fixture A-17 production policy release"
    ]
    assert gates["CONTROL_FIELD_ENCRYPTION_EVIDENCED"]["state"] == GateState.BLOCKED
    after = {
        kind: len(contact_repository.list(WORKSPACE_ID, kind))
        for kind in ("stage", "manifest", "readiness", "authorization", "attempt")
    }
    assert after == before


def test_texas_envelope_m66_gate_and_phased_permissions_are_exact(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    envelope = client.get("/api/v1/live-activation/launch-envelope", headers=auth_headers).json()[
        "record"
    ]
    assert envelope["country"] == "US"
    assert envelope["recipient_jurisdictions"] == ["US-TX"]
    assert envelope["nationwide_authorization"] is False
    assert envelope["delivery_enabled_by_default"] is False
    assert envelope["links_allowed"] is False
    assert envelope["attachments_allowed"] is False
    gate = client.get("/api/v1/live-activation/m6-6-gate", headers=auth_headers).json()["record"]
    assert gate["live_delivery_readiness_required"] is False
    assert gate["ai_authoritative"] is False
    permissions = client.get(
        "/api/v1/live-activation/m6-7-real-data-permissions", headers=auth_headers
    ).json()["record"]["permissions"]
    assert [item["activity"] for item in permissions] == [item.value for item in RealDataActivity]
    assert all(item["state"] == PermissionState.NOT_AUTHORIZED for item in permissions)


def test_provider_and_first_contact_readiness_are_deterministic(
    client: TestClient, clock: FakeClock
) -> None:
    principal = principal_for(client)
    service = client.app.state.activation_service
    records = satisfy_provider_phase(service, principal, clock)
    result = service.evaluate(principal)
    assert result.state == ReadinessState.READY_FOR_PROVIDER_CERTIFICATION
    assert all(
        item.state == GateState.SATISFIED
        for item in result.gates
        if item.phase == "provider_certification"
    )
    satisfy_first_contact_phase(service, principal, clock, records)
    result = service.evaluate(principal)
    assert result.state == ReadinessState.READY_FOR_FIRST_REAL_CONTACT_REVIEW
    assert not result.blocking_gate_ids
    assert result.manually_promoted is False


@pytest.mark.parametrize(
    ("mutation", "expected_gate"),
    [
        ("expired_policy", "A17_POLICY_RELEASE"),
        ("retention_gap", "A08_RETENTION_POLICY"),
        ("missing_step_up", "PRODUCTION_AUTHORIZATION_POLICY"),
        ("provider_drift", "PROVIDER_CERTIFICATION"),
        ("sender_failure", "PRESENCE_SENDER_DOMAIN_VERIFIED"),
        ("complaint_suspension", "OPERATIONAL_READINESS"),
        ("reply_monitoring_failure", "OPERATIONAL_READINESS"),
        ("kill_switch_failure", "OPERATIONAL_READINESS"),
    ],
)
def test_readiness_regresses_on_expiry_drift_and_operational_failures(
    client: TestClient,
    clock: FakeClock,
    mutation: str,
    expected_gate: str,
) -> None:
    principal = principal_for(client)
    service = client.app.state.activation_service
    records = satisfy_first_contact_phase(
        service, principal, clock, satisfy_provider_phase(service, principal, clock)
    )
    assert service.evaluate(principal).state == ReadinessState.READY_FOR_FIRST_REAL_CONTACT_REVIEW
    clock.advance(timedelta(seconds=1))
    now = clock.now()
    if mutation == "expired_policy":
        value = records["policy"].model_copy(
            update={
                "id": uuid4(),
                "version": "expired-policy",
                "created_at": now,
                "effective_at": now - timedelta(days=2),
                "expires_at": now - timedelta(days=1),
            }
        )
    elif mutation == "retention_gap":
        value = records["retention"].model_copy(
            update={
                "id": uuid4(),
                "version": "retention-gap",
                "created_at": now,
                "complete": False,
            }
        )
    elif mutation == "missing_step_up":
        value = records["authorization"].model_copy(
            update={
                "id": uuid4(),
                "version": "missing-step-up",
                "created_at": now,
                "step_up_required": False,
            }
        )
    elif mutation == "provider_drift":
        value = records["provider"].model_copy(
            update={
                "id": uuid4(),
                "version": "provider-policy-drift",
                "created_at": now,
                "policy_hash": stable_hash("drift"),
            }
        )
    elif mutation == "sender_failure":
        value = ExternalPresenceAttestation(
            id=uuid4(),
            workspace_id=principal.workspace_id,
            version="sender-domain-failed",
            configuration_hash=stable_hash("sender-domain-failed"),
            created_at=now,
            kind=ExternalPresenceKind.SENDER_DOMAIN_VERIFIED,
            state=AttestationState.FAILED,
            subject_ref="fixture://m6.5/sender/failure",
            evidence_refs=("fixture://m6.5/sender/failure/evidence",),
            attested_by="security_owner",
            effective_at=now,
            expires_at=now + timedelta(days=1),
        )
    else:
        operations = records["operations"]
        updates: dict[str, object] = {"id": uuid4(), "version": mutation, "created_at": now}
        if mutation == "complaint_suspension":
            updates["complaint_threshold_suspended"] = True
        elif mutation == "reply_monitoring_failure":
            updates["reply_monitoring_evidenced"] = False
        else:
            updates["kill_switch_evidenced"] = False
        value = operations.model_copy(update=updates)
    service.save_record(principal, value)
    result = service.evaluate(principal)
    gate = next(item for item in result.gates if item.gate_id == expected_gate)
    assert gate.state == GateState.BLOCKED
    assert result.state != ReadinessState.READY_FOR_FIRST_REAL_CONTACT_REVIEW


@pytest.mark.parametrize(
    ("change", "blocker"),
    [
        ({"recipient_jurisdiction": "US"}, "recipient_jurisdiction_not_exact_texas_scope"),
        ({"recipient_timezone": None}, "recipient_timezone_unknown"),
        (
            {"proof_scopes": (ProductionProofScope.SYNTAX_VALID,)},
            "required_proof_scopes_missing",
        ),
        ({"compliance_slots": ("sender_signature",)}, "m5_compliance_slot_missing"),
        ({"m5_revision_hash": stable_hash("changed")}, "m5_revision_hash_changed"),
        ({"policy_hash": stable_hash("changed")}, "policy_hash_changed"),
        ({"suppression_tombstone_active": True}, "suppression_tombstone_active"),
        ({"source_category": "third_party_enrichment"}, "source_category_not_approved"),
    ],
)
def test_shadow_ready_fails_closed_for_scope_proof_hash_and_suppression(
    client: TestClient,
    clock: FakeClock,
    change: dict[str, object],
    blocker: str,
) -> None:
    principal = principal_for(client)
    service = client.app.state.activation_service
    records = satisfy_provider_phase(service, principal, clock)
    permissions = shadow_permissions(service, principal, clock)
    manifest = valid_shadow_manifest(records, permissions).model_copy(update=change)
    result = service.evaluate_shadow(principal, manifest)
    assert result.state == ShadowState.BLOCKED
    assert blocker in result.blockers
    assert result.can_create_m6_send_ready is False
    assert result.can_transition_to_send_authorized is False
    assert result.consumable_by_delivery_worker is False


def test_shadow_ready_is_mandatory_distinct_and_cannot_authorize_or_deliver(
    client: TestClient, clock: FakeClock
) -> None:
    principal = principal_for(client)
    service = client.app.state.activation_service
    records = satisfy_provider_phase(service, principal, clock)
    permissions = shadow_permissions(service, principal, clock)
    result = service.evaluate_shadow(principal, valid_shadow_manifest(records, permissions))
    assert result.state == ShadowState.SHADOW_READY
    assert result.can_create_m6_send_ready is False
    with pytest.raises(ActivationValidationError):
        service.authorize_shadow(principal, result.id)


def test_real_data_permissions_are_independent_and_retention_permission_gap_blocks_shadow(
    client: TestClient, clock: FakeClock
) -> None:
    principal = principal_for(client)
    service = client.app.state.activation_service
    records = satisfy_provider_phase(service, principal, clock)
    permissions = shadow_permissions(service, principal, clock)
    clock.advance(timedelta(seconds=1))
    changed = tuple(
        item.model_copy(
            update={"state": PermissionState.NOT_AUTHORIZED}
            if item.activity == RealDataActivity.REAL_CONTACT_STORAGE
            else {}
        )
        for item in permissions.permissions
    )
    partial = permissions.model_copy(
        update={
            "id": uuid4(),
            "version": "contact-storage-not-authorized",
            "created_at": clock.now(),
            "permissions": changed,
        }
    )
    service.save_record(principal, partial)
    manifest = valid_shadow_manifest(records, partial)
    result = service.evaluate_shadow(principal, manifest)
    assert result.state == ShadowState.BLOCKED
    assert "permission_real_contact_storage_not_authorized" in result.blockers
    assert not any(
        item.state == PermissionState.AUTHORIZED
        for item in changed
        if item.activity == RealDataActivity.REAL_CONTACT_STORAGE
    )


@pytest.mark.security
def test_workspace_authorization_and_no_live_surfaces(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/live-activation/readiness", headers=auth_headers)
    readiness_id = UUID(response.json()["readiness"]["id"])
    assert (
        client.get(f"/api/v1/live-activation/readiness-revisions/{readiness_id}").status_code == 401
    )
    other = Principal(
        subject="other-workspace-reviewer",
        workspace_id=uuid4(),
        roles=frozenset({Role.REVIEWER}),
    )
    with pytest.raises(ActivationNotFoundError):
        client.app.state.activation_service.get_record(other, "activation_readiness", readiness_id)
    paths = set(client.app.openapi()["paths"])
    assert not any(
        token in path.lower()
        for path in paths
        for token in (
            "live-provider",
            "provider-submit",
            "domain-purchase",
            "contact-enrichment",
            "real-data-import",
            "shadow-authorizations",
            "shadow-deliveries",
            "m6-6-tournament",
        )
    )
    assert client.app.state.mock_delivery_provider.network_call_count == 0
    assert all(stage.value not in str(response.json()) for stage in Stage)
