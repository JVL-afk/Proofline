"""M6.8 communication-layer ports - interfaces only.

No implementation of a provider adapter or a generation store exists yet
(M6.8-1 is deterministic-only). These Protocols define the seams M6.8-2/M6.8-3
will fill. There is no delivery, recipient, or send port anywhere in this layer.
"""

from __future__ import annotations

from typing import Protocol

from opintel_communication.domain import (
    GenerationAttemptOutcome,
    GenerationResult,
    ProviderMetadata,
    SemanticEnvelope,
)


class ProviderAdapter(Protocol):
    """Provider-neutral generation seam (ADR-0011). The prompt bundle is assembled
    by the trusted control plane from a fixed versioned template plus the
    envelope rendered as data-only fields; the adapter only transports it."""

    certification_key: str  # comm.provider_certification.<provider>/<model>/<ver>/<cfg>

    def generate(self, prompt_bundle: str) -> tuple[str, ProviderMetadata]: ...


class GenerationStore(Protocol):
    """Immutable, append-only audit of every generation attempt. Raw provider
    responses are encrypted, access-controlled, and hard-deleted at the proposed
    30-day technical maximum (NOT legally approved); the durable
    hash/metadata/validator-result/normalized-artifact/claim-map/cost record
    follows the eventual ai_communication_generation policy."""

    def initialize(self) -> None: ...

    def record_attempt(
        self,
        envelope: SemanticEnvelope,
        generation_result: GenerationResult | None,
        outcome: GenerationAttemptOutcome,
        raw_provider_response: str | None,
        prompt_template_id: str,
        prompt_template_sha256: str,
        cost_usd: str,
    ) -> None: ...

    def purge_expired_raw_responses(self, now_epoch_seconds: int) -> int: ...
