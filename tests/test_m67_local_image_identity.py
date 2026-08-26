from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest

from scripts.verify_m67_local_image_identity import (
    OCI_CONFIG,
    OCI_LAYER,
    OCI_LAYER_GZIP,
    sha256_digest,
    verify,
)


def _compact(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _fixtures(tmp_path: Path) -> dict[str, object]:
    uncompressed = b"exact tar-layer bytes"
    compressed = gzip.compress(uncompressed, mtime=0)
    diff_id = sha256_digest(uncompressed)
    config = {
        "architecture": "amd64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [diff_id]},
    }
    config_raw = _compact(config)
    config_digest = sha256_digest(config_raw)
    config_descriptor = {
        "mediaType": OCI_CONFIG,
        "digest": config_digest,
        "size": len(config_raw),
    }
    annotations = {"frozen": "same"}
    archive_manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": config_descriptor,
        "layers": [
            {
                "mediaType": OCI_LAYER_GZIP,
                "digest": sha256_digest(compressed),
                "size": len(compressed),
            }
        ],
        "annotations": annotations,
    }
    archive_manifest_raw = _compact(archive_manifest)
    archive_digest = sha256_digest(archive_manifest_raw)
    storage_manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": config_descriptor,
        "layers": [{"mediaType": OCI_LAYER, "digest": diff_id, "size": len(uncompressed)}],
        "annotations": annotations,
    }
    storage_raw = _compact(storage_manifest)
    storage_digest = sha256_digest(storage_raw)
    index = {
        "schemaVersion": 2,
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": archive_digest,
                "size": len(archive_manifest_raw),
                "annotations": {"org.opencontainers.image.ref.name": "frozen"},
            }
        ],
    }
    archive_path = tmp_path / "image.tar"
    members = {
        "index.json": _compact(index),
        f"blobs/sha256/{archive_digest.removeprefix('sha256:')}": archive_manifest_raw,
        f"blobs/sha256/{config_digest.removeprefix('sha256:')}": config_raw,
        f"blobs/sha256/{sha256_digest(compressed).removeprefix('sha256:')}": compressed,
    }
    with tarfile.open(archive_path, "w") as archive:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return {
        "archive": archive_path,
        "archive_digest": archive_digest,
        "storage_raw": storage_raw,
        "storage_digest": storage_digest,
        "config_digest": config_digest,
        "storage_manifest": storage_manifest,
    }


def _verify(values: dict[str, object]) -> dict[str, object]:
    return verify(
        oci_archive_path=values["archive"],
        storage_manifest_raw=values["storage_raw"],
        expected_archive_manifest_digest=values["archive_digest"],
        expected_storage_manifest_digest=values["storage_digest"],
        expected_config_digest=values["config_digest"],
    )


def test_proves_compressed_archive_to_uncompressed_storage_equivalence(tmp_path: Path) -> None:
    values = _fixtures(tmp_path)
    result = _verify(values)
    assert result["classification"] == "LOCAL_REPRESENTATION_EQUIVALENT_PROVEN"
    assert result["ordered_layer_mappings"][0]["mapping"].startswith("GZIP_DECOMPRESS")
    assert result["shared_config"]["platform"] == {"os": "linux", "architecture": "amd64"}


def test_rejects_wrong_storage_manifest_identity(tmp_path: Path) -> None:
    values = _fixtures(tmp_path)
    with pytest.raises(ValueError, match="storage manifest digest"):
        verify(
            oci_archive_path=values["archive"],
            storage_manifest_raw=values["storage_raw"],
            expected_archive_manifest_digest=values["archive_digest"],
            expected_storage_manifest_digest="sha256:" + "0" * 64,
            expected_config_digest=values["config_digest"],
        )


def test_rejects_layer_mapping_difference(tmp_path: Path) -> None:
    values = _fixtures(tmp_path)
    storage = dict(values["storage_manifest"])
    storage["layers"] = [dict(storage["layers"][0], digest="sha256:" + "1" * 64)]
    values["storage_raw"] = _compact(storage)
    values["storage_digest"] = sha256_digest(values["storage_raw"])
    with pytest.raises(ValueError, match="rootfs diff IDs"):
        _verify(values)


def test_rejects_annotation_difference(tmp_path: Path) -> None:
    values = _fixtures(tmp_path)
    storage = dict(values["storage_manifest"])
    storage["annotations"] = {"frozen": "changed"}
    values["storage_raw"] = _compact(storage)
    values["storage_digest"] = sha256_digest(values["storage_raw"])
    with pytest.raises(ValueError, match="annotations differ"):
        _verify(values)
