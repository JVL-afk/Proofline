"""Prove equivalence between an OCI archive and Buildah containers-storage image.

The two manifests are allowed to use different layer representations. Equivalence requires an
identical config descriptor and annotations plus an ordered, byte-level mapping from every gzip
archive layer to the corresponding uncompressed storage layer/rootfs diff ID.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from typing import Any

OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
OCI_LAYER = "application/vnd.oci.image.layer.v1.tar"
OCI_LAYER_GZIP = "application/vnd.oci.image.layer.v1.tar+gzip"


def sha256_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json_object(name: str, payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def _require_single_oci_manifest(name: str, manifest: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != 2 or manifest.get("mediaType") != OCI_MANIFEST:
        raise ValueError(f"{name} is not a single OCI image manifest")
    if "manifests" in manifest or "subject" in manifest or "artifactType" in manifest:
        raise ValueError(f"{name} contains an index, subject, or artifact wrapper")
    if not isinstance(manifest.get("config"), dict):
        raise ValueError(f"{name} has no config descriptor")
    if not isinstance(manifest.get("layers"), list):
        raise ValueError(f"{name} has no ordered layer descriptors")


def verify(
    *,
    oci_archive_path: Path,
    storage_manifest_raw: bytes,
    expected_archive_manifest_digest: str,
    expected_storage_manifest_digest: str,
    expected_config_digest: str,
    expected_os: str = "linux",
    expected_architecture: str = "amd64",
) -> dict[str, Any]:
    with tarfile.open(oci_archive_path, "r") as archive:
        index_stream = archive.extractfile("index.json")
        if index_stream is None:
            raise ValueError("OCI archive has no index.json")
        index_raw = index_stream.read()
        index = _json_object("OCI archive index", index_raw)
        descriptors = index.get("manifests")
        if not isinstance(descriptors, list) or len(descriptors) != 1:
            raise ValueError("OCI archive must reference exactly one image manifest")
        archive_descriptor = descriptors[0]
        if not isinstance(archive_descriptor, dict):
            raise ValueError("OCI archive image descriptor is malformed")
        archive_digest = archive_descriptor.get("digest")
        if archive_digest != expected_archive_manifest_digest:
            raise ValueError("OCI archive manifest descriptor digest mismatch")
        archive_manifest_stream = archive.extractfile(
            f"blobs/sha256/{archive_digest.removeprefix('sha256:')}"
        )
        if archive_manifest_stream is None:
            raise ValueError("OCI archive manifest blob is absent")
        archive_manifest_raw = archive_manifest_stream.read()
        if sha256_digest(archive_manifest_raw) != archive_digest:
            raise ValueError("OCI archive manifest bytes do not match its descriptor")
        if archive_descriptor.get("size") != len(archive_manifest_raw):
            raise ValueError("OCI archive manifest size does not match its descriptor")
        archive_manifest = _json_object("OCI archive manifest", archive_manifest_raw)

        storage_digest = sha256_digest(storage_manifest_raw)
        if storage_digest != expected_storage_manifest_digest:
            raise ValueError("Buildah storage manifest digest mismatch")
        storage_manifest = _json_object("Buildah storage manifest", storage_manifest_raw)

        _require_single_oci_manifest("OCI archive manifest", archive_manifest)
        _require_single_oci_manifest("Buildah storage manifest", storage_manifest)

        archive_config = archive_manifest["config"]
        storage_config = storage_manifest["config"]
        if archive_config != storage_config:
            raise ValueError("config descriptors differ between local representations")
        if archive_config.get("mediaType") != OCI_CONFIG:
            raise ValueError("unexpected OCI config media type")
        if archive_config.get("digest") != expected_config_digest:
            raise ValueError("shared config digest differs from the approved identity")
        config_stream = archive.extractfile(
            f"blobs/sha256/{expected_config_digest.removeprefix('sha256:')}"
        )
        if config_stream is None:
            raise ValueError("OCI config blob is absent")
        config_raw = config_stream.read()
        if sha256_digest(config_raw) != expected_config_digest:
            raise ValueError("OCI config bytes do not match the shared descriptor")
        if archive_config.get("size") != len(config_raw):
            raise ValueError("OCI config size does not match its descriptor")
        config = _json_object("OCI config", config_raw)
        if config.get("os") != expected_os or config.get("architecture") != expected_architecture:
            raise ValueError("OCI config platform differs from the required runtime platform")

        archive_layers = archive_manifest["layers"]
        storage_layers = storage_manifest["layers"]
        if len(archive_layers) != len(storage_layers):
            raise ValueError("local representation layer counts differ")
        if any(item.get("mediaType") != OCI_LAYER_GZIP for item in archive_layers):
            raise ValueError("OCI archive layers are not all gzip OCI tar descriptors")
        if any(item.get("mediaType") != OCI_LAYER for item in storage_layers):
            raise ValueError("Buildah storage layers are not all uncompressed OCI tar descriptors")

        diff_ids = config.get("rootfs", {}).get("diff_ids")
        storage_digests = [item.get("digest") for item in storage_layers]
        if diff_ids != storage_digests:
            raise ValueError("Buildah storage layers do not equal the config rootfs diff IDs")

        mappings: list[dict[str, Any]] = []
        for layer_position, (compressed_descriptor, storage_descriptor) in enumerate(
            zip(archive_layers, storage_layers, strict=True), start=1
        ):
            compressed_digest = compressed_descriptor.get("digest")
            compressed_stream = archive.extractfile(
                f"blobs/sha256/{str(compressed_digest).removeprefix('sha256:')}"
            )
            if compressed_stream is None:
                raise ValueError(f"compressed OCI layer {layer_position} is absent")
            compressed_raw = compressed_stream.read()
            if sha256_digest(compressed_raw) != compressed_digest:
                raise ValueError(f"compressed OCI layer {layer_position} digest mismatch")
            if compressed_descriptor.get("size") != len(compressed_raw):
                raise ValueError(f"compressed OCI layer {layer_position} size mismatch")
            try:
                uncompressed_raw = gzip.decompress(compressed_raw)
            except OSError as error:
                raise ValueError(
                    f"compressed OCI layer {layer_position} is not valid gzip"
                ) from error
            uncompressed_digest = sha256_digest(uncompressed_raw)
            if uncompressed_digest != storage_descriptor.get("digest"):
                raise ValueError(
                    f"layer {layer_position} does not map to the storage representation"
                )
            if len(uncompressed_raw) != storage_descriptor.get("size"):
                raise ValueError(f"uncompressed OCI layer {layer_position} size mismatch")
            mappings.append(
                {
                    "position": layer_position,
                    "archive_compressed_digest": compressed_digest,
                    "archive_compressed_media_type": compressed_descriptor["mediaType"],
                    "archive_compressed_size": len(compressed_raw),
                    "storage_uncompressed_digest": uncompressed_digest,
                    "storage_uncompressed_media_type": storage_descriptor["mediaType"],
                    "storage_uncompressed_size": len(uncompressed_raw),
                    "config_rootfs_diff_id": diff_ids[layer_position - 1],
                    "mapping": "GZIP_DECOMPRESS_SHA256_EQUALS_STORAGE_DIGEST_AND_ROOTFS_DIFF_ID",
                }
            )

    if archive_manifest.get("annotations") != storage_manifest.get("annotations"):
        raise ValueError("local representation annotations differ")

    return {
        "classification": "LOCAL_REPRESENTATION_EQUIVALENT_PROVEN",
        "invariant": "LOCAL_IMAGE_IDENTITY",
        "local_image_identity": {
            "archive_manifest_digest": expected_archive_manifest_digest,
            "storage_manifest_digest": expected_storage_manifest_digest,
            "config_digest": expected_config_digest,
            "ordered_rootfs_diff_ids": diff_ids,
            "representation_relationship": (
                "Every ordered OCI-archive gzip layer hashes to its archive descriptor and "
                "decompresses byte-for-byte to the Buildah storage-layer digest, which equals "
                "the config rootfs diff ID at the same position."
            ),
        },
        "archive_representation": {
            "manifest_media_type": archive_manifest["mediaType"],
            "manifest_digest": expected_archive_manifest_digest,
            "manifest_byte_length": len(archive_manifest_raw),
            "manifest_serialization": "EXACT_ARCHIVE_BLOB_BYTES",
            "config": archive_manifest["config"],
            "layers": archive_layers,
            "annotations": archive_manifest.get("annotations", {}),
            "index_descriptor": archive_descriptor,
            "index_sha256": sha256_digest(index_raw),
        },
        "storage_representation": {
            "manifest_media_type": storage_manifest["mediaType"],
            "manifest_digest": expected_storage_manifest_digest,
            "manifest_byte_length": len(storage_manifest_raw),
            "manifest_serialization": "EXACT_CONTAINERS_STORAGE_RAW_BYTES",
            "config": storage_manifest["config"],
            "layers": storage_layers,
            "annotations": storage_manifest.get("annotations", {}),
        },
        "shared_config": {
            "digest": expected_config_digest,
            "byte_length": len(config_raw),
            "media_type": OCI_CONFIG,
            "platform": {"os": config["os"], "architecture": config["architecture"]},
            "ordered_rootfs_diff_ids": diff_ids,
            "config_labels": config.get("config", {}).get("Labels", {}),
        },
        "ordered_layer_mappings": mappings,
        "index_or_manifest_list": False,
        "attestations": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oci-archive", type=Path, required=True)
    parser.add_argument("--storage-image", required=True)
    parser.add_argument("--expected-archive-manifest-digest", required=True)
    parser.add_argument("--expected-storage-manifest-digest", required=True)
    parser.add_argument("--expected-config-digest", required=True)
    parser.add_argument("--expected-os", default="linux")
    parser.add_argument("--expected-architecture", default="amd64")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inspected = subprocess.run(
        [
            "wsl.exe",
            "skopeo",
            "inspect",
            "--raw",
            f"containers-storage:{args.storage_image}",
        ],
        check=True,
        capture_output=True,
    )
    result = verify(
        oci_archive_path=args.oci_archive,
        storage_manifest_raw=inspected.stdout,
        expected_archive_manifest_digest=args.expected_archive_manifest_digest,
        expected_storage_manifest_digest=args.expected_storage_manifest_digest,
        expected_config_digest=args.expected_config_digest,
        expected_os=args.expected_os,
        expected_architecture=args.expected_architecture,
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
