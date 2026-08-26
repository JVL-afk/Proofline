from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_m67_registry_image_identity import OCI_CONFIG, OCI_LAYER, OCI_LAYER_GZIP, verify


def _write(path: Path, value: object) -> bytes:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(payload)
    return payload


def _fixtures(tmp_path: Path) -> dict[str, Path]:
    diff_id = "sha256:" + "1" * 64
    config = {
        "architecture": "amd64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [diff_id]},
    }
    config_path = tmp_path / "config.json"
    config_raw = _write(config_path, config)
    descriptor = {
        "mediaType": OCI_CONFIG,
        "digest": "sha256:" + hashlib.sha256(config_raw).hexdigest(),
        "size": len(config_raw),
    }
    local = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": descriptor,
        "layers": [{"mediaType": OCI_LAYER, "digest": diff_id, "size": 10}],
        "annotations": {"source": "frozen"},
    }
    registry = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": descriptor,
        "layers": [
            {"mediaType": OCI_LAYER_GZIP, "digest": "sha256:" + "2" * 64, "size": 8}
        ],
        "annotations": {"source": "frozen"},
    }
    paths = {
        "local": tmp_path / "local.json",
        "registry": tmp_path / "registry.json",
        "reproduced": tmp_path / "reproduced.json",
        "config": config_path,
    }
    _write(paths["local"], local)
    _write(paths["registry"], registry)
    _write(paths["reproduced"], registry)
    return paths


def test_proves_exact_registry_representation(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    result = verify(
        local_manifest_path=paths["local"],
        registry_manifest_path=paths["registry"],
        reproduced_manifest_path=paths["reproduced"],
        config_path=paths["config"],
        expected_os="linux",
        expected_architecture="amd64",
    )
    assert result["classification"] == "REPRESENTATION_EQUIVALENT_PROVEN"
    assert result["registry_manifest"]["object_type"] == "SINGLE_PLATFORM_IMAGE_MANIFEST"
    assert result["attestations"] == []


def test_rejects_registry_bytes_not_reproduced(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    value = json.loads(paths["reproduced"].read_text())
    value["annotations"]["changed"] = "yes"
    _write(paths["reproduced"], value)
    with pytest.raises(ValueError, match="do not equal"):
        verify(
            local_manifest_path=paths["local"],
            registry_manifest_path=paths["registry"],
            reproduced_manifest_path=paths["reproduced"],
            config_path=paths["config"],
            expected_os="linux",
            expected_architecture="amd64",
        )


def test_rejects_wrong_runtime_platform(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    with pytest.raises(ValueError, match="platform"):
        verify(
            local_manifest_path=paths["local"],
            registry_manifest_path=paths["registry"],
            reproduced_manifest_path=paths["reproduced"],
            config_path=paths["config"],
            expected_os="linux",
            expected_architecture="arm64",
        )
