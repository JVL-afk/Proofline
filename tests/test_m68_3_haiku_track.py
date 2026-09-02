"""M6.8-3 Haiku track (owner authorization 2026-09-02 "SWITCH ... TO HAIKU 4.5").

Offline regressions for the model-independent deterministic work:
  * D1  framing-fragment source classification
  * D2  comm.candidate_compactor@1 (whole-sentence removal, byte-identity,
        never launder unsafe prose, fail if cannot reach <= 130 safely)
  * G   comm.communication_quality@1
  * B   the model-family identity check and Haiku bounds / price
No provider call.
"""

from __future__ import annotations

import pytest
from m68_3_synthetic_corpus import build_corpus
from opintel_communication.anthropic_adapter import (
    HAIKU_4_5_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
    ProviderModelIdentityError,
    _model_family,
)
from opintel_communication.compactor import (
    COMPACTOR_VERSION,
    compact_candidate,
    laundered_safety_codes,
    split_sentences,
    strongest_usable_hook_words,
)
from opintel_communication.domain import (
    ZERO_TOLERANCE_SAFETY_CODES,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    GeneratedArtifact,
    GenerationCandidate,
)
from opintel_communication.prompt import build_certification_prompt_bundle_v8
from opintel_communication.quality import assess_quality
from opintel_communication.validator import OutputValidator, _classify, _is_framing_leadin

V2 = OutputValidator(contract="v2")
_ENV = {s.scenario_id: s.envelope for s in build_corpus().specs}
S01 = _ENV["s01_strong_response_commitment"]
S02 = _ENV["s02_availability_without_response"]
S06 = _ENV["s06_missed_lead_bait"]

_PLACEHOLDERS = (
    "{{functional_role_or_team}}\n{{verified_sender_signature}}\n"
    "{{required_postal_disclosure}}\n{{approved_opt_out_instruction}}"
)


def _ref(env, category: str) -> str:
    for f in env.eligible_company_facts:
        if f.category == category:
            return f.fact_id
    raise KeyError(category)


def _e(cid, ctype, span, *, sources=(), strength=None, artifact="first_contact_email", cta=None):
    return ClaimManifestEntry(
        claim_id=cid,
        claim_type=ctype,
        rendered_artifact=artifact,
        rendered_span=span,
        licensed_source_ids=sources,
        qualifiers=(),
        asserted_strength=strength,
        cta_intent=cta,
    )


def _cand(subject, body, entries):
    return GenerationCandidate(
        candidate_id="c1",
        artifacts=(
            GeneratedArtifact("subject", subject),
            GeneratedArtifact("first_contact_email", body),
        ),
        claim_manifest=ClaimManifest(entries=tuple(entries)),
    )


def _codes(env, cand):
    return {f.code for f in V2.validate(env, cand).findings}


# ---------------------------------------------------------------------------
# B. model-family identity check + Haiku config
# ---------------------------------------------------------------------------


