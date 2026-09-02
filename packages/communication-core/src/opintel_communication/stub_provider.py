"""A deterministic stub ``ProviderAdapter``.

No network, no model. It is constructed with a fixed corpus of pre-written
candidates and, on ``generate``, serializes them to a JSON "raw response" plus
deterministic token/metadata fields derived from the prompt bundle. The
orchestrator then parses that raw string exactly as it would parse a real
provider's text, so the whole lifecycle (parse -> validate -> rank -> persist)
is exercised without a live model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from opintel_communication.domain import (
    STUB_PROVIDER_ADAPTER_VERSION,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
    GenerationResult,
    GenerationStatus,
    ProviderMetadata,
)
from opintel_communication.hashing import sha256_text


def _entry_to_json(e: ClaimManifestEntry) -> dict[str, object]:
    return {
        "claim_id": e.claim_id,
        "claim_type": str(e.claim_type),
        "rendered_artifact": e.rendered_artifact,
        "rendered_span": e.rendered_span,
        "licensed_source_ids": list(e.licensed_source_ids),
        "qualifiers": list(e.qualifiers),
        "asserted_strength": str(e.asserted_strength) if e.asserted_strength else None,
        "cta_intent": e.cta_intent,
    }


def _str_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(x) for x in value)


def _entry_from_json(d: dict[str, Any]) -> ClaimManifestEntry:
    strength = d.get("asserted_strength")
    return ClaimManifestEntry(
        claim_id=str(d["claim_id"]),
        claim_type=ClaimType(str(d["claim_type"])),
        rendered_artifact=str(d["rendered_artifact"]),
        rendered_span=str(d["rendered_span"]),
        licensed_source_ids=_str_list(d.get("licensed_source_ids")),
        qualifiers=_str_list(d.get("qualifiers")),
        asserted_strength=FactStrength(str(strength)) if strength else None,
        cta_intent=str(d["cta_intent"]) if d.get("cta_intent") else None,
    )


def _artifact_text(c: GenerationCandidate, kind: str) -> str:
    art = c.artifact(kind)
    return art.text if art is not None else ""


def serialize_candidates(candidates: tuple[GenerationCandidate, ...]) -> str:
    payload = {
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "subject": _artifact_text(c, "subject"),
                "body": _artifact_text(c, "first_contact_email"),
                "lead_source_id": c.lead_source_id,
                "claim_manifest": [_entry_to_json(e) for e in c.claim_manifest.entries],
            }
            for c in candidates
        ]
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _manifest_rows(value: Any) -> list[dict[str, Any]]:
    """Coerce a provider ``claim_manifest`` field into a list of entry dicts.

    A conformant response puts a bare list under ``claim_manifest``. Real models
    also emit it wrapped (``{"entries": [...]}`` / ``{"claims": [...]}`` /
    ``{"manifest": [...]}``) or, rarely, at the top level of the response. Non-dict
    members are skipped rather than raising ``AttributeError`` deep in parsing.
    """

    if isinstance(value, dict):
        for key in ("entries", "claims", "manifest", "claim_manifest"):
            inner = value.get(key)
            if isinstance(inner, list):
                value = inner
                break
        else:
            return []
    if not isinstance(value, list):
        return []
    return [e for e in value if isinstance(e, dict)]


def _candidate_from_row(
    row: dict[str, Any], *, fallback_manifest: Any = None
) -> GenerationCandidate:
    rows = _manifest_rows(row.get("claim_manifest"))
    if not rows and fallback_manifest is not None:
        rows = _manifest_rows(fallback_manifest)
    entries = tuple(_entry_from_json(e) for e in rows)
    return GenerationCandidate(
        candidate_id=str(row["candidate_id"]),
        artifacts=(
            GeneratedArtifact("subject", str(row.get("subject", ""))),
            GeneratedArtifact("first_contact_email", str(row.get("body", ""))),
        ),
        claim_manifest=ClaimManifest(entries=entries),
        lead_source_id=(str(row["lead_source_id"]) if row.get("lead_source_id") else None),
    )


def parse_provider_response(raw: str) -> GenerationResult:
    """Parse a raw stub/provider response into candidates.

    The provider is assumed non-authoritative and possibly non-conformant: a
    real model may emit a claim-manifest entry whose ``claim_type`` /
    ``asserted_strength`` is outside our vocabulary, omit a required field, or
    return a non-list ``candidates``. None of that may raise - it is a
    non-authoritative provider fault, surfaced as a dropped candidate and,
    when nothing survives, a REFUSED result with a reason.
    """

    try:
        data = json.loads(raw)
        rows = data["candidates"]
    except (ValueError, KeyError, TypeError):
        return GenerationResult(
            status=GenerationStatus.REFUSED, reason="unparseable provider response"
        )
    if not isinstance(rows, list):
        return GenerationResult(
            status=GenerationStatus.REFUSED, reason="provider 'candidates' is not a list"
        )

    # A model sometimes emits the manifest once, at the top level, instead of
    # per candidate; used only when a candidate row carries none of its own.
    top_manifest = data.get("claim_manifest")

    candidates: list[GenerationCandidate] = []
    dropped = 0
    drop_reasons: list[str] = []
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise TypeError("candidate row is not an object")
            candidates.append(_candidate_from_row(row, fallback_manifest=top_manifest))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            dropped += 1
            drop_reasons.append(f"{type(exc).__name__}: {exc}")

    if candidates:
        return GenerationResult(status=GenerationStatus.CANDIDATES, candidates=tuple(candidates))
    reason = "no parseable candidate"
    if drop_reasons:
        reason += f" ({dropped} malformed: {'; '.join(drop_reasons[:3])})"
    return GenerationResult(status=GenerationStatus.REFUSED, reason=reason)


@dataclass(frozen=True, slots=True)
class StubProfile:
    """Identifies one stub corpus so replay and drift checks can name it."""

    name: str
    certification_key: str


class StubProviderAdapter:
    """Implements the ``ProviderAdapter`` protocol with a fixed corpus."""

    adapter_version = STUB_PROVIDER_ADAPTER_VERSION

    def __init__(
        self,
        candidates: tuple[GenerationCandidate, ...],
        profile: StubProfile | None = None,
    ) -> None:
        self._candidates = candidates
        self.profile = profile or StubProfile(
            name="unnamed_stub",
            certification_key="comm.provider_certification.stub/deterministic/1/default",
        )

    @property
    def certification_key(self) -> str:
        return self.profile.certification_key

    def generate(self, prompt_bundle: str) -> tuple[str, ProviderMetadata]:
        raw = serialize_candidates(self._candidates)
        # Deterministic, bundle-derived token accounting - never wall-clock or random.
        digest = sha256_text(prompt_bundle)
        input_tokens = len(prompt_bundle) // 4
        output_tokens = len(raw) // 4
        return raw, ProviderMetadata(
            provider="stub",
            model="deterministic-corpus",
            model_version=STUB_PROVIDER_ADAPTER_VERSION,
            request_id=digest[:32],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
