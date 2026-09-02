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
    PROMPT_TEMPLATE_ID_CERT_V8,
    build_certification_prompt_bundle_v8,
)

_FROZEN_SONNET_KEY = "8fdd204f2408480cc6613d3e2f02bf041aaec734b5da9cdcda2570e0002e85da"
_PROMPT_SHA = "f529826219ef9b50185a9d138353e8116f34ec4c34fbf41e9d635ba20bdcb349"


def _runner() -> CertificationRunner:
    cfg = GenerationConfig(model=PINNED_MODEL, thinking="disabled", max_output_tokens=8000)
    adapter = AnthropicProviderAdapter("sk-ant-test", config=cfg)
    return CertificationRunner(
        adapter,
        bounds=SONNET_RETURN_CERT_BOUNDS,
        price_table=CONFIRMED_SONNET5_PRICE_TABLE,
        prompt_builder=build_certification_prompt_bundle_v8,
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


def test_sonnet_return_reuses_prompt_v8_unchanged() -> None:
    bundle = build_certification_prompt_bundle_v8(build_corpus().specs[0].envelope)
    assert bundle.template_id == PROMPT_TEMPLATE_ID_CERT_V8
    assert bundle.template_sha256 == _PROMPT_SHA


def test_sonnet_return_certification_key_is_frozen_and_distinct() -> None:
    runner = _runner()
    key = runner.certification_key(build_corpus())
    assert key.model == PINNED_MODEL == "claude-sonnet-5"
    assert key.prompt_template_id == PROMPT_TEMPLATE_ID_CERT_V8
    assert key.prompt_template_sha256 == _PROMPT_SHA
    assert key.output_validator_version == "comm.output_validator@4"
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