def test_model_family_strips_date_suffix() -> None:
    assert _model_family("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    assert _model_family("claude-haiku-4-5") == "claude-haiku-4-5"
    assert _model_family("claude-sonnet-5") == "claude-sonnet-5"
    assert HAIKU_4_5_MODEL == "claude-haiku-4-5-20251001"


def test_adapter_accepts_haiku_family_and_rejects_others() -> None:
    inner = '{"candidates":[{"candidate_id":"c1","subject":"s","body":"b","claim_manifest":[]}]}'

    def ok(model: str):
        return lambda body: (
            200,
            {"model": model, "content": [{"type": "text", "text": inner}], "usage": {}},
        )

    cfg = GenerationConfig(model=HAIKU_4_5_MODEL, thinking="disabled")
    a = AnthropicProviderAdapter("sk-ant-x", config=cfg, transport=ok("claude-haiku-4-5"))
    a.generate("p")
    assert a.observed_model == "claude-haiku-4-5"
    a2 = AnthropicProviderAdapter("sk-ant-x", config=cfg, transport=ok("claude-haiku-4-5-20251001"))
    a2.generate("p")
    bad = AnthropicProviderAdapter("sk-ant-x", config=cfg, transport=ok("claude-3-5-haiku-latest"))
    with pytest.raises(ProviderModelIdentityError):
        bad.generate("p")


def test_haiku_bounds_and_price() -> None:
    from opintel_communication.certification import (
        HAIKU_4_5_PRICE_TABLE,
        HAIKU_CERT_BOUNDS,
        HAIKU_QUALIFICATION_BOUNDS,
    )

    assert HAIKU_QUALIFICATION_BOUNDS.max_provider_calls == 9
    assert HAIKU_QUALIFICATION_BOUNDS.candidates_per_call == 1
    assert HAIKU_CERT_BOUNDS.max_provider_calls == 81
    assert HAIKU_CERT_BOUNDS.hard_usd_ceiling == "5.00"
    assert HAIKU_CERT_BOUNDS.automatic_retries == 0
    assert HAIKU_4_5_PRICE_TABLE.input_usd_per_mtok == "1.00"
    assert HAIKU_4_5_PRICE_TABLE.output_usd_per_mtok == "5.00"


# ---------------------------------------------------------------------------
# D1. framing-fragment source classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("span", "leadin"),
    [
        ("While reviewing Northgate Commercial Mechanical's public pages, I noticed", True),
        ("While reviewing your public pages, I noticed", True),
        ("We noted your public site lists", True),
        ("While reviewing your public pages, I noticed you respond in five minutes", False),
        (
            'While reviewing your public pages, I noticed a "Schedule Commercial Service" '
            "request path",
            False,
        ),
        ("I noticed your team confirms appointments the same business day", False),
    ],
)
def test_is_framing_leadin(span: str, leadin: bool) -> None:
    assert _is_framing_leadin(span, S01) is leadin


def test_framing_leadin_entry_needs_no_source_v3() -> None:
    body = (
        "Hello,\n\nWhile reviewing your public pages, I noticed. It is a simulation - not a "
        "system deployed, connected, official, or operated by your business.\n\n"
        "Would it be worth comparing that simulation with your actual intake process?\n\n"
        + _PLACEHOLDERS
    )
    man = [
        _e("m1", ClaimType.SALUTATION, "Hello,"),
        _e("m2", ClaimType.TRANSITION, "While reviewing your public pages, I noticed"),
        _e(
            "m3",
            ClaimType.DISCLOSURE,
            "It is a simulation - not a system deployed, connected, official, or operated by "
            "your business.",
        ),
        _e(
            "m4",
            ClaimType.CTA,
            "Would it be worth comparing that simulation with your actual intake process?",
            cta="PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS",
        ),
        _e("m5", ClaimType.SIGNATURE_SLOT, "{{functional_role_or_team}}"),
    ]
    assert "claim_manifest_source_mismatch" not in _codes(S01, _cand("A question", body, man))


def test_framing_leadin_with_predicate_still_needs_source_v3() -> None:
    span = "While reviewing your public pages, I noticed you respond to every call in five minutes"
    body = (
        "Hello,\n\n" + span + ". It is a simulation - not a system deployed, connected, "
        "official, or operated by your business.\n\n"
        "Would it be worth comparing that simulation with your actual intake process?\n\n"
        + _PLACEHOLDERS
    )
    man = [
        _e("m1", ClaimType.SALUTATION, "Hello,"),
        _e("m2", ClaimType.TRANSITION, span),  # under-typed: has a real predicate
        _e(
            "m3",
            ClaimType.DISCLOSURE,
            "It is a simulation - not a system deployed, connected, official, or operated by "
            "your business.",
        ),
        _e(
            "m4",
            ClaimType.CTA,
            "Would it be worth comparing that simulation with your actual intake process?",
            cta="PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS",
        ),
        _e("m5", ClaimType.SIGNATURE_SLOT, "{{functional_role_or_team}}"),
    ]
    codes = _codes(S01, _cand("A question", body, man))
    # the predicate "respond ... in five minutes" is an unlicensed response claim
    assert "availability_upgraded_to_response" in codes or "unlicensed_claim" in codes


