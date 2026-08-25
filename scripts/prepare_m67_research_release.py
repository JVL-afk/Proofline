"""Prepare one owner-approved exact M6.7 public-research release without AWS mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from opintel_shadow import (
    AuthorizedResearchReleaseCommand,
    LiveResearchPermissionRelease,
    PermissionActivity,
    PermissionState,
    stable_hash,
)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def prepare(predecessor_value: object, command_value: object) -> LiveResearchPermissionRelease:
    predecessor = LiveResearchPermissionRelease.model_validate(predecessor_value)
    command = AuthorizedResearchReleaseCommand.model_validate(command_value)
    now = datetime.now(UTC)
    if predecessor.id != command.current_release_id:
        raise ValueError("command does not bind predecessor")
    if predecessor.activity is not PermissionActivity.REAL_PUBLIC_RESEARCH:
        raise ValueError("predecessor is not REAL_PUBLIC_RESEARCH")
    if predecessor.state is not PermissionState.NOT_AUTHORIZED:
        raise ValueError("predecessor must be NOT_AUTHORIZED")
    if not command.starts_at <= now < command.expires_at:
        raise ValueError("owner-approved release window is not current")
    successor = predecessor.model_copy(
        update={
            "id": uuid4(),
            "version": f"{predecessor.version}.owner-authorized",
            "configuration_hash": stable_hash(command.model_dump(mode="json")),
            "created_at": now,
            "state": PermissionState.AUTHORIZED,
            "cohort_or_run_restriction": f"PHASE1_SLOT_{command.slot_number:02d}",
            "starts_at": command.starts_at,
            "expires_at": command.expires_at,
            "approval_ids": (command.owner_approval_id,),
            "slot_number": command.slot_number,
            "business_identity": command.business_identity,
            "exact_hostname": command.exact_hostname,
            "ordered_package_sha256": command.ordered_package_sha256,
            "research_runtime_revision": command.research_runtime_revision,
            "max_logical_requests": command.max_logical_requests,
            "max_attempts": command.max_attempts,
            "max_response_bytes": command.max_response_bytes,
            "max_total_bytes": command.max_total_bytes,
            "cost_ceiling_usd": command.cost_ceiling_usd,
            "allowed_source_scope": command.allowed_source_scope,
            "terminal_rollback_state": command.terminal_rollback_state,
            "owner_approval_sha256": command.owner_approval_sha256,
        }
    )
    return LiveResearchPermissionRelease.model_validate(successor.model_dump(mode="python"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--command", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release = prepare(
        json.loads(args.predecessor.read_text(encoding="utf-8")),
        json.loads(args.command.read_text(encoding="utf-8")),
    )
    payload = canonical_bytes(release.model_dump(mode="json")) + b"\n"
    args.output.write_bytes(payload)
    print(hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
