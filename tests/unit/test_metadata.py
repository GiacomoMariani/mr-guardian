from pathlib import Path

import pytest

from mr_guardian.core.metadata import resolve_description


def test_resolve_description_returns_inline_text() -> None:
    assert resolve_description(description="## Summary") == "## Summary"


def test_resolve_description_reads_file(tmp_path: Path) -> None:
    description_path = tmp_path / "mr.md"
    description_path.write_text("## Test Plan\n- Ran", encoding="utf-8")

    assert resolve_description(description_file=description_path) == "## Test Plan\n- Ran"


def test_resolve_description_rejects_inline_and_file(tmp_path: Path) -> None:
    description_path = tmp_path / "mr.md"
    description_path.write_text("## Summary", encoding="utf-8")

    with pytest.raises(ValueError, match="Use either"):
        resolve_description(description="inline", description_file=description_path)


def test_resolve_description_defaults_to_empty_text() -> None:
    assert resolve_description() == ""
