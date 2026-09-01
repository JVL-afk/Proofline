"""M6.8 communication-layer ports.

``ProviderAdapter`` is still an interface only - no real provider is called in
M6.8-2 (``StubProviderAdapter`` in ``stub_provider`` is the deterministic
stand-in; a live adapter waits for separate owner authorization at M6.8-3).

``GenerationStore`` now has a concrete reference implementation
(``store.InMemoryGenerationStore``); the Protocol records the seam a durable
implementation must satisfy. There is no delivery, recipient, or send port
anywhere in this layer.
"""

from __future__ import annotations

from typing import Protocol

from opintel_communication.domain import GenerationRecord, ProviderMetadata


class ProviderAdapter(Protocol):
    """Provider-neutral generation seam (ADR-0011). The prompt bundle is
    assembled by the trusted control plane from a fixed versioned template plus
    the envelope rendered as data-only fields; the adapter only transports it
    and returns raw text plus token metadata."""

    certification_key: str  # comm.provider_certification.<provider>/<model>/<ver>/<cfg>

    def generate(self, prompt_bundle: str) -> tuple[str, ProviderMetadata]: ...


class GenerationStore(Protocol):
    """Immutable, append-only, hash-chained audit of every generation attempt.

    Raw provider responses live in a separate short-retention vault (encrypted,
    access-controlled, crypto-erasable at the proposed 30-day technical maximum,
    POLICY_PENDING). The durable record - envelope hash, normalized candidates,
    manifests, validator result/findings, claim-to-evidence map, ranker
    breakdown, cost - is retained under the eventual ai_communication_generation
    policy and survives raw-response erasure intact.
    """

    store_version: str

    def initialize(self) -> None: ...

    @property
    def head_hash(self) -> str: ...

    @property
    def next_sequence(self) -> int: ...

    def append(self, record: GenerationRecord) -> GenerationRecord: ...

    def all_records(self) -> tuple[GenerationRecord, ...]: ...

    def by_envelope(self, envelope_sha256: str) -> tuple[GenerationRecord, ...]: ...

    def get(self, record_hash: str) -> GenerationRecord | None: ...

    def verify_chain(self) -> bool: ...

    def purge_expired_raw_responses(self, now_epoch_seconds: int) -> int: ...
