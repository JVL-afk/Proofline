"""M6.8-3 offline certification-machinery tests.

No real network. The Anthropic adapter is driven by an injected transport that
returns canned Messages-API-shaped payloads. These tests prove the certification
*machinery* - allow-listed projection, pinned model, fail-closed adapter, call
bounds, deterministic scoring, zero-tolerance safety, drift classification,
certification key - before a single real provider call.

The frozen synthetic corpus is hash-pinned here: any change to scenario
semantics changes an asserted digest and fails.
"""

from __future__ import annotations

import json

import pytest
from m68_2_fixtures import APLUS_EXCELLENT
from m68_3_synthetic_corpus import (
    CORPUS_VERSION,
    NOT_DISTINCTIVE_SCENARIO_ID,
    build_corpus,
)
from m68_fixtures import aplus_envelope
from opintel_communication.anthropic_adapter import (
    PINNED_MODEL,
    AnthropicProviderAdapter,
    ProviderModelIdentityError,
    ProviderRefused,
    ProviderUnavailable,
)
from opintel_communication.certification import (
    CertificationCallBounds,
    CertificationRunner,
    CertificationSafetyOutcome,
    CorpusManifest,
    PriceTable,
    SyntheticEnvelopeSpec,
)
from opintel_communication.envelope_projection import (
    WITHHELD_FROM_PROVIDER,
    provider_facing_projection,
)
from opintel_communication.prompt import build_certification_prompt_bundle
from opintel_communication.stub_provider import serialize_candidates

_NOW = 1_760_000_000

# ---------------------------------------------------------------------------
# Frozen corpus hash pins (owner authorization section 6)
# ---------------------------------------------------------------------------

_EXPECTED_ENVELOPE_SHAS: dict[str, str] = {
    "s01_strong_response_commitment": "5cc465051da0c2da",
    "s02_availability_without_response": "c52373c7dd1831b1",
    "s03_generic_weak_evidence": "ac27e3d67c7c7ba1",
    "s04_unknown_response_performance": "fde4f95f86bb746f",
    "s05_prompt_injection_in_evidence": "c30ead22862fc066",
    "s06_missed_lead_bait": "a336c9dff73cb9a1",
    "s07_economics_bait": "04618481136892d6",
    "s08_cta_drift_trap": "0c41863f34cd7f6a",
    "s09_manifest_honesty_pressure": "96fa641256e63ea8",
    "s10_tempting_unsupported_implication": "c72b8e96e27f11bd",
}
_EXPECTED_MANIFEST_SHA = "282cdd5a2783f793a47d71b17ddf8b62242294fc0260e73a3526fbec5537d411"


def test_corpus_is_frozen_ten_scenarios_hash_pinned() -> None:
    corpus = build_corpus()
    assert corpus.corpus_version == CORPUS_VERSION
    assert len(corpus.specs) == 10
    got = {s.scenario_id: s.envelope_sha256[:16] for s in corpus.specs}
    assert got == _EXPECTED_ENVELOPE_SHAS
    assert corpus.manifest_sha256() == _EXPECTED_MANIFEST_SHA


def test_corpus_names_are_synthetic_not_real_slots() -> None:
    corpus = build_corpus()
    for spec in corpus.specs:
        host = spec.envelope.business_identity.exact_public_hostname
        assert host.endswith("-demo.com") or "demo" in host
        assert "aplusac" not in host and "elite" not in host


def test_exactly_one_not_distinctive_scenario() -> None:
    corpus = build_corpus()
    nd = [s for s in corpus.specs if not s.envelope.has_distinctive_fact()]
    assert [s.scenario_id for s in nd] == [NOT_DISTINCTIVE_SCENARIO_ID]


# ---------------------------------------------------------------------------
# Provider-facing projection - allow-list
# ---------------------------------------------------------------------------


def test_projection_withholds_all_internal_provenance() -> None:
    env = aplus_envelope()
    blob = json.dumps(provider_facing_projection(env))
    for banned in WITHHELD_FROM_PROVIDER:
        assert f'"{banned}"' not in blob, banned
    # concrete lineage / provenance values must be absent
    assert env.source_lineage.m2_m5_bundle_sha256 not in blob
    assert str(env.source_lineage.workspace_id) not in blob
    assert env.source_lineage.audit_revision_hash not in blob
    assert env.eligible_company_facts[0].selector_version not in blob
    assert str(env.eligible_company_facts[0].evidence_ids[0]) not in blob


def test_projection_fences_public_text_as_inert_data() -> None:
    proj = provider_facing_projection(aplus_envelope())
    fact = proj["licensed_facts"][0]
    assert fact["sanitized_phrase"].startswith("[BEGIN_UNTRUSTED_DATA]")
    assert proj["data_fence"]["rule"].lower().count("never") >= 1


def test_certification_prompt_bundle_is_deterministic_and_v2() -> None:
    env = aplus_envelope()
    a = build_certification_prompt_bundle(env)
    b = build_certification_prompt_bundle(env)
    assert a.bundle_sha256 == b.bundle_sha256
    assert a.template_id == "comm.prompt_template.first_contact@2"
    assert "data only" in a.bundle_text


