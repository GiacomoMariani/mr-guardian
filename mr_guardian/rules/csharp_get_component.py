"""Rule detecting added GetComponent calls in Unity C# files."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_line_tokens,
    added_lines,
    changed_file_patterns,
    finding,
    matching_files,
)


class AddedLineTokenRule:
    """Flag added lines containing configured tokens."""

    def __init__(self, rule_id: str, default_tokens: tuple[str, ...]) -> None:
        self._rule_id = rule_id
        self._default_tokens = default_tokens

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        tokens = added_line_tokens(rule, self._default_tokens)
        findings: list[Finding] = []

        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            for diff_line in added_lines(changed_file):
                if any(token in diff_line.content for token in tokens):
                    findings.append(
                        finding(
                            rule,
                            f"Added line contains discouraged token: {diff_line.content.strip()}",
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings
