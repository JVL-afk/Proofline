"""Issue one approved PRIMARY_A challenge without storing its raw nonce in Git."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ACCOUNT_ID = "785072247535"
REGION = "us-east-2"
ACTOR_REF = "PRIMARY_A_ACTOR"
ENVIRONMENT = "M67_PHASE1_DEPLOYED_ENVIRONMENT"
IDP_ISSUER_REF = "arn:aws:sso:::instance/ssoins-668449c46cda2b4b"
AUDIENCE_REF = "sha256:cc50397ec7a6ad0d624f4fd034d92121d084fb231c1bd67909f020ae444a439c"
ASSIGNMENT_EVIDENCE_SHA256 = "82b7bf746bb80a63fde22d9918fdb2736b3ac27dba3ee275ed5332d2ce7560ba"
CHALLENGE_LIFETIME = timedelta(minutes=15)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def issue(*, output_dir: Path, owner_approval_sha256: str, now: datetime) -> tuple[Path, Path]:
    if len(owner_approval_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in owner_approval_sha256
    ):
        raise ValueError("owner approval SHA-256 must be 64 lowercase hexadecimal characters")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("issuance time must be timezone-aware")
    output_dir.mkdir(parents=True, exist_ok=True)
    public_path = output_dir / "primary-a-challenge-record.json"
    private_path = output_dir / "primary-a-challenge-secret.json"
    if public_path.exists() or private_path.exists():
        raise FileExistsError(
            "challenge already exists; issuance is single-use and non-overwriting"
        )

    nonce_bytes = secrets.token_bytes(32)
    nonce = base64.urlsafe_b64encode(nonce_bytes).decode().rstrip("=")
    challenge_id = f"M67-PRIMARY-A-{secrets.token_hex(8).upper()}"
    issued_at = now.astimezone(UTC)
    expires_at = issued_at + CHALLENGE_LIFETIME
    binding: dict[str, Any] = {
        "challenge_id": challenge_id,
        "actor_ref": ACTOR_REF,
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "environment": ENVIRONMENT,
        "idp_issuer_ref": IDP_ISSUER_REF,
        "audience_ref": AUDIENCE_REF,
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "owner_approval_sha256": owner_approval_sha256,
        "assignment_evidence_sha256": ASSIGNMENT_EVIDENCE_SHA256,
    }
    commitment = _sha256(_canonical(binding) + b"\0" + nonce.encode())
    public_record = {
        "record_type": "M67_PRIMARY_A_INDEPENDENT_AUTHENTICATION_CHALLENGE",
        "version": "1.0.0",
        "state": "PRIMARY_A_CHALLENGE_ISSUED",
        **binding,
        "challenge_nonce_commitment_sha256": commitment,
        "required_assurance": "MFA",
        "required_independent_session": True,
        "owner_session_prohibited": True,
        "one_time_use": True,
        "consumed": False,
        "permissions_granted": [],
    }
    private_record = {
        "challenge_id": challenge_id,
        "raw_nonce": nonce,
        "commitment_sha256": commitment,
        "expires_at": binding["expires_at"],
        "repository_storage_prohibited": True,
    }
    public_path.write_text(json.dumps(public_record, indent=2) + "\n", encoding="utf-8")
    private_path.write_text(json.dumps(private_record, indent=2) + "\n", encoding="utf-8")
    os.chmod(private_path, 0o600)
    return public_path, private_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--owner-approval-sha256", required=True)
    args = parser.parse_args()
    public_path, private_path = issue(
        output_dir=args.output_dir,
        owner_approval_sha256=args.owner_approval_sha256,
        now=datetime.now(UTC),
    )
    print(f"public_record={public_path}")
    print(f"private_secret={private_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
