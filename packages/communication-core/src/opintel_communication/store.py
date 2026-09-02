"""Append-only, hash-chained communication-generation audit store.

Reference in-memory implementation of the ``GenerationStore`` protocol. Records
are frozen dataclasses; a new attempt appends a new record and never mutates a
prior one. Each record's ``record_hash`` binds it to its predecessor, so any
later edit to history is detectable.

Raw provider responses are held in a separate ``RawResponseVault`` (short
retention, crypto-erasable). The audit record keeps only the raw response's
SHA-256 and a vault ref - erasing the raw text leaves every record intact and
still fully explains each accepted/rejected candidate.
"""

from __future__ import annotations

from opintel_communication.domain import (
    GENERATION_STORE_VERSION,
    GenerationRecord,
    HumanReviewState,
)
from opintel_communication.hashing import GENESIS_HASH, chain_hash
from opintel_communication.retention import RawResponseVault


def _candidate_compaction_body(c: object) -> dict[str, object]:
    """(Haiku track D2) compaction audit fields for one candidate. Only merged
    into the hashed body when the compactor is enabled for the run - a run with
    the compactor off keeps the exact record hash it had before this feature."""
    comp = getattr(c, "compaction", None)
    return {
        "compaction_applied": bool(getattr(comp, "applied", False)),
        "compaction_reached_target": getattr(comp, "reached_target", None),
        "compaction_words_before": getattr(comp, "words_before", None),
        "compaction_words_after": getattr(comp, "words_after", None),
        "compaction_removed_sentence_ids": sorted(
            r.sentence_id for r in getattr(comp, "removed_sentences", ())
        ),
        "compaction_manifest_entries_removed": sorted(
            getattr(comp, "manifest_entries_removed", ())
        ),
        "compaction_compacted_body_sha256": getattr(comp, "compacted_body_sha256", None),
        "original_content_sha256": (
            c.original_normalized.content_sha256  # type: ignore[attr-defined]
            if getattr(c, "original_normalized", None)
            else None
        ),
        "original_passed": (
            c.original_validation.passed  # type: ignore[attr-defined]
            if getattr(c, "original_validation", None)
            else None
        ),
        "original_finding_codes": (
            list(c.original_validation.finding_codes)  # type: ignore[attr-defined]
            if getattr(c, "original_validation", None)
            else None
        ),
        "laundered_safety_codes": list(getattr(c, "laundered_safety_codes", ())),
        "quality_classification": getattr(getattr(c, "quality", None), "classification", None),
    }


def _record_body(record: GenerationRecord) -> dict[str, object]:
    """The fields that the chain hash covers. Excludes ``record_hash`` itself
    and the mutable-by-design ``human_review_*`` pointers (review transitions
    append their own immutable events elsewhere and must not rewrite history)."""

    _compactor_on = bool(record.compactor_version)
    return {
        "record_id": record.record_id,
        "sequence": record.sequence,
        "previous_record_hash": record.previous_record_hash,
        "envelope_sha256": record.envelope_sha256,
        "envelope_schema_version": record.envelope_schema_version,
        "source_lineage_bundle_sha256": record.source_lineage_bundle_sha256,
        "provider_adapter_identity": record.provider_adapter_identity,
        "provider_certification_key": record.provider_certification_key,
        "model_placeholder": record.model_placeholder,
        "provider_placeholder": record.provider_placeholder,
        "config_placeholder": record.config_placeholder,
        "prompt_template_id": record.prompt_template_id,
        "prompt_template_sha256": record.prompt_template_sha256,
        "prompt_bundle_sha256": record.prompt_bundle_sha256,
        "raw_provider_response_sha256": record.raw_provider_response_sha256,
        "requested_candidate_count": record.requested_candidate_count,
        "returned_candidate_count": record.returned_candidate_count,
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "content_sha256": c.normalized.content_sha256,
                "body_word_count": c.normalized.body_word_count,
                "passed": c.validation.passed,
                "finding_codes": list(c.validation.finding_codes),
                "claim_evidence_map": [
                    {
                        "claim_id": link.claim_id,
                        "claim_type": str(link.claim_type),
                        "licensed_source_ids": list(link.licensed_source_ids),
                        "resolved_source_kinds": list(link.resolved_source_kinds),
                        "asserted_strength": (
                            str(link.asserted_strength) if link.asserted_strength else None
                        ),
                    }
                    for link in c.claim_evidence_map
                ],
                "rank": c.rank,
                **(_candidate_compaction_body(c) if _compactor_on else {}),
                "rank_total": (c.rank_score.total if c.rank_score else None),
                "rank_components": (
                    [
                        {
                            "name": comp.name,
                            "normalized": comp.normalized,
                            "weight": comp.weight,
                            "contribution": comp.contribution,
                            "raw_value": comp.raw_value,
                        }
                        for comp in c.rank_score.components
                    ]
                    if c.rank_score
                    else None
                ),
            }
            for c in record.candidates
        ],
        "passing_candidate_ids": list(record.passing_candidate_ids),
        "ranked_candidate_ids": list(record.ranked_candidate_ids),
        "validator_version": record.validator_version,
        "cta_parser_version": record.cta_parser_version,
        "ranker_version": record.ranker_version,
        "orchestrator_version": record.orchestrator_version,
        **({"compactor_version": record.compactor_version} if _compactor_on else {}),
        "store_version": record.store_version,
        "terminal_outcome": str(record.terminal_outcome),
        "generation_status": (str(record.generation_status) if record.generation_status else None),
        "reason": record.reason,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "cost_usd": record.cost_usd,
        "created_at_epoch_seconds": record.created_at_epoch_seconds,
        "diagnostics": [list(d) for d in record.diagnostics],
    }


