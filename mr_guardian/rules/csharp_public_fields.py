"""Rule detecting added public fields in Unity C# files."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_lines,
    changed_file_patterns,
    finding,
    matching_files,
)


class CSharpPublicFieldsRule:
    """Flag added public C# fields."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        findings: list[Finding] = []
        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            for diff_line in added_lines(changed_file):
                if _is_public_field(diff_line.content):
                    findings.append(
                        finding(
                            rule,
                            "Added public C# field should be private or explicitly justified.",
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )
        return findings


def _is_public_field(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("public "):
        return False
    if (
        "(" in stripped
        or stripped.startswith("public class ")
        or stripped.startswith("public enum ")
    ):
        return False
    return stripped.endswith(";")
