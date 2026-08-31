"""Canonical deterministic bundle attestations for the M6.7 sampled-slot
approval bindings ``sampled_slot_stage_coordinator_sha256`` and
``sampled_slot_m2_m5_runtime_sha256``.

Each binding is computed from an explicit frozen ordered file manifest checked
into source control at ``infra/terraform/phase1/bundle-manifests/<name>.manifest``.

Canonical serialization (``m67.sampled-slot-bundle@1``)
-----------------------------------------------------
1. Read the manifest: one repo-relative POSIX path per line. The file MUST be
   lexicographically sorted ascending, contain no blank lines, no comments, no
   duplicates, and at least one member. Any deviation raises ``BundleManifestError``
   -- the calculator fails closed rather than emitting a digest.
2. For each member: ``member_sha256 = sha256(<verbatim file bytes>).hexdigest()``.
   The member path must resolve to a regular file inside the repository root;
   an absolute path, a ``..`` escape, a directory, or a missing file raises
   ``BundleManifestError``.
3. Canonical bytes = for every member, in the frozen manifest order:
   ``f"{relpath}\\x00{member_sha256}\\x0a"`` concatenated, UTF-8 encoded.
   The NUL separator and trailing LF are fixed; nothing else is included --
   no filesystem traversal order, mtimes, absolute paths, Git state, or
   environment metadata influence the result.
4. ``bundle_digest = sha256(<canonical bytes>).hexdigest()``.

A member set that is byte-identical to a previous deployment legitimately
produces the same digest; a bundle whose bound implementation changed produces a
new digest.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ALGORITHM_VERSION = "m67.sampled-slot-bundle@1"
CANONICAL_SERIALIZATION = (
    "utf8( concat_for_each_member_in_frozen_manifest_order( "
    'relpath + "\\x00" + member_sha256_hex + "\\x0a" ) )'
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_DIR = _REPO_ROOT / "infra" / "terraform" / "phase1" / "bundle-manifests"

BUNDLES: tuple[str, ...] = ("stage_coordinator", "m2_m5_runtime")


class BundleManifestError(RuntimeError):
    """A bundle manifest is missing, malformed, or references an unresolvable
    member. The calculator never returns a digest in this case."""


@dataclass(frozen=True, slots=True)
class BundleAttestation:
    name: str
    algorithm: str
    manifest_relpath: str
    canonical_serialization: str
    members: tuple[tuple[str, str], ...]  # (relpath, member_sha256_hex)
    digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "algorithm": self.algorithm,
            "manifest": self.manifest_relpath,
            "canonical_serialization": self.canonical_serialization,
            "members": [{"path": p, "sha256": h} for p, h in self.members],
            "member_count": len(self.members),
            "bundle_sha256": self.digest,
        }


def _manifest_path(name: str) -> Path:
    return _MANIFEST_DIR / f"{name}.manifest"


def read_manifest(name: str, *, repo_root: Path | None = None) -> tuple[str, ...]:
    root = repo_root or _REPO_ROOT
    path = (root / "infra" / "terraform" / "phase1" / "bundle-manifests" / f"{name}.manifest")
    if not path.is_file():
        raise BundleManifestError(f"bundle manifest not found: {path}")
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # allow exactly one trailing newline
    members: list[str] = []
    for index, line in enumerate(lines, start=1):
        if line != line.strip() or line == "":
            raise BundleManifestError(
                f"{name}.manifest line {index}: blank line or surrounding whitespace"
            )
        if line.startswith("#"):
            raise BundleManifestError(f"{name}.manifest line {index}: comments are not allowed")
        if line.startswith("/") or line.startswith("\\") or ".." in Path(line).parts:
            raise BundleManifestError(f"{name}.manifest line {index}: unsafe path {line!r}")
        if "\\" in line:
            raise BundleManifestError(
                f"{name}.manifest line {index}: use POSIX '/' separators, not '\\'"
            )
        members.append(line)
    if not members:
        raise BundleManifestError(f"{name}.manifest has no members")
    if len(set(members)) != len(members):
        raise BundleManifestError(f"{name}.manifest contains duplicate members")
    if list(members) != sorted(members):
        raise BundleManifestError(
            f"{name}.manifest is not lexicographically sorted (frozen order violation)"
        )
    return tuple(members)


def _member_sha256(relpath: str, *, repo_root: Path) -> str:
    target = (repo_root / relpath).resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError as error:
        raise BundleManifestError(f"member escapes repository root: {relpath}") from error
    if not target.is_file():
        raise BundleManifestError(f"member is not a regular file: {relpath}")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def compute_bundle(name: str, *, repo_root: Path | None = None) -> BundleAttestation:
    root = (repo_root or _REPO_ROOT).resolve()
    members_order = read_manifest(name, repo_root=root)
    members = tuple((rp, _member_sha256(rp, repo_root=root)) for rp in members_order)
    canonical = b"".join(
        f"{rp}\x00{digest}\x0a".encode() for rp, digest in members
    )
    manifest_rel = (
        f"infra/terraform/phase1/bundle-manifests/{name}.manifest"
    )
    return BundleAttestation(
        name=name,
        algorithm=ALGORITHM_VERSION,
        manifest_relpath=manifest_rel,
        canonical_serialization=CANONICAL_SERIALIZATION,
        members=members,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def compute_all(*, repo_root: Path | None = None) -> dict[str, BundleAttestation]:
    return {name: compute_bundle(name, repo_root=repo_root) for name in BUNDLES}


def _main(argv: list[str]) -> int:
    want = [a for a in argv if not a.startswith("-")]
    as_json = "--json" in argv
    names = BUNDLES if not want or want == ["all"] else tuple(want)
    result = {name: compute_bundle(name).as_dict() for name in names}
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        for name, data in result.items():
            print(f"{name}: {data['bundle_sha256']}  ({data['member_count']} members)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
