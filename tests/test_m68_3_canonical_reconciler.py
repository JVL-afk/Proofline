"""M6.8-3 final architectural correction (owner authorization 2026-09-02 "FINAL
M6.8-3 ARCHITECTURAL CORRECTION"): the provider-authored claim manifest is
NON-AUTHORITATIVE; the rendered prose is the object of deterministic canonical
claim reconciliation. Section-10 adversarial regressions + section-4 fail-closed
proofs + provider-manifest disagreement diagnostics.
"""

from __future__ import annotations

from m68_3_synthetic_corpus import build_corpus
from opintel_communication.canonical_claim_reconciler import (
    CANONICAL_CLAIM_MAP_VERSION,
    CANONICAL_CLAIM_RECONCILER_VERSION,
    reconcile,
)
from opintel_communication.domain import (
    ZERO_TOLERANCE_SAFETY_CODES,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    GeneratedArtifact,
    GenerationCandidate,
    ValidatorSeverity,
)
from opintel_communication.validator import OutputValidator

_ENV = {s.scenario_id: s.envelope for s in build_corpus().specs}
S01 = _ENV["s01_strong_response_commitment"]  # RESPONSE_COMMITMENT + intake + commercial
S02 = _ENV["s02_availability_without_response"]  # 24/7 availability, no response commitment
V3 = OutputValidator(contract="v3")

_PH = (
    "\n{{verified_sender_signature}}\n{{required_postal_disclosure}}\n"
    "{{approved_opt_out_instruction}}\n{{functional_role_or_team}}"
)
_DISC = (
    "Based only on that public information, a short deterministic simulation was prepared using "
    "synthetic example inputs; it is a simulation, not a system deployed, connected, official, or "
    "operated by your business."
)
_CTA = "Would you be open to comparing that simulation with your actual intake process?"


def _fid(env, needle: str) -> str:
    for f in env.eligible_company_facts:
        if needle.lower() in f.sanitized_phrase.lower():
            return f.fact_id
    raise KeyError(needle)


def _e(cid, ctype, span, *, sources=(), strength=None):
    return ClaimManifestEntry(
        claim_id=cid,
        claim_type=ctype,
        rendered_artifact="first_contact_email",
        rendered_span=span,
        licensed_source_ids=tuple(sources),
        qualifiers=(),
        asserted_strength=strength,
        cta_intent=None,
    )


def _cand(body, entries=()):
    return GenerationCandidate(
        candidate_id="c1",
        artifacts=(
            GeneratedArtifact("subject", "A quick question"),
            GeneratedArtifact("first_contact_email", body),
        ),
        claim_manifest=ClaimManifest(entries=tuple(entries)),
    )


def _reconcile(body, env=S01, manifest=None):
    return reconcile(
        subject="A quick question",
        body=body,
        envelope=env,
        structured_cta=env.structured_cta,
        required_disclosures=env.required_disclosures,
        provider_manifest=manifest,
    )


def _v3_hard(env, body, entries=()):
    r = V3.validate(env, _cand(body, entries))
    return sorted({f.code for f in r.findings if f.severity != ValidatorSeverity.ADVISORY})


def _v3_pass(env, body, entries=()):
    return V3.validate(env, _cand(body, entries)).passed


_OPEN = (
    "While reviewing Northgate Commercial Mechanical's public pages, I noticed you list "
    '"Schedule Commercial Service" alongside "Commercial Rooftop Unit Repair".'
)
_BAYLINE_OPEN = (
    "While reviewing Bayline Air Systems public pages, I noticed a "
    '"Request a Commercial Visit" path alongside "24/7 Emergency Service".'
)


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------


def test_reconciler_and_map_versions() -> None:
    assert CANONICAL_CLAIM_RECONCILER_VERSION == "comm.canonical_claim_reconciler@1"
    assert CANONICAL_CLAIM_MAP_VERSION == "comm.canonical_claim_map@1"
    assert V3.version == "comm.output_validator@6"
    assert "unresolved_substantive_claim" in ZERO_TOLERANCE_SAFETY_CODES
    assert "canonical_reconciliation_incomplete" in ZERO_TOLERANCE_SAFETY_CODES