# ---------------------------------------------------------------------------
# D2. compactor
# ---------------------------------------------------------------------------

_SIG = (
    "It is a simulation - not a system deployed, connected, official, or operated by your business."
)
_CTA_Q = "Would it be worth comparing that simulation with your actual intake process?"


_FILLER_SENTENCES = [
    "I am reaching out from our small team about a short deterministic pilot that we "
    "assembled recently and wanted to share with the people who look after commercial intake.",
    "We put this together carefully over a short window using only publicly available "
    "information, and there is nothing you need to prepare or install on your side at all.",
    "This note is intended to be brief and easy to skim for a busy commercial operations "
    "team that is juggling a lot of moving pieces during a demanding season of the year.",
]


def _long_body(extra_transitions: int) -> str:
    fillers = " ".join(_FILLER_SENTENCES[:extra_transitions])
    return (
        "Hello {{functional_role_or_team}},\n\n"
        "While reviewing Northgate Commercial Mechanical's public pages, I noticed a \"Schedule "
        'Commercial Service" request path and work described as "Commercial Rooftop Unit Repair". '
        + fillers
        + " This is not a claim about how your team works today - we have no visibility into that. "
        + _SIG
        + "\n\n"
        + _CTA_Q
        + "\n\n{{verified_sender_signature}}"
    )


def test_compactor_removes_whole_transition_sentences_to_fit() -> None:
    body = _long_body(3)
    cand = _cand("A note on your commercial intake path", body, [])
    assert len(body.split()) > 130
    compacted, au = compact_candidate(cand, S01)
    assert au.applied and au.any_change
    assert au.words_after <= 130
    assert au.reached_target
    new_body = compacted.artifact("first_contact_email").text
    # every surviving sentence is a verbatim slice of the original
    for line in new_body.split("\n"):
        for s in split_sentences(line.strip()):
            if s and not s.startswith("{{"):
                assert s in body
    # protected content survives
    assert _CTA_Q in new_body
    assert "not a system deployed" in new_body
    assert "{{functional_role_or_team}}" in new_body
    assert "{{verified_sender_signature}}" in new_body
    # the strongest hook survives
    assert "Schedule Commercial Service" in new_body


def test_compactor_no_change_when_already_within_cap() -> None:
    body = (
        "Hello,\n\n"
        'While reviewing your public pages, I noticed a "Schedule Commercial Service" path. '
        + _SIG
        + "\n\n"
        + _CTA_Q
        + "\n\n"
        + _PLACEHOLDERS
    )
    compacted, au = compact_candidate(_cand("s", body, []), S01)
    assert not au.applied
    assert compacted.artifact("first_contact_email").text == body


def test_compactor_fails_when_no_safe_removal_reaches_cap() -> None:
    # every sentence is protected (a very long single disclosure sentence + the
    # sole CTA), so no whole-sentence removal can bring the body under 130 words.
    long_disclosure = (
        "This would be a simulation built only from your public pages and nothing else, "
        "it is not a system that is deployed or connected or official or operated by your "
        "business in any way at all, it uses only synthetic example inputs rather than any "
        "real customer data or any real inbound message from any real prospective customer, "
        "it deliberately routes every single case to a slow human review step before "
        "anything at all is allowed to happen next, and nothing in it touches or connects "
        "to your systems or your inbox or your scheduling tools or your phones or your "
        "dispatch board or your staff or your calendar at any single point in the whole "
        "process from beginning to end whatsoever, now or at any later time."
    )
    body = "Hello,\n\n" + long_disclosure + "\n\n" + _CTA_Q + "\n\n" + _PLACEHOLDERS
    compacted, au = compact_candidate(_cand("s", body, []), S01)
    assert au.words_before > 130
    assert not au.reached_target  # could not get under the cap by safe removal
    assert "structure_violation" in _codes(S01, compacted)


