"""Build an offline, business-only M6.7 seed/source package.

This module performs no network access and grants no authority. It freezes eligibility and
deduplication before generating a seed, then emits per-host review records that remain unapproved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

POLICY_VERSION = "m6.7.phase1.seed-generator-source-policy@1"
ORDERING_VERSION = "m6.7.phase1.seeded-order@1"
FRAME_MAXIMUM = 100
COHORT_TARGET = 24
REQUIRED_CATEGORIES = (
    "identity",
    "texas",
    "commercial_hvac",
    "b2b",
    "operational",
    "first_party_host",
)
INELIGIBILITY_REASONS = {
    "OUTSIDE_TEXAS",
    "NOT_COMMERCIAL_HVAC",
    "NOT_B2B",
    "CLOSED_OR_INACTIVE",
    "NO_PERMITTED_FIRST_PARTY_HOST",
}
PROHIBITED_FIELD_TERMS = (
    "person",
    "contact",
    "email",
    "phone",
    "employee",
    "staff",
    "decision_maker",
    "owner_name",
    "revenue",
    "headcount",
    "crm",
    "response_time",
    "lead_volume",
    "conversion",
    "opportunity",
    "internal_process",
    "internal_fact",
)
EMAIL_SHAPE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_SHAPE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_host(value: str) -> str:
    host = value.strip().rstrip(".").lower().encode("idna").decode("ascii")
    if not host or "." not in host or "/" in host or ":" in host:
        raise ValueError("candidate requires one exact DNS host without scheme, path, or port")
    return host


def reject_prohibited_content(value: object, *, key_path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if any(term in lowered for term in PROHIBITED_FIELD_TERMS):
                raise ValueError(f"prohibited seed field: {key_path}.{key}")
            if lowered == "source_artifact_sha256":
                continue
            reject_prohibited_content(item, key_path=f"{key_path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_prohibited_content(item, key_path=f"{key_path}[{index}]")
    elif isinstance(value, str) and (EMAIL_SHAPE.search(value) or PHONE_SHAPE.search(value)):
        raise ValueError(f"person/contact-shaped value prohibited at {key_path}")


def _validate_provenance(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("every candidate requires provenance")
    required = {
        "source_id",
        "source_artifact_ref",
        "source_artifact_sha256",
        "locator",
        "observed_at",
    }
    result: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("provenance must contain exactly the approved business-source fields")
        digest = str(entry["source_artifact_sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("source_artifact_sha256 must be a lowercase SHA-256 digest")
        result.append(cast(dict[str, Any], entry))
    return result


def _evidence_refs(candidate_hash: str, category: str, values: list[object]) -> list[str]:
    return [
        f"evidence-{stable_hash((candidate_hash, category, index, value))}"
        for index, value in enumerate(values)
    ]


@dataclass(frozen=True)
class FrozenFrame:
    candidates: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]
    frame_hash: str


def freeze_frame(observations: list[dict[str, Any]], *, source_policy_revision: str) -> FrozenFrame:
    """Validate, classify and deduplicate the frame without using outcomes or a seed."""
    if not COHORT_TARGET <= len(observations) <= FRAME_MAXIMUM:
        raise ValueError("candidate frame must contain between 24 and 100 observations")
    reject_prohibited_content(observations)
    prepared: list[dict[str, Any]] = []
    for source in observations:
        host = normalize_host(str(source["first_party_host_candidate"]))
        provenance = _validate_provenance(source["provenance"])
        categories = cast(dict[str, list[object]], source["eligibility_observations"])
        if set(categories) != set(REQUIRED_CATEGORIES):
            raise ValueError(
                "eligibility observations must contain exactly the required categories"
            )
        explicit_reason = source.get("explicit_ineligibility_reason")
        if explicit_reason is not None and explicit_reason not in INELIGIBILITY_REASONS:
            raise ValueError("unknown explicit ineligibility reason")
        missing = [
            name
            for name in REQUIRED_CATEGORIES
            if not isinstance(categories[name], list) or not categories[name]
        ]
        ambiguous = bool(source.get("identity_ambiguous", False))
        reasons = ([str(explicit_reason)] if explicit_reason else []) + [
            f"MISSING_{name.upper()}_EVIDENCE" for name in missing
        ]
        candidate_hash = stable_hash((source["public_business_name"], host, provenance))
        franchise = source.get("franchise_or_shared_brand_hint")
        prepared.append(
            {
                "candidate_ref": f"candidate-{candidate_hash}",
                "candidate_hash": candidate_hash,
                "source": source,
                "host": host,
                "provenance": provenance,
                "categories": categories,
                "organization_key": normalize_text(str(source["organization_group_hint"])),
                "lead_flow_key": normalize_text(str(source["lead_flow_unit_hint"])),
                "franchise_key": normalize_text(str(franchise)) if franchise else None,
                "eligibility_state": "REVIEW_REQUIRED"
                if ambiguous
                else "INELIGIBLE"
                if reasons
                else "ELIGIBLE",
                "reasons": reasons + (["AMBIGUOUS_BUSINESS_IDENTITY"] if ambiguous else []),
            }
        )
    prepared.sort(key=lambda item: str(item["candidate_ref"]))
    seen_hosts: set[str] = set()
    seen_units: set[tuple[str, str]] = set()
    seen_franchises: set[str] = set()
    candidates: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for item in prepared:
        state = str(item["eligibility_state"])
        reasons = list(cast(list[str], item["reasons"]))
        if state == "ELIGIBLE":
            unit = (str(item["organization_key"]), str(item["lead_flow_key"]))
            duplicate_reason = None
            if item["host"] in seen_hosts:
                duplicate_reason = "DUPLICATE_EXACT_HOST"
            elif unit in seen_units:
                duplicate_reason = "DUPLICATE_ORGANIZATION_LEAD_FLOW_UNIT"
            elif item["franchise_key"] and item["franchise_key"] in seen_franchises:
                duplicate_reason = "SHARED_BRAND_CAP_EXCEEDED"
            if duplicate_reason:
                state = "EXCLUDED_DUPLICATE_OR_CAP"
                reasons.append(duplicate_reason)
            else:
                seen_hosts.add(str(item["host"]))
                seen_units.add(unit)
                if item["franchise_key"]:
                    seen_franchises.add(str(item["franchise_key"]))
                source = cast(dict[str, Any], item["source"])
                categories = cast(dict[str, list[object]], item["categories"])
                candidate_hash = str(item["candidate_hash"])
                candidate = {
                    "candidate_ref": item["candidate_ref"],
                    "public_business_name": source["public_business_name"],
                    "public_business_aliases": source.get("public_business_aliases", []),
                    "texas_city_or_service_area": source.get("texas_city_or_service_area"),
                    "identity_business_evidence_refs": _evidence_refs(
                        candidate_hash, "identity", categories["identity"]
                    ),
                    "texas_eligibility_evidence_refs": _evidence_refs(
                        candidate_hash, "texas", categories["texas"]
                    ),
                    "commercial_hvac_evidence_refs": _evidence_refs(
                        candidate_hash, "commercial_hvac", categories["commercial_hvac"]
                    ),
                    "b2b_relevance_evidence_refs": _evidence_refs(
                        candidate_hash, "b2b", categories["b2b"]
                    ),
                    "first_party_host_candidate": item["host"],
                    "first_party_host_evidence_refs": _evidence_refs(
                        candidate_hash, "host", categories["first_party_host"]
                    ),
                    "organization_group_hint": source["organization_group_hint"],
                    "franchise_or_shared_brand_hint": source.get("franchise_or_shared_brand_hint"),
                    "lead_flow_unit_hint": source["lead_flow_unit_hint"],
                    "distinct_lead_flow_evidence_refs": _evidence_refs(
                        candidate_hash,
                        "lead_flow",
                        source.get("distinct_lead_flow_observations", []),
                    ),
                    "provenance": item["provenance"],
                }
                candidate["stable_unit_key"] = stable_hash(candidate)
                candidates.append(candidate)
        decisions.append(
            {"candidate_ref": item["candidate_ref"], "state": state, "reasons": reasons}
        )
    if len(candidates) < COHORT_TARGET:
        raise ValueError("fewer than 24 unambiguous eligible deduplicated units remain")
    canonical = sorted(candidates, key=lambda item: str(item["stable_unit_key"]))
    frame_hash = stable_hash(
        {"source_policy_revision": source_policy_revision, "candidates": canonical}
    )
    return FrozenFrame(tuple(canonical), tuple(decisions), frame_hash)


def assemble_package(
    frame: FrozenFrame,
    *,
    created_at: str,
    created_by_subject_ref: str,
    source_policy_revision: str,
    selection_seed: bytes,
) -> dict[str, Any]:
    if len(selection_seed) != 32:
        raise ValueError("selection seed must be exactly 32 bytes")
    ranked: list[dict[str, Any]] = []
    for candidate in frame.candidates:
        payload = b"\0".join(
            [
                ORDERING_VERSION.encode(),
                selection_seed,
                frame.frame_hash.encode(),
                str(candidate["stable_unit_key"]).encode(),
            ]
        )
        ranked.append({**candidate, "ordering_key": hashlib.sha256(payload).hexdigest()})
    ranked.sort(key=lambda item: (str(item["ordering_key"]), str(item["stable_unit_key"])))
    selected = [dict(item, slot=i + 1) for i, item in enumerate(ranked[:COHORT_TARGET])]
    reserve = [dict(item, reserve_position=i + 1) for i, item in enumerate(ranked[COHORT_TARGET:])]
    manifest: dict[str, Any] = {
        "record_type": "PHASE1_OWNER_SEED_MANIFEST_V1",
        "schema_version": "1.0.0",
        "state": "FROZEN_AWAITING_OWNER_ARTIFACT_APPROVAL",
        "policy_version": POLICY_VERSION,
        "candidate_frame_maximum": FRAME_MAXIMUM,
        "cohort_target": COHORT_TARGET,
        "source_policy_revision": source_policy_revision,
        "created_at": created_at,
        "created_by_subject_ref": created_by_subject_ref,
        "frozen_frame_hash": frame.frame_hash,
        "seed_commitment": hashlib.sha256(selection_seed).hexdigest(),
        "ordering_version": ORDERING_VERSION,
        "eligibility_decisions": list(frame.decisions),
        "selected": selected,
        "reserve": reserve,
        "manifest_hash": None,
    }
    manifest["manifest_hash"] = stable_hash(
        {k: v for k, v in manifest.items() if k != "manifest_hash"}
    )
    host_reviews = [
        {
            "source_id": f"FIRST_PARTY_DISCOVERY::{item['first_party_host_candidate']}",
            "exact_host": item["first_party_host_candidate"],
            "terms_review": "NOT_REVIEWED",
            "robots_review": "NOT_REVIEWED",
            "access_restrictions_review": "NOT_REVIEWED",
            "automated_access_review": "NOT_REVIEWED",
            "capture_storage_reuse_review": "NOT_REVIEWED",
            "copyright_contract_review": "NOT_REVIEWED",
            "technical_metadata": "PENDING_AUTHORIZED_COLLECTION",
            "human_conclusion": "PENDING",
            "final_state": "NOT_APPROVED",
        }
        for item in selected + reserve
    ]
    permissions = {
        name: "NOT_AUTHORIZED"
        for name in (
            "REAL_BUSINESS_DISCOVERY",
            "REAL_PUBLIC_RESEARCH",
            "PROFESSIONAL_IDENTITY_RESOLUTION",
            "REAL_CONTACT_STORAGE",
            "CONTACT_VERIFICATION",
            "SHADOW_ELIGIBILITY_EVALUATION",
            "SHADOW_READY_ASSESSMENT",
        )
    }
    package: dict[str, Any] = {
        "record_type": "M67_GENERATED_SEED_SOURCE_APPROVAL_PACKAGE",
        "version": "2.0.0",
        "state": "MANDATORY_STOP_AWAITING_SEED_ARTIFACT_AND_HOST_APPROVALS",
        "manifest": manifest,
        "host_reviews": host_reviews,
        "wildcard_approval_prohibited": True,
        "batch_signature_may_enumerate_hosts_but_not_wildcard": True,
        "outcome_based_replacement_prohibited": True,
        "permissions": permissions,
        "next_action": "STOP_FOR_OWNER_REVIEW; NO_RESEARCH_OR_SLOT_EXECUTION",
        "configuration_hash": None,
    }
    package["configuration_hash"] = stable_hash(
        {k: v for k, v in package.items() if k != "configuration_hash"}
    )
    return package


def build_package(
    observations: list[dict[str, Any]],
    *,
    created_at: str,
    created_by_subject_ref: str,
    source_policy_revision: str,
    selection_seed: bytes,
) -> dict[str, Any]:
    frame = freeze_frame(observations, source_policy_revision=source_policy_revision)
    return assemble_package(
        frame,
        created_at=created_at,
        created_by_subject_ref=created_by_subject_ref,
        source_policy_revision=source_policy_revision,
        selection_seed=selection_seed,
    )


def build_with_post_freeze_seed(
    observations: list[dict[str, Any]],
    *,
    created_at: str,
    created_by_subject_ref: str,
    source_policy_revision: str,
    seed_factory: Callable[[int], bytes] = secrets.token_bytes,
) -> tuple[dict[str, Any], bytes]:
    frame = freeze_frame(observations, source_policy_revision=source_policy_revision)
    seed = seed_factory(32)
    return (
        assemble_package(
            frame,
            created_at=created_at,
            created_by_subject_ref=created_by_subject_ref,
            source_policy_revision=source_policy_revision,
            selection_seed=seed,
        ),
        seed,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--created-by-subject-ref", required=True)
    parser.add_argument("--source-policy-revision", required=True)
    parser.add_argument("--private-seed-output", type=Path, required=True)
    args = parser.parse_args()
    observations = json.loads(args.observations.read_text(encoding="utf-8"))
    if not isinstance(observations, list):
        raise ValueError("observations must be a JSON array")
    package, seed = build_with_post_freeze_seed(
        cast(list[dict[str, Any]], observations),
        created_at=args.created_at,
        created_by_subject_ref=args.created_by_subject_ref,
        source_policy_revision=args.source_policy_revision,
    )
    args.output.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    args.private_seed_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_seed_output.write_text(seed.hex() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
