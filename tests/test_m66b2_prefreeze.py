from __future__ import annotations

import socket
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from opintel_qualification.domain import CorpusPartition
from opintel_qualification.tournament2_domain import (
    PostTournamentState,
    RecommendationDisposition,
    TournamentTask,
)
from opintel_qualification.tournament2_prefreeze import (
    ADDITIONAL_PROVIDER_ACCOUNT_REQUIRED,
    BINDINGS,
    DRAFT_MANIFEST,
    DRAFT_MANIFEST_HASH,
    MINIMAL_FALLBACK_ROSTER,
    REQUIRED_FUTURE_CREDENTIAL_CLASSES,
    REVIEWER_POLICY,
    DraftManifestState,
    ResolutionClass,
    SchemaFamily,
    VersionIdentityStatus,
    binding_cost_projections,
    certification_plan,
    objective_dominance_disposition,
    price_for,
    validate_draft_manifest,
    visible_token_projections,
)
from opintel_qualification.tournament2_reporting import (
    TaskReportRow,
    TournamentReport,
    validate_report,
)


def test_exact_roster_and_twelve_include_bindings_are_draft_only() -> None:
    assert DRAFT_MANIFEST.state is DraftManifestState.DRAFT
    assert {item.model for item in DRAFT_MANIFEST.deployments} == {
        "gpt-5.6-sol",
        "claude-sonnet-5",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    }
    assert len(BINDINGS) == 12
    actual = {(item.deployment_key, item.task) for item in BINDINGS}
    assert actual == {
        ("openai-gpt-5.6-sol", TournamentTask.EVIDENCE_INTERPRETATION),
        ("openai-gpt-5.6-sol", TournamentTask.CONTRADICTION_ANALYSIS),
        ("openai-gpt-5.6-sol", TournamentTask.OPPORTUNITY_REASONING),
        ("anthropic-claude-sonnet-5", TournamentTask.EVIDENCE_INTERPRETATION),
        ("anthropic-claude-sonnet-5", TournamentTask.CONTRADICTION_ANALYSIS),
        ("anthropic-claude-sonnet-5", TournamentTask.OPPORTUNITY_REASONING),
        ("anthropic-claude-sonnet-5", TournamentTask.AUDIT_WORDING),
        ("anthropic-claude-sonnet-5", TournamentTask.OUTREACH_WORDING),
        ("google-gemini-3.6-flash", TournamentTask.AUDIT_WORDING),
        ("google-gemini-3.6-flash", TournamentTask.OUTREACH_WORDING),
        ("google-gemini-3.5-flash-lite", TournamentTask.REPLY_CLASSIFICATION),
        (
            "google-gemini-3.5-flash-lite",
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
        ),
    }
    assert all("subject" not in item.task.value for item in BINDINGS)
    assert len(DRAFT_MANIFEST_HASH) == 64
    assert MINIMAL_FALLBACK_ROSTER == (
        "openai-gpt-5.6-sol",
        "anthropic-claude-sonnet-5",
        "google-gemini-3.5-flash-lite",
    )


def test_google_uses_stable_v1_and_every_external_capability_is_disabled() -> None:
    google = [item for item in DRAFT_MANIFEST.deployments if item.provider == "google"]
    assert {item.configuration.endpoint for item in google} == {"/v1/interactions"}
    assert {item.configuration.api_revision for item in google} == {"v1"}
    for deployment in DRAFT_MANIFEST.deployments:
        config = deployment.configuration
        assert not config.tools_enabled
        assert not config.browsing_enabled
        assert not config.file_access_enabled
        assert not config.function_calling_enabled
        assert not config.code_computer_enabled
        assert not config.sampling_parameters
        assert config.stateless
        assert config.storage_setting
        assert config.structured_output_field
        assert config.max_output_field
        assert config.policy_version == "m6.6b2.synthetic-task-policy@1"


def test_manifest_cannot_gain_execution_hidden_fixture_or_route_authority() -> None:
    for field in (
        "hidden_fixture_access",
        "credential_access",
        "provider_transport",
        "ready_for_execution",
        "live_authorization_active",
        "route_activation_allowed",
    ):
        with pytest.raises(ValueError, match="cannot grant execution"):
            validate_draft_manifest(replace(DRAFT_MANIFEST, **{field: True}))
    assert DRAFT_MANIFEST.synthetic_only


