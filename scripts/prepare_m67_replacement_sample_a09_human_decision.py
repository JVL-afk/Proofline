"""Prepare the content-minimized human A-09 package after a terminal review attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PACKAGE_FILE_SHA256 = "0283f0a6956f6bd11e9326419d9671a61cc57dac0b6d376b9e2b7a11f0507a70"
CHECKPOINT_SHA256 = "350ba47df4f76029b17d691c1c876e129b880f170d06cc9b32a4df6ef6b7a071"
TERMINAL_SHA256 = "796aed7d1ec320b953f319f5538a8d22a0deec0b8c40f9be909e8f0079e59d5c"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def recommendation(decision: dict[str, Any]) -> str:
    observations = decision["observations"]
    root = observations.get("root", {})
    robots = observations.get("robots", {})
    if robots.get("root_allowed_for_review_agent") is False:
        return "REJECT"
    if any(item.get("redirect_host") for item in observations.values()):
        return "REQUIRES_SUCCESSOR_HOST_REVIEW"
    if (
        root.get("status") == 200
        and robots.get("root_allowed_for_review_agent") is True
        and root.get("identity_signal") == "BUSINESS_NAME_TOKENS_PRESENT"
    ):
        return "APPROVE_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH"
    return "REQUIRES_FURTHER_HUMAN_REVIEW"


def build(package: dict[str, Any], checkpoint: dict[str, Any]) -> dict[str, Any]:
    completed = {item["slot"]: item for item in checkpoint["decisions"]}
    slots = []
    for row in package["slots"]:
        prior = completed.get(row["slot"])
        if prior:
            rec = recommendation(prior)
            evidence_state = "BOUNDED_A09_EVIDENCE_COMPLETE_FOR_SLOT"
            observations = prior["observations"]
        else:
            rec = "REQUIRES_SUCCESSOR_HOST_REVIEW"
            evidence_state = "NOT_REVIEWED_CONSUMED_ATTEMPT_TERMINATED_AT_SLOT_04"
            observations = None
        slots.append(
            {
                "slot": row["slot"],
                "company_name": row["company_name"],
                "submitted_website": row["company_website_original"],
                "candidate_hostname": row["candidate_hostname"],
                "mapping_immutable": True,
                "evidence_state": evidence_state,
                "content_minimized_observations": observations,
                "recommendation": rec,
                "recommendation_authoritative": False,
                "a09_approved": False,
            }
        )
    return {
        "schema_version": "m67-replacement-sample-a09-human-decision-package-v1",
        "state": "READY_FOR_SLOT01_A09_OWNER_DECISION_AND_REMAINING_HOST_SUCCESSOR_REVIEW",
        "ordered_package_file_sha256": PACKAGE_FILE_SHA256,
        "checkpoint_evidence_sha256": CHECKPOINT_SHA256,
        "terminal_record_sha256": TERMINAL_SHA256,
        "slot_count": 24,
        "completed_slots": [1, 2, 3],
        "remaining_slots": list(range(4, 25)),
        "automatic_approvals": 0,
        "slot01_priority": True,
        "slots": slots,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ordered-package", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package_raw = args.ordered_package.read_bytes()
    checkpoint_raw = args.checkpoint.read_bytes()
    if sha256_bytes(package_raw) != PACKAGE_FILE_SHA256:
        raise RuntimeError("ordered package hash mismatch")
    if sha256_bytes(checkpoint_raw) != CHECKPOINT_SHA256:
        raise RuntimeError("checkpoint hash mismatch")
    output = build(json.loads(package_raw), json.loads(checkpoint_raw))
    args.output.write_bytes(canonical_bytes(output))
    print(sha256_bytes(args.output.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