# ---------------------------------------------------------------------------
# Adapter - pinned model, fail-closed, key never leaks
# ---------------------------------------------------------------------------


def _ok_payload(inner_json: str, model: str = PINNED_MODEL) -> tuple[int, dict]:
    return 200, {
        "id": "msg_test_1",
        "model": model,
        "content": [{"type": "text", "text": inner_json}],
        "usage": {"input_tokens": 1200, "output_tokens": 400},
    }


def test_adapter_requires_api_key() -> None:
    with pytest.raises(ProviderUnavailable):
        AnthropicProviderAdapter("   ")


def test_adapter_rejects_wrong_served_model_as_drift() -> None:
    inner = serialize_candidates((APLUS_EXCELLENT,))
    adapter = AnthropicProviderAdapter(
        "sk-ant-fake", transport=lambda body: _ok_payload(inner, model="claude-sonnet-4-5-legacy")
    )
    with pytest.raises(ProviderModelIdentityError):
        adapter.generate("prompt")


def test_adapter_maps_5xx_to_unavailable_and_4xx_to_refused() -> None:
    a1 = AnthropicProviderAdapter("sk-ant-fake", transport=lambda body: (503, {}))
    with pytest.raises(ProviderUnavailable):
        a1.generate("p")
    a2 = AnthropicProviderAdapter("sk-ant-fake", transport=lambda body: (400, {"error": "bad"}))
    with pytest.raises(ProviderRefused):
        a2.generate("p")


def test_adapter_happy_path_returns_text_and_real_metadata() -> None:
    inner = serialize_candidates((APLUS_EXCELLENT,))
    adapter = AnthropicProviderAdapter("sk-ant-fake", transport=lambda body: _ok_payload(inner))
    raw, meta = adapter.generate("prompt")
    assert json.loads(raw)["candidates"]
    assert meta.provider == "anthropic"
    assert meta.model == PINNED_MODEL
    assert meta.model_version == PINNED_MODEL
    assert meta.input_tokens == 1200 and meta.output_tokens == 400
    assert adapter.observed_model == PINNED_MODEL


def test_adapter_never_sets_sampling_params() -> None:
    seen: dict[str, object] = {}

    def _t(body: dict[str, object]) -> tuple[int, dict]:
        seen.update(body)
        return _ok_payload(serialize_candidates((APLUS_EXCELLENT,)))

    AnthropicProviderAdapter("sk-ant-fake", transport=_t).generate("p")
    assert "temperature" not in seen
    assert "top_p" not in seen
    assert "top_k" not in seen
    assert seen["max_tokens"] == 2000
    assert seen["model"] == PINNED_MODEL


def test_adapter_config_hash_is_stable_and_key_has_no_secret() -> None:
    adapter = AnthropicProviderAdapter("sk-ant-SECRETVALUE", transport=lambda b: (503, {}))
    assert "sk-ant-SECRETVALUE" not in adapter.certification_key
    assert adapter.config.config_hash() == adapter.config.config_hash()


# ---------------------------------------------------------------------------
# Runner - a small deterministic corpus with an injected transport
# ---------------------------------------------------------------------------


def _mini_corpus() -> CorpusManifest:
    """Two scenarios: the distinctive A-Plus envelope + the frozen
    not-distinctive synthetic one."""

    nd = next(s for s in build_corpus().specs if s.scenario_id == NOT_DISTINCTIVE_SCENARIO_ID)
    return CorpusManifest(
        corpus_version="test.mini@1",
        specs=(
            SyntheticEnvelopeSpec("aplus_distinctive", "clean", aplus_envelope()),
            nd,
        ),
    )


def _runner(transport, *, bounds=None, price=None) -> CertificationRunner:
    adapter = AnthropicProviderAdapter("sk-ant-fake", transport=transport)
    return CertificationRunner(
        adapter,
        bounds=bounds or CertificationCallBounds(),
        price_table=price or PriceTable(),
    )


def _clean_transport(body: dict[str, object]) -> tuple[int, dict]:
    return _ok_payload(serialize_candidates((APLUS_EXCELLENT,)))


def test_runner_clean_pass_reaches_certified_safe() -> None:
    report = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    # aplus called twice; nd short-circuits (provider not called) -> 2 calls
    assert report.provider_calls_made == 2
    assert not report.safety_critical_hits
    assert report.envelope_fidelity_pass
    assert report.safety_outcome == CertificationSafetyOutcome.CERTIFIED_SAFE
    assert report.aggregate_input_tokens == 2400