def test_identity_and_account_unknowns_preserve_all_resolution_classes() -> None:
    identity = {item.provider: item.identity_status for item in DRAFT_MANIFEST.deployments}
    assert identity["openai"] is VersionIdentityStatus.LIVE_LINEAGE_REQUIRED
    assert identity["anthropic"] is VersionIdentityStatus.PROVIDER_DOCUMENTED_PINNED
    assert identity["google"] is VersionIdentityStatus.LIVE_LINEAGE_REQUIRED
    assert {item.resolution for item in DRAFT_MANIFEST.field_statuses} == set(ResolutionClass)
    assert all(
        not item.blocker
        for item in DRAFT_MANIFEST.field_statuses
        if item.resolution is ResolutionClass.PUBLIC_DOC_RESOLVED
    )
    assert all(
        item.blocker
        for item in DRAFT_MANIFEST.field_statuses
        if item.resolution is not ResolutionClass.PUBLIC_DOC_RESOLVED
    )


def test_schema_families_use_conservative_common_json_schema_subset() -> None:
    allowed = {
        "type",
        "object",
        "array",
        "string",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
    }

    def visit(value: dict[str, object]) -> None:
        assert set(value).issubset(allowed)
        properties = value.get("properties", {})
        assert isinstance(properties, dict)
        for child in properties.values():
            assert isinstance(child, dict)
            visit(child)
        items = value.get("items")
        if items is not None:
            assert isinstance(items, dict)
            visit(items)

    assert set(DRAFT_MANIFEST.schemas) == set(SchemaFamily)
    for schema in DRAFT_MANIFEST.schemas.values():
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        visit(schema)
    for binding in BINDINGS:
        assert binding.schema_hash
        assert (
            binding.max_output_tokens
            == {
                TournamentTask.EVIDENCE_INTERPRETATION: 1_800,
                TournamentTask.CONTRADICTION_ANALYSIS: 1_800,
                TournamentTask.OPPORTUNITY_REASONING: 2_200,
                TournamentTask.AUDIT_WORDING: 2_400,
                TournamentTask.OUTREACH_WORDING: 1_000,
                TournamentTask.REPLY_CLASSIFICATION: 500,
                TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION: 1_000,
            }[binding.task]
        )


def test_token_projection_opens_development_and_calibration_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import opintel_qualification.tournament2_prefreeze as prefreeze

    original = prefreeze.cases_for_partition
    requested: list[CorpusPartition] = []

    def guarded(partition: CorpusPartition):  # type: ignore[no-untyped-def]
        requested.append(partition)
        if partition is CorpusPartition.HIDDEN_QUALIFICATION:
            raise AssertionError("hidden corpus access attempted")
        return original(partition)

    monkeypatch.setattr(prefreeze, "cases_for_partition", guarded)
    projections = visible_token_projections()
    assert len(projections) == 7
    assert set(requested) == {CorpusPartition.DEVELOPMENT, CorpusPartition.CALIBRATION}
    assert all(item.maximum_input_tokens > 0 for item in projections)
    assert all("1 byte = 1 token" in item.method for item in projections)


def test_repetition_call_and_conservative_cost_projection_are_exact() -> None:
    projections = binding_cost_projections("2026-08-19")
    assert len(projections) == 12
    assert {item.expected_calls for item in projections} == {32}
    assert {item.maximum_retry_eligible_calls for item in projections} == {32}
    assert {item.maximum_calls for item in projections} == {64}
    assert sum(item.maximum_cost_micros for item in projections) == 21_970_113
    assert price_for("anthropic-claude-sonnet-5", "2026-08-31").output_usd_per_million == (
        Decimal("10")
    )
    assert price_for("anthropic-claude-sonnet-5", "2026-09-01").output_usd_per_million == (
        Decimal("15")
    )
    assert price_for("google-gemini-3.6-flash", "2026-12-31").output_usd_per_million == (
        Decimal("3.75")
    )
    assert price_for("google-gemini-3.6-flash", "2027-01-01").output_usd_per_million == (
        Decimal("7.50")
    )


