"""Deterministic rules for C# size and method shape."""

import re
from collections.abc import Iterable

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_lines,
    count_added_block_lines,
    csharp_files,
    finding,
    int_parameter,
    method_parameter_count,
)


class CSharpClassSizeRule:
    """Flag large added C# class blocks visible in the diff."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_class_lines = int_parameter(rule, "threshold", "max_class_lines")
        if max_class_lines is None:
            return []
        return _block_size_findings(
            context.review_input.changed_files,
            rule,
            max_lines=max_class_lines,
            declaration_pattern=re.compile(r"\bclass\s+\w+"),
            message_prefix="C# class",
        )


class CSharpMethodSizeRule:
    """Flag large added C# method blocks visible in the diff."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_method_lines = int_parameter(rule, "threshold", "max_method_lines")
        if max_method_lines is None:
            return []
        return _block_size_findings(
            context.review_input.changed_files,
            rule,
            max_lines=max_method_lines,
            declaration_pattern=re.compile(
                r"\b(public|private|protected|internal)\s+[\w<>\[\]]+\s+\w+\s*\("
            ),
            message_prefix="C# method",
        )


class CSharpMethodParameterCountRule:
    """Flag added C# method declarations with too many parameters."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        max_parameters = int_parameter(rule, "threshold", "max_method_parameters")
        if max_parameters is None:
            return []

        findings: list[Finding] = []
        for changed_file in csharp_files(context.review_input.changed_files):
            for diff_line in added_lines(changed_file):
                parameter_count = method_parameter_count(diff_line.content)
                if parameter_count is not None and parameter_count > max_parameters:
                    findings.append(
                        finding(
                            rule,
                            (
                                f"C# method has {parameter_count} parameters, above the "
                                f"configured limit of {max_parameters}."
                            ),
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )
        return findings


def _block_size_findings(
    changed_files: Iterable[ChangedFile],
    rule: PolicyRule,
    *,
    max_lines: int,
    declaration_pattern: re.Pattern[str],
    message_prefix: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for changed_file in csharp_files(changed_files):
        file_added_lines = added_lines(changed_file)
        for index, diff_line in enumerate(file_added_lines):
            if not declaration_pattern.search(diff_line.content):
                continue
            block_line_count = count_added_block_lines(file_added_lines[index:])
            if block_line_count > max_lines:
                findings.append(
                    finding(
                        rule,
                        (
                            f"{message_prefix} has {block_line_count} added lines, above "
                            f"the configured limit of {max_lines}."
                        ),
                        file_path=changed_file.path,
                        line_number=diff_line.new_line_number,
                    )
                )
    return findings
