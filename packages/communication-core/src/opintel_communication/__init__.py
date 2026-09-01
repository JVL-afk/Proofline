"""M6.8 Evidence-Bound Communication Transformer - deterministic core.

The deterministic engine (M2-M5) stays authoritative for *what may be said*. This
package is the deterministic authority (the semantic envelope), the deterministic
gate (the fail-closed output validator + CTA parser), and - from M6.8-2 - the
stubbed generation lifecycle: a deterministic provider stub, an append-only
hash-chained audit store, a deterministic candidate ranker, raw-response
retention machinery, and an immutable human-review domain. No provider
integration, no network, no send path.
"""

from opintel_communication.cta_parser import ParsedCta, cta_semantic_consistency, parse_cta
from opintel_communication.domain import (
    CANDIDATE_RANKER_VERSION,
    CLAIM_MANIFEST_SCHEMA_VERSION,
    CTA_PARSER_VERSION,
    GENERATION_ORCHESTRATOR_VERSION,
    GENERATION_STORE_VERSION,
    HUMAN_REVIEW_SCHEMA_VERSION,
    OUTPUT_VALIDATOR_VERSION,
    RETENTION_PROPOSAL,
    SEMANTIC_ENVELOPE_SCHEMA_VERSION,
    STUB_PROVIDER_ADAPTER_VERSION,
    CandidateAuditRow,
    ClaimEvidenceLink,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    CommunicationOutcome,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
    GenerationRecord,
    GenerationResult,
    GenerationStatus,
    HumanReview,
    HumanReviewAction,
    HumanReviewEvent,
    HumanReviewState,
    NormalizedCandidate,
    ProviderDriftDescriptor,
    RankComponent,
    RankedCandidate,
    RankScore,
    RawResponseRetention,
    SemanticEnvelope,
    ValidationResult,
    ValidatorFinding,
)
from opintel_communication.envelope import (
    assemble_envelope,
    compute_envelope_sha256,
    strength_for_fact,
)
from opintel_communication.hashing import canonical_json, chain_hash, sha256_hex, sha256_text
from opintel_communication.normalize import normalize_candidate
from opintel_communication.orchestration import GenerationOrchestrator
from opintel_communication.prompt import build_prompt_bundle
from opintel_communication.ranker import CandidateRanker
from opintel_communication.retention import (
    RawResponseVault,
    compute_expiry,
    is_expired,
    new_retention,
)
from opintel_communication.review import (
    ReviewTransitionError,
    accept_not_distinctive,
    open_review,
    reject_all,
    reject_candidate,
    select_candidate,
)
from opintel_communication.store import InMemoryGenerationStore, compute_record_hash
from opintel_communication.stub_provider import (
    StubProfile,
    StubProviderAdapter,
    parse_provider_response,
    serialize_candidates,
)
from opintel_communication.validator import OutputValidator

__all__ = [
    "CANDIDATE_RANKER_VERSION",
    "CLAIM_MANIFEST_SCHEMA_VERSION",
    "CTA_PARSER_VERSION",
    "GENERATION_ORCHESTRATOR_VERSION",
    "GENERATION_STORE_VERSION",
    "HUMAN_REVIEW_SCHEMA_VERSION",
    "OUTPUT_VALIDATOR_VERSION",
    "RETENTION_PROPOSAL",
    "SEMANTIC_ENVELOPE_SCHEMA_VERSION",
    "STUB_PROVIDER_ADAPTER_VERSION",
    "CandidateAuditRow",
    "CandidateRanker",
    "ClaimEvidenceLink",
    "ClaimManifest",
    "ClaimManifestEntry",
    "ClaimType",
    "CommunicationOutcome",
    "FactStrength",
    "GeneratedArtifact",
    "GenerationCandidate",
    "GenerationOrchestrator",
    "GenerationRecord",
    "GenerationResult",
    "GenerationStatus",
    "HumanReview",
    "HumanReviewAction",
    "HumanReviewEvent",
    "HumanReviewState",
    "InMemoryGenerationStore",
    "NormalizedCandidate",
    "OutputValidator",
    "ParsedCta",
    "ProviderDriftDescriptor",
    "RankComponent",
    "RankScore",
    "RankedCandidate",
    "RawResponseRetention",
    "RawResponseVault",
    "ReviewTransitionError",
    "SemanticEnvelope",
    "StubProfile",
    "StubProviderAdapter",
    "ValidationResult",
    "ValidatorFinding",
    "accept_not_distinctive",
    "assemble_envelope",
    "build_prompt_bundle",
    "canonical_json",
    "chain_hash",
    "compute_envelope_sha256",
    "compute_expiry",
    "compute_record_hash",
    "cta_semantic_consistency",
    "is_expired",
    "new_retention",
    "normalize_candidate",
    "open_review",
    "parse_cta",
    "parse_provider_response",
    "reject_all",
    "reject_candidate",
    "select_candidate",
    "serialize_candidates",
    "sha256_hex",
    "sha256_text",
    "strength_for_fact",
]
