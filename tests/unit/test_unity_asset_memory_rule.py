"""Tests for UNITY-ASSET-MEMORY-001 texture memory estimation (ticket 057)."""

import struct
from pathlib import Path

from mr_guardian.core.engine import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ChangedFile, ReviewInput
from mr_guardian.rules import default_rule_registry

_UNCOMPRESSED_META = """\
fileFormatVersion: 2
guid: 0123456789abcdef0123456789abcdef
TextureImporter:
  mipmaps:
    enableMipMap: 1
  maxTextureSize: 8192
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: 8192
    textureCompression: 0
    format: -1
"""


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def _changed(path: str) -> ChangedFile:
    return ChangedFile(path=Path(path), status="added", hunks=[])


def _review(changed: list[ChangedFile], repo_root: Path | None):
    rule = PolicyRule(
        id="UNITY-ASSET-MEMORY-001",
        type="deterministic",
        implementation="unity_asset_memory_delta",
        enabled=True,
        severity="blocking",
        source="unity-policy.yml#UNITY-ASSET-MEMORY-001",
        description="Asset memory.",
        parameters={"threshold": {"warn_mb": 25, "block_mb": 75}},
    )
    return run_review(
        policy=Policy(version=1, rules=[rule]),
        review_input=ReviewInput(base_ref="main", changed_files=changed),
        rule_registry=default_rule_registry(),
        repo_root=repo_root,
    )


def _write_texture(
    repo_root: Path, rel: str, width: int, height: int, meta: str = _UNCOMPRESSED_META
) -> None:
    asset = repo_root / rel
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(_png(width, height))
    (repo_root / (rel + ".meta")).write_text(meta, encoding="utf-8")


def test_flags_oversized_uncompressed_texture(tmp_path: Path) -> None:
    # 4096x4096 RGBA32 + mips ~= 85 MB, over the 75 MB block budget.
    _write_texture(tmp_path, "Assets/Art/huge.png", 4096, 4096)

    result = _review([_changed("Assets/Art/huge.png")], tmp_path)

    assert [f.rule_id for f in result.findings] == ["UNITY-ASSET-MEMORY-001"]
    assert result.findings[0].severity == "blocking"


def test_ignores_small_texture(tmp_path: Path) -> None:
    _write_texture(tmp_path, "Assets/Art/small.png", 256, 256)

    result = _review([_changed("Assets/Art/small.png")], tmp_path)

    assert result.findings == []


def test_no_finding_without_meta(tmp_path: Path) -> None:
    asset = tmp_path / "Assets/Art/lonely.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(_png(4096, 4096))

    result = _review([_changed("Assets/Art/lonely.png")], tmp_path)

    assert result.findings == []


def test_no_finding_without_repo_root() -> None:
    result = _review([_changed("Assets/Art/huge.png")], None)

    assert result.findings == []
