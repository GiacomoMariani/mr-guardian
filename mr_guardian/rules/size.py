"""Deterministic rules for review size."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import changed_line_count, finding, int_parameter


class ChangedFileCountRule:
    """Flag reviews that change too many files."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_changed_files = int_parameter(rule, "threshold", "max_changed_files")
        if max_changed_files is None:
            max_changed_files = int_parameter(rule, "match", "changed_files_count_greater_than")
        if max_changed_files is None:
            return []

        changed_file_count = len(context.review_input.changed_files)
        if changed_file_count <= max_changed_files:
            return []

        return [
            finding(
                rule,
                (
                    f"Review changes {changed_file_count} files, above the configured "
                    f"limit of {max_changed_files}."
                ),
            )
        ]


class ChangedLineCountRule:
    """Flag reviews that change too many lines."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_changed_lines = int_parameter(rule, "threshold", "max_changed_lines")
        if max_changed_lines is None:
            return []

        line_count = changed_line_count(context.review_input.changed_files)
        if line_count <= max_changed_lines:
            return []

        return [
            finding(
                rule,
                (
                    f"Review changes {line_count} lines, above the configured "
                    f"limit of {max_changed_lines}."
                ),
            )
        ]


class ChangedDirectoryCountRule:
    """Flag reviews that spread changes across too many directories."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_directories = int_parameter(rule, "threshold", "max_changed_directories")
        if max_directories is None:
            return []

        directories = {
            changed_file.path.parent.as_posix()
            for changed_file in context.review_input.changed_files
            if changed_file.path.parent.as_posix() != "."
        }
        if len(directories) <= max_directories:
            return []

        return [
            finding(
                rule,
                (
                    f"Review changes {len(directories)} directories, above the configured "
                    f"limit of {max_directories}."
                ),
            )
        ]