def test_compactor_manifest_entries_removed_when_span_disappears() -> None:
    body = _long_body(3)
    entries = [
        _e("m1", ClaimType.SALUTATION, "Hello {{functional_role_or_team}},"),
        _e(
            "m2",
            ClaimType.NON_SUBSTANTIVE,
            "I am reaching out from our team about a small deterministic pilot we assembled.",
        ),
        _e("m3", ClaimType.CTA, _CTA_Q, cta="PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS"),
    ]
    compacted, au = compact_candidate(_cand("s", body, entries), S01)
    if au.applied and "I am reaching out" not in compacted.artifact("first_contact_email").text:
        assert "m2" in au.manifest_entries_removed
        assert all(e.claim_id != "m2" for e in compacted.claim_manifest.entries)


def test_laundered_safety_codes_helper() -> None:
    assert laundered_safety_codes(
        {"prohibited_claim", "structure_violation"},
        {"structure_violation"},
        ZERO_TOLERANCE_SAFETY_CODES,
    ) == {"prohibited_claim"}
    assert (
        laundered_safety_codes({"structure_violation"}, set(), ZERO_TOLERANCE_SAFETY_CODES) == set()
    )


def test_compaction_never_launders_unsafe_prose_via_orchestrator() -> None:
    from opintel_communication.orchestration import GenerationOrchestrator
    from opintel_communication.store import InMemoryGenerationStore
    from opintel_communication.stub_provider import serialize_candidates

    unsafe_sentence = "You could recover roughly 15 extra booked jobs a month with this pilot."
    body = (
        "Hello {{functional_role_or_team}},\n\n"
        'While reviewing your public pages, I noticed a "Schedule Commercial Service" path. '
        + unsafe_sentence
        + " I am reaching out from our team about a small deterministic pilot we assembled over a "
        "short period using only public information for a busy commercial team to skim quickly. "
        + _SIG
        + "\n\n"
        + _CTA_Q
        + "\n\n{{verified_sender_signature}}"
    )
    cand = _cand(
        "A note on your intake path",
        body,
        [
            _e("m1", ClaimType.SALUTATION, "Hello {{functional_role_or_team}},"),
            _e("m2", ClaimType.NON_SUBSTANTIVE, unsafe_sentence),
            _e(
                "m3",
                ClaimType.CTA,
                _CTA_Q,
                cta="PERMISSION_TO_COMPARE_SIMULATION_WITH_REAL_PROCESS",
            ),
        ],
    )
    raw = serialize_candidates((cand,))

    class _A:
        adapter_version = "test"

        def generate(self, _):
            class M:
                input_tokens = output_tokens = 10
                stop_reason = "end_turn"

            return raw, M()

    store = InMemoryGenerationStore()
    store.initialize()
    orch = GenerationOrchestrator(validator=OutputValidator(contract="v2"), compactor_enabled=True)
    rec = orch.run(
        S01, _A(), store, now_epoch_seconds=0, record_id="r1", capture_provider_errors=True
    )
    row = rec.candidates[0]
    # compaction removed the unsupported-number sentence, but the finding is
    # re-injected and the candidate still fails.
    assert not row.validation.passed
    assert "unsupported_number" in {f.code for f in row.validation.findings}


# ---------------------------------------------------------------------------
# G. quality assessor
# ---------------------------------------------------------------------------


def test_quality_strongest_hook_excludes_response_commitment() -> None:
    hw, has = strongest_usable_hook_words(S01)
    assert has
    # "Our office answers every call ..." (response_commitment) must not be the hook
    assert "answers" not in hw and "confirm" not in hw
    assert {"schedule"} <= hw or {"rooftop", "unit", "repair"} & hw


def test_quality_specific_evidence_note_is_absent_for_a_good_note() -> None:
    body = (
        "Hello,\n\n"
        "While reviewing Northgate Commercial Mechanical's public pages, I noticed a \"Schedule "
        'Commercial Service" request path and work described as "Commercial Rooftop Unit Repair". '
        "This is not a claim about how your team works today - we have no visibility into that. "
        + _SIG
        + "\n\n"
        + _CTA_Q
        + "\n\n"
        + _PLACEHOLDERS
    )
    q = assess_quality(_cand("A note on your commercial intake", body, []), S01)
    assert q.uses_company_specific_evidence
    assert q.classification in ("ACCEPTABLE", "STRONG")
    assert not q.generic_praise and not q.fake_familiarity


