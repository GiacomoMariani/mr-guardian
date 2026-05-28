"""Typed review input models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

FileStatus = Literal["added", "modified", "deleted", "renamed", "unknown"]
DiffLineKind = Literal["context", "addition", "deletion"]


class DiffLine(BaseModel):
    """A single line inside a unified diff hunk."""

    model_config = ConfigDict(frozen=True)

    kind: DiffLineKind
    content: str
    old_line_number: int | None
    new_line_number: int | None


class DiffHunk(BaseModel):
    """A unified diff hunk for a changed file."""

    model_config = ConfigDict(frozen=True)

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine]


class ChangedFile(BaseModel):
    """A file changed relative to the review base."""

    model_config = ConfigDict(frozen=True)

    path: Path
    status: FileStatus
    hunks: list[DiffHunk]
    old_path: Path | None = None


class ReviewInput(BaseModel):
    """Input collected from a review provider."""

    model_config = ConfigDict(frozen=True)

    base_ref: str
    review_scope: str = "local-all-policies"
    changed_files: list[ChangedFile]
    title: str = ""
    description: str = ""
