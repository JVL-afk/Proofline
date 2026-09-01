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


def parse_provider_response(raw: str) -> GenerationResult:
    """Parse a raw stub/provider response into candidates. Malformed input is a
    non-authoritative provider fault, surfaced as an empty CANDIDATES result."""

    try:
        data = json.loads(raw)
        rows = data["candidates"]
    except (ValueError, KeyError, TypeError):
        return GenerationResult(
            status=GenerationStatus.REFUSED, reason="unparseable provider response"
        )

    candidates: list[GenerationCandidate] = []
    for row in rows:
        entries = tuple(_entry_from_json(e) for e in row.get("claim_manifest", []))
        candidates.append(
            GenerationCandidate(
                candidate_id=str(row["candidate_id"]),
                artifacts=(
                    GeneratedArtifact("subject", str(row.get("subject", ""))),
                    GeneratedArtifact("first_contact_email", str(row.get("body", ""))),
                ),
                claim_manifest=ClaimManifest(entries=entries),
                lead_source_id=(str(row["lead_source_id"]) if row.get("lead_source_id") else None),
            )
        )
    return GenerationResult(
        status=GenerationStatus.CANDIDATES if candidates else GenerationStatus.REFUSED,
        candidates=tuple(candidates),
    )


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