# --------------------------------------------------------------------------
# section 4 - fail-closed: the reconciler does not depend on the provider
# --------------------------------------------------------------------------


def test_omitted_response_claim_is_still_detected() -> None:
    body = f"{_OPEN} Your team responds to every request within five minutes. {_DISC} {_CTA}{_PH}"
    # NO manifest entry for the response claim
    codes = _v3_hard(S01, body, entries=[])
    assert "unlicensed_claim" in codes or "availability_upgraded_to_response" in codes
    assert not _v3_pass(S01, body)


def test_omitted_economic_implication_is_still_detected() -> None:
    body = f"{_OPEN} You probably lose leads after hours. {_DISC} {_CTA}{_PH}"
    assert not _v3_pass(S01, body)
    assert _reconcile(body).rejected_count >= 1


def test_omitted_integration_claim_is_still_detected() -> None:
    body = f"{_OPEN} This integrates directly with ServiceTitan. {_DISC} {_CTA}{_PH}"
    assert not _v3_pass(S01, body)


# --------------------------------------------------------------------------
# section 3 + 10 - do not trust provider claim types
# --------------------------------------------------------------------------


def test_unsupported_fact_falsely_labelled_disclosure_still_fails() -> None:
    body = (
        f"{_OPEN} It is a simulation - and your team also guarantees a one-hour on-site response. "
        f"{_DISC} {_CTA}{_PH}"
    )
    entries = [
        _e("m1", ClaimType.DISCLOSURE, "your team also guarantees a one-hour on-site response")
    ]
    assert not _v3_pass(S01, body, entries)


def test_provider_omits_a_valid_licensed_fact_still_passes_with_advisory() -> None:
    body = f"{_OPEN} {_DISC} A step that acknowledges and sorts new requests could be evaluated. {_CTA}{_PH}"  # noqa: E501
    # provider manifest omits the opening fact rows entirely
    m = _reconcile(body, manifest=ClaimManifest(entries=()))
    assert m.coverage == 1.0 and m.rejected_count == 0
    assert any(d.kind == "PROVIDER_OMITTED_CLAIM" for d in m.manifest_disagreements)
    # a v3 validate with an empty manifest still passes on the prose
    assert _v3_pass(S01, body, entries=[])


def test_provider_redundant_sourceless_wrapper_is_ignored_advisory() -> None:
    body = f"{_OPEN} {_DISC} {_CTA}{_PH}"
    intake = _fid(S01, "Schedule Commercial Service")
    comm = _fid(S01, "Commercial Rooftop Unit Repair")
    entries = [
        _e("m1", ClaimType.DISCLOSURE, _OPEN),  # source-less wrapper over the whole sentence
        _e("m2", ClaimType.FACT, '"Schedule Commercial Service"', sources=[intake]),
        _e("m3", ClaimType.FACT, '"Commercial Rooftop Unit Repair"', sources=[comm]),
    ]
    m = _reconcile(body, manifest=ClaimManifest(entries=entries))
    assert m.coverage == 1.0 and m.rejected_count == 0
    assert _v3_pass(S01, body, entries)


# --------------------------------------------------------------------------
# section 10 - availability vs response
# --------------------------------------------------------------------------


def test_availability_rendered_as_availability_passes() -> None:
    body = f"{_BAYLINE_OPEN} {_DISC} A step that acknowledges and sorts new requests could be evaluated. {_CTA}{_PH}"  # noqa: E501
    assert _v3_pass(S02, body, entries=[])


def test_availability_rendered_as_response_fails() -> None:
    body = (
        f"{_BAYLINE_OPEN} That means you answer commercial requests around the clock, 24/7. "
        f"{_DISC} {_CTA}{_PH}"
    )
    assert not _v3_pass(S02, body, entries=[])


def test_licensed_numeric_fact_passes_without_strength_increase() -> None:
    body = f"{_BAYLINE_OPEN} {_DISC} A step that acknowledges and sorts new requests could be evaluated. {_CTA}{_PH}"  # noqa: E501
    codes = _v3_hard(S02, body, entries=[])
    assert "unsupported_number" not in codes
    assert "strength_increase" not in codes


