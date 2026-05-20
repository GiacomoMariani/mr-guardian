"""Rule detecting newly added print calls in Python files."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile, DiffLine
from mr_guardian.rules.base import RuleEvaluationContext

RULE_ID = "PYTHON-PRINT-001"


class PythonPrintRule:
    """Detect newly added print calls in Python files."""

    @property
    def rule_id(self) -> str:
        return RULE_ID

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        """Return findings for added print calls."""
        findings: list[Finding] = []

        for changed_file in context.review_input.changed_files:
            if not _is_relevant_python_file(changed_file):
                continue

            for diff_line in _added_lines(changed_file):
                if "print(" in diff_line.content:
                    findings.append(
                        Finding(
                            rule_id=rule.id,
                            severity=rule.severity,
                            message=(
                                "print calls should not be introduced in production "
                                "Python code; use structured logging instead."
                            ),
                            source=rule.source,
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


def _is_relevant_python_file(changed_file: ChangedFile) -> bool:
    return (
        changed_file.status in {"added", "modified", "renamed"}
        and changed_file.path.suffix == ".py"
    )


def _added_lines(changed_file: ChangedFile) -> list[DiffLine]:
    return [
        diff_line
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind == "addition"
    ]
