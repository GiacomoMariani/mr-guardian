"""Local Git review input provider."""

import re
import subprocess
from pathlib import Path

from mr_guardian.models.review_input import (
    ChangedFile,
    DiffHunk,
    DiffLine,
    FileStatus,
    ReviewInput,
)

HUNK_HEADER_PATTERN = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


class GitProviderError(Exception):
    """Base error for local Git provider failures."""


class GitUnavailableError(GitProviderError):
    """Raised when the Git executable is unavailable."""


class GitRepositoryError(GitProviderError):
    """Raised when Git cannot collect review input from the repository."""


class LocalGitProvider:
    """Collect review input from a local Git repository."""

    def __init__(self, repo_path: str | Path = ".") -> None:
        self.repo_path = Path(repo_path)

    def collect(self, base_ref: str) -> ReviewInput:
        """Collect changed files and hunks compared with the base ref."""
        self._ensure_repository()
        name_status_output = self._run_git(
            "diff",
            "--name-status",
            "--find-renames",
            base_ref,
            "--",
        )
        changed_files = _parse_name_status(name_status_output)

        if not changed_files:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        diff_output = self._run_git("diff", "--find-renames", "--unified=0", base_ref, "--")
        hunks_by_path = _parse_diff_hunks(diff_output)

        return ReviewInput(
            base_ref=base_ref,
            changed_files=[
                file.model_copy(update={"hunks": hunks_by_path.get(file.path.as_posix(), [])})
                for file in changed_files
            ],
        )

    def developer_id(self) -> str:
        """Return the developer identity configured for the local repository."""
        self._ensure_repository()
        for config_key in ("user.name", "user.email"):
            try:
                value = self._run_git("config", "--local", "--get", config_key).strip()
            except GitRepositoryError:
                continue
            if value:
                return value
        return "unknown"

    def _ensure_repository(self) -> None:
        self._run_git("rev-parse", "--show-toplevel")

    def _run_git(self, *args: str) -> str:
        try:
            safe_repo_path = self.repo_path.resolve().as_posix()
            completed = subprocess.run(
                ["git", "-c", f"safe.directory={safe_repo_path}", "-C", str(self.repo_path), *args],
                capture_output=True,
                check=False,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            msg = "Git executable is not available on PATH."
            raise GitUnavailableError(msg) from exc

        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip() or "unknown Git error"
            msg = f"Git command failed: git {' '.join(args)}: {error}"
            raise GitRepositoryError(msg)

        return completed.stdout


def _parse_name_status(output: str) -> list[ChangedFile]:
    return [_parse_name_status_line(line) for line in output.splitlines() if line.strip()]


def _parse_name_status_line(line: str) -> ChangedFile:
    parts = line.split("\t")
    status_token = parts[0]
    status = _map_status(status_token)

    if status == "renamed" and len(parts) >= 3:
        return ChangedFile(path=Path(parts[2]), old_path=Path(parts[1]), status=status, hunks=[])

    if len(parts) < 2:
        return ChangedFile(path=Path(""), status="unknown", hunks=[])

    return ChangedFile(path=Path(parts[1]), status=status, hunks=[])


def _map_status(status_token: str) -> FileStatus:
    status_code = status_token[:1]
    if status_code == "A":
        return "added"
    if status_code == "M":
        return "modified"
    if status_code == "D":
        return "deleted"
    if status_code == "R":
        return "renamed"
    return "unknown"


def _parse_diff_hunks(output: str) -> dict[str, list[DiffHunk]]:
    mutable_hunks_by_path: dict[str, list[_MutableHunk]] = {}
    current_path: str | None = None
    current_hunk: _MutableHunk | None = None
    old_line_number = 0
    new_line_number = 0

    for line in output.splitlines():
        if line.startswith("diff --git "):
            current_path = _path_from_diff_git_line(line)
            current_hunk = None
            if current_path is not None:
                mutable_hunks_by_path.setdefault(current_path, [])
            continue

        if line.startswith("+++ "):
            current_path = _path_from_marker_line(line, current_path)
            if current_path is not None:
                mutable_hunks_by_path.setdefault(current_path, [])
            continue

        hunk_match = HUNK_HEADER_PATTERN.match(line)
        if hunk_match and current_path is not None:
            old_start = int(hunk_match.group("old_start"))
            old_count = int(hunk_match.group("old_count") or "1")
            new_start = int(hunk_match.group("new_start"))
            new_count = int(hunk_match.group("new_count") or "1")
            current_hunk = _MutableHunk(old_start, old_count, new_start, new_count)
            mutable_hunks_by_path[current_path].append(current_hunk)
            old_line_number = old_start
            new_line_number = new_start
            continue

        if current_hunk is None or current_path is None:
            continue

        if line.startswith("\\"):
            continue

        diff_line, old_line_number, new_line_number = _parse_diff_line(
            line,
            old_line_number,
            new_line_number,
        )
        if diff_line is not None:
            current_hunk.lines.append(diff_line)

    return {
        path: [hunk.to_diff_hunk() for hunk in hunks]
        for path, hunks in mutable_hunks_by_path.items()
    }


def _path_from_diff_git_line(line: str) -> str | None:
    parts = line.split(" ")
    if len(parts) < 4:
        return None
    return _strip_git_prefix(parts[3])


def _path_from_marker_line(line: str, fallback: str | None) -> str | None:
    marker_path = line[4:]
    if marker_path == "/dev/null":
        return fallback
    return _strip_git_prefix(marker_path)


def _strip_git_prefix(path: str) -> str:
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _parse_diff_line(
    line: str,
    old_line_number: int,
    new_line_number: int,
) -> tuple[DiffLine | None, int, int]:
    prefix = line[:1]
    content = line[1:]

    if prefix == "+":
        return (
            DiffLine(
                kind="addition",
                content=content,
                old_line_number=None,
                new_line_number=new_line_number,
            ),
            old_line_number,
            new_line_number + 1,
        )

    if prefix == "-":
        return (
            DiffLine(
                kind="deletion",
                content=content,
                old_line_number=old_line_number,
                new_line_number=None,
            ),
            old_line_number + 1,
            new_line_number,
        )

    if prefix == " ":
        return (
            DiffLine(
                kind="context",
                content=content,
                old_line_number=old_line_number,
                new_line_number=new_line_number,
            ),
            old_line_number + 1,
            new_line_number + 1,
        )

    return None, old_line_number, new_line_number


class _MutableHunk:
    def __init__(self, old_start: int, old_count: int, new_start: int, new_count: int) -> None:
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.lines: list[DiffLine] = []

    def to_diff_hunk(self) -> DiffHunk:
        return DiffHunk(
            old_start=self.old_start,
            old_count=self.old_count,
            new_start=self.new_start,
            new_count=self.new_count,
            lines=self.lines,
        )
