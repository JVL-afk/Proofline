"""Raw-response retention machinery for the communication-generation store.

Only the *raw provider response* is subject to short retention. Everything
needed to understand why a candidate was accepted or rejected - the normalized
candidate, its claim manifest, the validator result and findings, the
claim-to-evidence map, the ranker breakdown - lives in the immutable audit
record and is never touched here.

The duration is a proposed technical maximum. It stays POLICY_PENDING until
privacy/legal confirms it; nothing in this module treats 30 days as approved.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from opintel_communication.domain import RETENTION_PROPOSAL, RawResponseRetention

SECONDS_PER_DAY = 86_400
POLICY_STATUS_PENDING = "POLICY_PENDING"


def compute_expiry(stored_at_epoch_seconds: int, max_retention_days: int) -> int:
    if max_retention_days < 0:
        raise ValueError("max_retention_days must be >= 0")
    return stored_at_epoch_seconds + max_retention_days * SECONDS_PER_DAY


def new_retention(
    stored_at_epoch_seconds: int,
    max_retention_days: int = RETENTION_PROPOSAL.raw_provider_response_max_days,
) -> RawResponseRetention:
    return RawResponseRetention(
        stored_at_epoch_seconds=stored_at_epoch_seconds,
        max_retention_days=max_retention_days,
        expires_at_epoch_seconds=compute_expiry(stored_at_epoch_seconds, max_retention_days),
        policy_status=POLICY_STATUS_PENDING,
    )


def is_expired(retention: RawResponseRetention, now_epoch_seconds: int) -> bool:
    return now_epoch_seconds >= retention.expires_at_epoch_seconds


@dataclass(frozen=True, slots=True)
class RawResponseEntry:
    record_hash: str
    raw_sha256: str
    ciphertext: str | None
    retention: RawResponseRetention

    @property
    def erased(self) -> bool:
        return self.ciphertext is None


class RawResponseVault:
    """In-memory reference vault. A real implementation would hold ciphertext in
    an access-controlled store; the interface is what matters here.

    ``ciphertext`` stands in for "encrypted raw response". Crypto-erasure drops
    it and stamps the retention metadata; the ``raw_sha256`` is kept forever so
    the audit trail can still prove exactly what text was stored and later
    destroyed.
    """

    def __init__(self) -> None:
        self._entries: dict[str, RawResponseEntry] = {}

    def store(
        self,
        record_hash: str,
        raw_text: str,
        raw_sha256: str,
        retention: RawResponseRetention,
    ) -> RawResponseEntry:
        if record_hash in self._entries:
            raise ValueError(f"raw response for {record_hash} already stored (append-only)")
        entry = RawResponseEntry(
            record_hash=record_hash,
            raw_sha256=raw_sha256,
            ciphertext=f"enc({raw_text})",
            retention=retention,
        )
        self._entries[record_hash] = entry
        return entry

    def get(self, record_hash: str) -> RawResponseEntry | None:
        return self._entries.get(record_hash)

    def crypto_erase(
        self, record_hash: str, now_epoch_seconds: int, method: str = "key_destruction"
    ) -> bool:
        entry = self._entries.get(record_hash)
        if entry is None or entry.erased:
            return False
        self._entries[record_hash] = replace(
            entry,
            ciphertext=None,
            retention=replace(
                entry.retention,
                erased_at_epoch_seconds=now_epoch_seconds,
                erase_method=method,
            ),
        )
        return True

    def purge_expired(self, now_epoch_seconds: int) -> tuple[str, ...]:
        """Crypto-erase every entry whose retention window has closed. Returns
        the record hashes erased. Idempotent: an already-erased entry is skipped."""

        erased: list[str] = []
        for record_hash, entry in list(self._entries.items()):
            if not entry.erased and is_expired(entry.retention, now_epoch_seconds):
                self.crypto_erase(record_hash, now_epoch_seconds, method="expiry_purge")
                erased.append(record_hash)
        return tuple(sorted(erased))

    def all_entries(self) -> tuple[RawResponseEntry, ...]:
        return tuple(self._entries[k] for k in sorted(self._entries))
