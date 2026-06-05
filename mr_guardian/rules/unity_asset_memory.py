"""Deterministic rule estimating Unity texture runtime memory from changed assets.

Ticket 057. Rather than asking the developer for a report or ingesting a build
report, this rule reads the changed texture and its ``.meta`` (via the review
checkout wired in ticket 058) and estimates the runtime memory footprint:

    memory = effective_width * effective_height * bytes_per_pixel * mip_factor

``effective_*`` is the source dimension capped by the importer ``maxTextureSize``.
The estimate is deliberately rough (compressed-vs-uncompressed bits-per-pixel,
not the full Unity format enum) — it is a budget guard, not an exact figure.
"""

import struct
from pathlib import Path
from typing import Any

import yaml

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import finding

_TEXTURE_SUFFIXES = {".png", ".tga", ".psd", ".exr", ".tif", ".tiff", ".jpg", ".jpeg"}
_PARSEABLE_DIMENSION_SUFFIXES = {".png", ".tga"}
_DEFAULT_MAX_TEXTURE_SIZE = 2048
_UNCOMPRESSED_BITS_PER_PIXEL = 32
_COMPRESSED_BITS_PER_PIXEL = 8
_MIP_FACTOR = 4.0 / 3.0
_BYTES_PER_MB = 1024 * 1024
_DEFAULT_BLOCK_MB = 75


class UnityAssetMemoryRule:
    """Flag changed textures whose estimated runtime memory exceeds the budget."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        block_mb = _threshold_mb(rule, "block_mb", default=_DEFAULT_BLOCK_MB)
        findings: list[Finding] = []
        for changed_file in context.review_input.changed_files:
            if changed_file.status not in {"added", "modified", "renamed"}:
                continue
            if changed_file.path.suffix.lower() not in _TEXTURE_SUFFIXES:
                continue
            estimate_mb = _estimate_texture_mb(context, changed_file.path)
            if estimate_mb is None or estimate_mb < block_mb:
                continue
            findings.append(
                finding(
                    rule,
                    (
                        f"Estimated texture memory ~{estimate_mb:.0f} MB for "
                        f"{changed_file.path.as_posix()} exceeds the {block_mb} MB budget. "
                        "Lower Max Size, enable compression, or split the texture."
                    ),
                    file_path=changed_file.path,
                )
            )
        return findings


def _estimate_texture_mb(context: RuleEvaluationContext, asset_path: Path) -> float | None:
    importer = _texture_importer(context, asset_path)
    if importer is None:
        return None
    max_size = _max_texture_size(importer)
    bits_per_pixel = _bits_per_pixel(importer)
    mip_factor = _MIP_FACTOR if _mipmaps_enabled(importer) else 1.0

    dimensions = _image_dimensions(context, asset_path)
    if dimensions is None:
        width = height = max_size
    else:
        width = min(dimensions[0], max_size)
        height = min(dimensions[1], max_size)

    memory_bytes = width * height * (bits_per_pixel / 8) * mip_factor
    return memory_bytes / _BYTES_PER_MB


def _texture_importer(context: RuleEvaluationContext, asset_path: Path) -> dict[str, Any] | None:
    meta_bytes = context.read_changed_bytes(Path(asset_path.as_posix() + ".meta"))
    if meta_bytes is None:
        return None
    try:
        loaded = yaml.safe_load(meta_bytes)
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    importer = loaded.get("TextureImporter")
    return importer if isinstance(importer, dict) else None


def _default_platform_settings(importer: dict[str, Any]) -> dict[str, Any]:
    settings = importer.get("platformSettings")
    if not isinstance(settings, list):
        return {}
    entries = [entry for entry in settings if isinstance(entry, dict)]
    for entry in entries:
        if entry.get("buildTarget") == "DefaultTexturePlatform":
            return entry
    return entries[0] if entries else {}


def _max_texture_size(importer: dict[str, Any]) -> int:
    platform = _default_platform_settings(importer)
    for source in (platform.get("maxTextureSize"), importer.get("maxTextureSize")):
        if isinstance(source, int) and source > 0:
            return source
    return _DEFAULT_MAX_TEXTURE_SIZE


def _bits_per_pixel(importer: dict[str, Any]) -> int:
    compression = _default_platform_settings(importer).get("textureCompression")
    # 0 = uncompressed; 1/2/3 = compressed (normal / high quality / low).
    if compression == 0:
        return _UNCOMPRESSED_BITS_PER_PIXEL
    return _COMPRESSED_BITS_PER_PIXEL


def _mipmaps_enabled(importer: dict[str, Any]) -> bool:
    mipmaps = importer.get("mipmaps")
    if isinstance(mipmaps, dict) and "enableMipMap" in mipmaps:
        return bool(mipmaps.get("enableMipMap"))
    return bool(importer.get("enableMipMap", 0))


def _image_dimensions(context: RuleEvaluationContext, asset_path: Path) -> tuple[int, int] | None:
    suffix = asset_path.suffix.lower()
    if suffix not in _PARSEABLE_DIMENSION_SUFFIXES:
        return None
    data = context.read_changed_bytes(asset_path)
    if data is None:
        return None
    if suffix == ".png":
        return _png_dimensions(data)
    return _tga_dimensions(data)


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return (width, height) if width and height else None


def _tga_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 18:
        return None
    width, height = struct.unpack("<HH", data[12:16])
    return (width, height) if width and height else None


def _threshold_mb(rule: PolicyRule, key: str, *, default: int) -> int:
    threshold = rule.parameters.get("threshold")
    if isinstance(threshold, dict):
        value = threshold.get(key)
        if isinstance(value, int):
            return value
    return default
