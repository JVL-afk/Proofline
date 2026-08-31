"""Canonical deterministic bundle-attestation calculator (owner review B, 2026-08-31).

Proves the ``scripts.sampled_slot_bundle`` calculator is a real source-derived
attestation: same bytes + same manifest -> same digest; discovery order is
irrelevant; one bound byte changes the digest; an unbound file does not; a
malformed / inconsistent manifest fails closed rather than emitting another
attestation. Also enforces that the deployed tfvars binding values equal the
calculator output.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from scripts.sampled_slot_bundle import (
    BUNDLES,
    BundleManifestError,
    compute_all,
    compute_bundle,
    read_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TFVARS = REPO_ROOT / "infra" / "terraform" / "phase1" / "terraform.tfvars"
MANIFEST_DIR = REPO_ROOT / "infra" / "terraform" / "phase1" / "bundle-manifests"


def _materialize(tmp: Path, name: str, *, member_bytes: dict[str, bytes] | None = None,
                 manifest_text: str | None = None, reverse_write: bool = False) -> Path:
    """Build a minimal temp repo containing one bundle manifest + its members."""
    members = read_manifest(name, repo_root=REPO_ROOT)
    md = tmp / "infra" / "terraform" / "phase1" / "bundle-manifests"
    md.mkdir(parents=True)
    (md / f"{name}.manifest").write_text(
        manifest_text if manifest_text is not None else "\n".join(members) + "\n",
        encoding="utf-8",
    )
    order = list(reversed(members)) if reverse_write else list(members)
    for relpath in order:
        src = REPO_ROOT / relpath
        data = (member_bytes or {}).get(relpath, src.read_bytes())
        dst = tmp / relpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    return tmp


@pytest.mark.parametrize("name", BUNDLES)
def test_same_bytes_same_manifest_same_digest(name: str, tmp_path: Path) -> None:
    live = compute_bundle(name, repo_root=REPO_ROOT)
    again = compute_bundle(name, repo_root=REPO_ROOT)
    copy = compute_bundle(name, repo_root=_materialize(tmp_path, name))
    assert live.digest == again.digest == copy.digest
    assert live.members == copy.members
    assert live.algorithm == "m67.sampled-slot-bundle@1"


@pytest.mark.parametrize("name", BUNDLES)
def test_filesystem_discovery_order_cannot_change_digest(name: str, tmp_path: Path) -> None:
    forward = compute_bundle(name, repo_root=_materialize(tmp_path / "a", name))
    reverse = compute_bundle(
        name, repo_root=_materialize(tmp_path / "b", name, reverse_write=True)
    )
    assert forward.digest == reverse.digest == compute_bundle(name, repo_root=REPO_ROOT).digest


@pytest.mark.parametrize("name", BUNDLES)
def test_changing_one_bound_byte_changes_digest(name: str, tmp_path: Path) -> None:
    members = read_manifest(name, repo_root=REPO_ROOT)
    victim = members[0]
    mutated = (REPO_ROOT / victim).read_bytes() + b"\n# canary\n"
    root = _materialize(tmp_path, name, member_bytes={victim: mutated})
    assert compute_bundle(name, repo_root=root).digest != (
        compute_bundle(name, repo_root=REPO_ROOT).digest
    )


@pytest.mark.parametrize("name", BUNDLES)
def test_changing_an_unbound_file_does_not_change_digest(name: str, tmp_path: Path) -> None:
    root = _materialize(tmp_path, name)
    baseline = compute_bundle(name, repo_root=root).digest
    unbound = root / "packages" / "opportunity-core" / "src" / "opintel_opportunity" / "ports.py"
    unbound.parent.mkdir(parents=True, exist_ok=True)
    unbound.write_bytes(b"# an unbound file the manifest does not list\n")
    (root / "README.md").write_bytes(b"unrelated change\n")
    assert compute_bundle(name, repo_root=root).digest == baseline


@pytest.mark.parametrize("name", BUNDLES)
def test_missing_member_fails_closed(name: str, tmp_path: Path) -> None:
    root = _materialize(tmp_path, name)
    (root / read_manifest(name, repo_root=REPO_ROOT)[0]).unlink()
    with pytest.raises(BundleManifestError, match="not a regular file"):
        compute_bundle(name, repo_root=root)


@pytest.mark.parametrize("name", BUNDLES)
def test_unsorted_manifest_fails_closed(name: str, tmp_path: Path) -> None:
    members = list(read_manifest(name, repo_root=REPO_ROOT))
    if len(members) >= 2:
        members[0], members[1] = members[1], members[0]
    root = _materialize(tmp_path, name, manifest_text="\n".join(members) + "\n")
    with pytest.raises(BundleManifestError, match="sorted"):
        compute_bundle(name, repo_root=root)


@pytest.mark.parametrize("name", BUNDLES)
def test_duplicate_member_fails_closed(name: str, tmp_path: Path) -> None:
    members = list(read_manifest(name, repo_root=REPO_ROOT))
    root = _materialize(
        tmp_path, name, manifest_text="\n".join([*members, members[0]]) + "\n"
    )
    with pytest.raises(BundleManifestError, match="duplicate"):
        compute_bundle(name, repo_root=root)


@pytest.mark.parametrize("name", BUNDLES)
def test_empty_manifest_fails_closed(name: str, tmp_path: Path) -> None:
    root = _materialize(tmp_path, name, manifest_text="\n")
    with pytest.raises(BundleManifestError):
        compute_bundle(name, repo_root=root)


def test_extra_unlisted_member_in_bundle_dir_is_ignored_by_closed_manifest(
    tmp_path: Path,
) -> None:
    # A manifest referencing a file that does not exist fails closed; a bundle
    # source directory that gains an unlisted file has no effect (closed set).
    root = _materialize(tmp_path, "stage_coordinator")
    (root / "workers" / "intelligence" / "src" / "opintel_intelligence_worker"
     / "brand_new_coordinator_helper.py").write_bytes(b"x = 1\n")
    assert compute_bundle("stage_coordinator", repo_root=root).digest == (
        compute_bundle("stage_coordinator", repo_root=REPO_ROOT).digest
    )
    live = read_manifest("stage_coordinator", repo_root=REPO_ROOT)
    ghost = "workers/intelligence/src/opintel_intelligence_worker/ghost.py"
    with_ghost = sorted([*live, ghost])
    with pytest.raises(BundleManifestError, match="not a regular file"):
        compute_bundle(
            "stage_coordinator",
            repo_root=_materialize(
                tmp_path / "z", "stage_coordinator",
                manifest_text="\n".join(with_ghost) + "\n",
            ),
        )


@pytest.mark.parametrize("name", BUNDLES)
def test_member_digests_match_raw_file_bytes(name: str) -> None:
    att = compute_bundle(name, repo_root=REPO_ROOT)
    for relpath, member_sha in att.members:
        assert member_sha == hashlib.sha256((REPO_ROOT / relpath).read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("name", "tfvar"),
    [
        ("stage_coordinator", "sampled_slot_stage_coordinator_sha256"),
        ("m2_m5_runtime", "sampled_slot_m2_m5_runtime_sha256"),
    ],
)
def test_tfvars_binding_equals_canonical_calculator(name: str, tfvar: str) -> None:
    text = TFVARS.read_text(encoding="utf-8")
    match = re.search(rf'^{tfvar}\s*=\s*"([0-9a-f]{{64}})"', text, re.M)
    assert match, f"{tfvar} not found in terraform.tfvars"
    assert match.group(1) == compute_bundle(name, repo_root=REPO_ROOT).digest, (
        f"{tfvar} in terraform.tfvars does not match the canonical bundle calculator; "
        f"run `python -m scripts.sampled_slot_bundle` and update it."
    )


def test_calculator_covers_exactly_the_two_authorized_bindings() -> None:
    assert set(BUNDLES) == {"stage_coordinator", "m2_m5_runtime"}
    assert set(compute_all(repo_root=REPO_ROOT)) == set(BUNDLES)