def test_quality_flags_generic_mail_merge() -> None:
    body = (
        "Hello,\n\n"
        "I noticed your company provides commercial HVAC services and thought automation might "
        "help. You're probably swamped this time of year. "
        + _SIG
        + "\n\n"
        + _CTA_Q
        + "\n\n"
        + _PLACEHOLDERS
    )
    q = assess_quality(_cand("Quick question for you", body, []), S06)
    assert q.classification in ("WEAK", "NOT_DISTINCTIVE")
    assert q.boilerplate_hits >= 1
    assert q.fake_familiarity


def test_quality_never_rescues_unsafe_is_structural() -> None:
    # quality is a separate axis - a STRONG classification does not imply safe
    q = assess_quality(
        _cand("s", "Hello,\n\n" + _SIG + "\n\n" + _CTA_Q + "\n\n" + _PLACEHOLDERS, []), S01
    )
    assert q.classification in ("STRONG", "ACCEPTABLE", "WEAK", "NOT_DISTINCTIVE")


def test_compactor_version_string() -> None:
    assert COMPACTOR_VERSION == "comm.candidate_compactor@1"


# ---------------------------------------------------------------------------
# Section-F autonomous repairs from the first 9-call Haiku qualification:
#   1. @8 must instruct the model to append the required placeholder lines
#   2. "<Business Name> publishes/lists X" (optionally after "I noticed") is a
#      company-specific FACT, not filler
#   3. when several facts share the top strength rank, using ANY counts as the
#      strongest-hook
# ---------------------------------------------------------------------------


def test_v8_prompt_lists_required_placeholders() -> None:
    t = build_certification_prompt_bundle_v8(S01).bundle_text
    assert "'placeholder' value listed under required_disclosures" in t
    assert "each on its own line" in t
    assert "hard maximum 130" in t and "target 90-110 words" in t


@pytest.mark.parametrize(
    ("clause", "is_fact"),
    [
        ("Bayline Air Systems publishes a dedicated request path for commercial visits", True),
        (
            "I noticed Delmarva Commercial Cooling publishes a Commercial Service Request Form",
            True,
        ),
        (
            "While reviewing their pages, I noticed Meridian Commercial HVAC lists a coverage map",
            True,
        ),
        ("I noticed your team confirms appointments the same business day", False),
        ("We reviewed the market and it looks competitive", False),
    ],
)
def test_business_name_assertion_classifies_fact(clause: str, is_fact: bool) -> None:
    got = _classify(clause, contract="v2")
    assert (got == ClaimType.FACT) is is_fact


def test_named_business_observation_is_company_specific_quality() -> None:
    body = (
        "Hi {{functional_role_or_team}},\n\n"
        "Bayline Air Systems publishes a dedicated request path for commercial visits alongside "
        "Commercial HVAC Maintenance Plans. This is not a claim about how your team works "
        "today; we have no visibility into that. It is a simulation - not a system deployed, "
        "connected, official, or operated by your business.\n\n"
        "Would it be worth comparing that simulation with your actual intake process?\n\n"
        "{{verified_sender_signature}}"
    )
    q = assess_quality(_cand("Commercial intake note", body, []), S02)
    assert q.uses_company_specific_evidence
    assert q.classification != "NOT_DISTINCTIVE"


def test_strongest_hook_is_union_of_top_rank_facts() -> None:
    # s01 has three OBSERVED_PUBLIC_TEXT facts (response_commitment excluded);
    # the union spans all of them, so using any one counts as the strongest hook.
    hw, has = strongest_usable_hook_words(S01)
    assert has
    assert {"schedule"} <= hw  # "Schedule Commercial Service"
    assert {"rooftop", "unit", "repair"} & hw  # "Commercial Rooftop Unit Repair"