def test_invented_number_fails() -> None:
    body = f"{_OPEN} handling about 40 requests a week. {_DISC} {_CTA}{_PH}"
    codes = _v3_hard(S01, body, entries=[])
    assert "unsupported_number" in codes


# --------------------------------------------------------------------------
# section 10 - deployment / disclosure / CTA / injection / paraphrase
# --------------------------------------------------------------------------


def test_fake_deployment_claim_fails() -> None:
    body = f"{_OPEN} The simulation is now deployed and connected to your live scheduling system. {_CTA}{_PH}"  # noqa: E501
    assert not _v3_pass(S01, body, entries=[])


def test_required_negative_deployment_disclosure_passes() -> None:
    body = f"{_OPEN} {_DISC} A step that acknowledges and sorts new requests could be evaluated. {_CTA}{_PH}"  # noqa: E501
    assert _v3_pass(S01, body, entries=[])


def test_disclosure_lost_fails() -> None:
    body = (
        f"{_OPEN} A step that acknowledges and sorts new requests could be evaluated. {_CTA}{_PH}"
    )
    assert "disclosure_lost" in _v3_hard(S01, body, entries=[])


def test_cta_semantic_drift_fails() -> None:
    body = f"{_OPEN} {_DISC} Reply today to lock in a free commercial intake audit before month end.{_PH}"  # noqa: E501
    assert not _v3_pass(S01, body, entries=[])


def test_faithful_evidence_bound_paraphrase_passes() -> None:
    body = (
        "While reviewing Northgate Commercial Mechanical's public pages, I noticed the site lists "
        'a "Schedule Commercial Service" request path next to its "Commercial Rooftop Unit Repair" '
        f"work. {_DISC} A step that acknowledges and sorts new service requests could be evaluated. "  # noqa: E501
        f"{_CTA}{_PH}"
    )
    assert _v3_pass(S01, body, entries=[])


def test_unsupported_paraphrase_implication_fails() -> None:
    body = (
        f"{_OPEN} That intake path suggests inbound demand your current staffing may be missing. "
        f"{_DISC} {_CTA}{_PH}"
    )
    assert not _v3_pass(S01, body, entries=[])


# --------------------------------------------------------------------------
# coverage metric
# --------------------------------------------------------------------------


def test_unresolved_substantive_span_fails_closed() -> None:
    # a substantive clause carrying one word the reconciler can neither license
    # nor confidently reject -> coverage < 1.0 -> fail closed.
    body = f"{_OPEN} The intake path shows meaningful throughput signals. {_DISC} {_CTA}{_PH}"
    m = _reconcile(body)
    assert m.coverage < 1.0 or m.rejected_count >= 1
    assert not _v3_pass(S01, body, entries=[])


def test_clean_candidate_reaches_full_coverage() -> None:
    body = f"{_OPEN} {_DISC} A step that acknowledges and sorts new service requests could be evaluated. {_CTA}{_PH}"  # noqa: E501
    m = _reconcile(body)
    assert m.coverage == 1.0
    assert m.substantive_count >= 1
    assert m.licensed_count == m.substantive_count
    assert m.unresolved_count == 0


# --------------------------------------------------------------------------
# section 9 - historical adversarial fixtures replay clean through v3
# --------------------------------------------------------------------------

import pytest  # noqa: E402
from m68_fixtures import aplus_envelope  # noqa: E402
from test_m68_communication_validator import _ADVERSARIAL, _adv  # noqa: E402


@pytest.mark.parametrize(
    ("label", "sentence", "code"),
    [a for a in _ADVERSARIAL if a[0] not in ("cta_drift_meeting", "imperative_cta")],
    ids=[a[0] for a in _ADVERSARIAL if a[0] not in ("cta_drift_meeting", "imperative_cta")],
)
def test_historical_adversarial_fixture_still_fails_under_v3(
    label: str, sentence: str, code: str
) -> None:
    r = V3.validate(aplus_envelope(), _adv(sentence))
    assert not r.passed, f"{label}: v3 must still reject"
