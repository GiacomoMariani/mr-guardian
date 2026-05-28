"""Shared helpers for deterministic rules."""

import re
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile, DiffLine


def finding(
    rule: PolicyRule,
    message: str,
    *,
    file_path: Path | None = None,
    line_number: int | None = None,
) -> Finding:
    """Build a finding from policy rule metadata."""
    return Finding(
        rule_id=rule.id,
        severity=rule.severity,
        message=message,
        source=rule.source,
        evaluation=rule.evaluation,
        file_path=file_path,
        line_number=line_number,
    )


def int_parameter(rule: PolicyRule, group: str, key: str) -> int | None:
    """Read an integer parameter from a nested parameter group."""
    group_config = dict_parameter(rule, group)
    value = group_config.get(key)
    return value if isinstance(value, int) else None


def dict_parameter(rule: PolicyRule, key: str) -> dict[str, object]:
    """Read a dictionary parameter."""
    value = rule.parameters.get(key)
    return value if isinstance(value, dict) else {}


def string_list(value: object) -> list[str]:
    """Return string items from a list-like config value."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def changed_line_count(changed_files: Iterable[ChangedFile]) -> int:
    """Count added and deleted diff lines."""
    return sum(
        1
        for changed_file in changed_files
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind in {"addition", "deletion"}
    )


def changed_file_patterns(rule: PolicyRule) -> list[str]:
    """Read changed-file glob patterns from rule parameters."""
    match = dict_parameter(rule, "match")
    return string_list(match.get("changed_files"))


def matching_files(
    changed_files: Iterable[ChangedFile],
    patterns: Iterable[str],
) -> list[ChangedFile]:
    """Return changed files matching any configured glob pattern."""
    return [
        changed_file
        for changed_file in changed_files
        if changed_file.status in {"added", "modified", "renamed"}
        and matches_any(changed_file.path, patterns)
    ]


def matches_any(path: Path, patterns: Iterable[str]) -> bool:
    """Return whether a path matches any pattern, or all paths when no patterns exist."""
    pattern_list = list(patterns)
    if not pattern_list:
        return True

    path_text = path.as_posix()
    return any(matches_pattern(path_text, pattern) for pattern in pattern_list)


def matches_pattern(path_text: str, pattern: str) -> bool:
    """Match a POSIX path against a YAML glob pattern."""
    if fnmatchcase(path_text, pattern):
        return True
    if "/**/" in pattern and fnmatchcase(path_text, pattern.replace("/**/", "/")):
        return True
    return False


def added_lines(changed_file: ChangedFile) -> list[DiffLine]:
    """Return added lines from a changed file."""
    return [
        diff_line
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind == "addition"
    ]


def added_line_tokens(rule: PolicyRule, default_tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Read configured added-line token matches."""
    match = dict_parameter(rule, "match")
    tokens = string_list(match.get("added_lines_contain"))
    return tuple(tokens) or default_tokens


def csharp_files(changed_files: Iterable[ChangedFile]) -> list[ChangedFile]:
    """Return changed Unity C# files."""
    return [
        changed_file
        for changed_file in changed_files
        if changed_file.status in {"added", "modified", "renamed"}
        and changed_file.path.as_posix().startswith("Assets/")
        and changed_file.path.suffix == ".cs"
    ]


def count_added_block_lines(lines: list[DiffLine]) -> int:
    """Count the visible added lines in a brace-delimited block."""
    brace_depth = 0
    seen_open_brace = False
    count = 0
    for diff_line in lines:
        count += 1
        brace_depth += diff_line.content.count("{")
        if "{" in diff_line.content:
            seen_open_brace = True
        brace_depth -= diff_line.content.count("}")
        if seen_open_brace and brace_depth <= 0:
            return count
    return count


def method_parameter_count(line: str) -> int | None:
    """Return the parameter count for a C# method declaration line."""
    if not re.search(r"\b(public|private|protected|internal)\b", line):
        return None
    match = re.search(r"\((?P<parameters>[^)]*)\)", line)
    if match is None:
        return None
    parameters = match.group("parameters").strip()
    if not parameters:
        return 0
    return len([parameter for parameter in parameters.split(",") if parameter.strip()])
