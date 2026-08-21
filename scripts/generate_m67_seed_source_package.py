"""Generate an M6.7 business-only seed and enumerated host-review package.

The input is a system-captured, source-policy-approved business observation set. This tool performs
no network access and cannot authorize a source. Human conclusions remain pending per exact host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any, cast

PROHIBITED_TERMS = (
    "person",
    "contact",
    "email",
    "phone",
    "revenue",
    "crm",
    "response_time",
    "lead_volume",
    "opportunity",
)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def normalize_host(value: str) -> str:
    host = value.strip().rstrip(".").lower().encode("idna").decode("ascii")
    if not host or "." not in host or "/" in host or ":" in host:
        raise ValueError("candidate requires one exact DNS host without scheme, path, or port")
    return host


def reject_prohibited_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(term in lowered for term in PROHIBITED_TERMS):
                raise ValueError(f"prohibited seed field: {key}")
            reject_prohibited_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_prohibited_fields(item)


def evidence_refs(candidate_hash: str, category: str, values: list[object]) -> list[str]:
    return [
        f"evidence-{stable_hash((candidate_hash, category, index, value))}"
        for index, value in enumerate(values)
    ]


def build_package(
    observations: list[dict[str, Any]],
    *,
    created_at: str,
    created_by_subject_ref: str,
    source_policy_revision: str,
    selection_seed: bytes,
) -> dict[str, Any]:
    if not 24 <= len(observations) <= 100:
        raise ValueError("candidate frame must contain between 24 and 100 observations")
    reject_prohibited_fields(observations)
    candidates: list[dict[str, Any]] = []
    host_reviews: list[dict[str, Any]] = []
    for source in observations:
        host = normalize_host(str(source["first_party_host_candidate"]))
        candidate_hash = stable_hash((source["public_business_name"], host, source["provenance"]))
        candidate_ref = f"candidate-{candidate_hash}"
        categories = cast(dict[str, list[object]], source["eligibility_observations"])
        candidate = {
            "candidate_ref": candidate_ref,
            "public_business_name": source["public_business_name"],
            "public_business_aliases": source.get("public_business_aliases", []),
            "texas_city_or_service_area": source.get("texas_city_or_service_area"),
            "identity_business_evidence_refs": evidence_refs(
                candidate_hash, "identity", categories["identity"]
            ),
            "texas_eligibility_evidence_refs": evidence_refs(
                candidate_hash, "texas", categories["texas"]
            ),
            "commercial_hvac_evidence_refs": evidence_refs(
                candidate_hash, "hvac", categories["commercial_hvac"]
            ),
            "b2b_relevance_evidence_refs": evidence_refs(candidate_hash, "b2b", categories["b2b"]),
            "first_party_host_candidate": host,
            "first_party_host_evidence_refs": evidence_refs(candidate_hash, "host", [host]),
            "organization_group_hint": source["organization_group_hint"],
            "franchise_or_shared_brand_hint": source.get("franchise_or_shared_brand_hint"),
            "lead_flow_unit_hint": source["lead_flow_unit_hint"],
            "distinct_lead_flow_evidence_refs": evidence_refs(
                candidate_hash, "lead_flow", source.get("distinct_lead_flow_observations", [])
            ),
            "provenance": source["provenance"],
        }
        candidates.append(candidate)
        host_reviews.append(
            {
                "source_id": f"FIRST_PARTY_DISCOVERY::{host}",
                "exact_host": host,
                "terms_url": None,
                "robots_url": f"https://{host}/robots.txt",
                "technical_collection_state": "PENDING_AUTHORIZED_COLLECTION",
                "retrieved_at": None,
                "http_accessibility": None,
                "terms_hash": None,
                "robots_hash": None,
                "technical_restrictions": [],
                "human_conclusion": "PENDING",
                "final_state": "NOT_APPROVED",
            }
        )
    candidates.sort(
        key=lambda item: hashlib.sha256(
            selection_seed + str(item["candidate_ref"]).encode()
        ).hexdigest()
    )
    manifest: dict[str, Any] = {
        "record_type": "PHASE1_OWNER_SEED_MANIFEST_V1",
        "schema_version": "1.0.0",
        "state": "FROZEN",
        "candidate_frame_maximum": 100,
        "source_policy_revision": source_policy_revision,
        "created_at": created_at,
        "created_by_subject_ref": created_by_subject_ref,
        "seed_commitment": hashlib.sha256(selection_seed).hexdigest(),
        "candidates": candidates,
        "manifest_hash": None,
    }
    manifest["manifest_hash"] = stable_hash(
        {key: value for key, value in manifest.items() if key != "manifest_hash"}
    )
    package = {
        "record_type": "M67_GENERATED_SEED_SOURCE_APPROVAL_PACKAGE",
        "version": "1.0.0",
        "state": "AWAITING_PER_HOST_HUMAN_CONCLUSIONS",
        "manifest": manifest,
        "deterministic_selection_order_hash": stable_hash(
            [item["candidate_ref"] for item in candidates]
        ),
        "host_reviews": host_reviews,
        "wildcard_approval_prohibited": True,
        "batch_signature": None,
        "configuration_hash": None,
    }
    package["configuration_hash"] = stable_hash(
        {key: value for key, value in package.items() if key != "configuration_hash"}
    )
    return package


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
    seed = secrets.token_bytes(32)
    package = build_package(
        cast(list[dict[str, Any]], observations),
        created_at=args.created_at,
        created_by_subject_ref=args.created_by_subject_ref,
        source_policy_revision=args.source_policy_revision,
        selection_seed=seed,
    )
    args.output.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    args.private_seed_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_seed_output.write_text(seed.hex() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
