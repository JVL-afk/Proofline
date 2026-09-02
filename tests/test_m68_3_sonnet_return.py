"""M6.8-3 return-to-Sonnet-5 track (owner authorization 2026-09-02 "RETURN TO
SONNET 5 AND COMPLETE M6.8-3").

Haiku is HAIKU_NOT_QUALIFIED; claude-sonnet-5 is the selected model. All
model-independent improvements from the Haiku track are retained. These checks
pin the Sonnet certification tuple and confirm nothing about the shared
deterministic pipeline regressed.
"""

from __future__ import annotations

from m68_3_synthetic_corpus import build_corpus
from opintel_communication.anthropic_adapter import (
    PINNED_MODEL,
    AnthropicProviderAdapter,
    GenerationConfig,
)
from opintel_communication.certification import (
    CONFIRMED_SONNET5_PRICE_TABLE,
    SONNET_RETURN_CERT_BOUNDS,
    SONNET_RETURN_SANITY_BOUNDS,
    CertificationRunner,
)
from opintel_communication.prompt import (
    PROMPT_TEMPLATE_ID_CERT_V9,
    build_certification_prompt_bundle_v8,
    build_certification_prompt_bundle_v9,
)

_FROZEN_SONNET_KEY = "83cded100880154f94f14d7bd92bfd15b9e8e6f85de87528bf7220d7280a125b"
_PROMPT_SHA = "28f36553ff77d6041a168443a3de66597c1042d8108763a883993d52d96144c2"


def _runner() -> CertificationRunner:
    cfg = GenerationConfig(model=PINNED_MODEL, thinking="disabled", max_output_tokens=8000)
    adapter = AnthropicProviderAdapter("sk-ant-test", config=cfg)
    return CertificationRunner(
        adapter,
        bounds=SONNET_RETURN_CERT_BOUNDS,
        price_table=CONFIRMED_SONNET5_PRICE_TABLE,
        prompt_builder=build_certification_prompt_bundle_v9,
        validator_contract="v2",
        compactor_enabled=True,
        assess_candidate_quality=True,
    )


def test_sonnet_return_bounds() -> None:
    assert SONNET_RETURN_SANITY_BOUNDS.max_provider_calls == 9
    assert SONNET_RETURN_SANITY_BOUNDS.candidates_per_call == 1
    assert SONNET_RETURN_SANITY_BOUNDS.automatic_retries == 0
    assert SONNET_RETURN_CERT_BOUNDS.max_provider_calls == 81
    assert SONNET_RETURN_CERT_BOUNDS.max_output_tokens_per_call == 8_000
    assert SONNET_RETURN_CERT_BOUNDS.hard_usd_ceiling == "5.00"
    assert SONNET_RETURN_CERT_BOUNDS.automatic_retries == 0


def test_sonnet_price_table_is_owner_confirmed() -> None:
    assert CONFIRMED_SONNET5_PRICE_TABLE.confirmed is True
    assert CONFIRMED_SONNET5_PRICE_TABLE.input_usd_per_mtok == "2.00"
    assert CONFIRMED_SONNET5_PRICE_TABLE.output_usd_per_mtok == "10.00"


def test_sonnet_return_prompt_v9_is_v8_plus_single_candidate_only() -> None:
    env = build_corpus().specs[0].envelope
    v8 = build_certification_prompt_bundle_v8(env)
    v9 = build_certification_prompt_bundle_v9(env)
    assert v9.template_id == PROMPT_TEMPLATE_ID_CERT_V9
    assert v9.template_sha256 == _PROMPT_SHA
    assert v9.template_sha256 != v8.template_sha256
    # @9 is @8 with exactly one line added: the single-candidate constraint.
    added = [ln for ln in v9.bundle_text.splitlines() if ln not in v8.bundle_text.splitlines()]
    assert len(added) == 1
    assert "candidates array MUST contain EXACTLY ONE object" in added[0]
    # every other truth/safety/length/schema line is byte-identical
    removed = [ln for ln in v8.bundle_text.splitlines() if ln not in v9.bundle_text.splitlines()]
    assert removed == []


def test_sonnet_return_certification_key_is_frozen_and_distinct() -> None:
    runner = _runner()
    key = runner.certification_key(build_corpus())
    assert key.model == PINNED_MODEL == "claude-sonnet-5"
    assert key.prompt_template_id == PROMPT_TEMPLATE_ID_CERT_V9
    assert key.prompt_template_sha256 == _PROMPT_SHA
    assert key.output_validator_version == "comm.output_validator@5"
    assert key.cta_parser_version == "comm.cta_parser@2"
    assert key.observed_model_identity == "claude-sonnet-5"
    assert key.corpus_manifest_sha256 == (
        "282cdd5a2783f793a47d71b17ddf8b62242294fc0260e73a3526fbec5537d411"
    )
    # PRE_RUN_CONFIG_ID == FINAL_CERTIFICATION_KEY (no served-model drift expected).
    assert key.key_sha256() == _FROZEN_SONNET_KEY
    # Distinct from the Haiku qualification key and every prior Sonnet attempt key.
    assert key.key_sha256() != "672e000320da0752fadc4e259ab35c834848b991c484d07a81abda913569fea9"
    assert key.key_sha256() != "c64cd548572a37689e091743b905580da414f6bab29a1ca4bda914eda48609b6"


