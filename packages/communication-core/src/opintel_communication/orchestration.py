"""``comm.generation_orchestrator@1`` - the stubbed generation lifecycle.

    immutable semantic envelope
      -> prompt bundle (control-plane assembled, data-only envelope)
      -> stub provider request
      -> N bounded candidates + claim manifests
      -> deterministic validation (comm.output_validator@1)
      -> reject invalid candidates
      -> deterministic ranking of survivors (comm.candidate_ranker@1)
      -> append-only, hash-chained generation record
      -> human-review-ready state

No live provider. No automatic regeneration loop. Default N=3, hard maximum 5.

Terminals:
  * AI_COMMUNICATION_CANDIDATE_READY  - >=1 candidate passed; ranked; awaiting review
  * AI_COMMUNICATION_REJECTED         - candidates returned, none passed validation
  * COMMUNICATION_NOT_DISTINCTIVE_ENOUGH - envelope has no distinctive fact
All three are valid, non-send terminals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from opintel_communication.compactor import (
    COMPACTOR_VERSION,
    compact_candidate,
    laundered_safety_codes,
)
from opintel_communication.domain import (
    CTA_PARSER_VERSION,
    GENERATION_ORCHESTRATOR_VERSION,
    GENERATION_STORE_VERSION,
    HARD_MAX_CANDIDATE_COUNT,
    OUTPUT_VALIDATOR_VERSION,
    ZERO_TOLERANCE_SAFETY_CODES,
    CandidateAuditRow,
    ClaimEvidenceLink,
    CommunicationOutcome,
    ConditionalInference,
    EnvelopeFact,
    GenerationCandidate,
    GenerationRecord,
    GenerationStatus,
    HumanReviewState,
    M3FindingRef,
    Recommendation,
    SemanticEnvelope,
    ValidationResult,
    ValidatorFinding,
    ValidatorSeverity,
)
from opintel_communication.hashing import sha256_text
from opintel_communication.normalize import normalize_candidate
from opintel_communication.prompt import PromptBundle, build_prompt_bundle
from opintel_communication.quality import assess_quality
from opintel_communication.ranker import CandidateRanker
from opintel_communication.retention import new_retention
from opintel_communication.store import InMemoryGenerationStore, compute_record_hash
from opintel_communication.stub_provider import parse_provider_response
from opintel_communication.validator import OutputValidator

_ZERO_COST = "0.00"


def _source_kind(env: SemanticEnvelope, source_id: str) -> str:
    src = env.source_by_id(source_id)
    if isinstance(src, EnvelopeFact):
        return f"company_fact:{src.category}"
    if isinstance(src, M3FindingRef):
        return f"m3_finding:{src.kind}"
    if isinstance(src, ConditionalInference):
        return "conditional_inference"
    if isinstance(src, Recommendation):
        return "recommendation"
    return "unresolved"


def _claim_evidence_map(
    env: SemanticEnvelope, candidate: GenerationCandidate
) -> tuple[ClaimEvidenceLink, ...]:
    links: list[ClaimEvidenceLink] = []
    for entry in candidate.claim_manifest.entries:
        links.append(
            ClaimEvidenceLink(
                claim_id=entry.claim_id,
                claim_type=entry.claim_type,
                rendered_span=entry.rendered_span,
                licensed_source_ids=entry.licensed_source_ids,
                resolved_source_kinds=tuple(
                    _source_kind(env, sid) for sid in entry.licensed_source_ids
                ),
                asserted_strength=entry.asserted_strength,
            )
        )
    return tuple(links)


class GenerationOrchestrator:
    orchestrator_version = GENERATION_ORCHESTRATOR_VERSION

    def __init__(
        self,
        validator: OutputValidator | None = None,
        ranker: CandidateRanker | None = None,
        *,
        compactor_enabled: bool = False,
        assess_candidate_quality: bool = False,
    ) -> None:
        self._validator = validator or OutputValidator()
        self._ranker = ranker or CandidateRanker()
        # (Haiku track D2/G) both default OFF so existing runs are byte-identical.
        self._compactor_enabled = compactor_enabled
        self._assess_quality = assess_candidate_quality

    def run(
        self,
        envelope: SemanticEnvelope,
        adapter: object,
        store: InMemoryGenerationStore,
        *,
        now_epoch_seconds: int,
        requested_candidate_count: int | None = None,
        record_id: str,
        prompt_builder: Callable[[SemanticEnvelope], PromptBundle] = build_prompt_bundle,
        provider_context: tuple[tuple[str, str], ...] = (),
        cost_fn: Callable[[int, int], str] | None = None,
        capture_provider_errors: bool = False,
    ) -> GenerationRecord:
        """M6.8-2 defaults are unchanged. M6.8-3 certification passes
        ``prompt_builder=build_certification_prompt_bundle``, a real
        ``provider_context`` (provider / model / config identity to replace the
        pending placeholders), and a real ``cost_usd`` derived from provider
        token metadata."""

        gr = envelope.generation_request
        requested = requested_candidate_count or gr.candidate_count
        if not (1 <= requested <= HARD_MAX_CANDIDATE_COUNT):
            raise ValueError(f"requested_candidate_count must be 1..{HARD_MAX_CANDIDATE_COUNT}")

        diagnostics: list[tuple[str, str]] = []
        bundle = prompt_builder(envelope)
        ctx = dict(provider_context)

        distinctive = envelope.has_distinctive_fact()
        raw: str | None = None
        input_tokens = output_tokens = 0
        adapter_identity = (
            f"{type(adapter).__name__}@{getattr(adapter, 'adapter_version', 'unknown')}"
        )

        candidates: tuple[GenerationCandidate, ...] = ()
        gen_status: GenerationStatus | None = None
        provider_failed = False
        if not distinctive:
            terminal = CommunicationOutcome.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH
            gen_status = GenerationStatus.COMMUNICATION_NOT_DISTINCTIVE_ENOUGH
            reason = "envelope contains no fact distinctive enough for a non-generic opening"
            diagnostics.append(
                ("distinctiveness", "has_distinctive_fact=False; provider not called")
            )
        else:
            try:
                raw, meta = adapter.generate(bundle.bundle_text)  # type: ignore[attr-defined]
                input_tokens, output_tokens = meta.input_tokens, meta.output_tokens
                result = parse_provider_response(raw or "")
                candidates = result.candidates
                if len(candidates) > requested:
                    diagnostics.append(
                        (
                            "candidate_cap",
                            f"provider returned {len(candidates)}; capped to {requested}",
                        )
                    )
                    candidates = candidates[:requested]
                terminal = CommunicationOutcome.AI_COMMUNICATION_REJECTED
                gen_status = result.status
                reason = None
            except Exception as exc:  # fail-closed provider boundary
                if not capture_provider_errors:
                    raise
                provider_failed = True
                raw = None
                # A non-PASS provider outcome can still carry real API usage
                # (thinking-only, malformed candidate, 4xx with a body). Cost is
                # a separate field from outcome: bill the usage that came back.
                input_tokens = int(getattr(exc, "input_tokens", 0) or 0)
                output_tokens = int(getattr(exc, "output_tokens", 0) or 0)
                terminal = CommunicationOutcome(getattr(exc, "outcome", "GENERATION_REFUSED"))
                gen_status = GenerationStatus.REFUSED
                reason = f"provider call failed fail-closed: {type(exc).__name__}: {exc}"
                diagnostics.append(("provider_error", reason))
                _perr_type = str(getattr(exc, "provider_error_type", "") or "")
                _perr_msg = str(getattr(exc, "provider_error_message", "") or "")
                if _perr_type or _perr_msg:
                    diagnostics.append(
                        ("provider_error_detail", f"type={_perr_type!r} message={_perr_msg!r}")
                    )
                if input_tokens or output_tokens:
                    diagnostics.append(
                        (
                            "provider_usage_on_refusal",
                            f"input_tokens={input_tokens} output_tokens={output_tokens} "
                            f"request_id={getattr(exc, 'request_id', '')!r}",
                        )
                    )

        # -- validate every returned candidate --------------------------------
        audit_rows: list[CandidateAuditRow] = []
        passing: list[tuple[GenerationCandidate, object]] = []
        for cand in candidates:
            v_orig = self._validator.validate(envelope, cand)
            eff = cand
            validation = v_orig
            compaction = None
            original_validation = None
            original_normalized = None
            laundered: tuple[str, ...] = ()

            if self._compactor_enabled:
                compacted, comp_audit = compact_candidate(cand, envelope)
                compaction = comp_audit
                if comp_audit.any_change:
                    v_comp = self._validator.validate(envelope, compacted)
                    lc = laundered_safety_codes(
                        {f.code for f in v_orig.findings},
                        {f.code for f in v_comp.findings},
                        ZERO_TOLERANCE_SAFETY_CODES,
                    )
                    laundered = tuple(sorted(lc))
                    # (D2) compaction must never launder unsafe prose: re-attach
                    # any zero-tolerance safety finding that only disappeared
                    # because compaction removed its sentence.
                    extra = tuple(
                        ValidatorFinding(
                            code=c,
                            message=(
                                "present in the raw provider output; the sentence carrying it "
                                "was removed by comm.candidate_compactor@1 - still "
                                "certification-invalidating"
                            ),
                            severity=ValidatorSeverity.HARD_FAILURE,
                        )
                        for c in laundered
                    )
                    validation = ValidationResult(
                        candidate_id=v_comp.candidate_id,
                        passed=v_comp.passed and not laundered,
                        findings=v_comp.findings + extra,
                        validator_version=v_comp.validator_version,
                        cta_parser_version=v_comp.cta_parser_version,
                    )
                    eff = compacted
                    original_validation = v_orig
                    original_normalized = normalize_candidate(cand)

            quality = assess_quality(eff, envelope) if self._assess_quality else None
            row = CandidateAuditRow(
                candidate_id=cand.candidate_id,
                normalized=normalize_candidate(eff),
                claim_manifest=eff.claim_manifest,
                validation=validation,
                claim_evidence_map=_claim_evidence_map(envelope, eff),
                compaction=compaction,
                original_normalized=original_normalized,
                original_validation=original_validation,
                laundered_safety_codes=laundered,
                quality=quality,
            )
            audit_rows.append(row)
            if validation.passed:
                passing.append((eff, validation))

        ranked_ids: tuple[str, ...] = ()
        if distinctive and not provider_failed:
            if passing:
                ranked = self._ranker.rank(envelope, tuple(passing))  # type: ignore[arg-type]
                by_id = {r.candidate_id: r for r in ranked}
                audit_rows = [
                    replace(
                        row,
                        rank=by_id[row.candidate_id].rank,
                        rank_score=by_id[row.candidate_id].score,
                    )
                    if row.candidate_id in by_id
                    else row
                    for row in audit_rows
                ]
                ranked_ids = tuple(r.candidate_id for r in ranked)
                terminal = CommunicationOutcome.AI_COMMUNICATION_CANDIDATE_READY
                reason = None
            else:
                terminal = CommunicationOutcome.AI_COMMUNICATION_REJECTED
                reason = "all returned candidates failed deterministic validation"
                diagnostics.append(("validation", f"{len(candidates)} candidates, 0 passed"))

        passing_ids = tuple(sorted(c.candidate_id for c, _ in passing))
        # Read the certification key AFTER the call so it reflects the observed
        # serving-model identity, not the pre-call 'unobserved' placeholder.
        provider_cert_key = getattr(adapter, "certification_key", "n/a")

        # -- assemble the append-only record --------------------------------
        skeleton = GenerationRecord(
            record_id=record_id,
            sequence=store.next_sequence,
            previous_record_hash=store.head_hash,
            record_hash="",
            envelope_sha256=envelope.envelope_sha256,
            envelope_schema_version=envelope.schema_version,
            source_lineage_bundle_sha256=envelope.source_lineage.m2_m5_bundle_sha256,
            provider_adapter_identity=adapter_identity,
            provider_certification_key=provider_cert_key,
            model_placeholder=ctx.get("model", "<model:pending-m6.8-3>"),
            provider_placeholder=ctx.get("provider", "<provider:pending-m6.8-3>"),
            config_placeholder=ctx.get("config", "<config:pending-m6.8-3>"),
            prompt_template_id=bundle.template_id,
            prompt_template_sha256=bundle.template_sha256,
            prompt_bundle_sha256=bundle.bundle_sha256,
            raw_provider_response_sha256=(sha256_text(raw) if raw is not None else None),
            raw_provider_response_ref=None,
            raw_response_retention=None,
            requested_candidate_count=requested,
            returned_candidate_count=len(candidates),
            candidates=tuple(audit_rows),
            passing_candidate_ids=passing_ids,
            ranked_candidate_ids=ranked_ids,
            validator_version=getattr(self._validator, "version", OUTPUT_VALIDATOR_VERSION),
            cta_parser_version=getattr(self._validator, "cta_parser_version", CTA_PARSER_VERSION),
            ranker_version=self._ranker.version,
            orchestrator_version=self.orchestrator_version,
            compactor_version=(COMPACTOR_VERSION if self._compactor_enabled else ""),
            store_version=GENERATION_STORE_VERSION,
            terminal_outcome=terminal,
            generation_status=gen_status,
            reason=reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=(cost_fn(input_tokens, output_tokens) if cost_fn is not None else _ZERO_COST),
            human_review_state=HumanReviewState.PENDING,
            human_review_id=None,
            created_at_epoch_seconds=now_epoch_seconds,
            diagnostics=tuple(diagnostics),
        )
        record_hash = compute_record_hash(skeleton)
        retention = new_retention(now_epoch_seconds) if raw is not None else None
        record = replace(
            skeleton,
            record_hash=record_hash,
            raw_provider_response_ref=(f"vault:{record_hash}" if raw is not None else None),
            raw_response_retention=retention,
        )
        store.append(record)
        if raw is not None and retention is not None:
            store.vault.store(
                record_hash=record_hash,
                raw_text=raw,
                raw_sha256=sha256_text(raw),
                retention=retention,
            )
        return record
