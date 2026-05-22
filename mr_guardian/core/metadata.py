"""Local MR metadata helpers."""

from pathlib import Path


def resolve_description(
    *,
    description: str | None = None,
    description_file: str | Path | None = None,
) -> str:
    """Resolve MR description text from inline text or a file."""
    if description is not None and description_file is not None:
        msg = "Use either --description or --description-file, not both."
        raise ValueError(msg)

    if description is not None:
        return description

    if description_file is None:
        return ""

    return Path(description_file).read_text(encoding="utf-8")
