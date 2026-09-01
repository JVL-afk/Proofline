"""M6.8 Evidence-Bound Communication Transformer - deterministic core.

The deterministic engine (M2-M5) stays authoritative for *what may be said*. This
package is the deterministic authority (the semantic envelope) and the
deterministic gate (the fail-closed output validator + CTA parser). It contains
no provider integration, no network, and no send path.
"""

from opintel_communication.cta_parser import ParsedCta, cta_semantic_consistency, parse_cta
from opintel_communication.domain import (
    CLAIM_MANIFEST_SCHEMA_VERSION,
    CTA_PARSER_VERSION,
    OUTPUT_VALIDATOR_VERSION,
    SEMANTIC_ENVELOPE_SCHEMA_VERSION,
    ClaimManifest,
    ClaimManifestEntry,
    ClaimType,
    CommunicationOutcome,
    FactStrength,
    GeneratedArtifact,
    GenerationCandidate,
    GenerationResult,
    GenerationStatus,
    SemanticEnvelope,
    ValidationResult,
    ValidatorFinding,
)
from opintel_communication.envelope import (
    assemble_envelope,
    compute_envelope_sha256,
    strength_for_fact,
)
from opintel_communication.validator import OutputValidator

__all__ = [
    "CLAIM_MANIFEST_SCHEMA_VERSION",
    "CTA_PARSER_VERSION",
    "OUTPUT_VALIDATOR_VERSION",
    "SEMANTIC_ENVELOPE_SCHEMA_VERSION",
    "ClaimManifest",
    "ClaimManifestEntry",
    "ClaimType",
    "CommunicationOutcome",
    "FactStrength",
    "GeneratedArtifact",
    "GenerationCandidate",
    "GenerationResult",
    "GenerationStatus",
    "OutputValidator",
    "ParsedCta",
    "SemanticEnvelope",
    "ValidationResult",
    "ValidatorFinding",
    "assemble_envelope",
    "compute_envelope_sha256",
    "cta_semantic_consistency",
    "parse_cta",
    "strength_for_fact",
]