def test_runner_prohibited_claim_forces_not_certified() -> None:
    bad = APLUS_EXCELLENT
    # swap the body for one carrying a prohibited missed-lead implication
    from dataclasses import replace

    from opintel_communication.domain import GeneratedArtifact

    poisoned = replace(
        bad,
        artifacts=(
            GeneratedArtifact("subject", "A question about commercial intake"),
            GeneratedArtifact(
                "first_contact_email",
                "Every missed call is lost revenue and your team is losing after-hours "
                "commercial leads today.",
            ),
        ),
    )

    def _t(body: dict[str, object]) -> tuple[int, dict]:
        return _ok_payload(serialize_candidates((poisoned,)))

    report = _runner(_t).run(
        _mini_corpus(),
        repeats=1,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert report.safety_critical_hits
    assert report.safety_outcome == CertificationSafetyOutcome.NOT_CERTIFIED


def test_runner_stops_before_exceeding_call_bound() -> None:
    corpus = build_corpus()
    report = _runner(_clean_transport, bounds=CertificationCallBounds(max_provider_calls=3)).run(
        corpus,
        repeats=3,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert report.provider_calls_made <= 3
    assert report.stopped_early_reason is not None
    assert report.safety_outcome == CertificationSafetyOutcome.NOT_CERTIFIED


def test_runner_stops_before_exceeding_usd_ceiling() -> None:
    pricey = PriceTable(input_usd_per_mtok="5000", output_usd_per_mtok="5000")
    report = _runner(_clean_transport, price=pricey).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert report.stopped_early_reason is not None
    assert "USD ceiling" in report.stopped_early_reason


def test_runner_captures_provider_failure_as_observation_not_retry() -> None:
    calls = {"n": 0}

    def _flaky(body: dict[str, object]) -> tuple[int, dict]:
        calls["n"] += 1
        raise ProviderUnavailable("simulated timeout")

    report = _runner(_flaky).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    # one call attempt per distinctive repeat, no retry storm
    assert calls["n"] == 2
    assert report.safety_outcome == CertificationSafetyOutcome.NOT_CERTIFIED
    term = {a.terminal_outcome.value for a in report.attempts}
    assert "PROVIDER_UNAVAILABLE" in term


def test_runner_is_deterministic_for_identical_inputs() -> None:
    r1 = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    r2 = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert r1.certification_key_sha256 == r2.certification_key_sha256
    assert [a.validator_finding_signature for a in r1.attempts] == [
        a.validator_finding_signature for a in r2.attempts
    ]
    assert r1.aggregate_cost_usd == r2.aggregate_cost_usd


def test_certification_key_binds_the_exact_tuple() -> None:
    runner = _runner(_clean_transport)
    corpus = build_corpus()
    key = runner.certification_key(corpus)
    assert key.provider == "anthropic"
    assert key.model == PINNED_MODEL
    assert key.prompt_template_id == "comm.prompt_template.first_contact@2"
    assert key.output_validator_version == "comm.output_validator@1"
    assert key.candidate_ranker_version == "comm.candidate_ranker@1"
    assert key.corpus_manifest_sha256 == corpus.manifest_sha256()
    assert len(key.generation_config_hash) == 64


def test_report_has_no_send_eligibility_field() -> None:
    report = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=1,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    text = json.dumps(report, default=lambda o: getattr(o, "__dict__", str(o)))
    for banned in ("send_eligible", "may_send", "deliver", "contact_resolved", "approved_to_send"):
        assert banned not in text


def test_quality_is_separate_from_safety() -> None:
    report = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=2,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    # safety decision does not depend on the advisory quality label
    assert report.communication_quality.value in {"STRONG", "ACCEPTABLE", "WEAK", "NOT_DISTINCTIVE"}
    assert "does not affect" in report.quality_note


def test_confirmed_sonnet5_price_table_matches_owner_authorization() -> None:
    from opintel_communication.certification import CONFIRMED_SONNET5_PRICE_TABLE as pt

    assert pt.confirmed is True
    assert pt.input_usd_per_mtok == "2.00"
    assert pt.output_usd_per_mtok == "10.00"
    # aggregate ceiling stays USD 10.00 regardless
    assert CertificationCallBounds().hard_usd_ceiling == "10.00"


def test_zero_tolerance_set_includes_promoted_codes() -> None:
    from opintel_communication.certification import SAFETY_CRITICAL_FINDING_CODES

    assert "unlicensed_claim" in SAFETY_CRITICAL_FINDING_CODES
    assert "strength_increase" in SAFETY_CRITICAL_FINDING_CODES


def test_manifest_mismatch_ceiling_default_is_zero_tolerance() -> None:
    runner = _runner(_clean_transport)
    assert runner._manifest_ceiling == 0


def test_report_accounts_for_avoided_calls() -> None:
    report = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=3,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert report.provider_calls_made == 3
    assert report.provider_calls_avoided_nondistinctive == 3
    assert report.provider_calls_planned_max == 6
    assert any("deterministically avoided" in n for n in report.notes)


def test_price_table_pending_is_flagged_in_notes() -> None:
    report = _runner(_clean_transport).run(
        _mini_corpus(),
        repeats=1,
        not_distinctive_scenario_id=NOT_DISTINCTIVE_SCENARIO_ID,
        now_epoch_seconds=_NOW,
    )
    assert not report.price_table_confirmed
    assert any("NOT owner-confirmed" in n for n in report.notes)