def test_sonnet_return_runner_keeps_the_hard_thresholds() -> None:
    runner = _runner()
    assert str(runner._floor) == "0.80"
    assert str(runner._manifest_ceiling) == "0.00"


# ---------------------------------------------------------------------------
# Parser robustness (exposed by the 9-call sanity check: claude-sonnet-5
# sometimes emits the claim_manifest wrapped in an object or once at the top
# level instead of a bare per-candidate list). The recovery is additive - a
# conformant bare list is unchanged, a genuinely empty manifest stays empty
# (the validator's undeclared_rendered_claim is the right signal there).
# ---------------------------------------------------------------------------

import json  # noqa: E402

from opintel_communication.stub_provider import parse_provider_response  # noqa: E402

_ENT = {
    "claim_id": "m1",
    "claim_type": "FACT",
    "rendered_artifact": "first_contact_email",
    "rendered_span": "a Book Now path",
    "licensed_source_ids": ["x"],
}
_BASE = {"candidate_id": "c1", "subject": "s", "body": "body text"}


def test_parser_bare_list_unchanged() -> None:
    r = parse_provider_response(json.dumps({"candidates": [dict(_BASE, claim_manifest=[_ENT])]}))
    assert len(r.candidates[0].claim_manifest.entries) == 1


def test_parser_recovers_wrapped_and_top_level_manifest() -> None:
    for shape in (
        {"candidates": [dict(_BASE, claim_manifest={"entries": [_ENT]})]},
        {"candidates": [dict(_BASE, claim_manifest={"claims": [_ENT]})]},
        {"candidates": [_BASE], "claim_manifest": [_ENT]},
    ):
        r = parse_provider_response(json.dumps(shape))
        assert len(r.candidates[0].claim_manifest.entries) == 1


def test_parser_row_manifest_wins_over_top_level() -> None:
    raw = json.dumps(
        {"candidates": [dict(_BASE, claim_manifest=[_ENT, _ENT])], "claim_manifest": [_ENT]}
    )
    assert len(parse_provider_response(raw).candidates[0].claim_manifest.entries) == 2


def test_parser_skips_non_dict_manifest_members_without_raising() -> None:
    raw = json.dumps({"candidates": [dict(_BASE, claim_manifest=[_ENT, "oops", None, 42])]})
    r = parse_provider_response(raw)
    assert len(r.candidates[0].claim_manifest.entries) == 1


def test_parser_genuinely_empty_manifest_stays_empty() -> None:
    raw = json.dumps({"candidates": [dict(_BASE, claim_manifest=[])]})
    r = parse_provider_response(raw)
    assert len(r.candidates[0].claim_manifest.entries) == 0


# ---------------------------------------------------------------------------
# Bounded redundant-manifest-wrapper reconciliation (owner authorization
# 2026-09-02 "AUTHORIZE BOUNDED REDUNDANT-MANIFEST RECONCILIATION", section 4).
# A source-less wrapper entry escapes claim_manifest_source_mismatch ONLY when
# every substantive unit of its span is independently and validly licensed by
# finer-grained sibling entries and the wrapper itself adds nothing. The
# provider's declared claim_type is never trusted.
# ---------------------------------------------------------------------------

from opintel_communication.domain import (  # noqa: E402
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
)
from opintel_communication.validator import (  # noqa: E402
    OutputValidator,
    _redundant_wrapper_reconciled,
)

_ENVS = {s.scenario_id: s.envelope for s in build_corpus().specs}
_S01 = _ENVS["s01_strong_response_commitment"]  # Northgate Commercial Mechanical
_S02 = _ENVS["s02_availability_without_response"]  # Bayline Air Systems
_V2 = OutputValidator(contract="v2")

# real s01 / s02 envelope fact ids
_S01_INTAKE = "90e14c88-a134-52d4-b208-804f2792f4bb"  # "Schedule Commercial Service"
_S01_COMMERCIAL = "8eeca0ee-1e31-5980-ad12-d4fec04928d1"  # "Commercial Rooftop Unit Repair"
_S02_AVAIL = "28a739eb-1569-5e9e-8d0c-6f1a6bb8f6f4"  # "24/7 Emergency Service"
_S02_COMMERCIAL = "8f9bd8f2-3a82-5e37-9e63-3a3f6f2b6e8a"  # "Commercial HVAC Maintenance Plans"


def _we(cid: str, ctype: ClaimType, span: str, *, sources: tuple[str, ...] = (), strength=None):
    return ClaimManifestEntry(
        claim_id=cid,
        claim_type=ctype,
        rendered_artifact="first_contact_email",
        rendered_span=span,
        licensed_source_ids=sources,
        qualifiers=(),
        asserted_strength=strength,
        cta_intent=None,
    )


