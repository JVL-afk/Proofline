"""M6.8-2 - stubbed generation lifecycle, audit store, candidate ranker.

No live provider, no network, USD 0. Proves that candidates can be created (via a
deterministic stub), persisted append-only, validated, rejected or ranked, and
surfaced for human review - all reproducibly - before any real model exists.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from m68_2_fixtures import (
    APLUS_ALL_INVALID_SET,
    APLUS_AVAILABILITY_TO_RESPONSE,
    APLUS_EXCELLENT,
    APLUS_MANIFEST_LYING,
    APLUS_STRONG_PROSE_ONE_UNSUPPORTED,
    APLUS_UNSAFE_SUBJECT_SET,
    APLUS_VALID_SET,
    ELITE_AVAILABILITY_TO_RESPONSE,
    ELITE_SAFE,
    aplus_envelope,
    elite_envelope,
    em_envelope,
)
from opintel_communication import (
    CANDIDATE_RANKER_VERSION,
    GENERATION_ORCHESTRATOR_VERSION,
    GENERATION_STORE_VERSION,
    HUMAN_REVIEW_SCHEMA_VERSION,
    STUB_PROVIDER_ADAPTER_VERSION,
    CandidateRanker,
    CommunicationOutcome,
    GenerationOrchestrator,
    HumanReviewState,
    InMemoryGenerationStore,
    OutputValidator,
    RawResponseVault,
    ReviewTransitionError,
    StubProfile,
    StubProviderAdapter,
    accept_not_distinctive,
    build_prompt_bundle,
    compute_record_hash,
    new_retention,
    open_review,
    reject_all,
    reject_candidate,
    select_candidate,
)
from opintel_communication.retention import compute_expiry, is_expired

_NOW = 1_760_000_000
_PROFILE = StubProfile(
    name="m6.8-2-corpus",
    certification_key="comm.provider_certification.stub/deterministic/1/default",
)


def _fresh_store() -> InMemoryGenerationStore:
    store = InMemoryGenerationStore(vault=RawResponseVault())
    store.initialize()
    return store


def _run(envelope, candidates, *, store=None, n=None, record_id="rec-1", now=_NOW):
    store = store or _fresh_store()
    adapter = StubProviderAdapter(tuple(candidates), profile=_PROFILE)
    orch = GenerationOrchestrator()
    record = orch.run(
        envelope,
        adapter,
        store,
        now_epoch_seconds=now,
        requested_candidate_count=n,
        record_id=record_id,
    )
    return store, record


# ---------------------------------------------------------------------------
# Orchestration terminals
# ---------------------------------------------------------------------------


def test_valid_candidates_reach_candidate_ready_and_are_ranked() -> None:
    store, record = _run(aplus_envelope(), APLUS_VALID_SET)
    assert record.terminal_outcome is CommunicationOutcome.AI_COMMUNICATION_CANDIDATE_READY
    assert record.returned_candidate_count == 3
    assert set(record.passing_candidate_ids) == {
        "aplus-excellent",
        "aplus-valid-mid",
        "aplus-valid-weak",
    }
    assert record.ranked_candidate_ids == (
        "aplus-excellent",
        "aplus-valid-mid",
        "aplus-valid-weak",
    )
    assert record.human_review_state is HumanReviewState.PENDING
    assert store.verify_chain()


def test_all_invalid_candidates_reach_ai_communication_rejected() -> None:
    store, record = _run(aplus_envelope(), APLUS_ALL_INVALID_SET)
    assert record.terminal_outcome is CommunicationOutcome.AI_COMMUNICATION_REJECTED
    assert record.returned_candidate_count == 3
    assert record.passing_candidate_ids == ()
    assert record.ranked_candidate_ids == ()
    # the record still explains every rejection
    assert all(not c.validation.passed for c in record.candidates)
    assert all(c.validation.finding_codes for c in record.candidates)
    assert store.verify_chain()


def test_weak_envelope_is_not_distinctive_and_provider_is_not_called() -> None:
    _, record = _run(em_envelope(), APLUS_VALID_SET)
    assert record.terminal_outcome is CommunicationOutcome.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH
    assert record.returned_candidate_count == 0
    assert record.raw_provider_response_sha256 is None
    assert record.raw_provider_response_ref is None
    assert any("has_distinctive_fact=False" in d[1] for d in record.diagnostics)


def test_not_distinctive_and_rejected_are_valid_non_error_terminals() -> None:
    from opintel_communication.domain import VALID_NON_ERROR_TERMINALS

    assert CommunicationOutcome.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH in VALID_NON_ERROR_TERMINALS
    assert CommunicationOutcome.AI_COMMUNICATION_REJECTED in VALID_NON_ERROR_TERMINALS


def test_no_automatic_regeneration_loop() -> None:
    store, _ = _run(aplus_envelope(), APLUS_ALL_INVALID_SET)
    # a rejected terminal does not trigger another attempt
    assert len(store.all_records()) == 1


def test_default_n_is_three() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET, n=None)
    assert record.requested_candidate_count == 3


def test_hard_maximum_is_five() -> None:
    with pytest.raises(ValueError):
        _run(aplus_envelope(), APLUS_VALID_SET, n=6)


def test_provider_returning_more_than_requested_is_capped() -> None:
    corpus = (*APLUS_VALID_SET, ELITE_SAFE, APLUS_MANIFEST_LYING)
    _, record = _run(aplus_envelope(), corpus, n=3)
    assert record.returned_candidate_count == 3
    assert any(d[0] == "candidate_cap" for d in record.diagnostics)


# ---------------------------------------------------------------------------
# Subject + body atomicity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cand", APLUS_UNSAFE_SUBJECT_SET, ids=lambda c: c.candidate_id)
def test_safe_body_with_unsafe_subject_fails_the_candidate(cand) -> None:
    result = OutputValidator().validate(aplus_envelope(), cand)
    assert not result.passed
    _, record = _run(aplus_envelope(), (APLUS_EXCELLENT, cand))
    row = next(c for c in record.candidates if c.candidate_id == cand.candidate_id)
    assert not row.validation.passed
    assert cand.candidate_id not in record.ranked_candidate_ids


def test_candidate_content_hash_covers_subject() -> None:
    from opintel_communication import normalize_candidate

    base = APLUS_EXCELLENT
    other = replace(
        base,
        artifacts=(
            type(base.artifacts[0])("subject", "A different subject line entirely"),
            base.artifacts[1],
        ),
    )
    assert normalize_candidate(base).content_sha256 != normalize_candidate(other).content_sha256


# ---------------------------------------------------------------------------
# Specific failing categories
# ---------------------------------------------------------------------------


def test_strong_prose_with_one_unsupported_implication_fails() -> None:
    result = OutputValidator().validate(aplus_envelope(), APLUS_STRONG_PROSE_ONE_UNSUPPORTED)
    assert not result.passed
    assert "prohibited_claim" in result.finding_codes


def test_manifest_lying_about_the_prose_fails() -> None:
    result = OutputValidator().validate(aplus_envelope(), APLUS_MANIFEST_LYING)
    assert not result.passed
    assert "undeclared_rendered_claim" in result.finding_codes


def test_availability_to_response_fails_on_both_envelopes() -> None:
    a = OutputValidator().validate(aplus_envelope(), APLUS_AVAILABILITY_TO_RESPONSE)
    e = OutputValidator().validate(elite_envelope(), ELITE_AVAILABILITY_TO_RESPONSE)
    assert "availability_upgraded_to_response" in a.finding_codes
    assert "availability_upgraded_to_response" in e.finding_codes


def test_safe_elite_candidate_runs_to_candidate_ready() -> None:
    _, record = _run(elite_envelope(), (ELITE_SAFE,))
    assert record.terminal_outcome is CommunicationOutcome.AI_COMMUNICATION_CANDIDATE_READY
    assert record.ranked_candidate_ids == ("elite-safe",)


# ---------------------------------------------------------------------------
# Candidate ranker
# ---------------------------------------------------------------------------


def test_ranker_never_ranks_a_failed_candidate() -> None:
    v = OutputValidator()
    bad = APLUS_STRONG_PROSE_ONE_UNSUPPORTED
    with pytest.raises(ValueError):
        CandidateRanker().rank(aplus_envelope(), ((bad, v.validate(aplus_envelope(), bad)),))


def test_ranker_preserves_every_component_and_weights_sum_to_one() -> None:
    v = OutputValidator()
    env = aplus_envelope()
    passing = tuple((c, v.validate(env, c)) for c in APLUS_VALID_SET)
    ranked = CandidateRanker().rank(env, passing)
    assert [r.rank for r in ranked] == [1, 2, 3]
    for r in ranked:
        names = {comp.name for comp in r.score.components}
        assert names == {
            "distinguishing_fact_strength",
            "company_specific_content",
            "evidence_class_diversity",
            "brevity",
            "generic_phrase_ratio",
            "hedge_density",
            "quoted_fragment_count",
            "disclosure_opening_dominance",
        }
        assert abs(sum(comp.weight for comp in r.score.components) - 1.0) < 1e-9
        assert abs(sum(comp.contribution for comp in r.score.components) - r.score.total) < 1e-6


def test_ranker_order_is_deterministic() -> None:
    v = OutputValidator()
    env = aplus_envelope()
    passing = tuple((c, v.validate(env, c)) for c in APLUS_VALID_SET)
    a = CandidateRanker().rank(env, passing)
    b = CandidateRanker().rank(env, tuple(reversed(passing)))
    assert [r.candidate_id for r in a] == [r.candidate_id for r in b]


def test_ranker_does_not_expose_send_eligibility() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    top = record.candidates[0]
    score_fields = set(type(top.rank_score).__dataclass_fields__)
    component_fields = set(type(top.rank_score.components[0]).__dataclass_fields__)
    for banned in ("send", "eligible", "deliver", "approv"):
        assert not any(banned in f for f in score_fields | component_fields)
        assert not any(banned in f for f in record.__dataclass_fields__)
        assert not any(banned in f for f in type(record.candidates[0]).__dataclass_fields__)


# ---------------------------------------------------------------------------
# Append-only, hash-chained store
# ---------------------------------------------------------------------------


def test_store_is_append_only_and_hash_chained() -> None:
    store = _fresh_store()
    _, r0 = _run(aplus_envelope(), APLUS_VALID_SET, store=store, record_id="r0")
    _, r1 = _run(elite_envelope(), (ELITE_SAFE,), store=store, record_id="r1")
    assert (r0.sequence, r1.sequence) == (0, 1)
    assert r1.previous_record_hash == r0.record_hash
    assert store.verify_chain()


def test_tampering_a_record_breaks_chain_verification() -> None:
    store = _fresh_store()
    _run(aplus_envelope(), APLUS_VALID_SET, store=store)
    store._records[0] = replace(store._records[0], reason="tampered")
    assert not store.verify_chain()


def test_out_of_order_append_is_rejected() -> None:
    store = _fresh_store()
    _, r0 = _run(aplus_envelope(), APLUS_VALID_SET, store=store)
    forged = replace(r0, sequence=5)
    with pytest.raises(ValueError):
        store.append(forged)


def test_record_carries_the_full_audit_surface() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    assert record.envelope_sha256 and len(record.envelope_sha256) == 64
    assert record.envelope_schema_version == "comm.semantic_envelope@1"
    assert record.source_lineage_bundle_sha256
    assert "StubProviderAdapter@" in record.provider_adapter_identity
    assert record.provider_certification_key.startswith("comm.provider_certification.")
    assert record.model_placeholder and record.provider_placeholder and record.config_placeholder
    assert record.prompt_template_id == "comm.prompt_template.first_contact@1"
    assert len(record.prompt_template_sha256) == 64 and len(record.prompt_bundle_sha256) == 64
    assert len(record.raw_provider_response_sha256 or "") == 64
    assert record.validator_version == "comm.output_validator@1"
    assert record.ranker_version == CANDIDATE_RANKER_VERSION
    assert record.orchestrator_version == GENERATION_ORCHESTRATOR_VERSION
    assert record.store_version == GENERATION_STORE_VERSION
    assert record.cost_usd == "0.00"
    assert record.input_tokens > 0 and record.output_tokens > 0
    top = record.candidates[0]
    assert top.normalized.content_sha256 and top.normalized.body_word_count > 0
    assert top.claim_manifest.entries
    assert top.claim_evidence_map
    assert top.rank == 1 and top.rank_score is not None
    assert record.record_hash == compute_record_hash(replace(record, record_hash=""))


# ---------------------------------------------------------------------------
# Raw-response retention
# ---------------------------------------------------------------------------


def test_expiry_calculation() -> None:
    assert compute_expiry(1000, 30) == 1000 + 30 * 86_400
    r = new_retention(_NOW)
    assert r.max_retention_days == 30
    assert r.policy_status == "POLICY_PENDING"
    assert not is_expired(r, _NOW + 29 * 86_400)
    assert is_expired(r, _NOW + 30 * 86_400)


def test_crypto_erase_interface_and_idempotency() -> None:
    store, record = _run(aplus_envelope(), APLUS_VALID_SET)
    rh = record.record_hash
    assert store.vault.get(rh).ciphertext is not None
    assert store.vault.crypto_erase(rh, _NOW + 100)
    assert store.vault.get(rh).erased
    assert store.vault.get(rh).retention.erased_at_epoch_seconds == _NOW + 100
    # second erase is a no-op
    assert not store.vault.crypto_erase(rh, _NOW + 200)


def test_purge_expired_is_idempotent_and_keeps_hash() -> None:
    store, record = _run(aplus_envelope(), APLUS_VALID_SET)
    rh = record.record_hash
    kept_sha = store.vault.get(rh).raw_sha256
    assert store.purge_expired_raw_responses(_NOW + 31 * 86_400) == 1
    assert store.purge_expired_raw_responses(_NOW + 40 * 86_400) == 0
    entry = store.vault.get(rh)
    assert entry.erased and entry.raw_sha256 == kept_sha
    assert entry.retention.erase_method == "expiry_purge"


def test_normalized_artifact_and_audit_metadata_survive_raw_erasure() -> None:
    store, record = _run(aplus_envelope(), (APLUS_EXCELLENT, APLUS_STRONG_PROSE_ONE_UNSUPPORTED))
    store.vault.purge_expired(_NOW + 40 * 86_400)
    # the record is untouched: still explains the accepted and the rejected candidate
    still = store.get(record.record_hash)
    assert still.record_hash == record.record_hash
    accepted = next(c for c in still.candidates if c.candidate_id == "aplus-excellent")
    rejected = next(c for c in still.candidates if c.candidate_id == "aplus-one-unsupported")
    assert accepted.validation.passed and accepted.claim_evidence_map
    assert not rejected.validation.passed and rejected.validation.finding_codes
    assert accepted.normalized.normalized_body  # normalized artifact retained
    assert store.verify_chain()


# ---------------------------------------------------------------------------
# Human review
# ---------------------------------------------------------------------------


def test_open_review_is_pending_and_version_bound() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    review = open_review(record, "rev-1")
    assert review.state is HumanReviewState.PENDING
    assert review.envelope_sha256 == record.envelope_sha256
    assert review.generation_record_hash == record.record_hash
    assert review.selectable_candidate_ids == record.ranked_candidate_ids
    assert review.schema_version == HUMAN_REVIEW_SCHEMA_VERSION


def test_select_a_ranked_candidate() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    review = open_review(record, "rev-1")
    review = select_candidate(
        review, record, "aplus-excellent", at_epoch_seconds=_NOW, reviewer_ref="reviewer:a"
    )
    assert review.state is HumanReviewState.CANDIDATE_SELECTED
    assert review.selected_candidate_id == "aplus-excellent"


def test_a_validator_failed_candidate_is_structurally_unselectable() -> None:
    _, record = _run(aplus_envelope(), (APLUS_EXCELLENT, APLUS_STRONG_PROSE_ONE_UNSUPPORTED))
    review = open_review(record, "rev-1")
    assert "aplus-one-unsupported" not in review.selectable_candidate_ids
    with pytest.raises(ReviewTransitionError):
        select_candidate(
            review,
            record,
            "aplus-one-unsupported",
            at_epoch_seconds=_NOW,
            reviewer_ref="reviewer:a",
        )


def test_reject_all_is_terminal() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    review = reject_all(
        open_review(record, "rev-1"),
        record,
        at_epoch_seconds=_NOW,
        reviewer_ref="reviewer:a",
    )
    assert review.state is HumanReviewState.ALL_REJECTED
    with pytest.raises(ReviewTransitionError):
        select_candidate(review, record, "aplus-excellent", at_epoch_seconds=_NOW, reviewer_ref="r")


def test_accept_not_distinctive_only_valid_for_that_terminal() -> None:
    _, ready = _run(aplus_envelope(), APLUS_VALID_SET)
    with pytest.raises(ReviewTransitionError):
        accept_not_distinctive(
            open_review(ready, "rev-1"), ready, at_epoch_seconds=_NOW, reviewer_ref="r"
        )
    _, thin = _run(em_envelope(), APLUS_VALID_SET)
    review = accept_not_distinctive(
        open_review(thin, "rev-2"), thin, at_epoch_seconds=_NOW, reviewer_ref="r"
    )
    assert review.state is HumanReviewState.ACCEPTED_NOT_DISTINCTIVE


def test_review_is_bound_to_exact_record_hash() -> None:
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    review = open_review(record, "rev-1")
    wrong = replace(record, record_hash="deadbeef" * 8)
    with pytest.raises(ReviewTransitionError):
        reject_candidate(review, wrong, "aplus-excellent", at_epoch_seconds=_NOW, reviewer_ref="r")


def test_review_selectable_set_is_exactly_the_pass_validation_ranked_set() -> None:
    _, record = _run(
        aplus_envelope(),
        (APLUS_EXCELLENT, APLUS_STRONG_PROSE_ONE_UNSUPPORTED, APLUS_MANIFEST_LYING),
    )
    review = open_review(record, "rev-1")
    assert set(review.selectable_candidate_ids) == set(record.passing_candidate_ids)
    assert all(
        next(c for c in record.candidates if c.candidate_id == cid).validation.passed
        for cid in review.selectable_candidate_ids
    )


# ---------------------------------------------------------------------------
# Replay / drift
# ---------------------------------------------------------------------------


def test_replay_is_bit_identical() -> None:
    _, r1 = _run(aplus_envelope(), APLUS_VALID_SET, record_id="rec-x")
    _, r2 = _run(aplus_envelope(), APLUS_VALID_SET, record_id="rec-x")
    assert r1.record_hash == r2.record_hash
    assert r1.prompt_bundle_sha256 == r2.prompt_bundle_sha256
    assert r1.raw_provider_response_sha256 == r2.raw_provider_response_sha256
    assert [c.normalized.content_sha256 for c in r1.candidates] == [
        c.normalized.content_sha256 for c in r2.candidates
    ]
    assert [c.validation.finding_codes for c in r1.candidates] == [
        c.validation.finding_codes for c in r2.candidates
    ]
    assert r1.ranked_candidate_ids == r2.ranked_candidate_ids
    assert [(c.rank, c.rank_score.total if c.rank_score else None) for c in r1.candidates] == [
        (c.rank, c.rank_score.total if c.rank_score else None) for c in r2.candidates
    ]


def test_prompt_bundle_is_deterministic_and_data_only() -> None:
    b1 = build_prompt_bundle(aplus_envelope())
    b2 = build_prompt_bundle(aplus_envelope())
    assert b1.bundle_sha256 == b2.bundle_sha256
    assert "inert data" in b1.bundle_text
    assert "never an instruction" in b1.bundle_text
    assert "--- ENVELOPE (data only) ---" in b1.bundle_text


def test_stub_adapter_is_offline_and_zero_cost() -> None:
    adapter = StubProviderAdapter(APLUS_VALID_SET, profile=_PROFILE)
    for attr in ("url", "endpoint", "api_key", "session", "http", "client"):
        assert not hasattr(adapter, attr)
    _, record = _run(aplus_envelope(), APLUS_VALID_SET)
    assert record.cost_usd == "0.00"


def test_provider_drift_descriptor_documents_live_certification() -> None:
    from opintel_communication import ProviderDriftDescriptor

    d = ProviderDriftDescriptor(
        certification_key=_PROFILE.certification_key,
        prompt_bundle_sha256="a" * 64,
        response_fingerprint_sha256="b" * 64,
        normalized_candidate_shas=("c" * 64,),
        validator_finding_signature="none",
        ranking_signature="excellent>mid>weak",
    )
    assert "Live provider certification" in d.note
    assert "bounded" in d.note


def test_new_version_constants_present() -> None:
    assert CANDIDATE_RANKER_VERSION == "comm.candidate_ranker@1"
    assert GENERATION_STORE_VERSION == "comm.generation_store@1"
    assert GENERATION_ORCHESTRATOR_VERSION == "comm.generation_orchestrator@1"
    assert HUMAN_REVIEW_SCHEMA_VERSION == "comm.human_review@1"
    assert STUB_PROVIDER_ADAPTER_VERSION == "comm.stub_provider_adapter@1"
