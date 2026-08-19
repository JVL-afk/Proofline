"""Fail if local credential values occur in tracked files or reachable Git blobs."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from opintel_qualification_live.secrets import load_available_secret_bundle


def _git(*args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args],
        input=input_bytes,
        check=True,
        capture_output=True,
    ).stdout


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    return value


def main() -> int:
    args = parser().parse_args()
    bundle = load_available_secret_bundle(args.credentials)
    secrets = tuple(
        value.encode()
        for value in (
            bundle.for_provider("openai"),
            bundle.for_provider("anthropic"),
            bundle.for_provider("gemini"),
        )
        if value
    )
    if not secrets:
        print("Credential-value audit denied: no credential values were available.")
        return 2

    for raw_path in _git("ls-files", "-z").split(b"\0"):
        if not raw_path:
            continue
        path = Path(raw_path.decode())
        if path.is_file():
            data = path.read_bytes()
            if any(secret in data for secret in secrets):
                print(
                    "Credential-value audit failed: a tracked working-tree file contains a value."
                )
                return 1

    object_ids = sorted(
        {
            line.split(b" ", 1)[0]
            for line in _git("rev-list", "--objects", "--all").splitlines()
            if line
        }
    )
    type_output = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        input=b"\n".join(object_ids) + b"\n",
        check=True,
        capture_output=True,
    )
    blob_ids = []
    type_lines = type_output.stdout.splitlines()
    if len(type_lines) != len(object_ids):
        raise RuntimeError("unexpected git cat-file batch-check response count")
    for object_id, line in zip(object_ids, type_lines, strict=True):
        header = line.split()
        if len(header) != 3:
            raise RuntimeError("unexpected git cat-file batch-check response")
        if header[1] == b"blob":
            blob_ids.append(object_id)

    blob_output = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=b"\n".join(blob_ids) + b"\n",
        check=True,
        capture_output=True,
    )
    offset = 0
    for _object_id in blob_ids:
        line_end = blob_output.stdout.index(b"\n", offset)
        header = blob_output.stdout[offset:line_end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise RuntimeError("unexpected Git blob batch response")
        size = int(header[2])
        body_start = line_end + 1
        data = blob_output.stdout[body_start : body_start + size]
        offset = body_start + size + 1
        if any(secret in data for secret in secrets):
            print("Credential-value audit failed: a reachable Git blob contains a value.")
            return 1

    print(
        f"Credential-value audit passed: {len(secrets)} provider values are absent from "
        "tracked files and reachable Git blobs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