def _wcand(*entries: ClaimManifestEntry) -> GenerationCandidate:
    return GenerationCandidate(
        candidate_id="c1",
        artifacts=(
            GeneratedArtifact("subject", "q"),
            GeneratedArtifact("first_contact_email", "b"),
        ),
        claim_manifest=ClaimManifest(entries=tuple(entries)),
    )


def _real_source_id(env, needle: str) -> str:
    for f in env.eligible_company_facts:
        if needle.lower() in f.sanitized_phrase.lower():
            return f.fact_id
    raise KeyError(needle)


# resolve the ids robustly (corpus generation is deterministic but not pinned here)
_S02_AVAIL = _real_source_id(_S02, "24/7 Emergency Service")
_S02_COMMERCIAL = _real_source_id(_S02, "Commercial HVAC Maintenance Plans")
_S01_INTAKE = _real_source_id(_S01, "Schedule Commercial Service")
_S01_COMMERCIAL = _real_source_id(_S01, "Commercial Rooftop Unit Repair")


def test_wrapper_PASS_two_licensed_siblings_cover_the_sentence() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        'While reviewing the Bayline Air Systems public pages, I noticed "24/7 Emergency '
        'Service" alongside "Commercial HVAC Maintenance Plans".',
    )
    s1 = _we("m2", ClaimType.FACT, '"24/7 Emergency Service"', sources=(_S02_AVAIL,))
    s2 = _we(
        "m3", ClaimType.FACT, '"Commercial HVAC Maintenance Plans"', sources=(_S02_COMMERCIAL,)
    )
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1, s2), _S02) is True


def test_wrapper_FAIL_only_one_fact_has_a_licensed_sibling() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        'While reviewing the Bayline Air Systems public pages, I noticed "24/7 Emergency '
        'Service" alongside "Commercial HVAC Maintenance Plans".',
    )
    s1 = _we("m2", ClaimType.FACT, '"24/7 Emergency Service"', sources=(_S02_AVAIL,))
    s2_unlicensed = _we("m3", ClaimType.FACT, '"Commercial HVAC Maintenance Plans"', sources=())
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1, s2_unlicensed), _S02) is False


def test_wrapper_FAIL_unsupported_response_claim_in_the_wrapper() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service" and it looks like your team responds immediately.',
    )
    s1 = _we("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=(_S01_INTAKE,))
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1), _S01) is False


def test_wrapper_FAIL_invented_number_in_the_wrapper() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service" handling roughly 40 requests a week.',
    )
    s1 = _we("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=(_S01_INTAKE,))
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1), _S01) is False


def test_wrapper_FAIL_unsupported_economic_inference_in_the_wrapper() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service", which likely loses you revenue when calls go '
        "unanswered.",
    )
    s1 = _we("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=(_S01_INTAKE,))
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1), _S01) is False


def test_wrapper_FAIL_wrapper_asserts_stronger_evidence_than_siblings() -> None:
    wrapper = _we(
        "m1",
        ClaimType.FACT,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service" alongside "Commercial Rooftop Unit Repair".',
        strength=FactStrength.VERIFIED_FACT,
    )
    s1 = _we(
        "m2",
        ClaimType.FACT,
        '"Schedule Commercial Service"',
        sources=(_S01_INTAKE,),
        strength=FactStrength.OBSERVED_PUBLIC_TEXT,
    )
    s2 = _we(
        "m3",
        ClaimType.FACT,
        '"Commercial Rooftop Unit Repair"',
        sources=(_S01_COMMERCIAL,),
        strength=FactStrength.OBSERVED_PUBLIC_TEXT,
    )
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1, s2), _S01) is False


def test_wrapper_FAIL_no_sibling_entries_at_all() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service".',
    )
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper), _S01) is False


def test_wrapper_PASS_pure_framing_around_fully_licensed_siblings() -> None:
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service" alongside "Commercial Rooftop Unit Repair".',
    )
    s1 = _we("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=(_S01_INTAKE,))
    s2 = _we("m3", ClaimType.FACT, '"Commercial Rooftop Unit Repair"', sources=(_S01_COMMERCIAL,))
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1, s2), _S01) is True


def test_wrapper_FAIL_does_not_trust_a_DISCLOSURE_label_hiding_a_new_fact() -> None:
    # wrapper introduces "Emergency Chiller Replacement" (no sibling, no source)
    wrapper = _we(
        "m1",
        ClaimType.DISCLOSURE,
        "While reviewing the Northgate Commercial Mechanical public pages, I noticed "
        '"Schedule Commercial Service" and Emergency Chiller Replacement work.',
    )
    s1 = _we("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=(_S01_INTAKE,))
    assert _redundant_wrapper_reconciled(wrapper, _wcand(wrapper, s1), _S01) is False