def test_reviewer_policy_and_objective_dominance_are_exact_and_distinct() -> None:
    assert REVIEWER_POLICY.primary_reviewers == 3
    assert REVIEWER_POLICY.conditional_adjudicators == 1
    assert REVIEWER_POLICY.project_owner_may_be_primary
    assert REVIEWER_POLICY.blinded and REVIEWER_POLICY.randomized
    assert REVIEWER_POLICY.minimum_candidate_preferences == 2
    assert REVIEWER_POLICY.minimum_median_usefulness_delta == 1
    assert REVIEWER_POLICY.minimum_median_trustworthiness_delta == 0
    assert REVIEWER_POLICY.material_defects_allowed == 0
    assert set(REVIEWER_POLICY.objective_dominance_tasks) == {
        TournamentTask.REPLY_CLASSIFICATION,
        TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
    }
    assert RecommendationDisposition.DETERMINISTIC_SUPERIOR != (
        RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
    )
    assert (
        objective_dominance_disposition(
            TournamentTask.REPLY_CLASSIFICATION,
            automated_safety_passed=True,
            candidate_errors=2,
            deterministic_errors=0,
        )
        is RecommendationDisposition.DETERMINISTIC_SUPERIOR
    )
    assert (
        objective_dominance_disposition(
            TournamentTask.FIRST_PARTY_STATEMENT_EXTRACTION,
            automated_safety_passed=True,
            candidate_errors=0,
            deterministic_errors=0,
        )
        is RecommendationDisposition.SAFE_BUT_NO_MATERIAL_GAIN
    )
    with pytest.raises(ValueError, match="hard-gate"):
        objective_dominance_disposition(
            TournamentTask.REPLY_CLASSIFICATION,
            automated_safety_passed=False,
            candidate_errors=1,
            deterministic_errors=0,
        )


def test_deterministic_superior_is_no_route_and_not_a_hard_gate_change() -> None:
    row = TaskReportRow(
        TournamentTask.REPLY_CLASSIFICATION,
        UUID("10000000-0000-4000-8000-000000000001"),
        "google-gemini-3.5-flash-lite",
        RecommendationDisposition.DETERMINISTIC_SUPERIOR,
        PostTournamentState.NO_ROUTE,
        True,
        True,
        (),
        (),
        ("deterministic",),
        1,
        1,
        1,
        1,
    )
    report = TournamentReport(
        UUID("20000000-0000-4000-8000-000000000001"),
        datetime(2026, 8, 19, tzinfo=UTC),
        "m6.6b2@1",
        "synthetic@1",
        "evaluator@1",
        "safety@1",
        "data@1",
        "budget@1",
        (),
        (row,),
        (),
        1,
        1,
        True,
    )
    assert validate_report(report) is report
    with pytest.raises(ValueError, match="deterministic preference"):
        validate_report(replace(report, task_rows=(replace(row, deterministic_preferred=False),)))


def test_minimum_certification_plan_is_five_non_tournament_calls() -> None:
    plan = certification_plan("2026-08-19")
    assert len(plan) == 5
    assert {item.deployment_key for item in plan} == {
        "openai-gpt-5.6-sol",
        "anthropic-claude-sonnet-5",
        "google-gemini-3.6-flash",
        "google-gemini-3.5-flash-lite",
    }
    assert sum(item.deployment_key == "anthropic-claude-sonnet-5" for item in plan) == 2
    assert sum(item.second_call_adds_material_evidence for item in plan) == 1
    assert all("no tournament case" in item.synthetic_input_class for item in plan)
    assert all("returned_model" in item.metadata_required for item in plan)
    assert all(item.max_input_tokens > 0 and item.max_output_tokens > 0 for item in plan)
    assert sum(item.expected_max_cost_micros for item in plan) == 145_467


def test_no_credentials_new_account_or_network_transport_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("M6.6B-2 attempted network access")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    assert REQUIRED_FUTURE_CREDENTIAL_CLASSES == (
        "OpenAI API project credential",
        "Anthropic API workspace credential",
        "Google Gemini API paid-project credential",
    )
    assert not ADDITIONAL_PROVIDER_ACCOUNT_REQUIRED
    assert not DRAFT_MANIFEST.credential_access
    assert not DRAFT_MANIFEST.provider_transport
    assert binding_cost_projections("2026-08-19")