def compute_record_hash(record: GenerationRecord) -> str:
    return chain_hash(record.previous_record_hash, _record_body(record))


class InMemoryGenerationStore:
    """``GenerationStore`` reference implementation."""

    store_version = GENERATION_STORE_VERSION

    def __init__(self, vault: RawResponseVault | None = None) -> None:
        self._records: list[GenerationRecord] = []
        self.vault = vault or RawResponseVault()
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    @property
    def head_hash(self) -> str:
        return self._records[-1].record_hash if self._records else GENESIS_HASH

    @property
    def next_sequence(self) -> int:
        return len(self._records)

    def append(self, record: GenerationRecord) -> GenerationRecord:
        if not self._initialized:
            raise RuntimeError("store.initialize() must be called before append()")
        if record.sequence != len(self._records):
            raise ValueError(
                f"out-of-order append: record.sequence={record.sequence} "
                f"expected {len(self._records)}"
            )
        if record.previous_record_hash != self.head_hash:
            raise ValueError("previous_record_hash does not match the current chain head")
        expected = compute_record_hash(record)
        if record.record_hash != expected:
            raise ValueError("record_hash does not match the canonical hash of the record body")
        self._records.append(record)
        return record

    def all_records(self) -> tuple[GenerationRecord, ...]:
        return tuple(self._records)

    def by_envelope(self, envelope_sha256: str) -> tuple[GenerationRecord, ...]:
        return tuple(r for r in self._records if r.envelope_sha256 == envelope_sha256)

    def get(self, record_hash: str) -> GenerationRecord | None:
        for r in self._records:
            if r.record_hash == record_hash:
                return r
        return None

    def verify_chain(self) -> bool:
        prev = GENESIS_HASH
        for i, r in enumerate(self._records):
            if r.sequence != i or r.previous_record_hash != prev:
                return False
            if r.record_hash != compute_record_hash(r):
                return False
            prev = r.record_hash
        return True

    def attach_human_review(
        self, record_hash: str, review_id: str, state: HumanReviewState
    ) -> None:
        """Update ONLY the review pointer/state on a record. This is the single
        sanctioned mutation: it does not touch any hashed field, so
        ``verify_chain`` still passes. Review events themselves are immutable and
        held by the review log, not here."""

        from dataclasses import replace

        for i, r in enumerate(self._records):
            if r.record_hash == record_hash:
                self._records[i] = replace(r, human_review_id=review_id, human_review_state=state)
                return
        raise KeyError(record_hash)

    def purge_expired_raw_responses(self, now_epoch_seconds: int) -> int:
        return len(self.vault.purge_expired(now_epoch_seconds))
