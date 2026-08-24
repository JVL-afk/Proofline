"""Prepare offline A-09 decisions for the immutable manual Phase 1 sample."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any

EXPECTED_PACKAGE_FILE_SHA256 = "755279cb8e5ac06c579c411857bfc6d380602722813de1cda21175b9385b5467"
EXPECTED_PACKAGE_SEMANTIC_SHA256 = "8a0703e6a441e28a62ae5f5ed32faf0279502c695d34779132ffa48979074050"
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!.*\.\.)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$"
)
PROHIBITED_SUFFIXES = {
    "facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "x.com",
    "youtube.com", "yelp.com", "angi.com", "homeadvisor.com", "thumbtack.com",
    "google.com", "googleapis.com", "mapquest.com", "yellowpages.com", "bbb.org",
    "houzz.com", "nextdoor.com", "bit.ly", "tinyurl.com", "t.co", "linktr.ee",
    "amazon.com", "ebay.com",
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def structurally_safe(host: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not HOST_RE.fullmatch(host):
        reasons.append("MALFORMED_OR_NONCANONICAL_HOST")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        reasons.append("IP_LITERAL")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        reasons.append("LOCAL_OR_LOOPBACK_HOSTNAME")
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in PROHIBITED_SUFFIXES):
        reasons.append("PROHIBITED_THIRD_PARTY_HOST_CATEGORY")
    return not reasons, reasons


def prepare(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if package.get("package_sha256") != EXPECTED_PACKAGE_SEMANTIC_SHA256:
        raise ValueError("ordered package semantic hash mismatch")
    slots = package.get("slots")
    if not isinstance(slots, list) or [row.get("slot") for row in slots] != list(range(1, 25)):
        raise ValueError("immutable slot mapping mismatch")
    decisions: list[dict[str, Any]] = []
    structural_pass = 0
    for row in slots:
        host = row["candidate_hostname"]
        safe, reasons = structurally_safe(host)
        if safe:
            structural_pass += 1
            reasons.extend([
                "FIRST_PARTY_STATUS_OWNER_ATTESTED_BUT_NOT_INDEPENDENTLY_VERIFIED",
                "ROBOTS_TERMS_ACCESS_AND_REUSE_NOT_OBSERVED",
            ])
        decisions.append({
            "slot": row["slot"],
            "public_business_name": row["public_business_name"],
            "candidate_hostname": host,
            "mapping_immutable": True,
            "structural_review": "PASS" if safe else "REJECTED",
            "first_party_plausibility": "OWNER_ATTESTED_CANDIDATE_UNVERIFIED",
            "robots_review": "NOT_OBSERVED_NO_NETWORK_AUTHORITY",
            "terms_access_reuse_review": "NOT_OBSERVED_NO_NETWORK_AUTHORITY",
            "decision": "REQUIRES_HUMAN_REVIEW" if safe else "REJECTED",
            "reasons": reasons,
        })
    review: dict[str, Any] = {
        "record_type": "M67_MANUAL_PHASE1_EXACT_HOST_A09_OFFLINE_REVIEW",
        "state": "BLOCKED_PENDING_BOUNDED_EXACT_HOST_A09_ACCESS_REVIEW",
        "ordered_package_semantic_sha256": EXPECTED_PACKAGE_SEMANTIC_SHA256,
        "slot_count": 24,
        "replacements": 0,
        "network_operations": 0,
        "decisions": decisions,
        "review_sha256": None,
    }
    review["review_sha256"] = sha256_bytes(canonical_bytes({
        key: value for key, value in review.items() if key != "review_sha256"
    }))
    summary = {
        "record_type": "M67_MANUAL_PHASE1_EXACT_HOST_A09_OFFLINE_REVIEW_EVIDENCE",
        "state": review["state"],
        "ordered_package_semantic_sha256": EXPECTED_PACKAGE_SEMANTIC_SHA256,
        "offline_review_sha256": review["review_sha256"],
        "slot_count": 24,
        "structural_pass": structural_pass,
        "approved_for_bounded_first_party_public_research": 0,
        "rejected": 24 - structural_pass,
        "requires_human_review": structural_pass,
        "network_operations": 0,
        "m1_m5_operations": 0,
        "replacements": 0,
        "all_seven_m6_7_permissions": "NOT_AUTHORIZED",
    }
    return review, summary


def seal(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ordered-package", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.ordered_package.read_bytes()
    if sha256_bytes(raw) != EXPECTED_PACKAGE_FILE_SHA256:
        raise ValueError("ordered package file hash mismatch")
    review, summary = prepare(json.loads(raw))
    seal(args.review_output, review)
    seal(args.evidence_output, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
