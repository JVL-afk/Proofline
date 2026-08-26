"""Verify a Phase 1 registry manifest is a proven representation of a reviewed local image.

This verifier is deliberately network-free. Registry manifest bytes must be captured separately
through the bounded read-only registry API. A locally reproduced registry representation is
required so matching config metadata alone can never be treated as proof of equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
OCI_LAYER = "application/vnd.oci.image.layer.v1.tar"
OCI_LAYER_GZIP = "application/vnd.oci.image.layer.v1.tar+gzip"


def sha256_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> tuple[bytes, dict[str, Any]]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload, value


def _require_single_oci_image(name: str, manifest: dict[str, Any]) -> None:
    if manifest.get("mediaType") != OCI_MANIFEST:
        raise ValueError(f"{name} is not a single OCI image manifest")
    if "manifests" in manifest or "subject" in manifest or "artifactType" in manifest:
        raise ValueError(f"{name} contains an index, subject, or artifact wrapper")
    if not isinstance(manifest.get("config"), dict):
        raise ValueError(f"{name} has no config descriptor")
    if not isinstance(manifest.get("layers"), list):
        raise ValueError(f"{name} has no ordered layer descriptors")


def verify(
    *,
    local_manifest_path: Path,
    registry_manifest_path: Path,
    reproduced_manifest_path: Path,
    config_path: Path,
    expected_os: str,
    expected_architecture: str,
) -> dict[str, Any]:
    local_raw, local = _load(local_manifest_path)
    registry_raw, registry = _load(registry_manifest_path)
    reproduced_raw, reproduced = _load(reproduced_manifest_path)
    config_raw, config = _load(config_path)

    _require_single_oci_image("local manifest", local)
    _require_single_oci_image("registry manifest", registry)
    _require_single_oci_image("reproduced manifest", reproduced)

    if registry_raw != reproduced_raw:
        raise ValueError("registry manifest bytes do not equal the local reproduction")
    if local.get("config") != registry.get("config"):
        raise ValueError("registry config descriptor differs from the reviewed local image")
    config_descriptor = local["config"]
    if config_descriptor.get("mediaType") != OCI_CONFIG:
        raise ValueError("unexpected config media type")
    if config_descriptor.get("digest") != sha256_digest(config_raw):
        raise ValueError("config bytes do not match the shared config descriptor")
    if config.get("os") != expected_os or config.get("architecture") != expected_architecture:
        raise ValueError("config platform does not match the required ECS runtime platform")

    local_layers = local["layers"]
    registry_layers = registry["layers"]
    if len(local_layers) != len(registry_layers):
        raise ValueError("registry layer count differs from the reviewed local image")
    if any(item.get("mediaType") != OCI_LAYER for item in local_layers):
        raise ValueError("local manifest does not describe the reviewed uncompressed OCI layers")
    if any(item.get("mediaType") != OCI_LAYER_GZIP for item in registry_layers):
        raise ValueError("registry manifest does not contain the reproduced gzip representation")

    diff_ids = config.get("rootfs", {}).get("diff_ids")
    local_layer_digests = [item.get("digest") for item in local_layers]
    if diff_ids != local_layer_digests:
        raise ValueError("config rootfs diff IDs do not bind the ordered local layers")
    if local.get("annotations") != registry.get("annotations"):
        raise ValueError("registry annotations differ from the reviewed local manifest")

    return {
        "classification": "REPRESENTATION_EQUIVALENT_PROVEN",
        "invariant": (
            "DEPLOYMENT_IMAGE_DIGEST="
            "REGISTRY_MANIFEST_OR_INDEX_DIGEST_PROVEN_AFTER_PUBLICATION"
        ),
        "local_manifest": {
            "digest": sha256_digest(local_raw),
            "media_type": local["mediaType"],
            "layer_representation": "UNCOMPRESSED_OCI_TAR",
        },
        "registry_manifest": {
            "digest": sha256_digest(registry_raw),
            "media_type": registry["mediaType"],
            "object_type": "SINGLE_PLATFORM_IMAGE_MANIFEST",
            "layer_representation": "GZIP_COMPRESSED_OCI_TAR",
        },
        "reproduced_registry_manifest": {
            "digest": sha256_digest(reproduced_raw),
            "byte_equal_to_registry": True,
        },
        "platform": {"os": config["os"], "architecture": config["architecture"]},
        "config": config_descriptor,
        "rootfs_diff_ids": diff_ids,
        "registry_layers": registry_layers,
        "index_or_manifest_list": False,
        "child_manifests": [],
        "attestations": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-manifest", type=Path, required=True)
    parser.add_argument("--registry-manifest", type=Path, required=True)
    parser.add_argument("--reproduced-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-os", default="linux")
    parser.add_argument("--expected-architecture", default="amd64")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        local_manifest_path=args.local_manifest,
        registry_manifest_path=args.registry_manifest,
        reproduced_manifest_path=args.reproduced_manifest,
        config_path=args.config,
        expected_os=args.expected_os,
        expected_architecture=args.expected_architecture,
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
